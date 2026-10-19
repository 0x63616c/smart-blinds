#include "smart_blinds/control.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace blinds {
namespace {
bool finite(double x) { return std::isfinite(x); }
std::optional<double> interpolate(const std::array<Knot, Calibration::capacity>& knots,
                                  std::size_t size, double value, bool inverse) {
    if (size < 2 || !finite(value)) return std::nullopt;
    auto x = [inverse](const Knot& k) { return inverse ? k.height_mm : k.count; };
    auto y = [inverse](const Knot& k) { return inverse ? k.count : k.height_mm; };
    if (value < x(knots[0]) || value > x(knots[size - 1])) return std::nullopt;
    for (std::size_t i = 1; i < size; ++i) {
        if (value <= x(knots[i])) {
            const double f = (value - x(knots[i - 1])) / (x(knots[i]) - x(knots[i - 1]));
            return y(knots[i - 1]) + f * (y(knots[i]) - y(knots[i - 1]));
        }
    }
    return std::nullopt;
}
bool same_command(const Command& a, const Command& b) {
    return a.boot_nonce == b.boot_nonce && a.sequence == b.sequence &&
        a.calibration_revision == b.calibration_revision && a.start_ms == b.start_ms &&
        a.start_height_mm == b.start_height_mm && a.target_height_mm == b.target_height_mm &&
        a.speed_mm_s == b.speed_mm_s && a.accel_mm_s2 == b.accel_mm_s2;
}
}

bool Calibration::assign(const Knot* knots, std::size_t size, std::uint32_t revision) {
    if (!knots || size < 2 || size > capacity || revision == 0) return false;
    for (std::size_t i = 0; i < size; ++i) {
        // Physical installation envelope also prevents numeric overflow in interpolation.
        if (!finite(knots[i].count) || !finite(knots[i].height_mm) ||
            std::abs(knots[i].count) > 1e12 || std::abs(knots[i].height_mm) > 1e6) return false;
        if (i && (knots[i].count <= knots[i - 1].count ||
                  knots[i].height_mm <= knots[i - 1].height_mm)) return false;
    }
    std::copy(knots, knots + size, knots_.begin());
    size_ = size;
    revision_ = revision;
    return true;
}
std::optional<double> Calibration::height_at(double count) const {
    return interpolate(knots_, size_, count, false);
}
std::optional<double> Calibration::count_at(double height) const {
    return interpolate(knots_, size_, height, true);
}
double Calibration::low() const { return valid() ? knots_[0].height_mm : NAN; }
double Calibration::high() const { return valid() ? knots_[size_ - 1].height_mm : NAN; }
std::optional<Range> common_range(const Calibration* c, std::size_t size) {
    if (!c || !size) return std::nullopt;
    Range range{-std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity()};
    for (std::size_t i = 0; i < size; ++i) {
        if (!c[i].valid()) return std::nullopt;
        range.low_mm = std::max(range.low_mm, c[i].low());
        range.high_mm = std::min(range.high_mm, c[i].high());
    }
    if (range.low_mm >= range.high_mm) return std::nullopt;
    return range;
}
std::optional<double> group_height(const Range& range, double percent) {
    if (!finite(range.low_mm) || !finite(range.high_mm) || range.low_mm >= range.high_mm ||
        !finite(percent) || percent < 0 || percent > 100) return std::nullopt;
    return range.low_mm + (range.high_mm - range.low_mm) * percent / 100.;
}

