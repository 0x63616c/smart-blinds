#pragma once
#include <atomic>
#include <cstdint>

namespace blinds::runtime {
// Application-lifetime sink. Called after publication, never while holding an
// I/O lock. The implementation must not block (eventfd or task notification).
struct WakeSink {
    void* context=nullptr;
    bool (*signal)(void*)=nullptr;
    bool notify() const { return signal && signal(context); }
};

// SDK/ISR producers may revoke, but cannot mutate the inbox or touch I/O.
// A generation never wraps or becomes usable again after exhaustion.
class Revocation {
public:
    std::uint32_t generation() const { return generation_.load(std::memory_order_acquire); }
    void revoke() {
        auto prior=generation_.load(std::memory_order_relaxed);
        while(prior!=UINT32_MAX &&
              !generation_.compare_exchange_weak(prior,prior+1,std::memory_order_acq_rel)) {}
        if(prior==UINT32_MAX || prior==UINT32_MAX-1) failed_.store(true,std::memory_order_release);
    }
    void local_stop() { stop_.store(true,std::memory_order_release); revoke(); }
    bool take_stop() { return stop_.exchange(false,std::memory_order_acq_rel); }
    bool stop_pending() const { return stop_.load(std::memory_order_acquire); }
    void fail() { failed_.store(true,std::memory_order_release); revoke(); }
    bool failed() const { return failed_.load(std::memory_order_acquire); }
private:
    static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
    std::atomic<std::uint32_t> generation_{1};
    std::atomic<bool> stop_{false},failed_{false};
};

// An odd generation means the producer is between marking activity and
// publishing the copied request. A worker may never park against that boundary.
class Activity {
public:
    bool begin() {
        const auto value=current();
        if(value&1U || value>=UINT32_MAX-2) return false;
        value_.store(value+1,std::memory_order_release); return true;
    }
    void end() { value_.fetch_add(1,std::memory_order_release); } // Sole producer, paired with begin.
    std::uint32_t current() const { return value_.load(std::memory_order_acquire); }
private:
    std::atomic<std::uint32_t> value_{2};
};
struct Parked {
    std::uint64_t observed_us=0;
    std::uint32_t activity=0,revocation=0;
    bool off=false,healthy=false;
    bool current(std::uint64_t now,std::uint32_t current_activity,const Revocation& signals) const {
        return off && healthy && observed_us && observed_us<=now && now-observed_us<=30000 &&
            activity && !(activity&1U) && activity==current_activity &&
            revocation==signals.generation() && !signals.failed() && !signals.stop_pending();
    }
};
// Portable sleep handoff; the caller supplies physical readback, never a
// requested STOP or an idle enum as a substitute. Keep power owned on ambiguity.
inline Parked parked(std::uint64_t now,std::uint32_t before,std::uint32_t after,
                     std::uint32_t revocation_before,const Revocation& signals,
                     bool idle,bool actual_off,bool healthy) {
    return {now,after,revocation_before,
        idle && actual_off && before==after && !(after&1U) &&
            revocation_before==signals.generation(),healthy};
}
} // namespace blinds::runtime
