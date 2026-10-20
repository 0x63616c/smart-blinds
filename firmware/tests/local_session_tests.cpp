#include "motion_session_fixture.hpp"
#include <limits>
using namespace blinds;
using namespace session_test;
namespace {
using Owner=MotionSession::Owner;
using Phase=MotionSession::Phase;
using Result=MotionSession::Result;
LocalIntent intent(const Fixture& f,std::uint64_t gesture=1,LocalIntent::Endpoint endpoint=LocalIntent::Endpoint::up) {
    return {endpoint,99,gesture,1,f.io.now,f.io.now+40000,7};
}
void offline(SessionInput& in) {
    in.attached=in.radio_awake=false; in.clock.reset(); in.clock_probe=in.clock_connection=0;
}
MotionSession::Status tick(Fixture& f,std::optional<LocalIntent> local={}) { return f.tick(offline,local); }
void local_start(Fixture& f,std::uint64_t gesture=1,LocalIntent::Endpoint endpoint=LocalIntent::Endpoint::up) {
    f.refresh(); offline(f.input);
    check(f.cycle(intent(f,gesture,endpoint)).phase==Phase::preparing,"local admission failed");
    const auto command=f.session.status().command;
    check(command==0 && !f.session.status().ready,"local operation impersonated remote command/readiness");
    tick(f); check(f.io.counter && f.io.request_high,"local warmup failed");
    tick(f); check(!f.io.request_high && f.io.duty==0,"local arm moved before heartbeat");
    tick(f); check(f.io.pulses && f.io.duty==0 && !f.session.status().ready,"local heartbeat did not coast");
    check(tick(f).phase==Phase::moving,"local trajectory did not begin after hardware arming");
    tick(f);
}
void settled(Fixture& f) {
    for(unsigned i=0;i<20 && f.session.status().phase!=Phase::idle;++i) tick(f);
    check(f.session.status().phase==Phase::idle && f.session.status().reference_valid,"quiet OFF did not retain reference");
    check(f.session.ownership().owner==Owner::none,"terminal owner not released");
    f.off();
}
void stop(Fixture& f) {
    f.tick([](auto& in){offline(in);in.fast.stop_pressed=true;});
    check(f.session.status().phase==Phase::settling,"local STOP did not settle");
    settled(f);
}
void remote_ready(Fixture& f,std::uint64_t command) {
    ++f.io.now; // A newly received command is strictly after any OFF handoff.
    f.refresh();
    auto r=f.prepare(command,120);
    r.origin_um=static_cast<std::int64_t>(*f.session.status().height_mm*1000);
    f.queue(r);
    check(f.cycle().phase==Phase::preparing,"remote admission after handoff failed");
    f.tick(); f.tick();
    check(f.tick().ready,"remote handoff never became ready");
}
void full_local_trajectory() {
    for(auto endpoint:{LocalIntent::Endpoint::up,LocalIntent::Endpoint::down}) {
        Fixture f; f.reference(); f.inbox.disconnected();
        local_start(f,1,endpoint);
        check(f.session.ownership().owner==Owner::local && f.io.duty*(endpoint==LocalIntent::Endpoint::up ? 1 : -1)>0,
              "local endpoint polarity/ownership wrong");
        bool saw_settling=false;
        for(unsigned i=0;i<1000 && f.session.status().phase!=Phase::idle;++i) {
            const auto s=tick(f);
            if(s.phase==Phase::fault) {
                std::cerr<<"local trajectory fault result="<<static_cast<int>(s.result)
                    <<" reason="<<name(s.controller_reason)<<" count="<<f.io.count<<'\n';
            }
            check(s.phase!=Phase::fault,"local synthetic plant faulted");
            if(s.phase==Phase::settling) {
                saw_settling=true;
                check(f.io.request_high && f.io.duty==0 && f.io.counter && f.io.encoder,"local settling drove or dropped count");
            }
        }
        const auto s=f.session.status(); const auto o=f.session.ownership();
        check(s.phase==Phase::idle && saw_settling && s.result==Result::finished && s.command==0 &&
              o.local_result==Result::finished && o.last_owner==Owner::local && o.execution_epoch==1 &&
              s.height_mm && std::abs(*s.height_mm-(endpoint==LocalIntent::Endpoint::up ? 200 : 0))<1,
              "local final physical height/outcome missing");
        f.off();
    }
    for(auto endpoint:{LocalIntent::Endpoint::up,LocalIntent::Endpoint::down}) {
        Fixture f;
        const auto height=endpoint==LocalIntent::Endpoint::up ? 199.5 : .5;
        const auto count=*calibration().count_at(height);
        f.io.count=count;
        check(f.session.establish_reference({true,99,1,f.io.now,77,7,count}),"endpoint reference fixture");
        const auto s=f.cycle(intent(f,1,endpoint));
        check(s.phase==Phase::idle && s.result==Result::finished && s.height_mm==height &&
              f.io.log==std::vector<std::string>{"parked"} && f.session.ownership().execution_epoch==0 &&
              f.session.ownership().owner==Owner::none && f.session.ownership().local_result==Result::finished,
              "already-satisfied endpoint armed or invented a coordinate");
        f.off();
    }
    for(bool upper:{false,true}) {
        Fixture f; f.reference(); local_start(f);
        f.tick([&](auto& in){offline(in);in.fast.count=upper ? 3000.01 : -.01;});
        check(f.session.status().phase==Phase::fault && !f.session.status().reference_valid,
              "local endpoint tolerance masked out-of-range count");
        f.off();
    }
}
void execution_identity_and_handoff() {
    ExecutionEpoch epoch(std::numeric_limits<std::uint64_t>::max()-1);
    check(epoch.take()==std::numeric_limits<std::uint64_t>::max() && !epoch.take() && !epoch.take() &&
          epoch.value()==std::numeric_limits<std::uint64_t>::max(),"internal epoch wrapped or recovered");
    Fixture f; f.ready();
    check(f.io.epoch==1,"first execution epoch wrong");
    // A local gesture during remote ownership is STOP, never immediate takeover.
    f.tick({},intent(f));
    check(f.session.status().phase==Phase::settling && f.session.ownership().owner==Owner::remote &&
          f.session.ownership().execution_epoch==1 && f.session.ownership().local_result==Result::stopped,
          "gesture took over remote before settling");
    settled(f);
    local_start(f,2);
    check(f.io.epoch==2,"local reused remote execution epoch");
    const auto remote_floor=f.session.status().last_message;
    auto prepare=f.prepare(2); f.queue(prepare);
    tick(f);
    check(f.session.ownership().owner==Owner::local && f.session.ownership().execution_epoch==2 &&
          f.session.status().last_message>remote_floor && !f.session.status().ready,"remote prepare took local ownership");
    stop(f);
    auto replay=f.prepare(1); replay.origin_um=static_cast<std::int64_t>(*f.session.status().height_mm*1000);
    f.refresh(); f.queue(replay); f.cycle();
    check(f.session.ownership().execution_epoch==2 && !f.session.status().awake_required,"local cleared remote command floor");
    remote_ready(f,2);
    check(f.io.epoch==3 && f.session.status().command==2,"remote sequence and execution epoch still coupled");
    stop(f);
    // Largest valid remote command ID does not exhaust the internal/local space.
    Fixture huge; huge.reference(); remote_ready(huge,std::numeric_limits<std::uint64_t>::max());
    check(huge.io.epoch==1 && huge.session.status().command==std::numeric_limits<std::uint64_t>::max(),"max remote ID leaked into epoch");
    stop(huge); local_start(huge);
    check(huge.io.epoch==2 && huge.session.status().command==0,"max remote ID prevented independent local move");
    stop(huge);
}
void failed_start_consumes_epoch() {
    // OFF readback, origin and every initial setup operation fail independently.
    for(unsigned failure=1;failure<=8;++failure) {
        Fixture f; f.reference(); f.io.fail_at=failure;
        auto s=f.cycle(intent(f));
        check(s.phase==Phase::fault && f.session.ownership().execution_epoch==1 &&
              !s.reference_valid && f.io.duty==0,"failed start did not consume epoch/fault");
        const auto used=f.session.ownership().execution_epoch;
        f.io.fail_at=0; tick(f,intent(f,2));
        check(f.session.status().phase==Phase::fault && f.session.ownership().execution_epoch==used,
              "failed start automatically repaired/reused epoch");
    }
    Fixture slow; slow.reference(); slow.io.slow_at=1;
    check(slow.cycle(intent(slow)).phase==Phase::fault && slow.session.ownership().execution_epoch==1,
          "slow parked readback admitted local execution");
    Fixture unexpected; unexpected.reference(); unexpected.io.request_high=false; unexpected.io.duty=.3;
    check(unexpected.cycle(intent(unexpected)).phase==Phase::fault,"unexpected initial ON was not latched");
    unexpected.off(); // Failed first readback must perform OFF writes, not just return false.
    Fixture reversed;
    check(reversed.session.establish_reference({true,99,1,reversed.io.now,77,7,2990}),"clock reversal endpoint reference");
    reversed.io.clock_reads=0; reversed.io.reversed_read=2;
    check(reversed.cycle(intent(reversed)).phase==Phase::fault &&
          reversed.session.executor_fault()==MotionExecutor::Fault::clock &&
          !reversed.session.status().reference_valid,"initial no-op ignored readback clock reversal");
    reversed.off();
}
void cold_or_stale_is_not_a_pending_tap() {
    for(unsigned kind=0;kind<6;++kind) {
        Fixture f; f.reference(); auto tap=intent(f);
        switch(kind) {
        case 0:f.input.power.ready=false;break;
        case 1:f.input.power.observed_us-=250001;break;
        case 2:f.input.power.pack_binding=78;break;
        case 3:f.input.fast.valid=false;break;
        case 4:f.input.fast.sampled_us-=10001;break;
        case 5:f.input.fast.current_a=3;break;
        }
        f.cycle(tap);
        check(f.session.ownership().local_result==Result::power && !f.io.calls &&
              f.session.ownership().execution_epoch==0,"cold/stale tap touched I/O");
        for(unsigned i=0;i<20;++i) tick(f);
        check(!f.io.calls && !f.session.status().awake_required,"cold tap executed after warmup");
        tap=intent(f); f.cycle(tap);
        check(f.session.ownership().local_result==Result::stale && !f.io.calls,"refused gesture replayed");
        local_start(f,2); stop(f);
    }
    for(unsigned kind=0;kind<9;++kind) {
        Fixture f; f.reference(); auto tap=intent(f);
        switch(kind) {
        case 0:tap.boot=100;break;
        case 1:tap.gesture=0;break;
        case 2:tap.reference=2;break;
        case 3:tap.calibration=8;break;
        case 4:tap.issued_us=f.io.now+1;break;
        case 5:tap.expires_us=f.io.now;break;
        case 6:tap.expires_us=tap.issued_us+100001;break;
        case 7:tap.issued_us-=40001;break;
        case 8:tap.endpoint=static_cast<LocalIntent::Endpoint>(99);break;
        }
        f.cycle(tap);
        check(!f.io.calls && f.session.ownership().local_result!=Result::accepted,"invalid local binding/time admitted");
        for(unsigned i=0;i<12;++i) tick(f);
        check(!f.io.calls,"invalid local intent became executable later");
    }
    Fixture unreferenced; unreferenced.cycle(intent(unreferenced));
    check(unreferenced.session.ownership().local_result==Result::reference && !unreferenced.io.calls,"unknown reference admitted local");
    Fixture unqualified({}); unqualified.cycle(intent(unqualified));
    check(unqualified.session.ownership().local_result==Result::unqualified && !unqualified.io.calls,"default profile admitted local");
}
void stops_conflicts_and_network_scope() {
    Fixture queued; queued.reference(); queued.queue(queued.prepare());
    queued.cycle(intent(queued));
    check(queued.session.ownership().owner==Owner::local && !queued.inbox.pop(),"older remote prepare survived local admission");
    for(unsigned i=0;i<4;++i) tick(queued);
    stop(queued); for(unsigned i=0;i<40;++i) tick(queued);
    check(queued.session.status().phase==Phase::idle,"discarded remote autoexecuted after local");
    Fixture local; local.reference(); local_start(local);
    const auto epoch=local.io.epoch;
    const auto pulses=local.io.pulses;
    local.inbox.disconnected(); tick(local);
    check(local.session.status().phase==Phase::moving && local.io.epoch==epoch,"network loss aborted healthy local authority");
    check(local.inbox.connected(2),"new remote generation refused");
    local.queue(local.simple(wire::Kind::stop)); tick(local);
    check(local.session.status().phase==Phase::settling && local.session.ownership().owner==Owner::local &&
          local.io.pulses>=pulses,"authenticated STOP did not remain OFF-only");
    settled(local);
    Fixture handoff; handoff.reference(); local_start(handoff);
    handoff.tick([](auto& in){in.fast.stop_pressed=true;});
    for(unsigned i=0;i<10;++i) tick(handoff);
    check(handoff.session.status().phase==Phase::settling,"handoff race fixture settled early");
    const auto received=handoff.io.now;
    for(unsigned i=0;i<4;++i) handoff.queue(handoff.prepare(2+i));
    tick(handoff);
    check(handoff.session.status().phase==Phase::idle && !handoff.inbox.pop(),
          "remote backlog survived local OFF handoff");
    // Delayed publication from the other task still carries its original
    // pre-handoff receive time; it cannot acquire the newly idle executor.
    handoff.refresh(); handoff.queue(handoff.prepare(9),received); handoff.cycle();
    check(handoff.session.status().phase==Phase::idle && handoff.session.ownership().execution_epoch==1,
          "pre-handoff frame published late acquired remote ownership");
    const auto release=handoff.io.now;
    ++handoff.io.now; handoff.refresh(); handoff.queue(handoff.prepare(10),release); handoff.cycle();
    check(handoff.session.status().phase==Phase::idle && handoff.session.ownership().execution_epoch==1,
          "frame stamped exactly at local release acquired ownership");
    remote_ready(handoff,11); stop(handoff);
    Fixture noop;
    check(noop.session.establish_reference({true,99,1,noop.io.now,77,7,2990}),"no-op handoff reference");
    auto competing=noop.prepare(); competing.origin_um=199500; noop.queue(competing);
    check(noop.cycle(intent(noop)).phase==Phase::idle && !noop.inbox.pop(),"no-op retained older remote prepare");
    const auto noop_release=noop.io.now;
    ++noop.io.now; noop.refresh(); competing=noop.prepare(2); competing.origin_um=199500;
    noop.queue(competing,noop_release);
    noop.cycle();
    check(noop.session.status().phase==Phase::idle && noop.session.status().result==Result::finished &&
          noop.session.ownership().execution_epoch==0,"no-op admitted delayed/exact-release competing frame");
    remote_ready(noop,3); stop(noop);
    Fixture zero;
    zero.io.now=0; zero.io.operation_us=0;
    zero.input.fast={true,false,false,false,1,0,0,2990,.1};
    zero.input.power={true,0,77,11.1}; offline(zero.input);
    check(zero.session.establish_reference({true,99,1,0,77,7,2990}),"zero-time reference rejected");
    check(zero.cycle(intent(zero)).result==Result::finished && zero.io.now==0,"zero-time no-op fixture");
    // Presence cannot be encoded as a nonzero timestamp. This frame was
    // received at release 0 but is published after a fresh remote clock exists.
    zero.io.now=10000; zero.offset=0; zero.refresh();
    competing=zero.prepare(); competing.origin_um=199500;
    check(zero.inbox.push({competing,zero.inbox.connection(),0,true}),"zero-time late frame did not queue");
    check(zero.cycle().phase==Phase::idle && zero.session.ownership().execution_epoch==0 &&
          zero.io.log==std::vector<std::string>{"parked"},"zero-time no-op lost its release barrier");
    Fixture remote; remote.ready(); remote.inbox.disconnected();
    check(remote.tick().phase==Phase::fault && !remote.session.status().reference_valid,"remote loss retained authority/reference");
    remote.off();
    // Raw STOP consumes a coincident gesture, including both-button raw STOP.
    Fixture idle; idle.reference(); auto tap=intent(idle);
    idle.input.fast.stop_pressed=true; idle.cycle(tap);
    idle.refresh(); idle.cycle(tap);
    check(!idle.io.calls && idle.session.ownership().local_result==Result::stale,"STOP release replayed a coincident tap");
    // All startup phases respond to a new gesture as STOP. Before live counting
    // and arming, uncertainty deliberately loses reference instead of handoff.
    for(unsigned ticks=0;ticks<5;++ticks) {
        Fixture f; f.reference(); f.cycle(intent(f));
        for(unsigned i=0;i<ticks;++i) tick(f);
        const auto before=f.io.pulses;
        tick(f,intent(f,2));
        check(f.io.request_high && f.io.duty==0 && f.io.pulses==before &&
              f.session.ownership().execution_epoch==1,"active gesture started a second move");
        if(ticks<2) {
            check(f.session.status().phase==Phase::fault && !f.session.status().reference_valid,"early STOP guessed retained reference");
            f.off();
        } else {
            // Repeated new/held intents during settling still observe the
            // quiet interval; none is remembered for subsequent movement.
            for(unsigned i=0;i<12 && f.session.status().phase!=Phase::idle;++i) tick(f,intent(f,3+i));
            for(unsigned i=0;i<5;++i) tick(f);
            check(f.session.status().phase==Phase::idle,"gestures prevented bounded settling");
            f.off();
        }
    }
}
void physical_global_and_off_faults() {
    for(unsigned kind=0;kind<8;++kind) {
        Fixture f; f.reference(); local_start(f);
        const auto pulses=f.io.pulses;
        f.tick([&](auto& in) {
            offline(in); in.fast.stop_pressed=true;
            switch(kind) {
            case 0:in.manual_intervention=true;break;
            case 1:in.global_fault=true;break;
            case 2:in.fast.driver_fault=true;break;
            case 3:in.fast.current_a=3;break;
            case 4:in.power.ready=false;break;
            case 5:in.fast.encoder_epoch+=1;break;
            case 6:in.fast.sampled_us-=10001;break;
            case 7:in.power.pack_binding=78;break;
            }
        },intent(f,2));
        check(f.session.status().phase==Phase::fault && !f.session.status().reference_valid &&
              f.io.pulses==pulses,"STOP/local gesture masked a physical/global fault");
        f.off();
        tick(f,intent(f,3));
        check(f.session.status().phase==Phase::fault,"new local gesture cleared physical fault");
    }
    for(bool before_start:{false,true}) {
        Fixture f; f.reference();
        if(before_start) {
            f.io.parked_readback=false;
            check(f.cycle(intent(f)).phase==Phase::fault,"missing initial OFF proof admitted local");
        } else {
            local_start(f); f.tick([](auto& in){in.fast.stop_pressed=true;});
            f.io.parked_readback=false;
            for(unsigned i=0;i<20 && f.session.status().phase!=Phase::fault;++i) tick(f);
            check(f.session.status().phase==Phase::fault && !f.session.status().reference_valid,"failed final OFF proof allowed handoff");
            f.refresh(); f.queue(f.prepare()); f.cycle();
            check(f.session.ownership().execution_epoch==1,"remote acquired failed local teardown");
        }
    }
}
void unchanged_timing_and_ceiling() {
    for(unsigned startup_ticks:{0u,1u,2u,5u}) {
        Fixture f; f.reference(); f.cycle(intent(f));
        for(unsigned i=0;i<startup_ticks;++i) tick(f);
        const auto pulses=f.io.pulses;
        f.io.now+=20001; f.refresh(); offline(f.input);
        check(f.cycle().phase==Phase::fault && f.io.pulses==pulses &&
              f.session.executor_fault()==MotionExecutor::Fault::clock,"local control gap caught up/fed watchdog or hid first fault");
        f.off();
    }
    Calibration tall; const Knot knots[]={{0,0},{1000,100},{161000,8100}};
    check(tall.assign(knots,3,7),"tall fixture invalid");
    Fixture too_long(profile(),tall); too_long.reference(); too_long.cycle(intent(too_long));
    check(too_long.session.ownership().local_result==Result::deadline && !too_long.io.calls &&
          too_long.session.ownership().execution_epoch==0,"local endpoint exceeded 240-second ceiling");
    Calibration near_limit; const Knot near_knots[]={{0,0},{71500,7150}};
    check(near_limit.assign(near_knots,2,7),"near-ceiling calibration invalid");
    Fixture long_local(profile(),near_limit); long_local.reference();
    const auto began=long_local.io.now;
    local_start(long_local);
    for(unsigned i=0;i<24000 && long_local.session.status().phase!=Phase::idle;++i) {
        tick(long_local);
        check(long_local.session.status().phase!=Phase::fault,"healthy near-ceiling local trajectory faulted");
    }
    check(long_local.session.status().phase==Phase::idle && long_local.session.status().result==Result::finished &&
          long_local.io.now-began>230000000 && long_local.io.now-began<MotionSession::max_session_us,
          "local authority failed bounded long offline travel");
    long_local.off();
    Fixture f; f.reference(); local_start(f);
    const auto until=f.io.now+240000000;
    // Timing and physical limits remain dominant; a huge clock jump cannot
    // grant another 240 seconds or renew local authority.
    f.io.now=until; f.refresh();
    check(f.cycle().phase==Phase::fault && !f.session.status().reference_valid,"local deadline renewed on stalled worker");
    f.off();
}
}
int main() {
    full_local_trajectory(); execution_identity_and_handoff(); failed_start_consumes_epoch();
    cold_or_stale_is_not_a_pending_tap(); stops_conflicts_and_network_scope();
    physical_global_and_off_faults(); unchanged_timing_and_ceiling();
    std::cout<<"local ownership, independent epochs, settled handoff, cold refusal, timing and fault precedence passed\n";
}
