#include "smart_blinds/wifi_motion.hpp"
#include "smart_blinds/telemetry.hpp"
#include <cstdlib>
#include <cstring>
#include <iostream>
using namespace blinds;
using smart_blinds::wifi::MotionBinding;
namespace {
void check(bool c,const char* why) { if(!c) { std::cerr<<why<<'\n';std::exit(1); } }
struct Io final : MotionIo,CounterOrigin {
    std::uint64_t now=5000000,epoch=0;
    bool off=true,counting=false,encoder=false,locked=false;
    unsigned calls=0,samples=0;
    bool op() { ++calls; ++now; return true; }
    std::uint64_t now_us() const override { return now; }
    bool parked_off() override { return off && !counting && !encoder && !locked; }
    bool request_n(bool high) override { off=high;return op(); }
    bool charge_off() override { return op(); }
    bool coast() override { return op(); }
    bool wdi_high() override { return op(); }
    bool encoder_power(bool on) override { encoder=on;return op(); }
    bool counter_start(std::uint64_t e) override { counting=true;return epoch==e && op(); }
    bool counter_stop() override { counting=false;return op(); }
    bool awake_lock(bool on) override { locked=on;return op(); }
    bool pwm(int,double) override { return op(); }
    bool heartbeat_pulse() override { return op(); }
    bool set_counter_origin(std::uint64_t e,double value) override {
        check(off && !counting && value==500,"counter origin outside parked state");
        epoch=e;return op();
    }
};
Calibration calibration() {
    Calibration c; const Knot k[]={{0,0},{1000,100}};
    check(c.assign(k,2,7),"calibration fixture");return c;
}
BenchMotionProfile profile(bool q) {
    BenchMotionProfile p;p.bench_qualified=p.holding_qualified=q;p.qualification_id=123;return p;
}
runtime::Power power(std::uint64_t now) {
    runtime::Power p;
    p.gauge.state=power::State::ready;p.gauge.observed_us=now;
    p.gauge.voltage_earliest_us=now-400000;p.gauge.temperature_earliest_us=now-3200000;
    p.gauge.pack_binding=77;p.gauge.pack_v=11.1;
    p.charger.error=smart_blinds::charger::Error::none;p.charger.started_ms=p.charger.finished_ms=now/1000;
    return p;
}
struct Port final : smart_blinds::wifi::MotionPort {
    Io io; MotionSession::Inbox inbox{99}; runtime::Ingress input{inbox};
    runtime::Revocation signals; runtime::Network network{};runtime::Snapshot snapshot{};
    MotionSession session;
    bool enabled,raw_stop=false,off_readback=true;
    unsigned handoff_calls=0;
    std::uint64_t sequence=0;
    explicit Port(bool q) : session(io,io,calibration(),{},profile(q),99),enabled(q) {
        if(q) check(session.establish_reference({true,99,1,io.now,77,7,500}),"reference fixture");
    }
    runtime::Ingress& ingress() override { return input; }
    void publish(std::uint64_t now) override { network=input.snapshot(now);network.revocation=signals.generation(); }
    void notify() override {}
    void revoke() override { signals.revoke(); }
    bool qualified() const override { return enabled && !signals.failed(); }
    bool parked(std::uint64_t now) const override { return snapshot.parking.current(now,input.activity(),signals); }
    bool status(char* out,std::size_t size,std::uint64_t now) override {
        return runtime::status_json(out,size,99,snapshot,power(io.now),network,
            qualified() && snapshot.parking.revocation==signals.generation(),now);
    }
    bool telemetry(char* out,std::size_t size,std::uint64_t nonce,std::uint64_t now) override {
        return blinds::telemetry::json(out,size,99,nonce,now,{},false,false,1);
    }
    bool handoff(char* out,std::size_t size,std::uint64_t nonce) override {
        ++handoff_calls;
        const auto n=std::snprintf(out,size,"{\"nonce\":%llu,\"settled_off\":false}",static_cast<unsigned long long>(nonce));
        return n>0 && static_cast<std::size_t>(n)<size;
    }
    void cycle(bool defer=false) {
        const auto activity=input.activity(),rev=signals.generation();
        auto net=runtime::admitted_network(network,signals);
        const auto fast=runtime::observe(enabled,raw_stop,session.status().phase,signals,[&] {
            ++io.samples;
            return FastObservation{true,io.counting,false,false,++sequence,io.now,io.epoch,500,.1};
        });
        auto in=runtime::input(fast,power(io.now),net,io.now);
        const auto result=session.cycle(inbox,in,{},defer);
        const bool off=off_readback && io.off && !io.counting && !io.encoder && !io.locked;
        snapshot={result,net.connection,net.probe,
            runtime::parked(io.now,activity,input.activity(),rev,signals,!result.awake_required,off,enabled)};
    }
};
std::array<std::uint8_t,32> values(std::initializer_list<std::uint64_t> args) {
    std::array<std::uint8_t,32> out{};unsigned at=0;
    for(auto v:args) { for(unsigned i=0;i<8;++i) out[at+7-i]=static_cast<std::uint8_t>(v>>(8*i));at+=8; }
    return out;
}
struct Fixture {
    Port port;
    MotionBinding app;
    std::uint64_t owner=0;
    explicit Fixture(bool q=true) : port(q),app(99,port,{1000,2,q}) {
        smart_blinds::wifi::Credentials c;
        std::strcpy(c.ssid.data(),"disposable");std::strcpy(c.password.data(),"disposable");
        std::strcpy(c.identity.data(),"fixture");c.key[0]=1;c.approved=true;c.board_profile=1;
        check(app.policy.configure(c,0) && app.policy.begin_association(0) &&
            app.policy.network_ready(1,4999),"association fixture");
        owner=app.connected(port.io.now);check(owner,"owner fixture");
        const auto w=values({99,1});
        check(app.request(owner,"v1/wake",2,w.data(),16,port.io.now,port.io.now).code==68,"wake fixture");
        qualify();
    }
    void qualify() {
        const auto seq=app.probes.sequence()+1,now=port.io.now;
        auto b=values({99,seq});
        check(app.request(owner,"v1/clock",2,b.data(),16,now,now+100).code==69,"clock fixture");
        port.io.now=now+300;
        b=values({99,seq,now-1000100,now-999800});
        check(app.request(owner,"v1/qualify",2,b.data(),32,port.io.now,port.io.now).code==68,"qualify fixture");
    }
    MotionBinding::Reply send(std::uint64_t message,wire::Kind kind=wire::Kind::prepare) {
        wire::Request r{kind,7,99,message,1,app.probes.sequence(),port.io.now-1000000};
        if(kind==wire::Kind::prepare) {
            r.start_us=r.sent_us+300000;r.origin_um=50000;r.target_um=100000;
            r.speed_um_s=20000;r.acceleration_um_s2=40000;
        }
        const auto bytes=wire::encode(r);
        return app.request(owner,"v1/motion",2,bytes.data(),bytes.size(),port.io.now,port.io.now);
    }
    void ready() {
        check(send(1).code==68,"prepare rejected");
        port.cycle();
        for(unsigned i=0;i<3;++i) { port.io.now+=10000;port.cycle(); }
        check(port.session.status().ready && !port.io.off,"session never ready");
    }
};
void informational_without_wake() {
    Fixture f(false);
    f.port.io.now+=10000001;f.app.tick(f.port.io.now);
    check(!f.app.policy.awake(),"fixture wake did not expire");
    const auto wake=f.app.policy.last_wake(),probe=f.app.probes.sequence();
    const auto activity=f.port.input.activity();
    const auto operations=f.port.io.calls;
    const auto body=values({99,77});
    auto reply=f.app.request(f.owner,"v1/telemetry",2,body.data(),16,f.port.io.now,f.port.io.now);
    check(reply.code==69 && std::strstr(reply.body.data(),"\"state\":\"absent\""),"unqualified telemetry invented observation");
    check(std::strlen(reply.body.data())<768,"telemetry exceeded bounded reply");
    check(!f.app.policy.awake() && f.app.policy.last_wake()==wake && f.app.probes.sequence()==probe &&
          f.port.input.activity()==activity && f.port.io.calls==operations,"telemetry renewed authority or touched IO");
    check(f.app.request(f.owner,"v1/telemetry",1,nullptr,0,f.port.io.now,f.port.io.now).code==133,"GET method accepted");
    const auto wrong=values({100,77});
    check(f.app.request(f.owner,"v1/telemetry",2,wrong.data(),16,f.port.io.now,f.port.io.now).code==128,"old boot accepted");
}
void handoff_resource_is_observation_only() {
    Fixture f(false);
    f.port.io.now+=10000001;f.app.tick(f.port.io.now);
    const auto activity=f.port.input.activity(),ops=f.port.io.calls;
    const auto wake=f.app.policy.last_wake(),probe=f.app.probes.sequence();
    auto body=values({99,1});
    check(f.app.request(f.owner,"v1/handoff",2,body.data(),16,f.port.io.now,f.port.io.now).code==69,
          "unqualified handoff observation rejected");
    check(f.app.request(f.owner,"v1/handoff",2,body.data(),16,f.port.io.now,f.port.io.now).code==128,
          "replayed handoff request accepted");
    body=values({100,2});
    check(f.app.request(f.owner,"v1/handoff",2,body.data(),16,f.port.io.now,f.port.io.now).code==128,
          "foreign boot handoff request accepted");
    check(f.app.request(f.owner,"v1/handoff",1,nullptr,0,f.port.io.now,f.port.io.now).code==133,
          "GET handoff accepted");
    check(f.port.handoff_calls==1 && !f.app.policy.awake() && f.app.policy.last_wake()==wake &&
          f.app.probes.sequence()==probe && f.port.input.activity()==activity && f.port.io.calls==ops,
          "handoff observation changed authority or physical state");
}
void gates_and_ownership() {
    Fixture f(false);
    check(f.send(1).code==163 && !f.port.io.calls,"unqualified radio touched I/O");
    check(!f.app.probes.qualified(f.port.io.now),"unvalidated model became qualified");
    const auto before=f.owner;
    f.app.disconnected(before,f.port.io.now);
    check(!f.port.input.snapshot(f.port.io.now).connection,"disconnect retained inbox owner");
    // Closing a preflight session cancels its wake, but permits a fresh explicit
    // session. No old sequence/clock ownership is inherited.
    f.owner=f.app.connected(f.port.io.now+1);
    check(f.owner>before,"owner reused");
    check(f.app.request(before,"v1/status",1,nullptr,0,f.port.io.now+1,f.port.io.now+1).code==129,"old owner accepted");
}
void parking_races() {
    Fixture f;
    f.port.cycle();
    check(f.port.parked(f.port.io.now),"idle physical parking fixture");
    const auto old=f.port.snapshot.parking;
    check(f.send(1).code==68,"prepare not queued");
    check(!old.current(f.port.io.now,f.port.input.activity(),f.port.signals),"queued prepare reused idle proof");
    f.app.tick(f.port.io.now);
    check(f.app.policy.state()==smart_blinds::wifi::Policy::State::operation,"queued treated as completed");
    f.port.cycle();
    check(!f.port.parked(f.port.io.now),"preparing declared parked");
    runtime::Activity race;
    runtime::Revocation signals;
    const auto before=race.current();
    check(race.begin(),"begin race");
    auto p=runtime::parked(100,before,race.current(),signals.generation(),signals,true,true,true);
    check(!p.current(100,race.current(),signals),"in-flight producer allowed parking");
    race.end();
    check(!p.current(100,race.current(),signals),"completed producer repaired old proof");
    p=runtime::parked(100,race.current(),race.current(),signals.generation(),signals,true,true,true);
    check(p.current(30100,race.current(),signals) && !p.current(30101,race.current(),signals),
        "stopped worker freshness limit changed");
    signals.revoke();check(!p.current(101,race.current(),signals),"revocation retained OFF proof");
    runtime::Network net{};
    net.attached=net.awake=true;net.revocation=signals.generation();
    check(runtime::admitted_network(net,signals).attached,"matching acknowledged publication rejected");
    // The SDK callback runs after the owner captures its acknowledged epoch,
    // before its length-one queue write completes. Never relabel with 'current'.
    signals.revoke();
    check(!runtime::admitted_network(net,signals).attached,"racing old network publication authorized");
    net.revocation=signals.generation();signals.fail();
    check(!runtime::admitted_network(net,signals).attached,"delivery failure repaired by epoch acknowledgment");
}
void stop_and_revoke() {
    for(bool disconnect:{false,true}) {
        Fixture f;f.ready();
        f.port.io.now+=10000;
        check(f.send(2,wire::Kind::commit).code==68,"commit not queued");
        const auto samples=f.port.io.samples;
        if(disconnect) f.port.revoke(); // SDK callback before owner processes event.
        else f.port.signals.local_stop();
        f.port.cycle();
        check(f.port.io.off,"revocation/STOP did not inhibit");
        check(!f.port.session.status().ready,"old ready survived");
        if(disconnect) check(f.port.session.status().phase==MotionSession::Phase::fault,"async revocation did not fault");
        else {
            check(f.port.io.samples==samples,"STOP waited for ADC");
            check(f.port.session.status().phase==MotionSession::Phase::settling,"STOP skipped settling");
            for(unsigned i=0;i<11;++i) { f.port.io.now+=10000;f.port.cycle(); }
            check(f.port.session.status().result==MotionSession::Result::stopped && f.port.parked(f.port.io.now),
                  "settled STOP has no physical OFF proof");
            f.app.tick(f.port.io.now);
            check(f.app.policy.state()==smart_blinds::wifi::Policy::State::idle,"verified completion retained operation");
        }
    }
    runtime::Revocation signals;
    const auto fast=runtime::observe(true,false,MotionSession::Phase::moving,signals,[&] {
        signals.local_stop(); return FastObservation{};
    });
    check(fast.stop_pressed,"STOP during ADC missed same cycle");
}
void stop_replay_and_failed_off() {
    Fixture f;f.ready();
    f.port.io.now+=10000;
    check(f.send(10,wire::Kind::stop).code==68,"STOP rejected");
    check(f.send(9,wire::Kind::lease).code!=68,"STOP sequence floor lost");
    f.port.cycle();
    for(unsigned i=0;i<11;++i) { f.port.io.now+=10000;f.port.cycle(); }
    f.port.off_readback=false;f.port.cycle();
    f.app.tick(f.port.io.now);
    check(f.app.policy.state()==smart_blinds::wifi::Policy::State::operation,"failed OFF readback allowed sleep");
    f.port.io.now+=30001;f.app.tick(f.port.io.now);
    check(f.app.policy.state()==smart_blinds::wifi::Policy::State::operation,"stale worker allowed sleep");
    f.app.disconnected(f.owner,f.port.io.now);
    check(f.app.policy.state()==smart_blinds::wifi::Policy::State::fault && !f.app.connected(f.port.io.now+1),
        "active disconnect reconnected");
}
}
void telemetry_maximum_and_no_fake_freshness() {
    telemetry::Samples s{};
    s.battery={UINT64_MAX,UINT64_MAX,UINT32_MAX,UINT32_MAX,100,true,true};
    s.charger={UINT64_MAX,UINT32_MAX,true,true};
    s.pd={UINT64_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT16_MAX,telemetry::Source::policy_observed,true,true};
    s.fault=telemetry::Fault::lifecycle;s.fault_code=UINT16_MAX;
    char out[768]{};
    check(telemetry::json(out,sizeof(out),UINT64_MAX,UINT64_MAX,UINT64_MAX,s,true,true,UINT32_MAX),"maximum telemetry reply exceeds fixed capacity");
    check(std::strlen(out)<sizeof(out),"maximum telemetry length");
    check(!telemetry::json(out,32,1,1,1,s,false,false,1),"truncated telemetry accepted");
    s={};s.battery={0,1,1,1,42,true,true};
    check(telemetry::json(out,sizeof(out),1,1,12345,s,false,false,1),"zero-time observation rejected");
    check(std::strstr(out,"\"sample_us\":\"0000000000000000\""),"observation time restamped");
}
void off_transaction_and_deferred_admission() {
    runtime::OffTransaction hold;
    const auto first=hold.request();
    check(first && !hold.idle() && hold.pending()==first && !hold.held() && !hold.request(),"parallel hold request accepted");
    check(!hold.answer(first+4,true) && !hold.answer(first+1,true) && !hold.release(first+4),"wrong token changed hold");
    check(hold.answer(first,true) && hold.held()==first && !hold.answer(first,false),"grant not single-use");
    check(hold.release(first) && hold.idle() && !hold.release(first),"release replay accepted");
    const auto second=hold.request();
    check(second>first && !hold.release(first) && hold.answer(second,false) && !hold.held(),"old release revoked new token");
    check(hold.state(second)==runtime::OffTransaction::State::denied && hold.release(second),"denied token cannot close");
    Fixture f;
    check(f.send(1).code==68,"held prepare queue setup failed");
    f.port.cycle(true);
    check(f.port.inbox.pending() && f.port.inbox.received_message()==1 &&
          f.port.session.status().last_message==0 && f.port.io.off && !f.port.io.encoder,
          "OFF transaction consumed/armed ordinary request");
    check(f.send(2,wire::Kind::stop).code==68,"held STOP was rejected");
    f.port.io.now+=10000;f.port.cycle(true);
    check(!f.port.inbox.pending() && f.port.inbox.received_message()==2 &&
          f.port.session.status().result==MotionSession::Result::stopped && f.port.io.off,
          "held STOP failed to bypass/discard backlog");
    check(f.send(1).code!=68,"OFF hold reset producer replay floor");
    Fixture next;check(next.send(1).code==68,"release fixture prepare rejected");
    next.port.cycle(true);next.port.io.now+=10000;next.port.cycle(false);
    check(next.port.session.status().phase==MotionSession::Phase::preparing &&
          next.port.session.status().last_message==1 && !next.port.inbox.pending(),
          "released hold lost original pending command");
}
int main() {
    off_transaction_and_deferred_admission();
    telemetry_maximum_and_no_fake_freshness();
    informational_without_wake();handoff_resource_is_observation_only();gates_and_ownership();parking_races();stop_and_revoke();stop_replay_and_failed_off();
    std::cout<<"Wi-Fi binding, real session, raw STOP, parking and revocation tests passed\n";
}
