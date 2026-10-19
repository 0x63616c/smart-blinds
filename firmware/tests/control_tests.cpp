#include "smart_blinds/control.hpp"
#include "smart_blinds/platform.hpp"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>

using namespace blinds;
namespace {
int checks = 0;
void check(bool pass, const char* what) {
    ++checks;
    if (!pass) { std::cerr << "FAIL: " << what << '\n'; std::exit(1); }
}
bool near(double a, double b, double tolerance = 1e-8) { return std::abs(a - b) <= tolerance; }
Calibration calibration(double low = 0, double high = 1000) {
    Calibration c;
    const Knot knots[] = {{0, low}, {600, low + .4 * (high - low)}, {1000, high}};
    check(c.assign(knots, 3, 7), "valid nonlinear calibration");
    return c;
}
Measurement measurement(const Calibration& c, double height = 200) {
    return {*c.count_at(height), .2, 11.7, false, true};
}
Command command() { return {42, 1, 7, 1000, 200, 400, 20, 40}; }
void arm(Controller& c, const Measurement& m) {
    check(c.establish_reference(m) == Reason::ok, "physical reference accepted");
    check(c.prepare(command(), m, 500, 5) == Reason::ok, "prepare");
    check(c.commit(42, 1, 600) == Reason::ok, "commit");
    check(c.renew_lease(42, 1, 900, 900) == Reason::ok, "initial lease");
}
void test_actuator_gate() {
    class TestPort : public BoardPort {
    public:
        bool enabled = false, valid = false, driver_accepts = true;
        bool configured() const override { return valid; }
        Measurement read() override { return {}; }
        void disable_motor() override { enabled = false; }
        bool set_fabric_velocity(double) override { enabled = driver_accepts; return driver_accepts; }
    } port;
    ActuatorGate gate(port);
    Output moving{true, 20, 100, State::moving, Reason::ok};
    check(!gate.apply(moving) && !port.enabled, "unconfigured hardware cannot drive");
    port.valid = true;
    check(gate.apply(moving) && port.enabled, "configured hardware request");
    moving.velocity_mm_s = NAN;
    check(!gate.apply(moving) && !port.enabled, "invalid velocity disables output");
    moving.velocity_mm_s = 20; moving.state = State::fault;
    check(!gate.apply(moving) && !port.enabled, "fault state refuses output");
    moving.state = State::moving; port.driver_accepts = false;
    check(!gate.apply(moving) && !port.enabled, "driver rejection disables output");
    auto cal = calibration(); auto m = measurement(cal);
    Limits limits; limits.current_trip_a = NAN;
    Controller c(cal, limits, 42);
    check(c.establish_reference(m) == Reason::invalid, "invalid limits block reference and drive");
}
void test_calibration() {
    auto c = calibration();
    check(near(*c.height_at(300), 200), "nonlinear first segment");
    check(near(*c.height_at(800), 700), "nonlinear second segment");
    for (double h = 0; h <= 1000; h += 1.1)
        check(near(*c.height_at(*c.count_at(h)), h), "round-trip calibration");
    check(!c.height_at(-1) && !c.height_at(1001), "no extrapolation beyond calibrated travel");
    check(!c.count_at(NAN) && !c.height_at(INFINITY), "nonfinite rejected");
    const Knot duplicate[] = {{0, 0}, {0, 1}};
    check(!c.assign(duplicate, 2, 8), "duplicate count rejected");
    const Knot backwards[] = {{0, 1}, {1, 0}};
    check(!c.assign(backwards, 2, 8), "backwards mapping rejected");
    check(c.revision() == 7, "bad replacement preserves previous calibration");
    Calibration group[] = {calibration(0, 1000), calibration(100, 900), calibration(50, 1100)};
    auto range = common_range(group, 3);
    check(range && near(range->low_mm, 100) && near(range->high_mm, 900), "intersection not union");
    check(near(*group_height(*range, 50), 500), "group 50 percent is one common physical height");
    check(!group_height(*range, 101), "unreachable percentage rejected");
    Calibration separate[] = {calibration(0, 100), calibration(200, 300)};
    check(!common_range(separate, 2), "disjoint travel cannot form level group");
}
void test_trajectory() {
    Trajectory t;
    check(t.configure(0, 100, 20, 40), "trajectory configure");
    check(near(t.duration_s(), 5.5), "trapezoid duration");
    check(near(t.sample(.25).height_mm, 1.25), "acceleration distance");
    check(near(t.sample(1).velocity_mm_s, 20), "constant fabric speed");
    check(t.sample(5.5).finished && near(t.sample(5.5).height_mm, 100), "exact final level");
    check(t.configure(100, 99, 20, 40), "short reverse trajectory");
    check(t.duration_s() < 1 && t.sample(.05).velocity_mm_s < 0, "triangular reverse move");
    check(t.configure(5, 5, 20, 40) && t.sample(0).finished, "zero distance");
    check(!t.configure(0, 2, NAN, 1), "NaN speed rejected");
}
void test_protocol_guards() {
    auto cal = calibration(); auto m = measurement(cal); Controller c(cal, {}, 42); auto cmd = command();
    check(c.prepare(cmd, m, 500, 0) == Reason::unreferenced, "reboot never trusts old position");
    check(c.establish_reference(m) == Reason::ok, "establish reference");
    cmd.boot_nonce = 41;
    check(c.prepare(cmd, m, 500, 0) == Reason::wrong_boot, "old boot command rejected");
    cmd = command(); cmd.calibration_revision = 6;
    check(c.prepare(cmd, m, 500, 0) == Reason::stale_calibration, "stale geometry rejected");
    cmd = command();
    check(c.prepare(cmd, m, 500, 11) == Reason::clock_uncertain, "clock error rejected");
    check(c.prepare(cmd, m, 950, 0) == Reason::too_late, "late preparation rejected");
    cmd.start_height_mm = 190;
    check(c.prepare(cmd, m, 500, 0) == Reason::needs_alignment, "unaligned group cannot pretend to track together");
    cmd = command(); cmd.target_height_mm = 1001;
    check(c.prepare(cmd, m, 500, 0) == Reason::outside_range, "no per-blind target clamp");
    cmd = command();
    check(c.prepare(cmd, m, 500, 0) == Reason::ok, "prepare accepted");
    check(c.prepare(cmd, m, 510, 0) == Reason::ok, "identical retransmit idempotent");
    cmd.target_height_mm = 500;
    check(c.prepare(cmd, m, 520, 0) == Reason::busy, "changed payload same sequence rejected");
    check(!c.tick(m, 999, 0).motor_enable, "never starts before scheduled time");
    check(c.tick(m, 1000, 0).reason == Reason::no_commit, "prepare alone never drives motor");
    check(c.stop().state == State::fault, "stop cannot erase latched fault");
    check(c.establish_reference(m) == Reason::ok, "explicit recovery");
    check(c.prepare(command(), m, 500, 0) == Reason::stale_sequence, "aborted accepted command never replayed");
}
void test_stops_and_faults() {
    auto cal = calibration(); auto m = measurement(cal);
    {
        Controller c(cal, {}, 42); arm(c, m);
        check(c.tick(m, 1000, 0).state == State::moving, "scheduled start");
        check(c.tick(m, 1010, 0).motor_enable, "motor starts with acceleration");
        auto stop = c.stop(); check(!stop.motor_enable && stop.state == State::idle, "button stop immediate");
        check(c.commit(42, 1, 1010) == Reason::wrong_command, "duplicate commit after stop cannot restart");
    }
    {
        Controller c(cal, {}, 42); arm(c, m); c.tick(m, 1000, 0);
        check(c.renew_lease(42, 1, 900, 1001) == Reason::too_late, "duplicate heartbeat cannot extend lease");
        for (std::uint64_t now = 1010; now < 1200; now += 10) c.tick(m, now, 0);
        check(c.tick(m, 1200, 0).reason == Reason::lease_expired, "lost coordinator stops group member");
    }
    {
        Controller c(cal, {}, 42); arm(c, m); c.tick(m, 1000, 0);
        check(c.tick(m, 1060, 0).reason == Reason::control_gap, "missed control deadline stops motor");
    }
    {
        Controller c(cal, {}, 42); arm(c, m); m.current_a = 4;
        check(c.tick(m, 1000, 0).reason == Reason::overcurrent, "current fault before movement");
    }
    m = measurement(cal);
    {
        Controller c(cal, {}, 42); arm(c, m);
        check(c.tick(m, 1040, 0).reason == Reason::too_late, "late device must not join ongoing group");
    }
    {
        Controller c(cal, {}, 42); arm(c, m);
        for (std::uint64_t now = 1000; now <= 1600 && c.state() != State::unreferenced; now += 10) {
            c.renew_lease(42, 1, now, now); c.tick(m, now, 0);
        }
        check(c.reason() == Reason::no_encoder_motion, "stalled encoder detected");
        check(c.state() == State::unreferenced, "stall invalidates physical position confidence");
    }
    {
        Controller c(cal, {}, 42); c.establish_reference(m);
        check(c.local_move(true, m, 10) == Reason::ok, "local button independent of network");
        check(c.tick(m, 10, 999999).state == State::moving, "local movement needs no network clock");
        check(c.local_move(false, m, 20) == Reason::stopped, "opposite button stops before reversing");
    }
}
void test_remaining_fault_boundaries() {
    auto cal = calibration(); auto good = measurement(cal);
    for (int kind = 0; kind < 4; ++kind) {
        Controller c(cal, {}, 42); arm(c, good); auto bad = good;
        Reason expected = Reason::invalid;
        if (kind == 0) { bad.driver_fault = true; expected = Reason::driver_fault; }
        if (kind == 1) { bad.pack_v = 8; expected = Reason::low_battery; }
        if (kind == 2) { bad.power_ready = false; expected = Reason::power_unavailable; }
        if (kind == 3) { bad.encoder_count = NAN; expected = Reason::invalid; }
        auto out = c.tick(bad, 1000, 0);
        check(out.reason == expected && !out.motor_enable, "power/sensor fault disables before start");
    }
    {
        Controller c(cal, {}, 42); arm(c, good); c.tick(good, 1000, 0);
        check(c.tick(good, 990, 0).reason == Reason::control_gap, "backwards monotonic clock fails closed");
    }
    {
        Controller c(cal, {}, 42); arm(c, good); c.tick(good, 1000, 0);
        check(c.tick(good, 1010, 11).reason == Reason::clock_uncertain, "clock uncertainty can abort active motion");
    }
    {
        Controller c(cal, {}, 42); arm(c, good); c.tick(good, 1000, 0);
        for (std::uint64_t now = 1010; now <= 1100; now += 10) c.tick(good, now, 0);
        auto backwards = measurement(cal, 199);
        check(c.tick(backwards, 1110, 0).reason == Reason::wrong_direction, "encoder polarity reversal detected");
    }
    {
        Controller c(cal, {}, 42); arm(c, good); c.tick(good, 1000, 0);
        check(c.renew_lease(42, 1, 1200, 1100) == Reason::too_late, "future lease timestamp rejected");
        check(c.renew_lease(41, 1, 1100, 1100) == Reason::wrong_boot, "old boot lease rejected");
        check(c.renew_lease(42, 2, 1100, 1100) == Reason::wrong_command, "different move lease rejected");
        check(c.lose_reference().state == State::unreferenced, "explicit reference loss stops");
        check(c.local_move(true, good, 1120) == Reason::unreferenced, "unreferenced local movement refused");
    }
    {
        Controller c(cal, {}, 42); arm(c, good);
        check(c.renew_lease(42, 1, 1010, 1000, 10) == Reason::ok,
              "coordinator ahead within known clock error accepted");
        check(c.renew_lease(42, 1, 1021, 1010, 10) == Reason::too_late,
              "future timestamp beyond bound rejected");
        check(c.renew_lease(42, 1, 1020, 1010, 11) == Reason::clock_uncertain,
              "excessive lease clock uncertainty rejected");
        for (std::uint64_t now = 1000; now < 1300; now += 10) c.tick(good, now, 10);
        check(c.tick(good, 1300, 10).reason == Reason::lease_expired,
              "lease expires from earliest possible send time, not future estimate");
    }
}
void test_reverse_trajectory_control() {
    auto cal = calibration(); Controller c(cal, {}, 42);
    double height = 800;
    auto m = measurement(cal, height);
    auto cmd = command(); cmd.start_height_mm = 800; cmd.target_height_mm = 200;
    check(c.establish_reference(m) == Reason::ok, "reverse reference");
    check(c.prepare(cmd, m, 500, 0) == Reason::ok, "reverse prepare");
    check(c.commit(42, 1, 700) == Reason::ok, "reverse commit");
    Output out;
    for (std::uint64_t now = 1000; now <= 33000; now += 10) {
        height += out.velocity_mm_s * .01;
        c.renew_lease(42, 1, now, now);
        out = c.tick(measurement(cal, height), now, 0);
        check(c.state() != State::fault && c.state() != State::unreferenced,
              "reverse crosses nonlinear calibration boundary without false polarity fault");
    }
    check(c.state() == State::idle && near(height, 200, 1), "reverse final physical height");
}
void test_seven_blinds() {
    std::array<Calibration, 7> calibrations;
    for (std::size_t i = 0; i < 7; ++i) calibrations[i] = calibration(i * 10, 1000 + i * 20);
    auto range = common_range(calibrations.data(), 7);
    const double target = *group_height(*range, 50); // common [60,1000], target 530
    std::array<Controller, 7> devices = {
        Controller(calibrations[0], {}, 42), Controller(calibrations[1], {}, 42),
        Controller(calibrations[2], {}, 42), Controller(calibrations[3], {}, 42),
        Controller(calibrations[4], {}, 42), Controller(calibrations[5], {}, 42),
        Controller(calibrations[6], {}, 42)};
    std::array<double, 7> height{}; height.fill(200);
    std::array<Output, 7> out{};
    for (std::size_t i = 0; i < 7; ++i) {
        const auto m = measurement(calibrations[i], height[i]);
        auto cmd = command(); cmd.target_height_mm = target;
        check(devices[i].establish_reference(m) == Reason::ok, "reference group member");
        check(devices[i].prepare(cmd, m, 500, 5) == Reason::ok, "prepare group member");
        check(devices[i].commit(42, 1, 700) == Reason::ok, "commit group member");
    }
    // Ideal velocity actuator, deliberately different count-to-height maps. This proves
    // coordinate/protocol logic only; it does not model a motor, chain, clutch or radio.
    for (std::uint64_t now = 1000; now <= 19000; now += 10) {
        for (std::size_t i = 0; i < 7; ++i) {
            height[i] += out[i].velocity_mm_s * .01;
            devices[i].renew_lease(42, 1, now, now);
            out[i] = devices[i].tick(measurement(calibrations[i], height[i]), now, 5);
            check(out[i].state != State::fault && out[i].state != State::unreferenced, "simulated group stays healthy");
            check(near(height[0], height[i], .001), "different length blinds follow same physical trajectory");
        }
    }
    for (std::size_t i = 0; i < 7; ++i) {
        check(devices[i].state() == State::idle, "group member arrived");
        check(near(height[i], target, 1), "group member at common final level");
    }
}
}
int main() {
    test_actuator_gate(); test_calibration(); test_trajectory(); test_protocol_guards(); test_stops_and_faults(); test_remaining_fault_boundaries(); test_reverse_trajectory_control(); test_seven_blinds();
    std::cout << checks << " checks passed (host control logic; no hardware validation).\n";
}
