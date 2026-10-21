#include "motion_session_fixture.hpp"
using namespace blinds;
using namespace session_test;
namespace {
void receive_after_cycle_clock() {
    Fixture f;f.reference();
    const auto captured=f.io.now;
    std::uint64_t received=0;
    f.io.after_clock_sample=[&] {
        f.io.now+=10;received=f.io.now;f.queue(f.prepare());
    };
    const auto first=f.cycle();
    std::cout<<"receive interleave: captured="<<captured<<" received="<<received
             <<" observed="<<first.observed_us<<" message="<<first.last_message
             <<" phase="<<static_cast<unsigned>(first.phase)<<" result="<<static_cast<unsigned>(first.result)
             <<" io="<<f.io.calls<<std::endl;
    check(received==captured+10 && first.observed_us==captured,"producer seam did not cross clock observation");
    check(first.last_message==0 && f.inbox.pending() && f.io.calls==0,
          "post-clock command was consumed against an earlier cycle timestamp");
    f.refresh();const auto second=f.cycle();
    check(second.last_message==1 && second.phase==MotionSession::Phase::preparing &&
          second.result==MotionSession::Result::accepted && !f.inbox.pending(),
          "fresh post-clock arrival was not admitted on the next bounded cycle");
}
void inbox_clock_negative_controls() {
    // A physically future receipt is still invalid after the completed copy.
    Fixture future;future.reference();const auto future_request=future.prepare();future.queue(future_request,future.io.now+1);
    auto s=future.cycle();
    check(s.result==MotionSession::Result::invalid && s.last_message==1 && future.io.calls==0,
          "truly future receipt authorized motion or lost replay floor");
    check(!future.inbox.push({future_request,1,future.io.now,true}),"rejected future request replay floor reset");
    for(const auto age:{40000U,40001U}) {
        Fixture f;f.reference();auto r=f.prepare();r.sent_us-=age;f.queue(r,f.io.now-age);
        s=f.cycle();
        if(age==40000) check(s.result==MotionSession::Result::accepted && s.phase==MotionSession::Phase::preparing,
                            "exact queue-age boundary was narrowed");
        else check(s.result==MotionSession::Result::invalid && f.io.calls==0,
                   "old queue receipt authorized motion");
    }
    for(bool ahead:{false,true}) {
        Fixture f;f.reference();auto r=f.prepare();
        r.sent_us=ahead ? r.sent_us+20000 : r.sent_us-100001;f.queue(r);
        s=f.cycle();check(s.result==MotionSession::Result::stale && f.io.calls==0,
                         "future or old source timestamp gained authority");
    }
    Fixture backwards;backwards.reference();backwards.queue(backwards.prepare());
    backwards.io.reversed_read=backwards.io.clock_reads+1;s=backwards.cycle();
    check(s.result==MotionSession::Result::clock && s.phase==MotionSession::Phase::fault && backwards.io.calls==0,
          "reversed cycle clock authorized queued command");
    backwards.io.reversed_read=0;backwards.cycle();
    check(backwards.session.status().result==MotionSession::Result::clock,"later clock repaired first fault");
}
void snapshot_stop_and_queue_boundaries() {
    Fixture stopped;stopped.reference();stopped.queue(stopped.prepare());
    stopped.io.after_clock_sample=[&] {stopped.io.now+=10;stopped.queue(stopped.simple(wire::Kind::stop));};
    const auto s=stopped.cycle();
    check(s.result==MotionSession::Result::stopped && s.last_message==0 && stopped.io.calls==0 &&
          !stopped.inbox.pending(),"STOP arriving during time capture lost priority over copied prepare");
    // Physical STOP and explicit OFF holds cannot consume ordinary work early.
    Fixture raw;raw.reference();raw.queue(raw.prepare());raw.input.fast.stop_pressed=true;
    check(raw.cycle().result==MotionSession::Result::stopped && raw.io.calls==0 && !raw.inbox.pending(),
          "raw STOP did not drain ordinary work before execution");
    Fixture held;held.reference();held.queue(held.prepare());
    const auto h=held.session.cycle(held.inbox,held.input,{},true);
    check(h.last_message==0 && held.inbox.pending() && held.io.calls==0,"OFF hold consumed ordinary request");
    // Several arrivals still use the fixed four-slot queue and one copy/cycle.
    Fixture backlog;
    for(unsigned i=0;i<4;++i) backlog.queue(backlog.prepare(i+1));
    const auto overflow=backlog.prepare(5);
    check(!backlog.inbox.push({overflow,1,backlog.io.now,true}),"queue bound expanded");
    for(unsigned i=1;i<=4;++i) {
        const auto b=backlog.cycle();
        check(b.last_message==i && b.result==MotionSession::Result::reference && backlog.io.calls==0,
              "cycle consumed more than one queued ordinary request");
    }
    check(!backlog.inbox.pending(),"bounded backlog did not drain");
}
void interleaved_lease_keeps_source_expiry_and_cadence() {
    Fixture f;f.moving();
    // Make the deliberately 80 ms old source newer than the preceding lease.
    for(unsigned i=0;i<10;++i) f.tick();
    f.io.now+=10000;f.refresh();
    const auto prior=f.session.status().last_message;
    std::uint64_t received=0;
    f.io.after_clock_sample=[&] {
        f.io.now+=10;received=f.io.now;auto r=f.simple(wire::Kind::lease);r.sent_us-=80000;f.queue(r);
    };
    auto s=f.cycle();
    check(s.last_message==prior && f.inbox.pending() && s.phase==MotionSession::Phase::moving,
          "interleaved lease consumed against old cycle time");
    s=f.tick();check(s.last_message==f.message && s.result==MotionSession::Result::accepted,
                    "fresh interleaved lease rejected on next cycle");
    while(f.session.status().phase!=MotionSession::Phase::fault && f.io.now-received<300000) f.tick();
    check(f.session.status().phase==MotionSession::Phase::fault && f.io.now-received<230000,
          "snapshot order extended original source lease expiry");f.off();
    Fixture gap;gap.moving();gap.io.now+=21000;gap.refresh();gap.queue(gap.simple(wire::Kind::lease));
    check(gap.cycle().phase==MotionSession::Phase::fault,"queued lease hid missed control cadence");gap.off();
}
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
    receive_after_cycle_clock();
    inbox_clock_negative_controls();snapshot_stop_and_queue_boundaries();interleaved_lease_keeps_source_expiry_and_cadence();
    if(std::getenv("SB_TEST_INBOX_CLOCK_ONLY")) return 0;
    qualification(); complete_motion(); terminal_evidence(); stop_priority(); command_rejection(); fault_boundaries(); source_time_and_long_window(); setup_failure();
    std::cout<<"motion session qualification, scheduled lifecycle, source freshness, STOP/settle and fault boundaries passed\n";
}
