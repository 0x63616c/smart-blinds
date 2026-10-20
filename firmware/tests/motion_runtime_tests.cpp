#include "smart_blinds/motion_runtime.hpp"
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <thread>

using namespace blinds;
namespace {
void check(bool condition,const char* reason) {
    if(!condition) { std::cerr<<reason<<'\n'; std::exit(1); }
}
wire::Request request(std::uint64_t message=1,wire::Kind kind=wire::Kind::prepare) {
    if(kind==wire::Kind::prepare) return {kind,7,99,message,1,1,1000000,1300000,0,100000,20000,40000};
    return {kind,7,99,message,1,1,1000000};
}
void copied_ingress_and_stop() {
    MotionSession::Inbox inbox(99);
    runtime::Ingress ingress(inbox);
    auto bytes=wire::encode(request());
    using R=runtime::Ingress::Result;
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::unauthenticated,"unconnected accepted");
    check(ingress.connected(),"connection failed");
    check(ingress.submit(bytes.data(),bytes.size(),false,2000000)==R::unauthenticated,"unauthenticated accepted");
    check(ingress.submit(bytes.data(),bytes.size()-1,true,2000000)==R::malformed,"short frame accepted");
    for(unsigned seq=1;seq<=4;++seq) {
        bytes=wire::encode(request(seq));
        check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::queued,"valid enqueue failed");
    }
    bytes.fill(0xFF);
    auto first=inbox.pop();
    check(first && first->request.message==1 && first->request.target_um==100000 && first->connection==1 &&
        first->received_us==2000000,"input storage was retained or metadata invented");
    bytes=wire::encode(request(5));
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::queued,"freed slot not usable");
    bytes=wire::encode(request(6));
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::rejected,"overflow overwritten");
    bytes=wire::encode(request(7,wire::Kind::stop));
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::queued && inbox.stop_pending(),"STOP blocked by queue");
    inbox.discard();
    check(!inbox.pop(),"STOP boundary left backlog");
    bytes=wire::encode(request(6));
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::rejected,"post STOP lower sequence replayed");
    ingress.disconnected();
    check(!inbox.connection(),"disconnect not visible");
    check(ingress.connected() && inbox.connection()==2,"connection generation reused");
    check(ingress.submit(bytes.data(),bytes.size(),true,2000000)==R::rejected,"reconnect reset replay floor");
}
void clock_retention_and_invalidation() {
    MotionSession::Inbox inbox(99);
    runtime::Ingress ingress(inbox);
    smart_blinds::ClockProbes probes(99,{1000,2,true});
    check(ingress.connected(),"connection failed");
    ingress.radio(true,true);
    check(probes.begin(99,1,2000100,true) && probes.sent(2000200,true) &&
        probes.assess(99,1,1000000,1000300,2000400,true),"clock fixture failed");
    check(ingress.qualify(1,probes.bounds(),2000400),"bound rejected");
    check(probes.begin(99,2,2100100,true),"new probe rejected");
    check(!probes.bounds() && ingress.snapshot(2100200).probe==1,"pending probe erased accepted evidence");
    check(probes.sent(2100200,true) && probes.assess(99,2,1100000,1100300,2100400,true) &&
        ingress.qualify(2,probes.bounds(),2100400),"new bound rejected");
    check(ingress.snapshot(2100500).probe==2,"bound not replaced");
    check(!ingress.qualify(2,probes.bounds(),2100600) && !ingress.snapshot(2100700).clock,"bad assessment retained bound");
    check(ingress.qualify(3,probes.bounds(),2100800),"fixture cannot restore new bound");
    ingress.radio(true,false);
    check(!ingress.snapshot(2100900).clock,"sleep retained clock");
    ingress.radio(true,true);
    check(ingress.qualify(4,probes.bounds(),2100900),"clock restore failed");
    check(!ingress.snapshot(3100300).clock,"stale bound kept alive");
    check(ingress.qualify(5,probes.bounds(),2101000),"clock restore failed");
    ingress.disconnected(); ingress.connected();
    check(!ingress.snapshot(2101100).clock,"reconnect inherited prior peer clock");
    const auto unvalidated=smart_blinds::ClockBounds::estimate({1000000,2000100,2000200,1000300});
    check(!ingress.qualify(6,unvalidated,2000300),"unvalidated arithmetic became permission");
}
runtime::Power good_power(std::uint64_t now) {
    runtime::Power p;
    p.gauge.state=power::State::ready; p.gauge.observed_us=now;
    p.gauge.voltage_earliest_us=now-400000; p.gauge.temperature_earliest_us=now-3200000;
    p.gauge.pack_binding=77; p.gauge.pack_v=11.1; p.gauge.soc_percent=65;
    p.charger.error=smart_blinds::charger::Error::none;
    p.charger.started_ms=p.charger.finished_ms=now/1000;
    return p;
}
void status_and_power_age() {
    constexpr std::uint64_t now=5000000;
    auto evidence=good_power(now);
    evidence.window=7;
    check(evidence.at(now).ready,"power fixture invalid");
    check(evidence.in_window(7).at(now).ready && !evidence.in_window(8).at(now).ready &&
        !evidence.in_window(0).at(now).ready,"prior sensing window resurrected old evidence");
    runtime::Network net{};
    net.attached=net.awake=true; net.connection=1; net.probe=1;
    net.clock=smart_blinds::ClockBounds::estimate({now-1002000,now-1000,now-900,now-999900},{1000,2,true});
    const auto value=runtime::input({},evidence,net,now+250001);
    check(!value.power.ready,"receipt of old capture refreshed it");
    MotionSession::Status s{};
    s.ready=true; s.reference_valid=true; s.observed_us=now; s.phase=MotionSession::Phase::ready;
    s.height_mm=123.4;
    const runtime::Snapshot snapshot{s,net.connection,net.probe};
    char text[768];
    check(runtime::status_json(text,sizeof(text),99,snapshot,evidence,net,true,now),"status serialization failed");
    check(std::strstr(text,"\"ready\":true") && std::strstr(text,"\"soc_percent\":65.00"),"fresh status wrong");
    check(runtime::status_json(text,sizeof(text),99,snapshot,evidence,net,true,now+30001) &&
        std::strstr(text,"\"ready\":false"),"stale control observation ready");
    check(runtime::status_json(text,sizeof(text),99,snapshot,evidence,net,false,now) &&
        std::strstr(text,"\"ready\":false"),"unqualified I/O ready");
    for(unsigned fault=0;fault<6;++fault) {
        auto unavailable=net;
        if(fault==0) unavailable.clock.reset(); // Failed qualification, before the next control cycle.
        if(fault==1) unavailable.connection=0;
        if(fault==2) unavailable.attached=false;
        if(fault==3) unavailable.awake=false;
        if(fault==4) unavailable.probe=2; // New bounds must be accepted by the session before readiness.
        if(fault==5) unavailable.connection=2;
        check(runtime::status_json(text,sizeof(text),99,snapshot,evidence,unavailable,true,now) &&
            std::strstr(text,"\"ready\":false"),"cached status survived network evidence revocation");
    }
    evidence.gauge.state=power::State::bus;
    check(runtime::status_json(text,sizeof(text),99,snapshot,evidence,net,true,now) &&
        std::strstr(text,"\"power_ready\":false") && std::strstr(text,"\"soc_percent\":null"),"fault reused good cache");
    check(!runtime::status_json(text,20,99,snapshot,evidence,net,true,now),"truncated status success");
}
// Actual two-thread queue publication exercises copied envelopes/release-acquire
// ownership with 20,000 frames and verifies ordering during wraparound.
void producer_consumer() {
    MotionSession::Inbox inbox(99);
    runtime::Ingress ingress(inbox);
    check(ingress.connected(),"connection failed");
    std::thread producer([&] {
        for(std::uint64_t n=1;n<=20000;++n) {
            const auto bytes=wire::encode(request(n));
            while(ingress.submit(bytes.data(),bytes.size(),true,n)!=runtime::Ingress::Result::queued)
                std::this_thread::yield();
        }
    });
    for(std::uint64_t expected=1;expected<=20000;) {
        if(const auto next=inbox.pop()) {
            check(next->request.message==expected && next->received_us==expected &&
                next->request.target_um==100000 && next->authenticated,"torn/reordered publication");
            ++expected;
        } else std::this_thread::yield();
    }
    producer.join();
}
void configuration_defaults() {
    runtime::Configuration c;
    check(!c.valid(99),"empty configuration approved");
    c.task_timing_verified=c.bus_readback_verified=true; c.verified_for_boot=99;
    c.port.bench_qualified=true; c.port.qualification_id=1; c.port.motor_sign=c.port.encoder_sign=1;
    c.motion.bench_qualified=c.motion.holding_qualified=true; c.motion.qualification_id=1;
    const Knot k[]={{0,0},{1000,100}};
    c.calibration.assign(k,2,7);
    c.pack.full_profile_verified=c.pack.timing_verified=c.pack.sensor_placement_verified=true;
    c.pack.verified_for_boot=99; c.pack.qualification_id=2; c.pack.pack_binding=77;
    c.pack.dev_name=1; c.pack.pack_config=0x2009; c.pack.nv_config1=0x140; c.pack.sense_resistor=1000;
    c.pack.thermistor_config=0x91C3; c.clock.validated=true;
    check(c.valid(99) && !c.valid(100),"boot qualification binding broken");
    c.motion.qualification_id=2;
    check(!c.valid(99),"different I/O and controller qualification accepted");
    c.motion.qualification_id=1; c.motion.max_duty=.6;
    check(!c.valid(99),"controller duty above I/O limit accepted");
}
struct Io : MotionIo,CounterOrigin {
    std::uint64_t now=5000000,epoch=0;
    unsigned calls=0;
    bool off=true,counter=false;
    std::uint64_t now_us() const override { return now; }
    bool parked_off() override { return off && !counter; } // Synthetic port only.
    bool operation() { ++calls; ++now; return true; }
    bool request_n(bool high) override { off=high; return operation(); }
    bool charge_off() override { return operation(); }
    bool coast() override { return operation(); }
    bool wdi_high() override { return operation(); }
    bool encoder_power(bool) override { return operation(); }
    bool counter_start(std::uint64_t value) override { counter=true; return value==epoch && operation(); }
    bool counter_stop() override { counter=false; return operation(); }
    bool awake_lock(bool) override { return operation(); }
    bool pwm(int,double) override { return operation(); }
    bool heartbeat_pulse() override { return operation(); }
    bool set_counter_origin(std::uint64_t value,double count) override {
        check(off && !counter && count==500,"origin installed outside stopped state");
        epoch=value; return operation();
    }
};
void ingress_to_session_faults() {
    Calibration calibration;
    const Knot knots[]={{0,0},{1000,100}};
    check(calibration.assign(knots,2,7),"calibration failed");
    for(bool qualified:{false,true}) {
        Io io;
        BenchMotionProfile profile;
        profile.bench_qualified=profile.holding_qualified=qualified; profile.qualification_id=123;
        MotionSession session(io,io,calibration,{},profile,99);
        MotionSession::Inbox inbox(99); runtime::Ingress ingress(inbox);
        ingress.connected(); ingress.radio(true,true);
        std::uint64_t sequence=0,probe=0;
        SessionInput observation;
        const auto refresh=[&] {
            const auto bounds=smart_blinds::ClockBounds::estimate(
                {io.now-1002000,io.now-1000,io.now-900,io.now-999900},{1000,2,true});
            check(ingress.qualify(++probe,bounds,io.now),"runtime clock rejected");
            const FastObservation fast{true,io.counter,false,false,++sequence,io.now,io.epoch,500,.1};
            observation=runtime::input(fast,good_power(io.now),ingress.snapshot(io.now),io.now);
        };
        const auto submit=[&](wire::Kind kind,std::uint64_t message) {
            auto r=request(message,kind); r.probe=probe; r.sent_us=io.now-1000000;
            if(kind==wire::Kind::prepare) { r.start_us=r.sent_us+300000; r.origin_um=50000; }
            const auto bytes=wire::encode(r);
            check(ingress.submit(bytes.data(),bytes.size(),true,io.now)==runtime::Ingress::Result::queued,"runtime enqueue rejected");
        };
        refresh();
        check(session.establish_reference({true,99,1,io.now,77,7,500})==qualified,"reference qualification wrong");
        submit(wire::Kind::prepare,1);
        auto state=session.cycle(inbox,observation);
        if(!qualified) {
            check(state.result==MotionSession::Result::unqualified && io.calls==0,"default runtime touched motor I/O");
            continue;
        }
        for(unsigned i=0;i<3;++i) { io.now+=10000; refresh(); state=session.cycle(inbox,observation); }
        check(state.ready && !io.off,"canonical ingress never reached real session ready");
        io.now+=10000; refresh(); submit(wire::Kind::commit,2); state=session.cycle(inbox,observation);
        check(state.phase==MotionSession::Phase::committed,"canonical commit did not reach session");
        io.now+=10000; refresh();
        // A new invalid snapshot replaces the previous good one immediately.
        observation=runtime::input(observation.fast,{},ingress.snapshot(io.now),io.now);
        state=session.cycle(inbox,observation);
        check(state.phase==MotionSession::Phase::fault && !state.reference_valid && io.off && !io.counter,
            "failed sensor publication left an armed session");
    }
}
}
int main() {
    copied_ingress_and_stop(); clock_retention_and_invalidation(); status_and_power_age();
    producer_consumer(); configuration_defaults(); ingress_to_session_faults();
    std::cout<<"runtime ownership, clock retention, queue contention and freshness tests passed\n";
}
