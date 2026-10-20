#pragma once
#include "smart_blinds/motion_session.hpp"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <functional>
#include <vector>
#include <string>

namespace session_test {
using namespace blinds;
inline void check(bool ok,const char* message) { if(!ok) { std::cerr<<message<<'\n'; std::exit(1); } }
struct Io : MotionIo,CounterOrigin {
    std::uint64_t now=2000000,epoch=0;
    unsigned calls=0,pulses=0,fail_at=0,slow_at=0,operation_us=1;
    mutable unsigned clock_reads=0;
    unsigned reversed_read=0;
    bool request_high=true,encoder=false,counter=false,awake=false,parked_readback=true;
    double count=500,origin=500,duty=0;
    std::vector<std::string> log;
    std::uint64_t now_us() const override { return ++clock_reads==reversed_read ? now-1 : now; }
    bool parked_off() override { return action("parked") && parked_readback && request_high && !encoder && !counter && !awake && duty==0; }
    bool action(const char* name) { log.emplace_back(name); ++calls; now+=calls==slow_at ? 101 : operation_us; return calls!=fail_at; }
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
inline Calibration calibration() {
    Calibration c; const Knot k[]={{0,0},{1000,100},{3000,200}};
    check(c.assign(k,3,7),"calibration fixture invalid"); return c;
}
inline BenchMotionProfile profile() {
    BenchMotionProfile p; p.bench_qualified=p.holding_qualified=true; p.qualification_id=123;
    p.feedforward=.00025; return p;
}
struct Fixture {
    Io io;
    MotionSession session;
    MotionSession::Inbox inbox{99};
    SessionInput input;
    std::uint64_t sample=0,message=0,probe=1,offset=500000;
    explicit Fixture(BenchMotionProfile p=profile(),Calibration c=calibration(),Limits l={}) : session(io,io,c,l,p,99) {
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
    MotionSession::Status cycle(std::optional<LocalIntent> local={}) { return session.cycle(inbox,input,local); }
    MotionSession::Status tick(const std::function<void(SessionInput&)>& mutate={},std::optional<LocalIntent> local={}) {
        if(io.counter) io.count+=io.duty*4000*.01; // Synthetic plant only.
        io.now+=10000; refresh(); if(mutate) mutate(input); return cycle(local);
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
}
