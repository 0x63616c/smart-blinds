#pragma once
#include <cstdint>

namespace blinds::io {
// Current integrated C6 schematic contract. No caller-selectable pin defaults.
struct Pins {
    static constexpr int up=0, down=1, current=2, reference=3, encoder_a=6, encoder_b=7;
    static constexpr int sda=10, scl=11, wdi=16, charger_int=17;
    static constexpr int in1=18, in2=19, request_n=20, fault_n=21, charge_n=22, encoder_n=23;
};
class DisabledBackend {
public:
    virtual ~DisabledBackend() = default;
    // Write output latch before enabling the output. Must not arm any gate.
    virtual bool output(int pin, bool high) = 0;
    virtual bool configure_inputs() = 0;
    virtual bool configure_counter_stopped() = 0;
    virtual bool configure_pwm_stopped_low() = 0;
    virtual bool force_pwm_low() = 0;
    virtual bool outputs_are_off() = 0;
};

class DisabledSetup {
public:
    enum class State { untouched, ready, fault };
    explicit DisabledSetup(DisabledBackend& backend) : backend_(backend) {}
    bool initialize() {
        if (state_ != State::untouched) return false;
        // Shared request disables both driver and watchdog before WDI/PWM muxing.
        if (!backend_.output(Pins::request_n,true) || !backend_.output(Pins::charge_n,true) ||
            !backend_.output(Pins::encoder_n,true) || !backend_.output(Pins::wdi,true) ||
            !backend_.output(Pins::in1,false) || !backend_.output(Pins::in2,false) ||
            !backend_.configure_inputs() || !backend_.configure_counter_stopped() ||
            !backend_.configure_pwm_stopped_low() || !backend_.outputs_are_off()) {
            state_ = State::fault;
            hold_off();
            return false;
        }
        state_ = State::ready;
        return true;
    }
    bool hold_off() {
        // Attempt every independent stop operation even if one reports failure.
        bool ok = backend_.output(Pins::request_n,true);
        ok = backend_.output(Pins::charge_n,true) && ok;
        ok = backend_.output(Pins::encoder_n,true) && ok;
        ok = backend_.force_pwm_low() && ok;
        ok = backend_.output(Pins::in1,false) && ok;
        ok = backend_.output(Pins::in2,false) && ok;
        ok = backend_.output(Pins::wdi,true) && ok;
        ok = backend_.outputs_are_off() && ok;
        if (!ok) state_ = State::fault;
        return ok;
    }
    bool verify_off() {
        if(state_!=State::ready) return false;
        if(backend_.outputs_are_off()) return true;
        state_=State::fault; // Successful OFF recovery must not restore validity.
        hold_off();
        return false;
    }
    State state() const { return state_; }
    static constexpr bool motion_allowed() { return false; }
private:
    DisabledBackend& backend_;
    State state_ = State::untouched;
};

enum class ButtonAction { none, stop, up_tap, down_tap, service_hold };
// All times are local monotonic milliseconds. The owning control task polls at
// <=10 ms; this class is independent of networking and does not command motion.
class Buttons {
public:
    static constexpr std::uint64_t debounce_ms=20, service_hold_ms=1500, max_gap_ms=50;
    ButtonAction sample(bool up, bool down, bool active, std::uint64_t now) {
        const unsigned raw = (up ? 1U : 0U) | (down ? 2U : 0U);
        if (!initialized_) { initialized_=true; last_=candidate_since_=now; candidate_=raw; }
        else if (now < last_ || now-last_ > max_gap_ms) {
            reset_gesture(); ready_=false; stable_=0; candidate_=raw; candidate_since_=now; last_=now;
            return ButtonAction::stop;
        }
        last_=now;
        if (raw != candidate_) { candidate_=raw; candidate_since_=now; }
        // STOP has no debounce wait. Latch until a stable complete release so a
        // held stop button cannot become a new endpoint command after stopping.
        if (raw == 3 || (active && raw) || (ready_ && stable_ && raw && raw!=stable_)) {
            const bool new_stop = !blocked_;
            blocked_=true; ready_=false; reset_gesture();
            return new_stop ? ButtonAction::stop : ButtonAction::none;
        }
        if (now-candidate_since_ < debounce_ms) return ButtonAction::none;
        if (!ready_) {
            if (raw == 0) { ready_=true; blocked_=false; stable_=0; }
            return ButtonAction::none; // Held at boot never starts a gesture.
        }
        if (stable_ != raw) {
            stable_=raw;
            if (raw) {
                gesture_=raw; pressed_at_=candidate_since_; hold_reported_=false;
            } else {
                const auto old=gesture_;
                const bool tap=old && !hold_reported_ && candidate_since_-pressed_at_ < service_hold_ms;
                reset_gesture();
                return tap ? (old==1 ? ButtonAction::up_tap : ButtonAction::down_tap) : ButtonAction::none;
            }
        }
        if (raw && gesture_ && !hold_reported_ && now-pressed_at_ >= service_hold_ms) {
            hold_reported_=true;
            return ButtonAction::service_hold;
        }
        return ButtonAction::none;
    }
private:
    void reset_gesture() { gesture_=0; hold_reported_=false; }
    bool initialized_=false, ready_=false, blocked_=false, hold_reported_=false;
    unsigned candidate_=0, stable_=0, gesture_=0;
    std::uint64_t last_=0, candidate_since_=0, pressed_at_=0;
};
} // namespace blinds::io
