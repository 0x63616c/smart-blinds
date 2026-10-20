#include "smart_blinds/heartbeat.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
using smart_blinds::Heartbeat;
using Cycle = Heartbeat::Cycle;
void check(bool ok, const char* why) {
    if (!ok) { std::cerr << why << '\n'; std::exit(1); }
}
Heartbeat running() {
    Heartbeat value(99);
    check(value.arm(99, 1, Cycle{1, 0, true, true}, 0), "valid arm rejected");
    check(value.request_applied(0), "request acknowledgement failed");
    check(value.cycle(Cycle{2, 1001, true, true}, 1001), "first edge not requested");
    check(!value.pwm_allowed(), "PWM enabled before edge acknowledgement");
    check(value.edge_applied(1002), "first edge acknowledgement failed");
    return value;
}
int main() {
    {
        Heartbeat value(99);
        check(value.request_n_high() && !value.pwm_allowed() && value.resting_wdi_high(), "unsafe initial levels");
        check(!value.cycle(Cycle{1, 0, true, true}, 0), "idle cycle fed watchdog");
        check(!value.arm(98, 1, Cycle{1, 0, true, true}, 0), "wrong boot armed");
        check(!value.arm(99, 0, Cycle{1, 0, true, true}, 0), "zero command armed");
        check(!value.arm(99, 1, Cycle{0, 0, true, true}, 0), "missing cycle identity armed");
        check(!value.arm(99, 1, Cycle{1, 0, false, true}, 0), "unhealthy preflight armed");
        check(!value.arm(99, 1, Cycle{1, 0, true, false}, 0), "noncoasting preflight armed");
        check(!value.arm(99, 1, Cycle{1, 1, true, true}, 0), "future sample armed");
        check(!value.arm(99, 1, Cycle{1, 0, true, true}, 10001), "stale preflight armed");
        check(value.request_n_high(), "invalid preflight enabled request");
    }
    {
        Heartbeat value(99);
        check(value.arm(99, 1, Cycle{1, 0, true, true}, 0), "arm failed");
        check(value.request_applied(0), "request acknowledgement failed");
        check(!value.request_n_high() && !value.pwm_allowed(), "arming levels wrong");
        check(!value.cycle(Cycle{2, 150, true, true}, 150), "setup boundary fed");
        check(!value.cycle(Cycle{3, 1000, true, true}, 1000), "wake boundary fed");
        check(value.cycle(Cycle{4, 1001, true, true}, 1001), "wake completion failed");
        check(value.edge_applied(1002) && value.pwm_allowed(), "ack did not unlock PWM");
        check(!value.cycle(Cycle{5, 6002, true, false}, 6002), "single healthy cycle fed");
        check(!value.cycle(Cycle{6, 11002, true, false}, 11002), "exact 10ms interval fed");
        check(value.cycle(Cycle{7, 11003, true, false}, 11003), "strict lower boundary failed");
        check(value.edge_applied(11004), "subsequent edge failed");
        check(!value.cycle(Cycle{8, 21004, true, false}, 21004), "counter did not restart");
        check(value.cycle(Cycle{9, 31004, true, false}, 31004), "two 10ms iterations did not feed");
        check(value.edge_applied(31005), "20ms pulse failed");
    }
    {
        auto value = running();
        check(value.advance(30000) && !value.edge_pending(), "background inspection generated a pulse");
        check(!value.advance(46002), "exact upper deadline did not fault");
        check(value.request_n_high() && !value.pwm_allowed(), "deadline fault did not disable");
        check(!value.cycle(Cycle{3, 46003, true, false}, 46003), "catch-up pulse accepted");
        check(!value.arm(99, 2, Cycle{4, 46004, true, true}, 46004), "fault silently rearmed");
    }
    {
        Heartbeat value(99);
        check(value.arm(99, 1, Cycle{1, 0, true, true}, 0), "arm failed");
        check(value.request_applied(0), "request acknowledgement failed");
        check(value.cycle(Cycle{2, 1001, true, true}, 1001), "edge request failed");
        check(!value.edge_applied(1102), "late edge acknowledgement accepted");
        check(value.request_n_high() && !value.pwm_allowed(), "late acknowledgement did not fail closed");
    }
    {
        auto value = running();
        check(!value.cycle(Cycle{2, 2000, true, false}, 2000), "duplicate cycle accepted");
        check(value.state() == Heartbeat::State::fault, "duplicate cycle did not fault");
    }
    {
        auto value = running();
        check(!value.cycle(Cycle{3, 1001, true, false}, 2000), "reused sample accepted");
        check(value.state() == Heartbeat::State::fault, "sample replay did not fault");
    }
    {
        auto value = running();
        check(!value.cycle(Cycle{3, 2000, true, false}, 12001), "stale sample fed");
        check(value.request_n_high(), "stale cycle left permission active");
    }
    {
        auto value = running();
        check(!value.cycle(Cycle{3, 2000, false, false}, 2000), "unhealthy cycle fed");
        check(value.request_n_high(), "health fault left permission active");
    }
    {
        auto value = running();
        check(!value.advance(1001), "backward clock accepted");
        check(value.request_n_high(), "backward clock left permission active");
    }
    {
        auto value = running();
        value.stop(2000);
        check(value.request_n_high() && !value.pwm_allowed(), "stop failed");
        check(!value.arm(99, 1, Cycle{3, 2001, true, true}, 2001), "stopped command replayed");
        check(value.arm(99, 2, Cycle{3, 2002, true, true}, 2002), "fresh explicit arm rejected");
        value = Heartbeat(100); // Actual reboot creates a new boot-bound policy.
        check(value.request_n_high() && !value.pwm_allowed(), "reboot restored running state");
        check(!value.arm(99, 2, Cycle{3, 0, true, true}, 0), "old boot replay armed after reset");
    }
    {
        Heartbeat invalid(0);
        check(!invalid.arm(0, 1, Cycle{1, 0, true, true}, 0), "zero boot armed");
        const auto last = std::numeric_limits<std::uint64_t>::max();
        Heartbeat value(99);
        check(value.arm(99, 1, Cycle{1, last - 2000, true, true}, last - 2000), "near-wrap arm failed");
        check(value.request_applied(last - 2000), "near-wrap request acknowledgement failed");
        check(value.cycle(Cycle{2, last - 999, true, true}, last - 999), "near-wrap edge failed");
        check(value.edge_applied(last - 998), "near-wrap acknowledgement failed");
        check(!value.advance(0) && value.request_n_high(), "clock wrap did not disable");
    }
    {
        Heartbeat value(99);
        check(value.arm(99, 1, Cycle{1, 0, true, true}, 0), "arm failed");
        check(!value.request_applied(101), "late request acknowledgement accepted");
        check(value.request_n_high(), "late request left permission active");
    }
    {
        Heartbeat value(99);
        check(value.arm(99, 1, Cycle{1, 0, true, true}, 0), "arm failed");
        check(value.request_applied(100), "bounded request latency rejected");
        check(!value.cycle(Cycle{2, 1001, true, true}, 1001), "GPIO latency shortened wake wait");
        check(value.cycle(Cycle{3, 1101, true, true}, 1101), "full wake wait failed");
    }
    std::cout << "heartbeat sequence and fault boundaries passed\n";
}
