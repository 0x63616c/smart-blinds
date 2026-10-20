#pragma once
#include "smart_blinds/gauge_continuity.hpp"
#include <atomic>

namespace blinds::power::continuity {
// May be retired from another task, but that task MUST NOT remove driver
// handles. The actual bus owner does teardown after its synchronous read ends.
// Saturation is terminal: no wrap can revive an old ticket.
class BusEpoch {
public:
    static constexpr std::uint32_t successor(std::uint32_t value) {
        return value==UINT32_MAX ? UINT32_MAX:value+1;
    }
    std::uint32_t value() const { return value_.load(std::memory_order_acquire); }
    bool matches(std::uint32_t expected) const {
        return expected && expected<UINT32_MAX && value()==expected;
    }
    void retire() {
        auto old=value();
        while(old!=UINT32_MAX && !value_.compare_exchange_weak(old,successor(old),
                std::memory_order_acq_rel,std::memory_order_acquire)) {}
    }
    void retire_if(std::uint32_t expected) {
        if(expected && expected<UINT32_MAX)
            value_.compare_exchange_strong(expected,successor(expected),
                std::memory_order_acq_rel,std::memory_order_acquire);
    }
private:
    std::atomic<std::uint32_t> value_{1};
};
using Owner=std::uintptr_t;
class WordTransport {
public:
    virtual ~WordTransport()=default;
    virtual Owner current_owner() const=0;
    virtual std::int64_t now_us()=0;
    // Exactly pointer-write/repeated-start/two-byte read, never a data write.
    virtual bool transfer(std::uint8_t address,std::uint8_t pointer,
                          std::array<std::uint8_t,2>& bytes,std::uint32_t timeout_ms)=0;
};
struct WordAddress { std::uint8_t device=0,pointer=0; };
bool read_address(std::uint16_t logical_register,WordAddress& out);

// Shared by the C6 adapter and fake transport tests; the very same mapping,
// wire decoding, timeout and before/after ownership checks are exercised.
class OwnedWordBus final:public ReadOnlyBus {
public:
    OwnedWordBus(WordTransport& transport,BusEpoch& epoch,std::uint32_t expected,Owner owner)
        : transport_(transport),epoch_(epoch),expected_(expected),owner_(owner) {}
    bool accessible() const { return owner_ && transport_.current_owner()==owner_ && epoch_.matches(expected_); }
    std::int64_t now_us() override { return transport_.now_us(); }
    bool read_word(std::uint16_t reg,std::uint16_t& value,std::uint32_t timeout_ms) override;
private:
    WordTransport& transport_;
    BusEpoch& epoch_;
    const std::uint32_t expected_;
    const Owner owner_;
};
struct Publication {
    Result evidence{};
    std::uint32_t epoch=0,serial=0;
};

class OwnedSession {
public:
    OwnedSession(Profile profile,Context context,WordTransport& transport,BusEpoch& epoch,Owner owner)
        : context_(context),transport_(transport),epoch_(epoch),expected_(epoch.value()),
          bus_(transport,epoch,expected_,owner),monitor_(profile,context) {}
    OwnedSession(const OwnedSession&)=delete;
    OwnedSession& operator=(const OwnedSession&)=delete;
    bool can_attach(Context context) const;
    Publication read(Context context);
    bool park_light_sleep(Context context);
    bool resume_light_sleep(Context context);
    // Thread-safe cancellation only. No monitor mutation/driver teardown here.
    void retire() { published_.store(0,std::memory_order_release);epoch_.retire_if(expected_); }
    // This read-only publication fence may be used by the consumer task.
    // Use it again before consuming a queued report, alongside motion_power().
    bool current(const Publication& publication,std::uint64_t now_us) const;
private:
    bool allowed(Context context);
    Publication fail(Fault fault);
    const Context context_;
    WordTransport& transport_;
    BusEpoch& epoch_;
    const std::uint32_t expected_;
    OwnedWordBus bus_;
    Monitor monitor_; // Only the bound owner may touch this.
    std::uint32_t next_serial_=0;
    std::atomic<std::uint32_t> published_{0};
};
} // namespace blinds::power::continuity
