#pragma once
#include "smart_blinds/gauge_continuity.hpp"
#include <atomic>

namespace blinds::power::continuity {
class JointMailbox;
struct Window;
enum class Refresh;
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
    OwnedWordBus(WordTransport& transport,BusEpoch& epoch,std::uint32_t expected,Owner owner,
                 std::atomic<Fault>* failure=nullptr,JointMailbox* joint=nullptr)
        : transport_(transport),epoch_(epoch),expected_(expected),owner_(owner),
          failure_(failure ? failure:&own_failure_),joint_(joint) {}
    bool accessible() const { return owner_ && transport_.current_owner()==owner_ && epoch_.matches(expected_); }
    std::int64_t now_us() override { return transport_.now_us(); }
    bool read_word(std::uint16_t reg,std::uint16_t& value,std::uint32_t timeout_ms) override;
    Fault read_failure() const override { return failure_->load(std::memory_order_acquire); }
private:
    bool reject(Fault fault);
    WordTransport& transport_;
    BusEpoch& epoch_;
    const std::uint32_t expected_;
    const Owner owner_;
    std::atomic<Fault> own_failure_{Fault::none};
    std::atomic<Fault>* const failure_;
    JointMailbox* const joint_;
};
struct Publication {
    Result evidence{};
    std::uint32_t epoch=0,serial=0;
};

class OwnedSession final:private CaptureObserver {
public:
    OwnedSession(Profile profile,Context context,WordTransport& transport,BusEpoch& epoch,Owner owner)
        : context_(context),transport_(transport),epoch_(epoch),expected_(epoch.value()),
          bus_(transport,epoch,expected_,owner,&failure_),monitor_(profile,context),validation_(profile) {}
    OwnedSession(Profile profile,Context context,WordTransport& transport,BusEpoch& epoch,Owner owner,
                 JointMailbox& joint,smart_blinds::charger::Bq25798& charger);
    OwnedSession(const OwnedSession&)=delete;
    OwnedSession& operator=(const OwnedSession&)=delete;
    bool can_attach(Context context) const;
    Publication read(Context context);
    // Joint mode only: owns charger-first acquisition and final joint commit.
    Refresh refresh(Context context,Window window);
    bool park_light_sleep(Context context);
    bool resume_light_sleep(Context context);
    // Thread-safe cancellation only. No monitor mutation/driver teardown here.
    void retire() { failed(Fault::context); }
    // Standalone-mode publication fence, usable by the consumer task.
    // Use it again before consuming a queued report, alongside motion_power().
    bool current(const Publication& publication,std::uint64_t now_us) const;
private:
    Fault begin(std::int64_t started_us) noexcept override;
    Fault word(std::uint16_t reg,std::uint16_t raw) noexcept override;
    void failed(Fault fault) noexcept override;
    bool allowed(Context context);
    Publication fail(Fault fault);
    Result capture(Context context,std::uint64_t* completed_us=nullptr);
    const Context context_;
    WordTransport& transport_;
    BusEpoch& epoch_;
    const std::uint32_t expected_;
    std::atomic<Fault> failure_{Fault::none};
    OwnedWordBus bus_;
    Monitor monitor_; // Only the bound owner may touch this.
    CaptureValidation validation_;
    std::uint32_t next_serial_=0;
    std::atomic<std::uint32_t> published_{0};
    JointMailbox* const joint_=nullptr;
    smart_blinds::charger::Bq25798* const charger_=nullptr;
    std::uint64_t joint_started_us_=0; // Owner-only floor while a joint read runs.
};
} // namespace blinds::power::continuity
