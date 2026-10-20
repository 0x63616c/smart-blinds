#include "smart_blinds/charger.hpp"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <vector>
using namespace smart_blinds::charger;
namespace {
void check(bool value,const char* why) {
    if(!value) { std::cerr<<why<<'\n';std::exit(1); }
}
struct ChargeGate:Inhibit {
    bool good=true,off=false;
    std::function<void()> hook;
    bool hold_off() override { if(hook) hook();off=good;return good; }
};
struct Stationary:ParkGuard {
    ParkIdentity current{41,43,47,11,53};
    bool good=true,off=false;
    std::function<void()> hook;
    ParkIdentity identity() const override { return current; }
    bool hold_off() override { if(hook) hook();off=good;return good; }
};
struct Notice:FailureSink {
    Error first=Error::none;
    unsigned calls=0;
    std::function<void()> hook;
    void failed(Error reason) noexcept override {
        if(!calls) first=reason;
        ++calls;if(hook) hook();
    }
};
// Independent event model: TI Table7-17, §7.3.4.5, Table7-43.
// No production profile/predicate is used to generate autonomous values.
struct Chip:Bus {
    ChargeGate& charge;
    std::array<std::uint8_t,0x49> memory{};
    std::uint64_t time=1000;
    unsigned calls=0,fail_at=0;
    std::vector<unsigned> writes;
    bool no_writes=false, require_motor=false;
    Stationary* motor=nullptr;
    std::function<void(unsigned,unsigned,bool)> before,after;
    explicit Chip(ChargeGate& gate):charge(gate) {
        memory[0x48]=0x19;memory[0x0A]=0xA3;memory[0x13]=0x21;
        memory[0x14]=0x16;memory[0x07]=10;memory[0x0F]=0xA2;
        memory[0x1B]=0x0F;memory[0x1C]=0x0A;memory[0x1D]=1;
    }
    void unplug() {
        memory[5]=36;memory[0x1B]&=0xF0;memory[0x1C]=0;
        memory[0x22]|=0x0F;
        // In this model AUTO_INDET_EN=0 preserves the host's IINDPM.
        check(memory[0x11]==0,"fake unplug called with unexpected automatic detection");
    }
    void plug(std::uint8_t threshold,bool power_good=true) {
        memory[5]=threshold;memory[0x1B]=(memory[0x1B]&0xF0)|(power_good?15:7);
        memory[0x1C]=power_good?0x16:0x10;
        memory[0x22]|=0x0F;
        check(memory[0x11]==0,"fake plug called with unexpected automatic detection");
    }
    bool step(unsigned reg,bool write) {
        check(charge.off,"access before charge inhibit");
        if(require_motor) check(motor && motor->off,"access before motor OFF");
        ++calls;++time;
        if(before) before(calls,reg,write);
        return calls!=fail_at;
    }
    bool read(std::uint8_t reg,std::uint8_t* bytes,std::size_t size) override {
        if(!step(reg,false)) return false;
        check(reg+size<=memory.size(),"bad read shape");
        std::copy_n(memory.data()+reg,size,bytes);
        for(std::size_t n=0;n<size;++n)
            if(reg+n>=0x22 && reg+n<=0x27) memory[reg+n]=0;
        if(after) after(calls,reg,false);
        return true;
    }
    bool write(std::uint8_t reg,const std::uint8_t* bytes,std::size_t size) override {
        check(!no_writes,"reconciliation wrote a register");
        if(!step(reg,true)) return false;
        check(size && size<=2 && reg+size<=memory.size(),"bad write shape");
        check(reg!=0x0F || !(bytes[0]&0x20),"EN_CHG enabled");
        check(reg!=0x12 || !(bytes[0]&0x40),"OTG enabled");
        check(reg!=0x09 || !(bytes[0]&0x40),"register reset");
        writes.push_back(reg);std::copy_n(bytes,size,memory.data()+reg);
        if(reg==0x10) memory[0x10]&=0xF7;
        if(reg==0x06 && (memory[0x14]&2)) { memory[6]=0;memory[7]=std::min(memory[7],std::uint8_t{10}); }
        if(after) after(calls,reg,true);
        return true;
    }
    std::uint64_t now_ms() const override { return time; }
    void wait_ms(unsigned delay) override { time+=delay; }
};
struct Fixture {
    ChargeGate charge;Stationary motor;Notice notice;
    Chip chip{charge};
    Bq25798 device{chip,charge,&notice};
    explicit Fixture(bool bound=true) {
        check(device.configure(SourceVoltage::nine)==Error::none,"configure failed");
        chip.motor=&motor;chip.require_motor=true;
        const auto result=bound?device.park_off(motor):device.park_off(static_cast<Inhibit&>(motor));
        check(result.valid(),"initial park failed");
        chip.no_writes=true;chip.calls=0;chip.writes.clear();
    }
    void protections() {
        check(chip.memory[6]==0 && chip.memory[7]==10 && chip.memory[0x14]==0x16 &&
              chip.memory[0x0F]==0x82 && chip.memory[0x11]==0 && chip.memory[0x10]==0x90 &&
              chip.memory[0x12]==0 && chip.memory[0x15]==0xAA &&
              charge.off && motor.off,"OFF protection changed");
    }
};
void accepted_events() {
    Fixture idle;const auto unchanged=idle.device.reconcile_parked(idle.motor);
    check(unchanged.valid() && !unchanged.source_event && unchanged.previous_vindpm==80 &&
          unchanged.observed_vindpm==80 && idle.device.parked(),"unchanged failed");
    idle.protections();
    for(const auto value:{36,76,136,220}) {
        Fixture f;f.chip.unplug();f.chip.plug(static_cast<std::uint8_t>(value),value!=36);
        const auto started=f.chip.time;
        const auto r=f.device.reconcile_parked(f.motor);
        check(r.valid() && r.source_event && r.previous_vindpm==80 && r.observed_vindpm==value &&
              r.observation.flags[0]==15 && r.observation.started_ms==started &&
              r.observation.finished_ms==f.chip.time && f.chip.memory[0x22]==0,
              "connected autonomous threshold rejected/history restamped");
        f.protections();check(f.chip.writes.empty(),"adoption wrote hardware");
        const auto repeat=f.device.reconcile_parked(f.motor);
        check(repeat.valid() && !repeat.source_event && repeat.previous_vindpm==value,
              "expected image not updated exactly");
        f.chip.no_writes=false;
        check(f.device.resume_off(f.motor).valid() &&
              f.chip.writes==std::vector<unsigned>{0x10},"resume did not retain opaque image");
        f.chip.writes.clear();
        check(f.device.capture_off().valid(),"resumed exact image rejected");
        check(!f.device.reconcile_parked(f.motor).valid(),"active object reconciled");
    }
    Fixture removed;removed.chip.unplug();
    const auto r=removed.device.reconcile_parked(removed.motor);
    check(r.valid() && !r.observation.source_present() && r.observed_vindpm==36,"unplug rejected");
    removed.protections();
    Fixture same;same.chip.unplug();same.chip.plug(80);
    check(same.device.reconcile_parked(same.motor).source_event,"equal threshold lost event");
    Fixture no_flag;no_flag.chip.unplug();no_flag.chip.memory[0x22]=0;
    check(no_flag.device.reconcile_parked(no_flag.motor).valid(),"observed present-state change rejected");
}
void no_implicit_authority() {
    Fixture plain(false);plain.chip.unplug();
    check(!plain.device.reconcile_parked(plain.motor).valid() && !plain.chip.calls,
          "ordinary park granted authority");
    Fixture f;f.chip.no_writes=false;
    Bq25798 adopted(f.chip,f.charge);
    check(adopted.adopt_parked(SourceVoltage::nine,f.motor).valid(),"enum adoption setup failed");
    f.chip.calls=0;f.chip.no_writes=true;f.chip.unplug();
    check(!adopted.reconcile_parked(f.motor).valid() && !f.chip.calls,"enum adoption granted authority");
    // An accepted dynamic threshold stays exact for the ordinary monitor.
    Fixture drift;drift.chip.unplug();check(drift.device.reconcile_parked(drift.motor).valid(),"setup failed");
    drift.chip.memory[5]=76;drift.chip.no_writes=false;
    check(!drift.device.resume_off(drift.motor).valid() && drift.chip.writes.empty(),
          "ordinary verification acquired a REG05 mask");
    Fixture raw;raw.chip.no_writes=false;
    check(!raw.device.resume_off(static_cast<Inhibit&>(raw.motor)).valid() && raw.chip.writes.empty(),
          "unbound resume bypassed parked ownership");
}
void bound_park_guards() {
    ChargeGate charge;Stationary motor;Chip chip(charge);Bq25798 device(chip,charge);
    check(device.configure(SourceVoltage::nine)==Error::none,"setup configure failed");
    chip.motor=&motor;chip.require_motor=true;chip.calls=0;
    check(device.park_off(motor).valid(),"bound park failed");
    const auto count=chip.calls;
    for(unsigned at=1;at<=count;++at) {
        ChargeGate g;Stationary m;Notice notice;Chip b(g);Bq25798 d(b,g,&notice);
        check(d.configure(SourceVoltage::nine)==Error::none,"setup configure failed");
        b.motor=&m;b.require_motor=true;b.calls=0;b.fail_at=at;
        check(!d.park_off(m).valid() && d.first_error()==Error::bus,"bound park failure ignored");
        b.fail_at=0;b.no_writes=true;b.unplug();
        check(!d.reconcile_parked(m).valid() && notice.calls==1,"failed park granted authority");
    }
    for(unsigned kind=0;kind<3;++kind) {
        ChargeGate g;Stationary m;Chip b(g);Bq25798 d(b,g);
        check(d.configure(SourceVoltage::nine)==Error::none,"setup configure failed");
        b.motor=&m;b.require_motor=true;b.calls=0;
        if(kind==0) m.current.boot=0;
        else b.after=[&](unsigned call,unsigned,bool) {
            if(call==count-2) {
                if(kind==1) ++m.current.pack;
                else b.unplug();
            }
        };
        check(!d.park_off(m).valid(),"invalid or changing bound park granted authority");
    }
}
void refusal_table() {
    for(unsigned kind=0;kind<10;++kind) {
        Fixture f;f.chip.unplug();
        if(kind==0) { f.chip.memory[5]=35; }
        if(kind==1) { f.chip.plug(221); }
        if(kind==2) { f.chip.memory[5]=76; }
        if(kind==3) { f.chip.plug(76);f.chip.memory[0x22]=8; }
        if(kind==4) { f.chip.plug(76);f.chip.memory[0x22]=0; }
        if(kind==5) { f.chip.memory[0x1B]|=8; }
        if(kind==6) { f.chip.memory[0x22]|=0x10; }
        if(kind==7) { f.chip.memory[0x1B]|=0x20; }
        if(kind==8) { f.chip.memory[0x22]|=0x20; }
        if(kind==9) { f.chip.memory[0x48]=0x18; }
        const auto r=f.device.reconcile_parked(f.motor);
        check(!r.valid() && f.chip.writes.empty() && !f.device.parked() &&
              !f.device.configured() && f.notice.calls==1,"unsafe source/image accepted");
    }
    // Independent protected-byte inventory, not generated from profile().
    constexpr std::array<unsigned,27> bytes{0,1,2,3,4,6,7,8,9,10,13,14,15,16,17,18,19,20,
                                            21,22,23,24,46,47,48,71,72};
    for(auto reg:bytes) for(unsigned bit=0;bit<8;++bit) {
        Fixture f;f.chip.unplug();f.chip.memory[reg]^=1U<<bit;
        check(!f.device.reconcile_parked(f.motor).valid() && f.chip.writes.empty(),
              "non-REG05 bit drift tolerated");
    }
}
void transfer_and_context_faults() {
    Fixture good;good.chip.unplug();check(good.device.reconcile_parked(good.motor).valid(),"setup failed");
    const auto count=good.chip.calls;
    for(unsigned at=1;at<=count;++at) {
        Fixture f;f.chip.unplug();f.chip.fail_at=at;
        const auto r=f.device.reconcile_parked(f.motor);
        check(!r.valid() && f.device.first_error()==Error::bus &&
              f.device.transition_failure()==Error::bus && f.notice.calls==1,
              "read failure ignored");
        // Neither successful words nor later configure/clock faults repair it.
        f.chip.fail_at=0;f.chip.time=0;f.chip.no_writes=false;
        check(!f.device.reconcile_parked(f.motor).valid(),"failed object revived");
        check(f.device.configure(SourceVoltage::nine)!=Error::none &&
              f.device.first_error()==Error::bus && f.notice.first==Error::bus &&
              f.notice.calls==1 && f.chip.writes.empty(),"first cause erased");
    }
    for(unsigned field=0;field<5;++field) for(unsigned at:{0U,3U,count}) {
        Fixture f;f.chip.unplug();
        const auto change=[&] {
            if(field==0) ++f.motor.current.boot;
            if(field==1) ++f.motor.current.pack;
            if(field==2) ++f.motor.current.qualification;
            if(field==3) ++f.motor.current.epoch;
            if(field==4) ++f.motor.current.owner;
        };
        if(!at) change();
        else f.chip.after=[&](unsigned call,unsigned,bool) { if(call==at) change(); };
        check(!f.device.reconcile_parked(f.motor).valid() && f.chip.writes.empty(),
              "binding loss accepted");
        if(!at) check(!f.chip.calls,"wrong binding accessed bus");
    }
    for(unsigned at:{0U,3U,count}) {
        Fixture f;f.chip.unplug();
        if(!at) f.motor.good=false;
        else f.chip.after=[&](unsigned call,unsigned,bool) { if(call==at) f.motor.good=false; };
        check(!f.device.reconcile_parked(f.motor).valid(),"lost physical OFF accepted");
    }
    Fixture primary;primary.chip.unplug();primary.chip.memory[0x25]=2;
    primary.notice.hook=[&] { primary.charge.good=false; };
    const auto result=primary.device.reconcile_parked(primary.motor);
    check(result.observation.flags[3]==2 && primary.device.first_error()==Error::temperature &&
          primary.device.inhibit_failed() && result.observation.error==Error::inhibit,
          "thermal history/first cause lost during inhibit failure");
}
void edge_races_and_time() {
    Fixture good;good.chip.unplug();check(good.device.reconcile_parked(good.motor).valid(),"setup failed");
    const auto count=good.chip.calls;
    // Every intermediate bus boundary sees an additional source event.
    for(unsigned at=3;at<count;++at) {
        Fixture f;f.chip.unplug();
        f.chip.after=[&](unsigned call,unsigned,bool) {
            if(call==at) { f.chip.plug(136);f.chip.unplug(); } // Same final state, new edge.
        };
        check(!f.device.reconcile_parked(f.motor).valid(),"mid-read source edge accepted");
    }
    for(unsigned reg:{0x20,0x21,0x25,0x26,0x27,0x22}) {
        for(unsigned at:{1U,20U,count-2}) {
            Fixture f;f.chip.unplug();
            f.chip.before=[&](unsigned call,unsigned,bool) {
                if(call==at) f.chip.memory[reg]|=reg==0x22?0x20:1;
            };
            const auto r=f.device.reconcile_parked(f.motor);
            check(!r.valid() && f.notice.calls==1,"late fault lost");
        }
    }
    for(unsigned duration:{250U,251U,750U,751U}) {
        Fixture f;f.chip.unplug();
        f.chip.before=[&](unsigned call,unsigned,bool) {
            if(call==count) f.chip.time+=duration-count;
        };
        const auto r=f.device.reconcile_parked(f.motor);
        check(r.valid()==(duration==250),"operation duration boundary wrong");
    }
    Fixture reversed;reversed.chip.unplug();
    reversed.chip.before=[&](unsigned call,unsigned,bool) { if(call==4) reversed.chip.time=0; };
    check(!reversed.device.reconcile_parked(reversed.motor).valid() &&
          reversed.device.first_error()==Error::clock,"reversed clock accepted");
    Fixture resume;resume.chip.unplug();check(resume.device.reconcile_parked(resume.motor).valid(),"setup failed");
    resume.chip.calls=0;resume.chip.no_writes=false;
    resume.chip.before=[&](unsigned call,unsigned,bool) { if(call==3) resume.chip.plug(136); };
    check(!resume.device.resume_off(resume.motor).valid() && resume.chip.writes.empty(),
          "new source edge hidden by watchdog restore");
    Fixture equal;equal.chip.unplug();equal.chip.plug(80);
    check(!equal.device.resume_off(equal.motor).valid() && equal.chip.writes.empty(),
          "equal-threshold edge bypassed explicit reconciliation");
    for(unsigned field=0;field<5;++field) {
        Fixture f;f.chip.no_writes=false;
        if(field==0) ++f.motor.current.boot;
        if(field==1) ++f.motor.current.pack;
        if(field==2) ++f.motor.current.qualification;
        if(field==3) ++f.motor.current.epoch;
        if(field==4) ++f.motor.current.owner;
        check(!f.device.resume_off(f.motor).valid() && f.chip.writes.empty(),
              "resume lost parked ownership");
    }
}
}
int main() {
    accepted_events();no_implicit_authority();bound_park_guards();refusal_table();
    transfer_and_context_faults();edge_races_and_time();
    std::cout<<"parked source reconciliation tests passed\n";
}
