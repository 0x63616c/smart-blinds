#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace blinds {

// Count polarity is normalized by the platform: increasing counts raises the fabric.
// Heights are millimetres above ONE shared room datum, not motor shaft angles.
struct Knot { double count; double height_mm; };
class Calibration {
public:
    static constexpr std::size_t capacity = 16;
    bool assign(const Knot* knots, std::size_t size, std::uint32_t revision);
    std::optional<double> height_at(double count) const;
    std::optional<double> count_at(double height_mm) const;
    double low() const;
    double high() const;
    std::uint32_t revision() const { return revision_; }
    bool valid() const { return size_ >= 2; }
private:
    std::array<Knot, capacity> knots_{};
    std::size_t size_ = 0;
    std::uint32_t revision_ = 0;
};

struct Range { double low_mm; double high_mm; };
std::optional<Range> common_range(const Calibration* calibrations, std::size_t size);
std::optional<double> group_height(const Range& range, double open_percent);

struct Sample { double height_mm; double velocity_mm_s; bool finished; };
// Symmetric acceleration-limited physical-height trajectory (triangular for short moves).
class Trajectory {
public:
    bool configure(double start_mm, double target_mm, double speed_mm_s, double accel_mm_s2);
    Sample sample(double seconds) const;
    double duration_s() const { return duration_; }
    double target() const { return target_; }
private:
    double start_ = 0, target_ = 0, distance_ = 0, direction_ = 1;
    double accel_ = 1, peak_ = 0, ramp_ = 0, cruise_ = 0, duration_ = 0;
};

enum class State { unreferenced, idle, prepared, armed, moving, fault };
enum class Reason {
    ok, invalid, busy, unreferenced, wrong_boot, stale_sequence, wrong_command,
    stale_calibration, clock_uncertain, too_late, too_early, outside_range,
    needs_alignment, power_unavailable, no_commit, lease_expired, tracking_error,
    no_encoder_motion, wrong_direction, driver_fault, overcurrent, low_battery,
    control_gap, reference_lost, stopped, motion_timeout
};
const char* name(Reason reason);
const char* name(State state);

// All example limits MUST be replaced by measured motor/pack limits before motor enable.
struct Limits {
    double max_speed_mm_s = 30;
    double max_accel_mm_s2 = 60;
    double start_tolerance_mm = 5;
    double tracking_tolerance_mm = 8;
    double endpoint_tolerance_mm = 1;
    double current_trip_a = 3;
    double min_pack_v = 9.6;
    double proportional_gain_per_s = 3;
    std::uint64_t max_clock_error_ms = 10;
    std::uint64_t min_prepare_lead_ms = 100;
    std::uint64_t max_prepare_lead_ms = 10000;
    std::uint64_t latest_start_ms = 30;
    std::uint64_t lease_ms = 300;
    std::uint64_t max_control_gap_ms = 50;
    std::uint64_t no_motion_ms = 400;
    std::uint64_t tracking_grace_ms = 200;
    std::uint64_t settle_timeout_ms = 1500;
};
struct Measurement {
    double encoder_count = 0;
    double current_a = 0;
    double pack_v = 0;
    bool driver_fault = false;
    bool power_ready = false;
};
struct Command {
    std::uint64_t boot_nonce = 0; // device challenge changes on EVERY reboot
    std::uint64_t sequence = 0;   // monotonically increasing within that boot
    std::uint32_t calibration_revision = 0;
    std::uint64_t start_ms = 0;   // synchronized coordinator monotonic clock
    double start_height_mm = 0;  // one common trajectory origin for aligned group
    double target_height_mm = 0;
    double speed_mm_s = 0;
    double accel_mm_s2 = 0;
};
struct Output {
    bool motor_enable = false;
    double velocity_mm_s = 0; // platform closes encoder speed loop and clamps current
    double desired_height_mm = 0;
    State state = State::unreferenced;
    Reason reason = Reason::unreferenced;
};

class Controller {
public:
    Controller(Calibration calibration, Limits limits, std::uint64_t boot_nonce);
    // Only call after a physical known-height reference procedure has succeeded.
    // The platform must reset/offset the count to the calibrated reference before this call.
    Reason establish_reference(const Measurement& measurement);
    Reason prepare(const Command& command, const Measurement& measurement,
                   std::uint64_t now_ms, std::uint64_t clock_error_ms);
    Reason commit(std::uint64_t boot_nonce, std::uint64_t sequence, std::uint64_t now_ms);
    Reason renew_lease(std::uint64_t boot_nonce, std::uint64_t sequence,
                       std::uint64_t sent_ms, std::uint64_t now_ms);
    Output tick(const Measurement& measurement, std::uint64_t now_ms,
                std::uint64_t clock_error_ms);
    // Local input takes precedence. Any button during group motion stops it immediately.
    Output stop();
    Output lose_reference();
    // A local up/down tap requests its calibrated endpoint without a radio lease.
    Reason local_move(bool up, const Measurement& measurement, std::uint64_t now_ms);
    State state() const { return state_; }
    Reason reason() const { return reason_; }
    std::uint64_t consumed_sequence() const { return last_sequence_; }
private:
    Reason validate_measurement(const Measurement& m) const;
    Output fail(Reason reason, bool reference_invalid = false);
    Output output(double speed = 0, double desired = 0) const;
    bool active() const;
    Calibration calibration_;
    Limits limits_;
    std::uint64_t boot_nonce_, last_sequence_ = 0;
    Command command_{};
    Trajectory trajectory_;
    State state_ = State::unreferenced;
    Reason reason_ = Reason::unreferenced;
    bool referenced_ = false, local_ = false, configured_ = false;
    std::uint64_t lease_until_ms_ = 0, lease_sent_ms_ = 0, last_tick_ms_ = 0;
    std::uint64_t last_motion_ms_ = 0, last_good_tracking_ms_ = 0;
    double last_motion_height_ = 0, last_requested_ = 0;
};

} // namespace blinds
