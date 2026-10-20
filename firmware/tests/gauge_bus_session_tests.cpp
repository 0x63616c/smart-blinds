#include "smart_blinds/gauge_bus_session.hpp"
#include <cstdlib>
#include <functional>
#include <iostream>
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
        bytes={static_cast<std::uint8_t>(words[reg]),static_cast<std::uint8_t>(words[reg]>>8)};
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
} // namespace
int main() {
    mapping_and_wire_failure();publication_and_park();ownership_and_faults();atomic_epoch();
    std::cout<<"owned gauge bus mapping, endian, timeout, epoch, task and publication fences passed\n";
}