bool Trajectory::configure(double start, double target, double speed, double accel) {
    if (!finite(start) || !finite(target) || !finite(speed) || !finite(accel) ||
        speed <= 0 || accel <= 0) return false;
    start_ = start;
    target_ = target;
    distance_ = std::abs(target - start);
    direction_ = target >= start ? 1 : -1;
    accel_ = accel;
    peak_ = std::min(speed, std::sqrt(distance_ * accel));
    ramp_ = peak_ / accel;
    cruise_ = peak_ == 0 ? 0 : std::max(0., (distance_ - peak_ * ramp_) / peak_);
    duration_ = 2 * ramp_ + cruise_;
    return finite(duration_);
}
Sample Trajectory::sample(double t) const {
    if (!finite(t) || t < 0) return {start_, 0, false};
    if (t >= duration_) return {target_, 0, true};
    double distance = 0, speed = 0;
    if (t < ramp_) { distance = .5 * accel_ * t * t; speed = accel_ * t; }
    else if (t < ramp_ + cruise_) {
        distance = .5 * peak_ * ramp_ + peak_ * (t - ramp_); speed = peak_;
    } else {
        const double remaining = duration_ - t;
        distance = distance_ - .5 * accel_ * remaining * remaining;
        speed = accel_ * remaining;
    }
    return {start_ + direction_ * distance, direction_ * speed, false};
}

