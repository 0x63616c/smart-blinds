#include "smart_blinds/port_checks.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <limits>
using namespace blinds::port;
namespace {
void check(bool value,const char* label) { if(!value) { std::cerr<<label<<'\n'; std::exit(1); } }
Profile profile() { return {true,77,1,1,.5,540,0}; }
void measurements() {
    check(!Profile{}.valid(),"unqualified default allowed");
    auto p=profile();
    check(p.valid(),"qualified fixture profile rejected");
    check(current(p,2048,1080)==2.,"current conversion");
    p.current_zero_mv=10;
    check(current(p,0,0)==0.,"small negative noise not clamped");
    check(current(p,1000,550)==1.,"measured zero correction ignored");
    p.current_zero_mv=50;
    check(!current(p,0,0),"implausible negative current accepted");
    p=profile();
    for(int raw : {-1,4090,4095,65535}) check(!current(p,raw,1080),"saturated ADC accepted");
    for(int mv : {-1,3001,65535}) check(!current(p,2048,mv),"out-of-range voltage accepted");
    check(normalized_count(p,123,1000)==1123.,"positive count polarity");
    p.encoder_sign=-1;
    check(normalized_count(p,123,1000)==877.,"reverse encoder polarity");
    check(normalized_count(p,-123,1000)==1123.,"reverse raw count");
    check(!normalized_count(p,std::numeric_limits<int>::min(),0),"overflow count accepted");
    check(!normalized_count(p,100000000,0),"large accumulation accepted");
    check(!normalized_count(p,1,-1e12),"origin overflow accepted");
    check(!normalized_count(p,0,std::numeric_limits<double>::infinity()),"infinite origin accepted");
    std::array<Profile,10> invalid;
    invalid.fill(profile());
    invalid[0].bench_qualified=false; invalid[1].qualification_id=0;
    invalid[2].encoder_sign=0; invalid[3].motor_sign=2;
    invalid[4].max_duty=.81; invalid[5].max_duty=0;
    invalid[6].current_mv_per_a=0; invalid[7].current_zero_mv=101;
    invalid[8].max_duty=std::numeric_limits<double>::quiet_NaN();
    invalid[9].current_mv_per_a=std::numeric_limits<double>::infinity();
    for(const auto& bad:invalid) check(!bad.valid() && !current(bad,1000,500) && !normalized_count(bad,1,0),"bad profile produced trusted evidence");
}
CounterReadback counter(bool running) {
    CounterReadback r;
    r.routes_correct=r.pads_input_only=r.clock_enabled=r.edge_actions=r.level_actions=r.filter=r.limit_events=true;
    r.reset=false; r.paused=!running; r.high_limit=30000; r.low_limit=-30000;
    return r;
}
void counters() {
    check(!counter_valid({},false),"empty register image accepted");
    for(bool running:{false,true}) {
        auto good=counter(running); check(counter_valid(good,running),"counter valid state rejected");
        check(!counter_valid(good,!running),"counter running/paused mismatch accepted");
        const std::array<bool CounterReadback::*,7> required={&CounterReadback::routes_correct,&CounterReadback::pads_input_only,
            &CounterReadback::clock_enabled,&CounterReadback::edge_actions,&CounterReadback::level_actions,
            &CounterReadback::filter,&CounterReadback::limit_events};
        for(auto field:required) { auto bad=good; bad.*field=false; check(!counter_valid(bad,running),"counter configuration corruption accepted"); }
        auto bad=good; bad.reset=true; check(!counter_valid(bad,running),"counter held in reset accepted");
        bad=good; bad.high_limit=32767; check(!counter_valid(bad,running),"changed overflow limit accepted");
        bad=good; bad.low_limit=0; check(!counter_valid(bad,running),"unsigned/missing negative limit accepted");
    }
}
PwmReadback pwm(int direction=0,bool awake=true) {
    PwmReadback r;
    r.routes_correct=r.outputs_enabled=r.uninverted=r.plain_paths=r.timer_up=r.timer_select_zero=r.clock_divider_valid=true;
    r.immediate_force=r.comparator_tez=true; r.compare_pending=false;
    r.timer_running=awake; r.timer_stopped=!awake; r.period=500;
    r.action_a=0x12; r.action_b=0x42; r.force_a=r.force_b=1;
    if(direction==1) { r.force_a=0; r.compare_a=250; }
    if(direction==-1) { r.force_b=0; r.compare_b=250; }
    return r;
}
void outputs() {
    check(!pwm_valid({},0,0,false),"empty PWM image accepted");
    check(pwm_valid(pwm(0,false),0,0,false),"stopped coast rejected");
    check(!pwm_valid(pwm(0,true),0,0,false),"timer unexpectedly running while idle");
    for(int direction:{-1,0,1}) {
        const auto ticks=direction==0 ? 0U : 250U;
        const auto good=pwm(direction);
        check(pwm_valid(good,direction,ticks,true),"good PWM state rejected");
        const std::array<bool PwmReadback::*,10> required={&PwmReadback::routes_correct,&PwmReadback::outputs_enabled,
            &PwmReadback::uninverted,&PwmReadback::plain_paths,&PwmReadback::timer_up,&PwmReadback::timer_running,
            &PwmReadback::timer_select_zero,&PwmReadback::clock_divider_valid,&PwmReadback::immediate_force,
            &PwmReadback::comparator_tez};
        for(auto field:required) { auto bad=good; bad.*field=false; check(!pwm_valid(bad,direction,ticks,true),"PWM route/clock/control corruption accepted"); }
        auto bad=good; bad.period=499; check(!pwm_valid(bad,direction,ticks,true),"wrong PWM frequency accepted");
        bad=good; bad.action_a^=1; check(!pwm_valid(bad,direction,ticks,true),"wrong waveform A action accepted");
        bad=good; bad.action_b^=1; check(!pwm_valid(bad,direction,ticks,true),"wrong waveform B action accepted");
        bad=good; bad.force_a=bad.force_b=0; check(!pwm_valid(bad,direction,ticks,true),"both bridge inputs released");
        bad=good; (direction>0 ? bad.pad_b : bad.pad_a)=true;
        check(!pwm_valid(bad,direction,ticks,true),"inactive bridge input physically high");
        if(direction) {
            bad=good; bad.compare_pending=true; check(!pwm_valid(bad,direction,ticks,true),"unapplied shadow accepted");
            bad=good; (direction>0 ? bad.compare_a : bad.compare_b)=249;
            check(!pwm_valid(bad,direction,ticks,true),"stale duty readback accepted");
            check(!pwm_valid(good,direction,0,true) && !pwm_valid(good,direction,500,true),"invalid duty ticks accepted");
            check(!pwm_valid(good,-direction,ticks,true),"wrong physical direction accepted");
            check(!pwm_valid(good,direction,ticks,false),"PWM without awake lock accepted");
            bad=good; (direction>0 ? bad.pad_a : bad.pad_b)=true;
            check(pwm_valid(bad,direction,ticks,true),"active PWM pad sample phase incorrectly treated as steady low");
        }
    }
}
}
int main() { measurements(); counters(); outputs(); std::cout<<"C6 measurement bounds and register corruption checks passed\n"; }
