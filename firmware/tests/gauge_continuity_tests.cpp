#include "smart_blinds/gauge_continuity.hpp"
#include <cstdlib>
#include <functional>
#include <iostream>
#include <type_traits>
#include <vector>
using namespace blinds::power;
namespace gc=blinds::power::continuity;
namespace {
void check(bool condition,const char* message) {
    if(!condition) { std::cerr<<message<<'\n';std::exit(1); }
}
gc::Context context() { return {99,17,2,7,10}; }
gc::Profile profile() {
    gc::Profile p;
    auto& pack=p.pack;
    pack.full_profile_verified=pack.timing_verified=pack.sensor_placement_verified=true;
    pack.verified_for_boot=99;pack.qualification_id=10;pack.pack_binding=7;
    pack.dev_name=0x420A;pack.pack_config=0x2009;pack.nv_config1=0x0140;
    pack.sense_resistor=1000;pack.thermistor_config=0x91C3;
    p.rom={0x1234,0x5678,0x9ABC,0xDEF0};
    p.nv_config=0x2290;p.config=0x2210;p.config2=0x2010;
    p.mode_continuity_verified=p.exclusive_access_verified=true;
    p.max_light_sleep_us=60000000;
    return p; // Synthetic fixtures only; NOT commissioned board records.
}
struct Bus final:gc::ReadOnlyBus {
    std::array<std::uint16_t,512> words{};
    std::vector<std::uint16_t> calls;
    std::int64_t time=1000000,step=100;
    std::size_t fail_at=0,backwards_at=0;
    std::function<void(Bus&,std::uint16_t&)> hook;
    Bus() {
        const auto p=profile();
        words[0x021]=p.pack.dev_name;words[0x1B5]=p.pack.pack_config;
        words[0x1B8]=p.pack.nv_config0;words[0x1B9]=p.pack.nv_config1;
        words[0x1CF]=p.pack.sense_resistor;words[0x1CA]=p.pack.thermistor_config;
        words[0x00B]=p.config;words[0x0AB]=p.config2;words[0x1B0]=p.nv_config;
        for(std::size_t i=0;i<4;++i) words[0x1BC+i]=p.rom[i];
        words[0x0F1]=3;words[0x006]=50*256;
        words[0x0DA]=words[0x0DB]=35520;
        words[0x0D8]=words[0x0D7]=words[0x0D6]=47360;
        words[0x01C]=static_cast<std::uint16_t>(-6400);
        words[0x139]=words[0x13A]=25*256;
    }
    std::int64_t now_us() override { return time; }
    bool read_word(std::uint16_t address,std::uint16_t& value,std::uint32_t timeout) override {
        check(timeout==10,"reader changed per-transfer bound");
        check(address<words.size(),"out-of-range register");
        calls.push_back(address);time+=step;
        value=words[address];
        if(hook) hook(*this,value);
        if(calls.size()==backwards_at) time-=step+1;
        return calls.size()!=fail_at;
    }
};
gc::Capture capture(std::int64_t at) { Bus b;b.time=at;return gc::read_capture(b); }
gc::Result observe(gc::Monitor& monitor,std::int64_t at) {
    const auto c=capture(at);
    return monitor.observe(c,context(),static_cast<std::uint64_t>(c.gauge.read_finished_us));
}
void warm(gc::Monitor& monitor) {
    check(observe(monitor,1000000).report.state==State::warming,"cold initial history skipped");
    check(observe(monitor,4194799).report.state==State::warming,"thermal bound shortened");
    check(observe(monitor,4200000).report.ready(),"complete thermal history rejected");
}
void bounded_reader() {
    Bus bus;const auto c=gc::read_capture(bus);
    check(c.gauge.valid && c.error==gc::ReadError::none && bus.calls.size()==52,"complete capture failed");
    const std::vector<std::uint16_t> guard={0x000,0x0AF,0x0D9,0x0B0,0x03D,0x0F1,0x1A8,
        0x00B,0x0AB,0x1B0,0x1BB,0x1BC,0x1BD,0x1BE,0x1BF,0x021,0x1B5,0x1B8,
        0x1B9,0x1CF,0x1CA};
    const std::vector<std::uint16_t> payload={0x006,0x0DA,0x01C,0x01B,0x0D8,0x0D7,
        0x0D6,0x0DB,0x13A,0x139};
    auto expected=guard;expected.insert(expected.end(),payload.begin(),payload.end());
    expected.insert(expected.end(),guard.begin(),guard.end());
    check(bus.calls==expected,"primary-derived bracket sequence changed");
    check(c.gauge.read_started_us==1000000 && c.gauge.read_finished_us==1005200,"source times fabricated");
    for(std::size_t i=1;i<=52;++i) {
        Bus failed;failed.fail_at=i;
        const auto f=gc::read_capture(failed);
        check(!f.gauge.valid && f.error==gc::ReadError::bus && failed.calls.size()==i,"read failure retried or ignored");
        Bus backwards;backwards.backwards_at=i;
        check(gc::read_capture(backwards).error==gc::ReadError::clock &&
              backwards.calls.size()==i,"clock reversal ignored");
    }
    Bus blocked;blocked.step=10001;
    check(gc::read_capture(blocked).error==gc::ReadError::timeout && blocked.calls.size()==1,
          "non-compliant slow bus escaped timeout");
    Bus cumulative;cumulative.step=5000;
    check(gc::read_capture(cumulative).error==gc::ReadError::timeout && cumulative.calls.size()==50,
          "capture deadline restarted per transfer");
    for(std::int64_t extra:{400,401}) {
        Bus edge;edge.step=4800;
        edge.hook=[extra](Bus& b,std::uint16_t&){if(b.calls.size()==52) b.time+=extra;};
        check(gc::read_capture(edge).gauge.valid==(extra==400),"250ms capture boundary changed");
    }
    Bus negative;negative.time=std::numeric_limits<std::int64_t>::min();
    check(gc::read_capture(negative).error==gc::ReadError::clock && negative.calls.empty(),"negative clock accepted");
    Bus bracket;
    bracket.hook=[](Bus& b,std::uint16_t& value) {
        if(b.calls.size()==2) value=0x0008; // Latched prior fault only in head.
        if(b.calls.size()==37) value=1; // Tail FETStatus.
    };
    const auto merged=gc::read_capture(bracket);
    check((merged.gauge.protection_status&8) && merged.gauge.fet_status==1,
          "head alert or tail FET state was lost");
}
void qualification() {
    gc::Monitor unknown({},context());
    check(!observe(unknown,1000000).report.ready() && unknown.fault()==gc::Fault::qualification,
          "empty profile accepted");
    check(profile().valid(99) && !profile().valid(100),"boot binding missing");
    for(unsigned variant=0;variant<12;++variant) {
        auto p=profile();
        switch(variant) {
        case 0:p.mode_continuity_verified=false;break;
        case 1:p.exclusive_access_verified=false;break;
        case 2:p.max_light_sleep_us=0;break;
        case 3:p.rom.fill(0);break;
        case 4:p.rom.fill(0xFFFF);break;
        case 5:p.config|=0x80;break; // SHIP
        case 6:p.nv_config|=0x20;break; // ALSH
        case 7:p.config|=0x40;break; // COMMSH
        case 8:p.config|=8;break; // FTHRM
        case 9:p.config&=~0x10;break; // ETHRM
        case 10:p.config2|=0x8000;break; // POR_CMD
        case 11:p.pack.hibernate_config|=0x8000;break;
        }
        check(!p.valid(99),"unqualified continuity mode accepted");
    }
    for(unsigned bit=0;bit<16;++bit) {
        const auto mask=static_cast<std::uint16_t>(1u<<bit);
        if(mask&0x0168) { auto p=profile();p.nv_config|=mask;check(!p.valid(99),"nConfig forbidden bit accepted"); }
        if(mask&0x81EA) { auto p=profile();p.config|=mask;check(!p.valid(99),"Config forbidden bit accepted"); }
        if(mask&0xC023) { auto p=profile();p.config2|=mask;check(!p.valid(99),"Config2 forbidden bit accepted"); }
    }
    auto fixed=profile();fixed.nv_config&=~0x10;check(!fixed.valid(99),"nConfig fixed bit ignored");
    fixed=profile();fixed.config2&=~0x10;check(!fixed.valid(99),"Config2 fixed bit ignored");
    static_assert(!std::is_copy_constructible_v<gc::Monitor>);
    static_assert(!std::is_move_constructible_v<gc::Monitor>);
}
void light_sleep_and_freshness() {
    gc::Monitor m(profile(),context());warm(m);
    check(m.park_light_sleep(context(),4300000) && m.phase()==gc::Phase::parked,"known sleep rejected");
    check(m.resume_light_sleep(context(),10000000) && m.phase()==gc::Phase::awaiting_capture,"resume rejected");
    const auto result=observe(m,10000000);const auto& r=result.report;
    check(r.ready() && result.phase==gc::Phase::active,"valid continuation repeated warmup");
    check(r.observed_us==10000000 && r.voltage_earliest_us==9600000 && r.temperature_earliest_us==6800000,
          "continuity reused old values or promoted observation to conversion");
    check(r.temperature_c[0]==25 && r.temperature_c[1]==25,"constant thermal values treated as a stalled ADC");
    smart_blinds::charger::OffCapture off;
    off.error=smart_blinds::charger::Error::none;off.started_ms=10000;off.finished_ms=10006;
    check(motion_power(r,off,10006000).ready,"unchanged power freshness rejected new read");
    check(!motion_power(r,off,10250001).ready,"continuity widened status freshness");
    auto bad=r;bad.voltage_earliest_us=9255999;
    check(!motion_power(bad,off,10006000).ready,"continuity widened voltage freshness");
    bad=r;bad.temperature_earliest_us=5755999;
    check(!motion_power(bad,off,10006000).ready,"continuity widened temperature freshness");
    check(m.park_light_sleep(context(),10006000),"second fresh park rejected");
    check(m.resume_light_sleep(context(),70006000),"exact qualified interval rejected");
    check(observe(m,70006000).report.ready(),"second valid ticket failed");
    gc::Monitor reboot(profile(),context());
    check(observe(reboot,70006000).report.state==State::warming,"new object restored previous ticket");
}
void invalidation() {
    for(unsigned variant=0;variant<17;++variant) {
        gc::Monitor m(profile(),context());warm(m);
        auto ctx=context();
        if(variant<5) {
            switch(variant) {
            case 0:++ctx.boot;break;case 1:++ctx.bus_generation;break;
            case 2:++ctx.monitoring_session;break;case 3:++ctx.pack_binding;break;
            case 4:++ctx.qualification_id;break;
            }
            check(!m.park_light_sleep(ctx,4300000),"changed context kept continuity");
        } else if(variant==5) {
            check(!m.park_light_sleep(ctx,4450001),"stale ready report issued ticket");
        } else {
            check(m.park_light_sleep(ctx,4300000),"park failed");
            if(variant==6) check(!m.resume_light_sleep(ctx,64300001),"expired interval accepted");
            else if(variant==7) check(!m.resume_light_sleep(ctx,4299999),"reversed sleep clock accepted");
            else if(variant==8) check(!m.park_light_sleep(ctx,4300001),"double park accepted");
            else if(variant==9) check(!observe(m,4400000).report.ready(),"capture while parked accepted");
            else {
                check(m.resume_light_sleep(ctx,10000000),"resume failed");
                if(variant==10) check(!m.resume_light_sleep(ctx,10000001),"ticket reused");
                else {
                    auto c=capture(10000000);std::uint64_t now=10006000;
                    if(variant==11) c=capture(9999999); // New, but before wake.
                    if(variant==12) c=capture(4200000); // Pre-sleep report replay.
                    if(variant==13) now=10250001; // Stale source status.
                    if(variant==14) c.gauge.read_finished_us=10006001; // Future.
                    if(variant==15) c.gauge.valid=false;
                    if(variant==16) m.invalidate(); // Ambiguous writer/power event.
                    check(!m.observe(c,ctx,now).report.ready(),"invalid resume evidence accepted");
                }
            }
        }
        check(m.phase()==gc::Phase::invalid,"continuity failure not latched");
        check(!observe(m,80000000).report.ready(),"healthy later capture silently restored ticket");
    }
    gc::Monitor cold(profile(),context());
    check(!cold.park_light_sleep(context(),1000000),"cold instance issued ticket");
    gc::Monitor duplicate(profile(),context());warm(duplicate);
    check(!observe(duplicate,4200000).report.ready(),"repeated source capture accepted");
    gc::Monitor overlapping(profile(),context());warm(overlapping);
    check(!observe(overlapping,4205199).report.ready(),"overlapping capture intervals accepted");
    gc::Monitor boundary(profile(),context());warm(boundary);
    const auto c=capture(4400000);
    check(boundary.observe(c,context(),4650000).report.ready(),"exact 250ms source-age boundary rejected");
}
void guard_faults() {
    for(bool tail:{false,true}) for(unsigned variant=0;variant<19;++variant) {
        gc::Monitor m(profile(),context());warm(m);
        check(m.park_light_sleep(context(),4300000) && m.resume_light_sleep(context(),10000000),"park/resume failed");
        auto c=capture(10000000);auto& g=tail ? c.after:c.before;
        switch(variant) {
        case 0:g.status|=2;break;case 1:g.status2|=2;break;case 2:g.fstat|=1;break;
        case 3:g.alerts|=8;break;case 4:g.protection|=8;break;case 5:g.battery_status|=0x100;break;
        case 6:g.fets=1;break;case 7:g.config|=0x80;break;case 8:g.config2|=0x8000;break;
        case 9:g.nv_config|=0x20;break;case 10:g.hibernate|=0x8000;break;
        case 11:g.rom[2]^=1;break;case 12:g.dev_name^=1;break;case 13:g.pack_config^=0x2000;break;
        case 14:g.nv_config0^=1;break;case 15:g.nv_config1^=1;break;case 16:g.sense^=1;break;
        case 17:g.thermistor^=1;break;case 18:c.gauge.thermistors[1]=40*256;break;
        }
        check(!m.observe(c,context(),10006000).report.ready() && m.phase()==gc::Phase::invalid,
              "head/tail fault or mismatched profile accepted");
    }
    gc::Monitor full(profile(),context());warm(full);
    auto c=capture(4400000);c.before.alerts=c.after.alerts=0x2000;
    check(full.observe(c,context(),4406000).report.ready(),"benign Full alert rejected");
}
} // namespace
int main() {
    bounded_reader();qualification();light_sleep_and_freshness();invalidation();guard_faults();
    std::cout<<"isolated gauge continuity, source age, 52-point bus faults and transition controls passed\n";
}