Controller::Controller(Calibration c, Limits limits, std::uint64_t boot_nonce)
    : calibration_(c), limits_(limits), boot_nonce_(boot_nonce) {
    const double values[] = {limits.max_speed_mm_s, limits.max_accel_mm_s2,
        limits.start_tolerance_mm, limits.tracking_tolerance_mm, limits.endpoint_tolerance_mm,
        limits.current_trip_a, limits.min_pack_v, limits.proportional_gain_per_s};
    configured_ = c.valid() && boot_nonce != 0;
    for (double value : values) configured_ &= finite(value) && value > 0 && value < 1e6;
    configured_ &= limits.max_clock_error_ms > 0 && limits.min_prepare_lead_ms > 0 &&
        limits.max_prepare_lead_ms >= limits.min_prepare_lead_ms && limits.latest_start_ms > 0 &&
        limits.lease_ms > limits.latest_start_ms && limits.max_control_gap_ms > 0 &&
        limits.no_motion_ms > limits.max_control_gap_ms && limits.tracking_grace_ms > 0 &&
        limits.settle_timeout_ms > 0;
    if (!configured_) { state_ = State::fault; reason_ = Reason::invalid; }
}
bool Controller::active() const {
    return state_ == State::prepared || state_ == State::armed || state_ == State::moving;
}
Reason Controller::validate_measurement(const Measurement& m) const {
    if (!configured_) return Reason::invalid;
    if (!finite(m.current_a) || !finite(m.pack_v) || !finite(m.encoder_count)) return Reason::invalid;
    if (m.driver_fault) return Reason::driver_fault;
    if (!m.power_ready) return Reason::power_unavailable;
    if (std::abs(m.current_a) > limits_.current_trip_a) return Reason::overcurrent;
    if (m.pack_v < limits_.min_pack_v) return Reason::low_battery;
    if (!calibration_.height_at(m.encoder_count)) return Reason::outside_range;
    return Reason::ok;
}
Reason Controller::establish_reference(const Measurement& m) {
    if (active()) return Reason::busy;
    const auto reason = validate_measurement(m);
    if (reason != Reason::ok) return reason;
    referenced_ = true;
    state_ = State::idle;
    reason_ = Reason::ok;
    return Reason::ok;
}
Reason Controller::prepare(const Command& c, const Measurement& m,
                           std::uint64_t now, std::uint64_t error) {
    if (!boot_nonce_ || c.boot_nonce != boot_nonce_) return Reason::wrong_boot;
    if (active()) {
        if (same_command(c, command_)) return Reason::ok; // retransmission: no reschedule
        return Reason::busy;
    }
    if (!referenced_ || state_ == State::unreferenced) return Reason::unreferenced;
    if (state_ == State::fault) return reason_;
    if (!c.sequence || c.sequence <= last_sequence_) return Reason::stale_sequence;
    if (c.calibration_revision != calibration_.revision()) return Reason::stale_calibration;
    if (error > limits_.max_clock_error_ms) return Reason::clock_uncertain;
    if (c.start_ms <= now || c.start_ms - now < limits_.min_prepare_lead_ms) return Reason::too_late;
    if (c.start_ms - now > limits_.max_prepare_lead_ms) return Reason::too_early;
    if (!finite(c.speed_mm_s) || !finite(c.accel_mm_s2) || c.speed_mm_s <= 0 ||
        c.speed_mm_s > limits_.max_speed_mm_s || c.accel_mm_s2 <= 0 ||
        c.accel_mm_s2 > limits_.max_accel_mm_s2) return Reason::invalid;
    const auto reason = validate_measurement(m);
    if (reason != Reason::ok) return reason;
    if (!calibration_.count_at(c.target_height_mm) || !calibration_.count_at(c.start_height_mm))
        return Reason::outside_range;
    const double height = *calibration_.height_at(m.encoder_count);
    if (std::abs(c.start_height_mm - height) > limits_.start_tolerance_mm) return Reason::needs_alignment;
    if (!trajectory_.configure(c.start_height_mm, c.target_height_mm, c.speed_mm_s, c.accel_mm_s2))
        return Reason::invalid;
    command_ = c;
    last_sequence_ = c.sequence; // accepted but aborted commands can never execute again
    state_ = State::prepared;
    reason_ = Reason::ok;
    local_ = false;
    lease_until_ms_ = lease_sent_ms_ = 0;
    return Reason::ok;
}
Reason Controller::commit(std::uint64_t boot, std::uint64_t sequence, std::uint64_t now) {
    if (boot != boot_nonce_) return Reason::wrong_boot;
    if (sequence != command_.sequence || !active()) return Reason::wrong_command;
    if (state_ == State::armed || state_ == State::moving) return Reason::ok;
    if (now >= command_.start_ms) return Reason::too_late;
    state_ = State::armed;
    return Reason::ok;
}
Reason Controller::renew_lease(std::uint64_t boot, std::uint64_t sequence,
                               std::uint64_t sent, std::uint64_t now) {
    if (boot != boot_nonce_) return Reason::wrong_boot;
    if (local_ || sequence != command_.sequence || !active()) return Reason::wrong_command;
    // Authentication and clock synchronization precede this API. Old packets must not extend a lease.
    if (sent <= lease_sent_ms_ || sent > now || now - sent >= limits_.lease_ms)
        return Reason::too_late;
    if (sent > std::numeric_limits<std::uint64_t>::max() - limits_.lease_ms) return Reason::invalid;
    lease_sent_ms_ = sent;
    lease_until_ms_ = sent + limits_.lease_ms;
    return Reason::ok;
}
Output Controller::output(double speed, double desired) const {
    return {state_ == State::moving && speed != 0, speed, desired, state_, reason_};
}
Output Controller::fail(Reason reason, bool lost) {
    if (lost) referenced_ = false;
    state_ = lost ? State::unreferenced : State::fault;
    reason_ = reason;
    return output();
}
Output Controller::stop() {
    // Faults require explicit recovery; STOP must never clear a fault latch.
    if (state_ != State::fault && state_ != State::unreferenced) {
        state_ = referenced_ ? State::idle : State::unreferenced;
        reason_ = Reason::stopped;
    }
    return output();
}
Output Controller::lose_reference() { return fail(Reason::reference_lost, true); }
Reason Controller::local_move(bool up, const Measurement& m, std::uint64_t now) {
    if (active()) { stop(); return Reason::stopped; }
    if (!referenced_) return Reason::unreferenced;
    if (state_ == State::fault) return reason_;
    const auto reason = validate_measurement(m);
    if (reason != Reason::ok) return reason;
    const double height = *calibration_.height_at(m.encoder_count);
    trajectory_.configure(height, up ? calibration_.high() : calibration_.low(),
                          limits_.max_speed_mm_s, limits_.max_accel_mm_s2);
    command_.start_ms = now;
    command_.target_height_mm = trajectory_.target();
    command_.start_height_mm = height;
    state_ = State::armed;
    reason_ = Reason::ok;
    local_ = true;
    return Reason::ok;
}
Output Controller::tick(const Measurement& m, std::uint64_t now, std::uint64_t error) {
    if (!active()) return output();
    const auto valid = validate_measurement(m);
    if (valid != Reason::ok) return fail(valid, valid == Reason::outside_range || valid == Reason::invalid);
    if (!local_ && error > limits_.max_clock_error_ms) return fail(Reason::clock_uncertain);
    if (state_ == State::prepared) {
        if (now >= command_.start_ms) return fail(Reason::no_commit);
        return output();
    }
    if (state_ == State::moving && now < last_tick_ms_) return fail(Reason::control_gap);
    if (now < command_.start_ms) return output();
    if (!local_ && (now >= lease_until_ms_)) return fail(Reason::lease_expired);
    const double height = *calibration_.height_at(m.encoder_count);
    if (state_ == State::armed) {
        if (now - command_.start_ms > limits_.latest_start_ms) return fail(Reason::too_late);
        if (std::abs(height - command_.start_height_mm) > limits_.start_tolerance_mm)
            return fail(Reason::needs_alignment, true);
        state_ = State::moving;
        last_tick_ms_ = last_motion_ms_ = last_good_tracking_ms_ = now;
        last_motion_height_ = height;
        last_requested_ = 0;
    } else if (now < last_tick_ms_ || now - last_tick_ms_ > limits_.max_control_gap_ms) {
        return fail(Reason::control_gap);
    }
    const auto sample = trajectory_.sample(static_cast<double>(now - command_.start_ms) / 1000.);
    if (sample.finished && std::abs(height - command_.target_height_mm) <= limits_.endpoint_tolerance_mm) {
        state_ = State::idle;
        reason_ = Reason::ok;
        return output(0, command_.target_height_mm);
    }
    if (static_cast<double>(now - command_.start_ms) > trajectory_.duration_s() * 1000 +
        static_cast<double>(limits_.settle_timeout_ms)) return fail(Reason::motion_timeout);
    const double error_mm = sample.height_mm - height;
    if (std::abs(error_mm) <= limits_.tracking_tolerance_mm) last_good_tracking_ms_ = now;
    else if (now - last_good_tracking_ms_ > limits_.tracking_grace_ms)
        return fail(Reason::tracking_error, true);
    const double requested = std::clamp(sample.velocity_mm_s + limits_.proportional_gain_per_s * error_mm,
                                        -limits_.max_speed_mm_s, limits_.max_speed_mm_s);
    if (std::abs(height - last_motion_height_) >= .25) {
        if (std::abs(last_requested_) > 2 && (height - last_motion_height_) * last_requested_ < -.25)
            return fail(Reason::wrong_direction, true);
        last_motion_height_ = height;
        last_motion_ms_ = now;
    } else if (std::abs(requested) > 2 && now - last_motion_ms_ > limits_.no_motion_ms) {
        return fail(Reason::no_encoder_motion, true);
    }
    last_requested_ = requested;
    last_tick_ms_ = now;
    return output(requested, sample.height_mm);
}

const char* name(State s) {
    switch (s) {
#define STATE(x) case State::x: return #x
    STATE(unreferenced); STATE(idle); STATE(prepared); STATE(armed); STATE(moving); STATE(fault);
#undef STATE
    }
    return "invalid";
}
const char* name(Reason r) {
    switch (r) {
#define REASON(x) case Reason::x: return #x
    REASON(ok); REASON(invalid); REASON(busy); REASON(unreferenced); REASON(wrong_boot);
    REASON(stale_sequence); REASON(wrong_command); REASON(stale_calibration); REASON(clock_uncertain);
    REASON(too_late); REASON(too_early); REASON(outside_range); REASON(needs_alignment);
    REASON(power_unavailable); REASON(no_commit); REASON(lease_expired); REASON(tracking_error);
    REASON(no_encoder_motion); REASON(wrong_direction); REASON(driver_fault); REASON(overcurrent);
    REASON(low_battery); REASON(control_gap); REASON(reference_lost); REASON(stopped); REASON(motion_timeout);
#undef REASON
    }
    return "invalid";
}
} // namespace blinds
