#include "smart_blinds/gauge_bus_session.hpp"
#include <cstdlib>
#include <functional>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
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
    p.mode_continuity_verified=p.exclusive_access_verified=true;p.max_light_sleep_us=60000000;
    return p; // Synthetic evidence, never a device qualification.
}
struct Wire final:gc::WordTransport {
    struct Call { std::uint8_t device,pointer;std::uint32_t timeout; };
    std::array<std::uint16_t,512> words{};
    std::vector<Call> calls;
    gc::Owner owner=1;
    std::int64_t time=1000000,step=100;
    std::size_t fail_at=0,clocks=0;
    std::function<void()> during_transfer,on_clock;
    std::function<void(std::size_t,std::uint16_t&)> word_hook;
    Wire() {
        const auto p=profile();
        words[0x021]=p.pack.dev_name;words[0x1B5]=p.pack.pack_config;
        words[0x1B9]=p.pack.nv_config1;words[0x1CF]=p.pack.sense_resistor;
        words[0x1CA]=p.pack.thermistor_config;words[0x00B]=p.config;
        words[0x0AB]=p.config2;words[0x1B0]=p.nv_config;
        for(std::size_t i=0;i<4;++i) words[0x1BC+i]=p.rom[i];
        words[0x0F1]=3;words[0x006]=50*256;
        words[0x0DA]=words[0x0DB]=35520;
        words[0x0D8]=words[0x0D7]=words[0x0D6]=47360;
        words[0x01C]=static_cast<std::uint16_t>(-6400);
        words[0x139]=words[0x13A]=25*256;
    }
    gc::Owner current_owner() const override { return owner; }
    std::int64_t now_us() override { ++clocks;if(on_clock) on_clock();return time; }
    bool transfer(std::uint8_t device,std::uint8_t pointer,std::array<std::uint8_t,2>& bytes,
                  std::uint32_t timeout) override {
        check(device==0x36 || device==0x0B,"invalid physical address");
        calls.push_back({device,pointer,timeout});
        const auto reg=static_cast<std::uint16_t>(pointer+(device==0x0B ? 0x100:0));
        auto raw=words[reg];
        if(word_hook) word_hook(calls.size(),raw);
        bytes={static_cast<std::uint8_t>(raw),static_cast<std::uint8_t>(raw>>8)};
        time+=step;
        if(during_transfer) during_transfer();
        return calls.size()!=fail_at;
    }
};
gc::Publication warm(gc::OwnedSession& session,Wire& wire) {
    check(session.can_attach(context()),"qualified session attachment gate failed");
    const auto first=session.read(context());
    check(first.evidence.report.state==blinds::power::State::warming && !session.current(first,wire.time),
          "session removed initial warmup");
    wire.time=4200000;
    const auto ready=session.read(context());
    check(ready.evidence.report.ready() && session.current(ready,wire.time),"warm session not publishable");
    return ready;
}
void mapping_and_wire_failure() {
    const std::vector<std::uint16_t> normal={0x000,0x006,0x00B,0x01B,0x01C,0x021,0x03D,
        0x0AB,0x0AF,0x0B0,0x0D6,0x0D7,0x0D8,0x0D9,0x0DA,0x0DB,0x0F1};
    const std::vector<std::uint16_t> shadow={0x139,0x13A,0x1A8,0x1B0,0x1B5,0x1B8,0x1B9,
        0x1BB,0x1BC,0x1BD,0x1BE,0x1BF,0x1CA,0x1CF};
    gc::BusEpoch epoch;Wire wire;gc::OwnedWordBus bus(wire,epoch,epoch.value(),1);
    for(const auto& regs:{normal,shadow}) for(auto reg:regs) {
        wire.words[reg]=0xC3A5;std::uint16_t result=0;
        check(bus.read_word(reg,result,10) && result==0xC3A5,"little-endian word decode failed");
        const auto call=wire.calls.back();
        check(call.device==(reg<0x100 ? 0x36:0x0B) && call.pointer==(reg&0xFF) && call.timeout==10,
              "logical address or timeout mapping changed");
    }
    for(auto reg:{0x060,0x061,0x0C0,0x100,0x180,0x1FF,0x200,0xFFFF}) {
        gc::WordAddress address{0xFF,0xFF};
        check(!gc::read_address(static_cast<std::uint16_t>(reg),address) && !address.device && !address.pointer,
              "non-reviewed/command address accepted");
    }
    for(unsigned kind=0;kind<5;++kind) {
        gc::BusEpoch lost;Wire w;gc::OwnedWordBus b(w,lost,lost.value(),1);
        if(kind==0) w.fail_at=1;
        if(kind==1) w.owner=2;
        if(kind==2) w.during_transfer=[&]{lost.retire();};
        if(kind==3) w.during_transfer=[&]{w.owner=2;};
        std::uint16_t value=0xFEED;
        check(!b.read_word(kind==4 ? 0x060:0x021,value,10) && value==0xFEED,
              "word fault exposed partial data");
        const auto count=w.calls.size();w.owner=1;w.fail_at=0;w.during_transfer={};
        check(!b.read_word(0x021,value,10) && w.calls.size()==count,"successful later word repaired epoch");
    }
    gc::BusEpoch timeout_epoch;Wire w;gc::OwnedWordBus b(w,timeout_epoch,timeout_epoch.value(),1);
    std::uint16_t value=0;
    check(!b.read_word(0x021,value,100) && w.calls.empty(),"unbounded timeout propagated");
}
void publication_and_park() {
    gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
    const auto old=warm(session,wire);
    check(!session.current(old,old.evidence.report.observed_us+250001),"stale publication accepted");
    check(session.park_light_sleep(context()) && !session.current(old,wire.time),
          "park left old readiness available");
    wire.time=10000000;check(session.resume_light_sleep(context()),"known light resume rejected");
    check(!session.current(old,wire.time),"resume restored pre-sleep publication");
    const auto current=session.read(context());
    check(session.current(current,wire.time) && !session.current(old,wire.time),
          "new read reused pre-sleep serial");
    check(current.evidence.report.observed_us==10000000,"new source stamp lost");
    epoch.retire();
    check(!session.current(current,wire.time),"external retirement left queued publication valid");
    const auto count=wire.calls.size();
    check(!session.read(context()).evidence.report.ready() && wire.calls.size()==count,"retired session touched bus");
    // Old-object cleanup must not retire a newly issued generation.
    const auto fresh=epoch.value();session.retire();
    check(epoch.value()==fresh,"old session cleanup invalidated a newer epoch");
    auto next=context();++next.bus_generation;++next.monitoring_session;
    gc::OwnedSession next_session(profile(),next,wire,epoch,1);
    check(next_session.can_attach(next) && next_session.read(next).evidence.report.state==blinds::power::State::warming,
          "new explicitly selected session skipped cold history");
}
void ownership_and_faults() {
    for(unsigned kind=0;kind<3;++kind) for(std::size_t position=1;position<=52;++position) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.time=4300000;
        if(kind==0) wire.fail_at=position;
        else wire.during_transfer=[&,kind,position]{
            if(wire.calls.size()==position) {
                if(kind==1) epoch.retire();
                else wire.owner=2;
            }
        };
        const auto result=session.read(context());
        check(!result.evidence.report.ready() && wire.calls.size()==position,
              "mid-transfer loss published evidence or continued reading");
        check(!session.current(old,wire.time),"failed capture did not revoke earlier publication");
        wire.owner=1;wire.fail_at=0;wire.during_transfer={};
        check(!session.read(context()).evidence.report.ready() && wire.calls.size()==position,
              "later success repaired ambiguous capture");
    }
    gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
    const auto old=warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;
    wire.on_clock=[&]{if(wire.clocks==107) epoch.retire();}; // after complete read, before interpretation.
    check(!session.read(context()).evidence.report.ready() && wire.calls.size()==52 &&
          !session.current(old,wire.time),"retirement at interpretation published ready");
    for(unsigned kind=0;kind<5;++kind) {
        gc::BusEpoch e;Wire w;gc::OwnedSession s(profile(),context(),w,e,1);
        warm(s,w);w.calls.clear();
        auto changed=context();
        if(kind==0) ++changed.monitoring_session;
        if(kind==1) ++changed.pack_binding;
        if(kind==2) ++changed.qualification_id;
        if(kind==3) ++changed.bus_generation;
        if(kind==4) w.owner=2;
        check(!s.read(changed).evidence.report.ready() && w.calls.empty(),"changed owner/context performed I2C");
    }
    gc::BusEpoch e;Wire w;gc::OwnedSession slow(profile(),context(),w,e,1);
    w.step=10001;
    check(!slow.read(context()).evidence.report.ready() && w.calls.size()==1,"slow SDK transfer accepted");
    w.step=100;
    check(!slow.read(context()).evidence.report.ready() && w.calls.size()==1,"timeout auto-recovered");
    gc::BusEpoch unqualified;Wire unused;gc::OwnedSession disabled({},context(),unused,unqualified,1);
    check(!disabled.can_attach(context()) && !disabled.read(context()).evidence.report.ready() &&
          unused.calls.empty(),"default profile attached/read hardware");
}
void atomic_epoch() {
    static_assert(gc::BusEpoch::successor(UINT32_MAX)==UINT32_MAX);
    static_assert(gc::BusEpoch::successor(UINT32_MAX-1)==UINT32_MAX);
    gc::BusEpoch epoch;
    std::vector<std::thread> retiring;
    for(int i=0;i<4;++i) retiring.emplace_back([&]{for(int n=0;n<1000;++n) epoch.retire();});
    for(auto& t:retiring) t.join();
    check(epoch.value()==4001 && !epoch.matches(1),"concurrent retirement lost monotonic generations");
    epoch.retire_if(1);check(epoch.value()==4001,"stale token retired current bus");
    epoch.retire_if(4001);check(epoch.value()==4002,"current token failed to retire");
}
void refresh_lifetime() {
    gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
    const auto old=warm(session,wire);
    wire.time=4300000;wire.calls.clear();wire.step=450; // Wire arithmetic only, not hardware timing.
    unsigned retained=0;
    wire.during_transfer=[&] {
        check(session.current(old,wire.time),"healthy refresh withdrew last completed report");
        check(old.evidence.report.observed_us==4200000 && old.evidence.report.voltage_earliest_us==3800000 &&
              old.evidence.report.temperature_earliest_us==1000000,"retained source times changed");
        ++retained;
    };
    const auto next=session.read(context());
    check(retained==52 && session.current(next,wire.time) && !session.current(old,wire.time),
          "refresh did not replace exactly one completed serial");
    check(next.serial==old.serial+1 && next.evidence.report.observed_us==4300000 &&
          next.evidence.report.voltage_earliest_us==3900000,"new report lost its source time");

    // Exact expiry during an otherwise successful read must remain visible.
    wire.calls.clear();wire.time=4549900;wire.step=100;
    wire.during_transfer=[&] {
        const bool expected=wire.time<=4550000;
        check(session.current(next,wire.time)==expected,"refresh masked original observation expiry");
    };
    const auto newer=session.read(context());
    check(session.current(newer,wire.time) && !session.current(next,wire.time),"stale report revived");

    // Retirement, park and resume keep their existing destructive semantics.
    wire.during_transfer={};
    check(session.park_light_sleep(context()) && !session.current(newer,wire.time),"park retained prior");
    wire.time=10000000;check(session.resume_light_sleep(context()),"resume failed");
    wire.during_transfer=[&]{check(!session.current(newer,wire.time),"resumed read revived pre-sleep report");};
    check(session.current(session.read(context()),wire.time),"fresh post-resume capture failed");
}
void immediate_faults() {
    for(unsigned kind=0;kind<4;++kind) for(std::size_t position=1;position<=52;++position) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;
        if(kind==0) wire.fail_at=position;
        wire.during_transfer=[&] {
            if(wire.calls.size()!=position) return;
            if(kind==1) wire.time-=101; // Returned clock goes backwards.
            if(kind==2) wire.time+=9901; // Exactly 10001 us total word duration.
            if(kind==3) session.retire();
        };
        const auto final_clock=2*position+(kind==0 || kind==3 ? 1:2);
        bool probed=false;
        wire.on_clock=[&] {
            if(wire.clocks==final_clock) {
                check(!session.current(old,4300000),"detected error retained prior until capture return");
                probed=true;
                wire.time=-1; // A subsequent clock fault must not replace first cause.
            }
        };
        const auto result=session.read(context());
        const auto expected=kind==0 ? gc::Fault::bus:kind==3 ? gc::Fault::context:gc::Fault::clock;
        check(probed && result.evidence.fault==expected && wire.calls.size()==position,
              "first fault cause, synchronous revocation or early termination lost");
        wire.on_clock={};wire.during_transfer={};wire.fail_at=0;wire.time=4400000;
        check(session.read(context()).evidence.fault==expected && wire.calls.size()==position,
              "later successful read repaired or relabelled first fault");
    }
    // Initial/start chronology and final clock are independently checked.
    for(unsigned kind=0;kind<5;++kind) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.clocks=0;
        wire.time=kind==0 ? -1:kind==1 ? 4200000:kind==2 ? 4205199:4300000;
        if(kind==3) wire.on_clock=[&]{if(wire.clocks==2) wire.time=-1;};
        if(kind==4) wire.on_clock=[&]{if(wire.clocks==106) wire.time=-1;};
        const auto bad=session.read(context());
        check(bad.evidence.fault==gc::Fault::clock && !session.current(old,4300000) &&
              wire.calls.size()==(kind==4 ? 52:0),"start/pre-word/final clock fault escaped");
    }
    for(unsigned extra:{400,401}) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;wire.step=4800;
        wire.during_transfer=[&]{if(wire.calls.size()==52) wire.time+=extra;};
        bool final_seen=false;
        wire.on_clock=[&] {
            if(wire.clocks==106) {
                final_seen=true;
                check(epoch.matches(1)==(extra==400),"total timeout retirement waited for capture return");
            }
        };
        const auto result=session.read(context());
        check(final_seen && session.current(result,wire.time)==(extra==400),"owned 250ms boundary changed");
        if(extra==401) check(result.evidence.fault==gc::Fault::clock,"total overrun reason lost");
    }
    {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;wire.step=10000;
        wire.during_transfer=[&]{wire.step=100;}; // Exact 10ms first transfer remains allowed.
        check(session.read(context()).evidence.report.ready(),"exact 10ms word duration rejected");
    }
    {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;wire.step=5000;
        bool revoked=false;
        wire.on_clock=[&]{if(wire.clocks==103) revoked=!epoch.matches(1);};
        const auto result=session.read(context());
        check(revoked && wire.calls.size()==50 && result.evidence.fault==gc::Fault::clock,
              "deadline reached before next transfer was issued or failed to revoke");
    }
}
void received_word_faults() {
    // Every guard position, including the very last tail word. The Full bit
    // control and predicate parity are tested in gauge_continuity_tests.
    const std::array<std::uint16_t,21> bad={2,8,8,2,1,1,0x100,
        0,0,0,0x8000,0,0,0,0,0,0,1,0,0,0};
    for(bool tail:{false,true}) for(std::size_t i=0;i<bad.size();++i) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;
        const auto position=1+i+(tail ? 31:0);
        wire.word_hook=[&](std::size_t at,std::uint16_t& raw){if(at==position) raw=bad[i];};
        bool revoked_before_final=false;
        wire.on_clock=[&] {
            if(wire.clocks==position*2+2) {
                check(!session.current(old,wire.time),"bad guard remained current before final interpretation");
                revoked_before_final=true;
                wire.time=-1;
            }
        };
        const auto result=session.read(context());
        check(revoked_before_final && wire.calls.size()==position &&
              result.evidence.fault==(i<7 ? gc::Fault::protection:gc::Fault::profile),
              "head/tail guard failure delayed or first cause replaced");
    }
    const std::pair<std::size_t,std::uint16_t> bad_values[]={
        {23,0},{24,0x7FFF},{24,0x8000},{26,0},{27,0},{28,0},{29,0},{30,40*256},{31,9*256}
    };
    for(auto bad:bad_values) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.clocks=0;wire.time=4300000;
        wire.word_hook=[&](std::size_t at,std::uint16_t& raw){if(at==bad.first) raw=bad.second;};
        bool revoked=false;
        wire.on_clock=[&]{if(wire.clocks==bad.first*2+2) revoked=!session.current(old,wire.time);};
        const auto result=session.read(context());
        check(revoked && result.evidence.fault==gc::Fault::values && wire.calls.size()==bad.first,
              "received bad value masked by previous report");
    }
}
void concurrent_refresh() {
    // Real cross-thread publication queries, deterministic transfer barriers.
    for(bool cancel:{false,true}) {
        gc::BusEpoch epoch;Wire wire;gc::OwnedSession session(profile(),context(),wire,epoch,1);
        const auto old=warm(session,wire);wire.calls.clear();wire.time=4300000;
        std::mutex mutex;std::condition_variable condition;
        unsigned arrived=0,released=0;
        wire.during_transfer=[&] {
            std::unique_lock<std::mutex> lock(mutex);++arrived;condition.notify_one();
            condition.wait(lock,[&]{return released==arrived;});
        };
        gc::Publication result;
        std::thread owner([&]{result=session.read(context());});
        const unsigned count=cancel ? 31:52;
        for(unsigned n=1;n<=count;++n) {
            std::unique_lock<std::mutex> lock(mutex);
            condition.wait(lock,[&]{return arrived==n;});
            check(session.current(old,wire.time),"concurrent healthy refresh withdrew report");
            if(cancel && n==count) {
                session.retire();
                check(!session.current(old,wire.time),"cross-task cancellation waited for sensor task");
            }
            released=n;condition.notify_one();
        }
        owner.join();
        check(!session.current(old,wire.time),"superseded or retired serial survived");
        check(session.current(result,wire.time)==!cancel,"late completion defeated cancellation");
    }
}
} // namespace
int main() {
    mapping_and_wire_failure();publication_and_park();ownership_and_faults();atomic_epoch();
    refresh_lifetime();immediate_faults();received_word_faults();concurrent_refresh();
    std::cout<<"owned gauge bus mapping, endian, timeout, epoch, task and publication fences passed\n";
}
