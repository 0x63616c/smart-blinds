#include "smart_blinds/clock_bounds.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
using namespace smart_blinds;
void require(bool result, const char* why) { if (!result) { std::cerr << why << '\n'; std::exit(1); } }
// Physical experiment: host starts at 1 s; device has +100 ms offset, outward
// flight a, processing p, inward flight b. Known offset must remain in interval.
ClockExchange sample(std::uint64_t a, std::uint64_t b, std::uint64_t p = 100) {
    return {1000000, 1100000 + a, 1100000 + a + p, 1000000 + a + p + b};
}
int main() {
    for (auto a : {0, 1000, 10000, 40000}) for (auto b : {0, 1000, 10000, 40000}) {
        auto bound = ClockBounds::estimate(sample(a,b));
        require(bool(bound), "valid exchange rejected");
        require(bound->lower_us() <= 100000 && bound->upper_us() >= 100000, "asymmetric path excluded true offset");
        require(!bound->host_qualified(bound->host_reference_us()), "unvalidated clock model qualified");
    }
    auto tight = ClockBounds::estimate(sample(1000,9000), {1000,2,true});
    require(tight->host_qualified(tight->host_reference_us()), "bounded asymmetric exchange rejected");
    require(!tight->host_qualified(tight->host_reference_us()+1000001), "stale exchange qualified");
    require(!tight->host_qualified(tight->host_reference_us()-1), "clock reversal qualified");
    auto wide = ClockBounds::estimate(sample(0,40000), {1000,2,true});
    require(!wide->host_qualified(wide->host_reference_us()), "asymmetric bias silently assumed away");
    auto drift = ClockBounds::estimate(sample(9000,9000), {1000,2,true});
    require(drift->host_qualified(drift->host_reference_us()), "initial clock fit rejected");
    require(!drift->host_qualified(drift->host_reference_us()+1000000), "drift growth ignored");
    require(!ClockBounds::estimate({100,200,300,99}), "reverse host time accepted");
    require(!ClockBounds::estimate({100,300,200,400}), "reverse device time accepted");
    require(!ClockBounds::estimate({100,200,400,200}), "negative flight time accepted");
    require(!ClockBounds::estimate({0,1,2,500001}), "unbounded round trip accepted");
    require(!ClockBounds::estimate({0,1,2,3},{10001,2,true}), "unsupported drift model accepted");
    require(!ClockBounds::estimate({0,1,2,std::numeric_limits<std::uint64_t>::max()}), "unsigned timestamp overflow accepted");
    // A physically simulated +700 ppm device clock, not symmetric-delay input.
    for (auto a : {0, 1000, 10000, 40000}) for (auto b : {0, 1000, 10000, 40000}) {
        const std::uint64_t t1 = 1000000, t4 = t1 + a + 100 + b;
        const auto device_time = [](std::uint64_t host) { return host + 100000 + (host * 700) / 1000000; };
        auto bound = ClockBounds::estimate({t1, device_time(t1+a), device_time(t1+a+100), t4});
        require(bool(bound), "bounded oscillator drift rejected");
        const auto actual_offset = static_cast<std::int64_t>(device_time(t4)-t4);
        require(bound->lower_us() <= actual_offset && bound->upper_us() >= actual_offset, "drifting true offset excluded");
    }
    ClockProbes device(42);
    require(!device.begin(42,1,1000000,false), "sleeping probe accepted");
    require(device.begin(42,1,1101000,true), "awake probe rejected");
    require(device.sent(1101100,true), "probe timestamp rejected");
    require(!device.assess(41,1,1000000,1010100,1101200,true), "wrong boot assessed");
    require(device.assess(42,1,1000000,1010100,1110200,true), "valid assessment rejected");
    require(bool(device.bounds()) && !device.qualified(1110200), "assumed model became validated");
    require(!device.assess(42,1,1000000,1010100,1110300,true), "assessment replay accepted");
    device.advance(1110400,false);
    require(!device.bounds(), "sleep preserved assessment");
    require(!device.begin(42,1,1110500,true), "old probe sequence reused after sleep");
    require(device.begin(42,2,1110600,true), "fresh probe rejected");
    require(!device.advance(1110599,true), "clock reversal accepted");
    require(!device.begin(42,3,1200000,true), "clock fault silently cleared");
    ClockProbes validated(43, {1000,2,true});
    require(validated.begin(43,1,1101000,true) && validated.sent(1101100,true), "test-model probe failed");
    require(validated.assess(43,1,1000000,1010100,1110200,true) && validated.qualified(1110200), "validated test model not qualified");
    require(validated.begin(43,2,1110300,true) && !validated.bounds(), "new probe retained old assessment identity");
    require(validated.sent(1110400,true), "replacement probe failed");
    require(!validated.assess(43,2,1010000,1010500,1610401,true), "late proof accepted");
    require(!validated.bounds(), "late proof retained assessment");
    std::cout << "clock interval, drift and challenge boundaries passed\n";
}
