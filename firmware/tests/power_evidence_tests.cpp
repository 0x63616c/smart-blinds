#include "smart_blinds/power_evidence.hpp"
#include <cstdlib>
#include <iostream>
using namespace blinds::power;
namespace {
void check(bool value,const char* text) { if(!value) { std::cerr<<text<<'\n'; std::exit(1); } }
PackProfile profile() {
    PackProfile p;
    p.full_profile_verified=p.timing_verified=p.sensor_placement_verified=true;
    p.verified_for_boot=99; p.qualification_id=10; p.pack_binding=7;
    p.dev_name=0x420A; p.pack_config=0x2009; p.nv_config1=0x0140;
    p.sense_resistor=1000; p.thermistor_config=0x91C3;
    return p; // Synthetic fixture; not a production pack configuration.
}
GaugeCapture capture(std::uint64_t at) {
    const auto p=profile(); GaugeCapture c;
    c.valid=true; c.read_started_us=at; c.read_finished_us=at+10000;
    c.dev_name=p.dev_name; c.pack_config=p.pack_config; c.nv_config1=p.nv_config1;
    c.sense_resistor=p.sense_resistor; c.thermistor_config=p.thermistor_config;
    c.cells.fill(47360); c.pack_voltage=c.protected_voltage=35520; // 3 x 3.7 V.
    c.thermistors.fill(25*256); c.fet_status=3; c.soc=50*256; c.current=static_cast<std::uint16_t>(-6400);
    return c;
}
Report warm(GaugeMonitor& m) {
    check(m.observe(capture(1000000),1010000).state==State::warming,"did not require initial thermal conversion window");
    return m.observe(capture(4300000),4310000);
}
void measured_age() {
    GaugeMonitor m(99,profile()); const auto r=warm(m);
    check(r.ready() && r.soc_percent==50. && r.current_a==-1.,"qualified capture/telemetry rejected");
    check(std::abs(r.pack_v-11.1)<1e-9,"pack unit conversion wrong");
    check(r.observed_us==4300000 && r.voltage_earliest_us==3900000 && r.temperature_earliest_us==1100000,"receipt promoted to conversion time");
    auto off=smart_blinds::charger::OffCapture{};
    off.error=smart_blinds::charger::Error::none; off.started_ms=4300; off.finished_ms=4310;
    check(motion_power(r,off,4310000).ready,"battery-only joint evidence rejected");
    check(!motion_power(r,off,4560000).ready,"cached status renewed by receipt time");
    off.started_ms=4000; check(!motion_power(r,off,4310000).ready,"stale charger state accepted");
    off.started_ms=4300; off.finished_ms=4320; check(!motion_power(r,off,4310000).ready,"future charger accepted");
    check(m.observe(capture(4300000),4560000).state==State::clock,"same ADC read treated as freshly converted");
    auto loss=capture(4600000); loss.valid=false;
    check(m.observe(loss,4610000).state==State::bus,"missing carrier accepted");
    check(m.observe(capture(4700000),4710000).state==State::warming,"reconnect skipped renewed warmup");
    GaugeMonitor reset(99,profile()); check(warm(reset).ready(),"warm failed");
    check(reset.observe(capture(4400000),4000000).state==State::clock,"reverse clock accepted");
    check(reset.observe(capture(4500000),4510000).state==State::clock,"clock fault implicitly cleared");
}
void qualification() {
    GaugeMonitor unknown(99,{});
    check(unknown.observe(capture(1000000),1010000).state==State::unqualified,"successful I2C became qualification");
    auto p=profile();
    check(p.valid(99) && !p.valid(100),"commissioning escaped boot binding");
    p.pack_config&=~0x2000; check(!p.valid(99),"22.4 second Batt mode accepted");
    p=profile(); p.hibernate_config=0x8000; check(!p.valid(99),"unbounded hibernate age accepted");
    p=profile(); p.temperature_period_bound_us=100000; check(!p.valid(99),"thermistor nominal period ignored");
    p=profile(); p.voltage_period_bound_us=100000; check(!p.valid(99),"gauge conversion magically faster");
    p=profile(); p.pack_config=0x2005; check(!p.valid(99),"single temperature channel passed two-channel policy");
    p=profile(); p.nv_config1=0; check(!p.valid(99),"protector disabled profile accepted");
}
void unhealthy() {
    for(int scenario=0;scenario<18;++scenario) {
        GaugeMonitor m(99,profile()); check(warm(m).ready(),"warm failed");
        auto c=capture(4400000);
        switch(scenario) {
        case 0: c.status=2; break;
        case 1: c.status2=2; break;
        case 2: c.fstat=1; break;
        case 3: c.protection_status=8; break;
        case 4: c.battery_status=0x100; break;
        case 5: c.fet_status=1; break;
        case 6: c.cells[0]=40000; break;
        case 7: c.cells[1]=55000; break;
        case 8: c.thermistors[0]=9*256; break;
        case 9: c.thermistors[1]=40*256; break;
        case 10: c.protected_voltage=0; break;
        case 11: c.sense_resistor=0; break;
        case 12: c.thermistor_config=0; break;
        case 13: c.dev_name^=1; break;
        case 14: c.pack_config^=0x2000; break;
        case 15: c.read_finished_us=c.read_started_us+300000; break;
        case 16: c.current=0x7FFF; break;
        case 17: c.read_started_us=1000000; break;
        }
        check(!m.observe(c,4410000).ready(),"unhealthy or stale capture accepted");
    }
    GaugeMonitor full(99,profile()); check(warm(full).ready(),"warm failed");
    auto c=capture(4400000); c.protection_status=0x2000; c.soc=101*256;
    const auto r=full.observe(c,4410000);
    check(r.ready() && !r.soc_percent,"full flag prevented motion or impossible SOC fabricated");
}
}
int main() { measured_age(); qualification(); unhealthy(); std::cout<<"gauge conversion age, qualification and joint OFF-state evidence passed\n"; }
