#include "smart_blinds/motion_session.hpp"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <functional>
#include <vector>
#include <string>
using namespace blinds;
namespace {
void check(bool ok,const char* message) { if(!ok) { std::cerr<<message<<'\n'; std::exit(1); } }
struct Io : MotionIo,CounterOrigin {
    std::uint64_t now=2000000,epoch=0;
    unsigned calls=0,pulses=0,fail_at=0,slow_at=0;
    bool request_high=true,encoder=false,counter=false,awake=false;
    double count=500,origin=500,duty=0;
    std::vector<std::string> log;
    std::uint64_t now_us() const override { return now; }
    bool action(const char* name) { log.emplace_back(name); ++calls; now+=calls==slow_at ? 101 : 1; return calls!=fail_at; }
    bool request_n(bool high) override { if(!action(high ? "off":"arm")) return false; request_high=high; return true; }
    bool coast() override { if(!action("coast")) return false; duty=0; return true; }
    bool wdi_high() override { return action("high"); }
    bool charge_off() override { return action("charge-off"); }
    bool encoder_power(bool on) override { if(!action(on ? "encoder-on":"encoder-off")) return false; encoder=on; return true; }
    bool counter_start(std::uint64_t value) override {
        check(request_high && awake && encoder && value==epoch,"counter started without safe setup");
        if(!action("counter-start")) return false;
        counter=true; count=origin; return true;
    }
    bool counter_stop() override { if(!action("counter-stop")) return false; counter=false; return true; }
    bool awake_lock(bool on) override { if(!action(on ? "awake-on":"awake-off")) return false; awake=on; return true; }
    bool pwm(int direction,double value) override {
        check(!request_high && pulses && counter && encoder && awake && value>0 && value<=.5,"unprepared PWM");
        if(!action("pwm")) return false;
        duty=direction*value; return true;
    }
    bool heartbeat_pulse() override {
        check(!request_high && counter && awake && encoder,"unprepared heartbeat");
        if(!action("pulse")) return false;
        ++pulses; return true;
    }
    bool set_counter_origin(std::uint64_t value,double base) override {
        check(!counter && request_high && duty==0,"counter origin changed during motion");
        if(!action("origin")) return false;
        epoch=value; origin=base; return true;
    }
};
Calibration calibration() {
    Calibration c; const Knot k[]={{0,0},{1000,100},{3000,200}};
    check(c.assign(k,3,7),"calibration fixture invalid"); return c;
}
BenchMotionProfile profile() {
    BenchMotionProfile p; p.bench_qualified=p.holding_qualified=true; p.qualification_id=123;
    p.feedforward=.00025; return p;
}
struct Fixture {
    Io io;
    MotionSession session;
    MotionSession::Inbox inbox{99};
    SessionInput input;
    std::uint64_t sample=0,message=0,probe=1,offset=500000;
    explicit Fixture(BenchMotionProfile p=profile(),Calibration c=calibration()) : session(io,io,c,{},p,99) {
        check(inbox.connected(1),"session connection failed"); refresh();
    }
    void refresh() {
        input.fast={true,io.counter,false,false,++sample,io.now,io.epoch,io.count,.1};
        input.power={true,io.now,77,11.1}; input.attached=input.radio_awake=true;
        input.clock_probe=probe; input.clock_connection=inbox.connection();
        input.clock=smart_blinds::ClockBounds::estimate({io.now-offset-2000,io.now-1000,io.now-900,io.now-offset+100},
            {1000,2,true});
        check(input.clock.has_value(),"clock fixture invalid");
    }
    void reference() { check(session.establish_reference({true,99,1,io.now,77,7,500}),"physical reference rejected"); }
    wire::Request prepare(std::uint64_t command=1,double target=150) {
        return {wire::Kind::prepare,7,99,++message,command,probe,io.now-offset,
            io.now-offset+300000,50000,static_cast<std::int64_t>(target*1000),20000,40000};
    }
    wire::Request simple(wire::Kind kind,std::uint64_t command=1) {
        return {kind,7,99,++message,command,probe,io.now-offset,0,0,0,0,0};
    }
    void queue(wire::Request r,std::uint64_t received=0) {
        check(inbox.push({r,inbox.connection(),received ? received : io.now,true}),"frame did not queue");
    }
    MotionSession::Status cycle() { return session.cycle(inbox,input); }
    MotionSession::Status tick(const std::function<void(SessionInput&)>& mutate={}) {
        if(io.counter) io.count+=io.duty*4000*.01; // Synthetic plant only.
        io.now+=10000; refresh(); if(mutate) mutate(input); return cycle();
    }
    void ready() {
        reference(); queue(prepare());
        check(cycle().phase==MotionSession::Phase::preparing,"prepare failed");
        check(tick().phase==MotionSession::Phase::preparing && io.counter,"counter did not warm");
        check(tick().phase==MotionSession::Phase::preparing && !io.request_high && io.duty==0 && !io.pulses,"arm incorrectly moved");
        check(tick().ready && io.duty==0 && io.pulses==1,"ready preceded first healthy heartbeat");
    }
    void commit() { queue(simple(wire::Kind::commit)); check(tick().phase==MotionSession::Phase::committed,"commit rejected"); }
    void moving() {
        ready(); commit();
        for(int i=0;i<40 && session.status().phase!=MotionSession::Phase::moving;++i) {
            if(i%10==0) queue(simple(wire::Kind::lease));
            tick();
        }
        check(session.status().phase==MotionSession::Phase::moving,"scheduled start never occurred");
        tick(); check(io.duty>0,"moving session applied no PWM");
    }
    void off() { check(io.request_high && io.duty==0 && !io.counter && !io.encoder && !io.awake,"resources not off"); }
};
void qualification() {
    Fixture disabled({});
    check(!disabled.session.establish_reference({true,99,1,disabled.io.now,77,7,500}),"default profile accepted reference");
    disabled.queue(disabled.prepare());
    check(disabled.cycle().result==MotionSession::Result::unqualified && disabled.io.calls==0,"default session touched I/O");
    for(int kind=0;kind<8;++kind) {
        Fixture f; PhysicalReference r{true,99,1,f.io.now,77,7,500};
        switch(kind) {
        case 0:r.independently_observed=false;break; case 1:r.boot=1;break; case 2:r.record=0;break;
        case 3:r.observed_us=f.io.now+1;break; case 4:r.observed_us-=100001;break; case 5:r.calibration=8;break;
        case 6:r.pack_binding=0;break; case 7:r.count=4000;break;
        }
        check(!f.session.establish_reference(r) && f.io.calls==0,"invalid physical reference accepted");
    }
    Fixture unknown; unknown.queue(unknown.prepare());
    check(unknown.cycle().result==MotionSession::Result::reference && unknown.io.calls==0,"unknown boot reference moved");
}
void complete_motion() {
    Fixture f; f.ready(); f.commit();
    bool moved=false,settling=false;
    for(int i=0;i<900 && f.session.status().phase!=MotionSession::Phase::idle;++i) {
        if(i%10==0 && f.session.status().phase!=MotionSession::Phase::settling) f.queue(f.simple(wire::Kind::lease));
        const auto s=f.tick();
        moved |= s.phase==MotionSession::Phase::moving;
        if(s.phase==MotionSession::Phase::settling) {
            settling=true; check(f.io.request_high && f.io.counter && f.io.duty==0,"settling lost encoder or drove motor");
        }
        if(s.phase==MotionSession::Phase::fault) {
            std::cerr<<"normal synthetic motion fault result="<<static_cast<int>(s.result)<<" count="<<f.io.count<<'\n';
            check(false,"normal synthetic trajectory faulted");
        }
    }
    auto s=f.session.status();
    check(moved && settling && s.phase==MotionSession::Phase::idle && s.reference_valid &&
        s.result==MotionSession::Result::finished && s.height_mm && std::abs(*s.height_mm-150)<1,"endpoint/final reference incorrect");
    f.off();
    auto old=f.prepare(); f.queue(old); f.tick();
    check(f.session.status().result==MotionSession::Result::finished && f.io.duty==0,"completed outcome lost to rejected replay");
    auto next=f.prepare(2,80); next.origin_um=static_cast<std::int64_t>(*s.height_mm*1000); f.queue(next);
    check(f.tick().phase==MotionSession::Phase::preparing,"fresh command after settle rejected");
    check(std::abs(f.io.origin-f.io.count)<.01,"next origin omitted final coasting count");
}
void terminal_evidence() {
    for(bool stop : {false,true}) {
        Fixture f; f.ready(); f.commit();
        for(int i=0;i<900 && f.session.status().phase!=MotionSession::Phase::settling;++i) {
            if(stop && i==40) f.queue(f.simple(wire::Kind::stop));
            else if(i%10==0) f.queue(f.simple(wire::Kind::lease));
            f.tick();
        }
        const auto outcome=stop ? MotionSession::Result::stopped : MotionSession::Result::finished;
        check(f.session.status().phase==MotionSession::Phase::settling,"no terminal settling fixture");
        f.queue(f.simple(wire::Kind::lease)); auto s=f.tick();
        check(s.result==outcome && s.last_message==f.message,"late lease erased terminal outcome or replay floor");
        auto next=f.prepare(2,80); next.origin_um=static_cast<std::int64_t>(*s.height_mm*1000);
        f.queue(next); s=f.tick();
        check(s.result==outcome && s.phase==MotionSession::Phase::settling && s.last_message==f.message,
            "prepare during settling replaced terminal evidence");
        check(!f.inbox.push({next,f.inbox.connection(),f.io.now,true}),"duplicate accepted after settling rejection");
        for(int i=0;i<20 && s.phase!=MotionSession::Phase::idle;++i) s=f.tick();
        check(s.phase==MotionSession::Phase::idle && s.result==outcome,"terminal outcome not retained into idle");
        f.queue(f.simple(wire::Kind::lease)); s=f.tick();
        check(s.result==outcome && s.last_message==f.message,"idle late lease erased terminal outcome");
        next=f.prepare(2,80); next.origin_um=static_cast<std::int64_t>(*s.height_mm*1000);
        f.queue(next); s=f.tick();
        check(s.phase==MotionSession::Phase::preparing && s.result==MotionSession::Result::accepted,
            "valid next job did not replace terminal evidence");
    }
    Fixture bad; bad.moving(); bad.queue(bad.simple(wire::Kind::stop)); bad.tick();
    bad.queue(bad.simple(wire::Kind::lease));
    const auto fault=bad.tick([](auto& in){in.power.ready=false;});
    check(fault.phase==MotionSession::Phase::fault && fault.result==MotionSession::Result::power,
        "terminal preservation masked a settling fault");
}
void stop_priority() {
    Fixture f; f.moving(); const auto pulses=f.io.pulses;
    for(int i=0;i<4;++i) f.queue(f.simple(wire::Kind::lease));
    f.queue(f.simple(wire::Kind::stop));
    auto s=f.tick(); check(s.phase==MotionSession::Phase::settling && f.io.request_high && f.io.duty==0,"STOP queued behind lease backlog");
    check(f.io.pulses==pulses,"STOP fed heartbeat");
    for(int i=0;i<5;++i) { f.io.count+=2; f.tick([](auto& in){in.fast.stop_pressed=true;}); }
    check(f.session.status().phase==MotionSession::Phase::settling,"coasting preserved count early");
    for(int i=0;i<12;++i) f.tick([](auto& in){in.fast.stop_pressed=true;});
    s=f.session.status(); check(s.phase==MotionSession::Phase::idle && s.reference_valid && s.result==MotionSession::Result::stopped,"held STOP failed quiet teardown");
    check(f.io.pulses==pulses && !f.inbox.pop(),"STOP replayed work/fed watchdog"); f.off();
    Fixture raw; raw.moving(); raw.queue(raw.simple(wire::Kind::commit));
    check(raw.tick([](auto& in){in.fast.stop_pressed=true;}).phase==MotionSession::Phase::settling && raw.io.request_high,"raw button did not override commit");
}
void command_rejection() {
    for(int kind=0;kind<12;++kind) {
        Fixture f; f.reference(); auto r=f.prepare();
        switch(kind) {
        case 0:r.sent_us-=110000;break; case 1:r.sent_us+=20000;break; case 2:r.start_us=r.sent_us+20000;break;
        case 3:r.probe=2;break; case 4:r.target_um=201000;break; case 5:r.origin_um=70000;break;
        case 6:r.speed_um_s=1;break; case 7:r.calibration=8;break; case 8:f.input.power.ready=false;break;
        case 9:f.input.clock_connection=2;break; case 10:f.input.radio_awake=false;break;
        case 11:f.input.clock=smart_blinds::ClockBounds::estimate({1,1001,1101,2101});break;
        }
        f.queue(r); auto s=f.cycle();
        check(!s.awake_required && f.io.calls==0 && s.result!=MotionSession::Result::accepted,"invalid preparation touched I/O");
    }
    Fixture stale; stale.reference(); stale.queue(stale.prepare(),stale.io.now-40001);
    check(stale.cycle().result==MotionSession::Result::invalid && stale.io.calls==0,"stale queue authorized motion");
    Fixture early; early.reference(); early.queue(early.prepare()); early.cycle();
    early.queue(early.simple(wire::Kind::commit)); early.tick();
    check(early.session.status().phase==MotionSession::Phase::preparing,"commit before actual readiness accepted");
}
void fault_boundaries() {
    for(int kind=0;kind<15;++kind) {
        Fixture f; f.moving(); const auto pulses=f.io.pulses;
        f.tick([&](auto& in){
            switch(kind) {
            case 0:in.power.ready=false;break; case 1:in.power.pack_binding=78;break;
            case 2:in.power.observed_us-=250001;break; case 3:in.fast.valid=false;break;
            case 4:in.fast.driver_fault=true;break; case 5:in.fast.current_a=3;break;
            case 6:in.fast.encoder_epoch=2;break; case 7:in.fast.sampled_us-=10001;break;
            case 8:in.fast.count_valid=false;break; case 9:in.attached=false;break;
            case 10:in.radio_awake=false;break; case 11:in.clock.reset();break;
            case 12:in.clock_connection=2;break; case 13:in.manual_intervention=true;break;
            case 14:in.clock=smart_blinds::ClockBounds::estimate({f.io.now-520000,f.io.now-1000,f.io.now-900,f.io.now-517900},{1000,2,true});break;
            }
        });
        const auto s=f.session.status();
        check(s.phase==MotionSession::Phase::fault && !s.reference_valid && f.io.pulses==pulses,"bad live evidence did not inhibit without feeding");
        f.off();
        check(!f.session.establish_reference({true,99,2,f.io.now,77,7,500}),"fault implicitly cleared by reference");
    }
    Fixture detach; detach.moving(); detach.inbox.disconnected();
    check(detach.tick().phase==MotionSession::Phase::fault,"DTLS disconnect retained moving session"); detach.off();
    const auto fault_result=detach.session.status().result;
    check(detach.inbox.connected(2),"recovery connection failed"); detach.queue(detach.simple(wire::Kind::stop));
    check(detach.tick().result==fault_result && detach.session.status().phase==MotionSession::Phase::fault,
        "STOP erased latched fault diagnostic");
    Fixture reconnect; reconnect.moving(); check(reconnect.inbox.connected(2),"new generation failed");
    check(reconnect.tick().phase==MotionSession::Phase::fault,"DTLS reconnect restored motion"); reconnect.off();
    Fixture expiry; expiry.moving();
    for(int i=0;i<35 && expiry.session.status().phase!=MotionSession::Phase::fault;++i) expiry.tick();
    check(expiry.session.status().phase==MotionSession::Phase::fault,"lease never expired"); expiry.off();
    Fixture no_commit; no_commit.ready();
    for(int i=0;i<40 && no_commit.session.status().phase!=MotionSession::Phase::fault;++i) {
        if(i%10==0) no_commit.queue(no_commit.simple(wire::Kind::lease));
        no_commit.tick();
    }
    check(no_commit.session.status().phase==MotionSession::Phase::fault && no_commit.io.duty==0,"missed commit moved"); no_commit.off();
}
void source_time_and_long_window() {
    Fixture delayed; delayed.ready(); delayed.commit();
    for(int i=0;i<10;++i) delayed.tick();
    auto r=delayed.simple(wire::Kind::lease); r.sent_us-=80000; delayed.queue(r);
    check(delayed.tick().result==MotionSession::Result::accepted,"fresh delayed source lease rejected");
    const auto received=delayed.io.now;
    while(delayed.session.status().phase!=MotionSession::Phase::fault && delayed.io.now-received<300000) delayed.tick();
    check(delayed.io.now-received<230000,"receive time extended an 80 ms old lease"); delayed.off();
    Fixture stale_clock; stale_clock.moving();
    const auto old=stale_clock.input.clock;
    for(int i=0;i<70 && stale_clock.session.status().phase!=MotionSession::Phase::fault;++i) {
        if(i%10==0) stale_clock.queue(stale_clock.simple(wire::Kind::lease));
        stale_clock.tick([&](auto& in){in.clock=old;});
    }
    check(stale_clock.session.status().phase==MotionSession::Phase::fault &&
        stale_clock.session.status().result==MotionSession::Result::clock,"clock evidence lived indefinitely"); stale_clock.off();
    Calibration tall; const Knot knots[]={{0,0},{1000,100},{61000,3100}};
    check(tall.assign(knots,3,7),"tall fixture invalid");
    Fixture long_move(profile(),tall); long_move.reference(); long_move.queue(long_move.prepare(1,3000)); long_move.cycle();
    long_move.tick(); long_move.tick(); check(long_move.tick().ready,"long move not prepared"); long_move.commit();
    const auto began=long_move.io.now;
    for(int i=0;i<1600;++i) {
        if(i%10==0) long_move.queue(long_move.simple(wire::Kind::lease));
        auto s=long_move.tick();
        check(s.phase!=MotionSession::Phase::fault && s.awake_required,"healthy long session lost bounded awake hold");
    }
    check(long_move.io.now-began>15000000 && long_move.session.status().phase==MotionSession::Phase::moving,
        "motion incorrectly inherited 10-second radio-only wake window");
    long_move.tick([](auto& in){in.fast.stop_pressed=true;});
    for(int i=0;i<12;++i) long_move.tick();
    long_move.off();
    Fixture too_slow(profile(),tall); too_slow.reference(); auto slow=too_slow.prepare(1,3000); slow.speed_um_s=1000;
    too_slow.queue(slow); check(too_slow.cycle().result==MotionSession::Result::deadline && !too_slow.io.calls,
        "remote trajectory bypassed four-minute hard session ceiling");
}
void setup_failure() {
    for(int kind=0;kind<2;++kind) {
        Fixture f; f.reference(); if(kind) f.io.slow_at=1; else f.io.fail_at=1;
        f.queue(f.prepare());
        check(f.cycle().phase==MotionSession::Phase::fault && f.io.duty==0,"origin failure not latched");
    }
    Fixture gap; gap.moving(); gap.io.now+=21000; gap.refresh();
    check(gap.cycle().phase==MotionSession::Phase::fault,"missed control deadline caught up"); gap.off();
}
}
int main() {
    qualification(); complete_motion(); terminal_evidence(); stop_priority(); command_rejection(); fault_boundaries(); source_time_and_long_window(); setup_failure();
    std::cout<<"motion session qualification, scheduled lifecycle, source freshness, STOP/settle and fault boundaries passed\n";
}
