#pragma once
#include <cstdint>
#include <limits>

namespace smart_blinds {
// Authenticated wake requests change radio policy only. They never authorize motion.
// Call from one owner. A boot nonce must be freshly generated on every boot.
class RadioWindow {
public:
    enum class State { offline, sleepy, awake, cooldown, clock_fault };
    static constexpr std::uint64_t awake_ms = 10000;
    static constexpr std::uint64_t cooldown_ms = 5000;
    explicit RadioWindow(std::uint64_t boot) : boot_(boot) {}

    void attached(bool value, std::uint64_t now) {
        if (!advance(now)) return;
        attached_ = value && boot_ != 0;
        if (!attached_) {
            if (state_ == State::awake) cooldown_until_ = deadline_ + cooldown_ms;
            state_ = State::offline;
        } else if (state_ == State::offline) {
            state_ = now < cooldown_until_ ? State::cooldown : State::sleepy;
        }
    }
    bool wake(std::uint64_t boot, std::uint64_t sequence, std::uint64_t now) {
        if (!advance(now) || !attached_ || state_ != State::sleepy || boot != boot_ ||
            sequence <= last_sequence_ || now > std::numeric_limits<std::uint64_t>::max() - awake_ms - cooldown_ms)
            return false;
        last_sequence_ = sequence;
        deadline_ = now + awake_ms;
        state_ = State::awake;
        return true;
    }
    bool advance(std::uint64_t now) {
        if (state_ == State::clock_fault) return false;
        if (now < last_now_) {
            state_ = State::clock_fault;
            attached_ = false;
            return false;
        }
        last_now_ = now;
        if (state_ == State::awake && now >= deadline_) {
            cooldown_until_ = deadline_ + cooldown_ms;
            state_ = State::cooldown;
        }
        if (state_ == State::cooldown && now >= cooldown_until_)
            state_ = attached_ ? State::sleepy : State::offline;
        return true;
    }
    void cancel(std::uint64_t now) {
        if (!advance(now)) return;
        if (state_ == State::awake) {
            cooldown_until_ = deadline_ + cooldown_ms;
            state_ = State::cooldown;
        }
    }
    State state() const { return state_; }
    bool rx_on_when_idle() const { return state_ == State::awake; }
    std::uint64_t deadline() const { return deadline_; }
    std::uint64_t last_sequence() const { return last_sequence_; }
    // Clock qualification and motion authorization are deliberately absent.
private:
    std::uint64_t boot_, last_sequence_ = 0, last_now_ = 0;
    std::uint64_t deadline_ = 0, cooldown_until_ = 0;
    State state_ = State::offline;
    bool attached_ = false;
};
}
