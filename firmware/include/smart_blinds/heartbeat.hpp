#pragma once
#include <cstdint>

namespace smart_blinds {
// Single control-task owner only. This policy never writes a GPIO or schedules
// a timer. The board driver must apply the requested safe levels and acknowledge
// each physical WDI falling-edge write; see docs/firmware/watchdog-heartbeat.md.
class Heartbeat {
public:
    enum class State { idle, arming, running, fault };
    static constexpr std::uint64_t setup_us = 150;
    static constexpr std::uint64_t driver_wake_us = 1000;
    static constexpr std::uint64_t feed_min_us = 10000; // Strictly greater.
    static constexpr std::uint64_t feed_max_us = 45000; // Strictly less.
    static constexpr std::uint64_t sample_max_age_us = 10000;
    static constexpr std::uint64_t edge_ack_budget_us = 100;

    struct Cycle {
        std::uint64_t sequence;
        std::uint64_t sampled_us;
        bool healthy; // Includes reference, power, lease and applied-output checks.
        bool inputs_coast; // IN1/IN2 are confirmed 00 before the first heartbeat.
    };

    explicit Heartbeat(std::uint64_t boot) : boot_(boot) {}

    bool arm(std::uint64_t boot, std::uint64_t command, const Cycle& preflight,
             std::uint64_t now) {
        if (!advance(now) || state_ != State::idle || boot == 0 || boot != boot_ ||
            command <= last_command_ || !preflight.healthy || !preflight.inputs_coast ||
            preflight.sequence == 0 || !fresh(preflight.sampled_us, now)) return false;
        last_command_ = command;
        last_cycle_ = preflight.sequence;
        last_sample_us_ = preflight.sampled_us;
        last_cycle_us_ = armed_us_ = now;
        healthy_cycles_ = 0;
        request_acknowledged_ = false;
        state_ = State::arming;
        return true;
    }

    // Acknowledge immediately after lowering the physical request. Start the
    // wake wait here, so GPIO-write latency cannot shorten the driver wake time.
    bool request_applied(std::uint64_t now) {
        if (!advance(now) || state_ != State::arming || request_acknowledged_) return fail();
        armed_us_ = now;
        request_acknowledged_ = true;
        return true;
    }

    // Returns true for one new falling-edge request. Duplicate calls, stale
    // samples, a missed deadline or an unacknowledged edge fail closed.
    bool cycle(const Cycle& value, std::uint64_t now) {
        if (!advance(now) || !active()) return false;
        if (!request_acknowledged_ || edge_pending_ || !value.healthy || value.sequence <= last_cycle_ ||
            value.sampled_us <= last_sample_us_ || now <= last_cycle_us_ ||
            !fresh(value.sampled_us, now) ||
            (state_ == State::arming && !value.inputs_coast)) return fail();
        last_cycle_ = value.sequence;
        last_sample_us_ = value.sampled_us;
        last_cycle_us_ = now;
        if (state_ == State::arming) {
            if (now - armed_us_ <= setup_us || now - armed_us_ <= driver_wake_us) return false;
        } else {
            if (healthy_cycles_ < 2) ++healthy_cycles_;
            if (healthy_cycles_ < 2 || now - last_edge_us_ <= feed_min_us) return false;
        }
        edge_pending_ = true;
        edge_requested_us_ = now;
        return true;
    }

    // Call only after the driver actually wrote the falling edge, with its local
    // monotonic timestamp. An accepted request alone cannot unlock PWM.
    bool edge_applied(std::uint64_t now) {
        if (!advance(now) || !active() || !edge_pending_) return fail();
        if (state_ == State::running && now - last_edge_us_ <= feed_min_us) return fail();
        last_edge_us_ = now;
        healthy_cycles_ = 0;
        edge_pending_ = false;
        state_ = State::running;
        return true;
    }

    // Deadline inspection can only stop a session; it never generates a feed.
    bool advance(std::uint64_t now) {
        if (state_ == State::fault) return false;
        if (now < last_now_) return fail();
        last_now_ = now;
        if (state_ == State::arming && !request_acknowledged_ && now - armed_us_ > edge_ack_budget_us) return fail();
        if (active() && ((edge_pending_ && now - edge_requested_us_ > edge_ack_budget_us) ||
            now - (state_ == State::arming ? armed_us_ : last_edge_us_) >= feed_max_us)) return fail();
        return true;
    }

    void stop(std::uint64_t now) {
        if (!advance(now)) return;
        state_ = State::idle;
        edge_pending_ = false;
        request_acknowledged_ = false;
        healthy_cycles_ = 0;
    }

    State state() const { return state_; }
    bool request_n_high() const { return !active(); }
    bool pwm_allowed() const { return state_ == State::running; }
    bool edge_pending() const { return edge_pending_; }
    // WDI's resting level is always HIGH. A falling-edge request is a bounded
    // LOW-then-HIGH write by the owning task, never a peripheral pulse train.
    static constexpr bool resting_wdi_high() { return true; }

private:
    bool active() const { return state_ == State::arming || state_ == State::running; }
    static bool fresh(std::uint64_t sample, std::uint64_t now) {
        return sample <= now && now - sample <= sample_max_age_us;
    }
    bool fail() { state_ = State::fault; edge_pending_ = false; healthy_cycles_ = 0; return false; }
    std::uint64_t boot_, last_command_ = 0, last_now_ = 0;
    std::uint64_t armed_us_ = 0, last_edge_us_ = 0, edge_requested_us_ = 0;
    std::uint64_t last_cycle_ = 0, last_sample_us_ = 0, last_cycle_us_ = 0;
    unsigned healthy_cycles_ = 0;
    bool edge_pending_ = false, request_acknowledged_ = false;
    State state_ = State::idle;
};
}
