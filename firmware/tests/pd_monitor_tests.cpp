#include "smart_blinds/pd_monitor.hpp"
#include <algorithm>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <vector>
using namespace smart_blinds::pd;
namespace {
void check(bool v,const char* why) { if(!v) { std::cerr<<why<<'\n';std::exit(1); } }
FactoryRecord record() {
    FactoryRecord r;r.board=1;r.boot=2;r.qualification=3;
    r.exact_nvm_verified=r.above_5v_gate_verified=r.shared_bus_verified=r.req_src_current_zero=r.source_path_verified=true;
    r.device_id=0x25;r.live_pdos={0x04019096,0x0002D0FA,0x0004B0FA};return r;
}
// Independent ST register/event model, not built from production constants.
struct Chip:Bus {
    std::array<std::uint8_t,256> r{};
    std::uint64_t now=1000;
    unsigned reads=0,writes=0,fail_at=0,payload=0;
    bool ignore_mask=false,forbid_write=false;
    std::function<void(unsigned,std::uint8_t)> hook;
    Chip() { reset(); }
    void word(unsigned address,std::uint32_t value) { for(unsigned i=0;i<4;++i) r[address+i]=value>>(8*i); }
    void reset() {
        r.fill(0);r[0x2F]=0x25;r[0x0C]=0xFB;r[0x12]=0x10;r[0x13]=0x40;r[0x0F]=0x0F;
        r[0x70]=3;word(0x85,0x04019096);word(0x89,0x0002D0FA);word(0x8D,0x0004B0FA);
    }
    void attach() {
        r[0x0E]=0x21;r[0x10]=0x0A;r[0x15]=2;r[0x29]=0x18;
        r[0x0D]|=1;r[0x0F]|=0x0E;r[0x16]|=4;
        word(0x91,0x2303E8FA); // source PDO2, USB/no-suspend flags, 2.5 A operating/max.
    }
    void detach() { r[0x0E]=0;r[0x10]=4;r[0x15]=0;r[0x29]=0x13;r[0x0D]|=1;r[0x0F]|=0x0E; }
    bool read(std::uint8_t pointer,std::uint8_t* bytes,std::size_t n) override {
        ++reads;++now;if(hook) hook(reads,pointer);
        if(reads==fail_at) return false;
        payload+=n;std::copy_n(r.data()+pointer,n,bytes);
        for(unsigned i=0;i<n;++i) {
            const auto p=pointer+i;
            if(p==0x0D || p==0x0F || p==0x12 || p==0x14 || p==0x16) r[p]=0;
        }
        return true;
    }
    bool alert_mask(std::uint8_t value) override {
        check(!forbid_write,"unexpected mask write during status operation");++writes;
        if(!ignore_mask) r[0x0C]=value;
        return true;
    }
    std::uint64_t now_ms() const override { return now; }
};
struct Fixture {
    Chip chip;Monitor monitor;
    explicit Fixture(bool approved=true):monitor(chip,approved?record():FactoryRecord{}) {
        const auto init=monitor.initialize(0);
        check(init.error==Error::none && init.history[2]==0x10 && init.history[1]==0x0F,
              "initial clear-on-read evidence lost");
        check(chip.r[0x0C]==0x89 && chip.writes==1,"mask setup/reserved bits incorrect");
        chip.forbid_write=true;chip.attach();
    }
    Observation ready() {
        check(monitor.poll().state==State::negotiating,"attach event qualified immediately");
        chip.now+=100;check(monitor.poll().state==State::negotiating,"quiet interval bypassed");
        chip.now+=500;return monitor.poll();
    }
};
void qualification_and_age() {
    Fixture f;const auto a=f.ready();
    check(a.state==State::ready && a.current_ma==2500 && f.monitor.authority(a,a.finished_ms),"current not qualified");
    check(f.monitor.authority(a,a.started_ms+250) && !f.monitor.authority(a,a.started_ms+251),"age boundary changed");
    check(!f.monitor.current(a,a.finished_ms-1),"future observation current");
    const auto newer=f.monitor.poll();
    check(!f.monitor.current(a,newer.finished_ms) && f.monitor.current(newer,newer.finished_ms),"arbitrary old serial accepted");
    Fixture empty(false);auto unapproved=empty.ready();
    check(unapproved.state==State::unapproved,"missing factory record authorized source");
    unapproved.state=State::ready;unapproved.current_ma=2500;
    check(!empty.monitor.authority(unapproved,unapproved.finished_ms),"caller relabeled unapproved report");
    auto restamped=newer;restamped.started_ms=restamped.finished_ms;
    check(!f.monitor.current(restamped,restamped.finished_ms),"caller renewed source timestamp");
    Fixture source_position;source_position.ready();source_position.chip.word(0x91,0x7303E8FA);
    check(source_position.monitor.poll().state==State::ready,"source PDO7 confused with sink PDO index");
    for(auto bad:{0x2303E8F9U,0x2303E4FAU,0x2703E8FAU,0x2B03E8FAU,0xA303E8FAU,0x0343E8FAU}) {
        Fixture d;d.ready();d.chip.word(0x91,bad);
        check(d.monitor.poll().state!=State::ready,"bad RDO/current accepted");
    }
    for(auto pe:{0,0x17,0x19,0x3A,0x3B,0x40}) {
        Fixture state;state.ready();state.chip.r[0x29]=pe;
        check(state.monitor.poll().state!=State::ready,"non-ready PE accepted");
    }
    for(auto port:{0x01,0x61,0x29,0x25}) {
        Fixture state;state.ready();state.chip.r[0x0E]=port;
        check(state.monitor.poll().state!=State::ready,"wrong sink role accepted");
    }
    Fixture detached;detached.ready();detached.chip.detach();
    const auto b=detached.monitor.poll();check(b.state==State::detached && !b.current_ma,"detached retained authority");
}
void stop_classification() {
    Fixture f;const auto prior=f.ready();
    f.chip.r[0x16]=4;const auto message=f.monitor.poll();
    check(message.state==State::negotiating && !discontinuity(prior,message),
          "ordinary PD message was classified as source discontinuity");
    f.chip.r[0x16]=1;const auto reset=f.monitor.poll();
    check(discontinuity(message,reset),"hard reset did not request source STOP classification");
    Fixture d;const auto attached=d.ready();d.chip.detach();
    check(discontinuity(attached,d.monitor.poll()),"detach did not request source STOP classification");
}
void reset_events_and_policy() {
    for(auto address:{0x14,0x16}) {
        Fixture f;const auto before=f.ready();f.chip.r[address]=address==0x14?0x0E:1;
        const auto a=f.monitor.poll();check(a.state==State::negotiating && a.epoch!=before.epoch,"reset did not revoke");
        check(!f.monitor.current(before,a.finished_ms),"old reset epoch current");
        f.chip.now+=100;f.monitor.poll();f.chip.now+=500;
        check(f.monitor.poll().state==State::ready,"fresh reset recovery failed");
    }
    Fixture por;por.ready();por.chip.reset();por.chip.attach();
    check(por.monitor.poll().error==Error::mask,"POR mask reset not detected");
    por.chip.r[0x0C]=0x89;
    check(por.monitor.initialize(0).error==Error::mask,"unexpected reset silently repaired");
    for(unsigned address:{0x70,0x85,0x86,0x87,0x88,0x89,0x8C,0x8D,0x90}) {
        Fixture f;f.ready();f.chip.r[address]^=1;
        check(f.monitor.poll().error==Error::policy,"live approved PDO drift ignored");
    }
    Fixture changed;changed.ready();changed.chip.reads=0;
    changed.chip.hook=[&](unsigned n,std::uint8_t) { if(n==8) changed.chip.detach(); };
    check(changed.monitor.poll().state!=State::ready,"mid-capture detach qualified");
    Fixture late_pe;late_pe.ready();late_pe.chip.reads=0;
    late_pe.chip.hook=[&](unsigned n,std::uint8_t) { if(n==12) late_pe.chip.r[0x29]=0x17; };
    check(late_pe.monitor.poll().state==State::negotiating,"post-RDO PE transition accepted");
    Fixture chatter;chatter.ready();chatter.chip.reads=0;
    chatter.chip.hook=[&](unsigned n,std::uint8_t) { if(n==7) { chatter.chip.detach();chatter.chip.attach(); } };
    check(chatter.monitor.poll().state==State::negotiating,"equal final state masked chatter");
    Fixture fault;fault.ready();fault.chip.r[0x12]=0x20;
    const auto f=fault.monitor.poll();
    check(f.error==Error::fault && f.history[2]==0x20 && fault.chip.r[0x12]==0,"fault evidence lost on clear");
    fault.chip.now=0;const auto again=fault.monitor.poll();
    check(again.error==Error::fault && again.history==f.history && again.started_ms==f.started_ms &&
          again.serial==f.serial,"later clock erased first cause/history");
}
void owner_replacement_mask() {
    Chip c;Monitor first(c,record());check(first.initialize(0).error==Error::none,"first setup failed");
    const auto mask=first.configured_mask();const auto writes=c.writes;c.forbid_write=true;
    Monitor next(c,record());check(next.initialize(0,mask).error==Error::none && c.writes==writes,
                                 "healthy owner replacement wrote configuration");
    c.reset();Monitor reset(c,record());
    check(reset.initialize(0,mask).error==Error::mask && c.writes==writes,
          "POR between owners repaired by mask setup");
}
void failures() {
    Fixture good;good.ready();good.chip.reads=0;good.monitor.poll();const auto count=good.chip.reads;
    for(unsigned fail=1;fail<=count;++fail) {
        Fixture f;f.ready();f.chip.reads=0;f.chip.fail_at=fail;
        const auto a=f.monitor.poll();check(a.error==Error::bus && !a.current_ma,"read failure retained authority");
        f.chip.fail_at=0;check(f.monitor.poll().error==Error::bus,"later success repaired error");
    }
    Fixture slow;slow.ready();slow.chip.hook=[&](unsigned,std::uint8_t) { slow.chip.now+=101; };
    check(slow.monitor.poll().error==Error::timeout,"blocked status bypassed operation bound");
    Fixture clock;clock.ready();clock.chip.now=1;
    check(clock.monitor.poll().error==Error::clock,"clock rollback accepted");
    Chip hot;hot.r[0x12]=0x20;Monitor m(hot,record());
    check(m.initialize(0).error==Error::fault && hot.writes==0,"setup write cleared prior fault");
    Chip ignored;ignored.ignore_mask=true;Monitor n(ignored,record());
    check(n.initialize(0).error==Error::mask,"unverified interrupt setup accepted");
    Chip early;Monitor e(early,record());
    check(e.initialize(early.now-29).error==Error::uninitialized && early.writes==0,"power stabilization bypassed");
}
}
int main() { qualification_and_age();stop_classification();reset_events_and_policy();owner_replacement_mask();failures();Fixture meter;meter.ready();meter.chip.reads=meter.chip.payload=0;meter.monitor.poll();
std::cout<<"PD poll: "<<meter.chip.reads<<" reads, "<<meter.chip.payload<<" payload bytes\n";
std::cout<<"PD status policy: all scenarios passed\n"; }
