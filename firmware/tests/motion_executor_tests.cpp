#include "smart_blinds/motion_executor.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
using namespace blinds;
void expect(bool ok,const char* message) { if(!ok) { std::cerr<<message<<'\n'; std::exit(1); } }
struct FakeIo final : MotionIo {
    std::uint64_t time=1000000;
    unsigned calls=0, fail_at=0, slow_at=0, pulses=0;
    bool request_high=true, encoder=false, counter=false, awake=false;
    double duty=0;
    std::vector<std::string> log;
    std::uint64_t now_us() const override { return time; }
    bool action(const char* name) {
        log.emplace_back(name); ++calls; time+=calls==slow_at ? 101 : 1;
        return calls!=fail_at;
    }
    bool request_n(bool high) override { if(!action(high ? "request-off":"request-on")) return false; request_high=high; return true; }
    bool charge_off() override { return action("charge-off"); }
    bool coast() override { if(!action("coast")) return false; duty=0; return true; }
    bool wdi_high() override { return action("wdi-high"); }
    bool encoder_power(bool on) override { if(!action(on ? "encoder-on":"encoder-off")) return false; encoder=on; return true; }
    bool counter_start(std::uint64_t epoch) override {
        expect(encoder && awake && request_high && epoch,"counter start without preparation");
        if(!action("counter-start")) return false;
        counter=true; return true;
    }
    bool counter_stop() override { if(!action("counter-stop")) return false; counter=false; return true; }
    bool awake_lock(bool on) override { if(!action(on ? "awake-on":"awake-off")) return false; awake=on; return true; }
    bool pwm(int direction,double value) override {
        expect(!request_high && counter && encoder && awake && pulses,"PWM before physical prerequisites/first heartbeat");
        expect((direction==1 || direction==-1) && std::isfinite(value) && value>0 && value<=.5,"invalid PWM");
        if(!action(direction==1 ? "pwm-forward":"pwm-reverse")) return false;
        duty=direction*value; return true;
    }
    bool heartbeat_pulse() override {
        expect(!request_high && counter && encoder && awake,"heartbeat without active control session");
        if(!action("pulse")) return false;
        ++pulses; ++time; return true;
    }
};
Calibration calibration() {
    Calibration c; const Knot knots[]={{0,0},{1000,100},{3000,200}};
    expect(c.assign(knots,3,7),"calibration failed"); return c;
}
BenchMotionProfile bench_profile() { BenchMotionProfile p; p.bench_qualified=true; p.qualification_id=123; return p; }
struct Fixture {
    FakeIo io;
    MotionExecutor executor;
    explicit Fixture(BenchMotionProfile profile=bench_profile()) : executor(io,calibration(),profile,99) {}
    std::uint64_t sequence=0;
    double count=500;
    MotionEvidence evidence() {
        MotionEvidence e; e.sequence=++sequence; e.sampled_us=io.time; e.power_sampled_us=io.time;
        e.encoder_epoch=1; e.control_valid_until_us=io.time+300000;
        e.calibration_revision=7; e.count=count; e.current_a=.1; e.pack_v=11.1;
        e.power_ready=true; e.reference_valid=true; e.driver_fault=false;
        return e;
    }
    Output target(double velocity=20) { return {true,velocity,100,blinds::State::moving,Reason::ok}; }
    void sensing() {
        expect(executor.open_sensing(99,1,evidence()),"open sensing failed");
        io.time+=5001;
        expect(executor.poll_sensing(evidence()),"settled encoder failed");
    }
    void armed() { sensing(); ++io.time; expect(executor.arm(evidence()),"arm failed"); }
    bool tick(double velocity=20,double delta=2) { io.time+=10000; count+=delta; return executor.update(target(velocity),evidence()); }
    void running() { armed(); expect(tick(),"first heartbeat failed"); expect(tick(),"first PWM failed"); }
};
void slope() {
    const auto c=calibration();
    expect(c.count_rate(500,10)==100 && c.count_rate(1500,10)==200,"nonlinear calibration speed lost");
    expect(c.count_rate(1000,10)==200 && c.count_rate(1000,-10)==-100,"directional knot slope wrong");
    expect(!c.count_rate(0,-1) && !c.count_rate(3000,1),"outward endpoint velocity allowed");
    expect(c.count_rate(0,0)==0 && !c.count_rate(3001,0),"stationary/range handling wrong");
    expect(!c.count_rate(100,std::numeric_limits<double>::quiet_NaN()),"NaN rate accepted");
}
void lifecycle() {
    FakeIo no_io; MotionExecutor disabled(no_io,calibration(),{},99);
    MotionEvidence absent;
    expect(!disabled.open_sensing(99,1,absent) && no_io.calls==0,"unqualified profile touched hardware");
    Fixture f;
    expect(f.executor.open_sensing(99,1,f.evidence()),"open failed");
    expect(f.io.log==std::vector<std::string>({"request-off","coast","wdi-high","charge-off","awake-on","encoder-on"}),"encoder startup ordering wrong");
    expect(!f.executor.poll_sensing(f.evidence()) && !f.io.counter,"settling bypassed");
    f.io.time+=5001; expect(f.executor.poll_sensing(f.evidence()),"counter did not start");
    ++f.io.time; expect(f.executor.arm(f.evidence()),"arm rejected");
    expect(!f.io.request_high && !f.io.pulses && f.io.duty==0,"arm started PWM");
    f.io.time+=1000;
    expect(f.executor.update(f.target(),f.evidence()) && f.io.pulses==1,"first healthy edge failed");
    expect(f.io.duty==0,"PWM applied in first heartbeat iteration");
    expect(f.tick(),"running tick failed");
    expect(f.io.duty>0 && f.io.pulses==1,"single subsequent cycle fed heartbeat");
    expect(f.tick(),"second running tick failed");
    expect(f.io.pulses==2,"two healthy cycles did not feed");
    f.io.log.clear();
    expect(f.executor.stop(),"normal stop failed");
    expect(f.io.log==std::vector<std::string>({"request-off","coast","wdi-high","charge-off","counter-stop","encoder-off","awake-off"}),"stop ordering wrong");
    expect(!f.io.encoder && !f.io.counter && !f.io.awake && f.io.request_high && f.io.duty==0,"stop left resources active");
    expect(!f.executor.open_sensing(99,1,f.evidence()),"stopped command replayed");
}
void transfer_failures() {
    Fixture success; success.running(); const auto operations=success.io.calls;
    for(unsigned failure=1;failure<=operations;++failure) {
        Fixture f; f.io.fail_at=failure;
        bool ok=f.executor.open_sensing(99,1,f.evidence());
        if(ok) { f.io.time+=5001; ok=f.executor.poll_sensing(f.evidence()); }
        if(ok) { ++f.io.time; ok=f.executor.arm(f.evidence()); }
        if(ok) ok=f.tick();
        if(ok) ok=f.tick();
        expect(!ok && f.executor.state()==MotionExecutor::State::fault,"injected lifecycle operation failure accepted");
        expect(f.io.request_high && f.io.duty==0 && !f.io.encoder,"operation failure did not clean up");
        expect(!f.tick(),"fault implicitly recovered");
    }
    Fixture slow; slow.io.slow_at=1;
    expect(!slow.executor.open_sensing(99,1,slow.evidence()) && slow.executor.fault()==MotionExecutor::Fault::io,"unbounded I/O accepted");
    for(unsigned failure=1;failure<=7;++failure) {
        Fixture f; f.running(); f.io.calls=0; f.io.fail_at=failure; f.io.log.clear();
        expect(!f.executor.stop() && f.executor.state()==MotionExecutor::State::fault,"stop failure not latched");
        expect(f.io.log.size()==7,"cleanup short-circuited after failure");
    }
    for(unsigned slow=1;slow<=7;++slow) {
        Fixture f; f.running(); f.io.calls=0; f.io.slow_at=slow; f.io.log.clear();
        expect(!f.executor.stop() && f.executor.fault()==MotionExecutor::Fault::io,"slow stop operation accepted");
        expect(f.io.log.size()==7,"slow cleanup skipped remaining OFF writes");
    }
}
void evidence_faults() {
    for(int kind=0;kind<17;++kind) {
        Fixture f; f.running(); f.io.time+=10000; auto e=f.evidence();
        switch(kind) {
        case 0:e.power_ready=false;break;
        case 1:e.reference_valid=false;break;
        case 2:e.driver_fault=true;break;
        case 3:e.current_a=3;break;
        case 4:e.pack_v=9;break;
        case 5:e.sampled_us=f.io.time-10001;break;
        case 6:e.sampled_us=f.io.time+1;break;
        case 7:e.encoder_epoch=2;break;
        case 8:e.calibration_revision=6;break;
        case 9:e.control_valid_until_us=f.io.time;break;
        case 10:e.sequence=1;break;
        case 11:e.power_sampled_us=f.io.time-250001;break;
        case 12:e.power_sampled_us=f.io.time+1;break;
        case 13:e.current_a=std::numeric_limits<double>::quiet_NaN();break;
        case 14:e.count+=1000;break;
        case 15:e.control_valid_until_us=f.io.time+MotionExecutor::cycle_max_us;break;
        case 16:e.count=std::numeric_limits<double>::infinity();break;
        }
        const auto pulses=f.io.pulses;
        expect(!f.executor.update(f.target(),e),"bad evidence accepted");
        expect(f.io.request_high && f.io.pulses==pulses,"fault fed watchdog or left gate requested");
    }
    Fixture gap; gap.running(); gap.io.time+=20001;
    expect(!gap.executor.update(gap.target(),gap.evidence()),"late control caught up");
    Fixture reverse; reverse.running(); reverse.io.time=1;
    expect(!reverse.executor.update(reverse.target(),reverse.evidence()) && reverse.executor.fault()==MotionExecutor::Fault::clock,"clock reversal not latched");
    Fixture idle; idle.sensing(); idle.io.time+=5000000;
    expect(!idle.executor.poll_sensing(idle.evidence()) && !idle.io.encoder,"sensing session did not expire");
    Fixture late_arm; late_arm.sensing(); late_arm.io.time+=5000000;
    expect(!late_arm.executor.arm(late_arm.evidence()) && late_arm.io.request_high,"arm bypassed sensing deadline");
    Fixture pressed; pressed.running(); auto e=pressed.evidence(); e.stop_pressed=true;
    expect(pressed.executor.update(pressed.target(),e) && pressed.executor.state()==MotionExecutor::State::idle,"local STOP did not override");
}
void output_faults() {
    for(int kind=0;kind<6;++kind) {
        Fixture f; f.running(); f.io.time+=10000; auto output=f.target();
        switch(kind) {
        case 0:output.state=static_cast<blinds::State>(999);break;
        case 1:output.velocity_mm_s=std::numeric_limits<double>::quiet_NaN();break;
        case 2:output.velocity_mm_s=31;break;
        case 3:output.state=blinds::State::prepared;break;
        case 4:output.reason=Reason::lease_expired;break;
        case 5:output.motor_enable=false;break;
        }
        const auto pulses=f.io.pulses;
        expect(!f.executor.update(output,f.evidence()) && f.executor.fault()==MotionExecutor::Fault::output,"invalid motion output accepted");
        expect(f.io.request_high && f.io.pulses==pulses,"invalid output fed watchdog or left motor requested");
    }
}
void reversal_and_stall() {
    Fixture f; f.running(); f.io.log.clear();
    expect(f.tick(-20,2) && f.io.duty==0,"reversal did not coast first");
    expect(f.tick(-20,0) && f.io.duty==0,"reversal coast interval bypassed");
    expect(f.tick(-20,0) && f.io.duty<0,"stationary reversal did not resume");
    auto first_reverse=std::find(f.io.log.begin(),f.io.log.end(),"pwm-reverse");
    expect(first_reverse!=f.io.log.end() && std::count(f.io.log.begin(),first_reverse,"coast")>=2,"reverse PWM preceded coasting");
    Fixture stalled; stalled.running(); bool ok=true;
    for(int i=0;i<50 && ok;++i) ok=stalled.tick(20,0);
    expect(!ok && stalled.executor.fault()==MotionExecutor::Fault::stalled && stalled.io.request_high,"no-progress fault missing");
    Fixture backwards; backwards.running();
    for(int i=0;i<60 && backwards.executor.state()!=MotionExecutor::State::fault;++i) backwards.tick(-20,2);
    expect(backwards.executor.fault()==MotionExecutor::Fault::reversal,"unsettled reversal did not time out");
    Fixture overspeed; overspeed.running();
    for(int i=0;i<20;++i) expect(overspeed.tick(20,10) && overspeed.io.duty==0,"overspeed attempted opposing drive");
    expect(overspeed.tick(20,0) && overspeed.io.duty>0,"coast saturation wound up the integral");
    auto profile=bench_profile(); profile.feedforward=.1;
    Fixture saturated(profile); saturated.running();
    expect(saturated.io.duty==.5,"maximum duty was not clamped");
}
void controller_plant() {
    // Illustrative first-order plants, not a model of the purchased motor.
    // Exercise the real trajectory -> calibrated count rate -> PI -> feedback
    // chain across a calibration-slope change and two motor response gains.
    for(const double plant_gain:{3500.,6500.,-5000.}) {
        auto profile=bench_profile(); profile.feedforward=1./5000.;
        Fixture f(profile); f.sensing();
        Controller controller(calibration(),{},99);
        auto measurement=[&]{return Measurement{f.count,.1,11.1,false,true};};
        expect(controller.establish_reference(measurement())==Reason::ok,"plant reference failed");
        auto now_ms=f.io.time/1000;
        const Command command{99,1,7,now_ms+150,50,150,20,60};
        expect(controller.prepare(command,measurement(),now_ms,0)==Reason::ok,"plant prepare failed");
        expect(controller.commit(99,1,now_ms)==Reason::ok,"plant commit failed");
        expect(controller.renew_lease(99,1,now_ms,now_ms)==Reason::ok,"plant initial lease failed");
        std::uint64_t valid_until=(now_ms+300)*1000;
        ++f.io.time; auto e=f.evidence(); e.control_valid_until_us=valid_until;
        expect(f.executor.arm(e),"plant arm failed");
        double rate=0;
        bool completed=false, crossed_knot=false;
        for(int step=0;step<900;++step) {
            const double requested=f.io.request_high ? 0 : f.io.duty*plant_gain;
            rate+=(requested-rate)*.2; // 50 ms nominal response at a 10 ms step.
            f.count+=rate*.01;
            f.io.time+=10000;
            now_ms=f.io.time/1000;
            if(step%8==0) {
                expect(controller.renew_lease(99,1,now_ms,now_ms)==Reason::ok,"plant lease renewal failed");
                valid_until=(now_ms+300)*1000;
            }
            const auto output=controller.tick(measurement(),now_ms,0);
            e=f.evidence(); e.control_valid_until_us=valid_until;
            expect(f.executor.update(output,e),"plant executor rejected valid control cycle");
            if(now_ms<command.start_ms) expect(f.io.duty==0,"plant moved before scheduled start");
            crossed_knot |= f.count>1000;
            if(output.state==blinds::State::idle || output.state==blinds::State::unreferenced || output.state==blinds::State::fault) {
                completed=true;
                expect(f.io.request_high && f.io.duty==0,"controller stop left active output");
                if(plant_gain<0) {
                    expect(output.reason==Reason::wrong_direction,"reversed plant did not lose reference");
                } else {
                    expect(output.state==blinds::State::idle && crossed_knot,"plant failed before calibrated endpoint");
                    expect(std::abs(*calibration().height_at(f.count)-150)<=1,"closed-loop endpoint outside tolerance");
                }
                break;
            }
        }
        expect(completed,"closed-loop plant did not finish or fault within budget");
    }
}
int main() { slope(); lifecycle(); transfer_failures(); evidence_faults(); output_faults(); reversal_and_stall(); controller_plant(); std::cout<<"motion lifecycle, ordered I/O, PI/reversal, closed-loop plant and fault tests passed\n"; }
