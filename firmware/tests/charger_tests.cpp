#include "smart_blinds/charger.hpp"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <functional>
#include <vector>
#include <utility>
using namespace smart_blinds::charger;
void require(bool value, const char* message) { if (!value) { std::cerr << message << '\n'; std::exit(1); } }

struct Gate final : Inhibit {
    bool off = false, works = true;
    unsigned requests = 0;
    std::function<void()> during;
    bool hold_off() override { ++requests;if(during) during();off = works; return works; }
};
struct FakeBus final : Bus {
    Gate& gate;
    std::array<std::uint8_t,0x49> memory{};
    std::uint64_t time = 1000, conversion_done = 0;
    unsigned calls = 0, fail_at = 0, step_ms = 1;
    unsigned ilim_steps = 10; // 100 mA minimum, 10 mA units; TI section 7.3.4.3.
    bool adc_stuck = false, adc_ignored = false, frozen_clock = false;
    int corrupt_address = -1;
    std::vector<unsigned> writes;
    explicit FakeBus(Gate& g) : gate(g) {
        memory[0x48]=0x19; memory[0x0A]=0xA3; memory[0x13]=0x21;
        memory[0x14]=0x16; word(0x06,ilim_steps); // External limit enabled at reset.
        memory[0x0F]=0xA2; memory[0x1B]=0x0F; memory[0x1C]=0x0A; memory[0x1D]=1;
        word(0x35,9000); word(0x3B,11100); word(0x3D,11100); word(0x3F,600); word(0x41,50);
    }
    void word(unsigned reg, unsigned value) { memory[reg]=value>>8; memory[reg+1]=value&255; }
    bool advance() {
        require(gate.off,"bus operation occurred before independent charge inhibit");
        if (!frozen_clock) time += step_ms;
        if (conversion_done && time >= conversion_done && !adc_stuck) {
            memory[0x2E]=0x40; memory[0x1E]|=0x20; memory[0x24]|=0x20; conversion_done=0;
        }
        return ++calls != fail_at;
    }
    bool read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size) override {
        if (!advance()) return false;
        require(reg+size<=memory.size(),"read outside documented register map");
        std::copy_n(memory.data()+reg,size,bytes);
        if (reg==corrupt_address) bytes[0]^=1;
        for (std::size_t i=0;i<size;++i) if (reg+i>=0x22 && reg+i<=0x27) memory[reg+i]=0;
        return true;
    }
    bool write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size) override {
        if (!advance()) return false;
        require(size<=2 && reg+size<=memory.size(),"invalid register write shape");
        require(reg!=0x0F || !(bytes[0]&0x20),"configuration enabled charging");
        require(reg!=0x12 || !(bytes[0]&0x40),"configuration enabled OTG");
        require(reg!=0x09 || !(bytes[0]&0x40),"configuration reset registers");
        writes.push_back(reg);
        if (reg==0x2E && bytes[0]==0xC0 && adc_ignored) return true;
        std::copy_n(bytes,size,memory.data()+reg);
        // One documented clamp-compatible write model: an excessive request
        // cannot read back above ILIM while EN_EXTILIM remains set. This does
        // not claim silicon's exact ADC rounding or rejected-write behavior.
        if(reg==0x06 && size==2 && (memory[0x14]&2))
            word(0x06,std::min<unsigned>((bytes[0]<<8)|bytes[1],ilim_steps));
        if (reg==0x10) memory[0x10]&=~0x08; // WD_RST is self-clearing.
        if (reg==0x2E && bytes[0]==0xC0) {
            conversion_done=time+216; // Nine 15-bit channels, typical 24 ms/channel.
            memory[0x1E]&=~0x20; memory[0x24]&=~0x20;
        }
        return true;
    }
    std::uint64_t now_ms() const override { return time; }
    void wait_ms(unsigned duration) override { if (!frozen_clock) time+=duration; }
};
struct Fixture {
    Gate gate;
    FakeBus bus{gate};
    Bq25798 device{bus,gate};
    void configure() { require(device.configure(SourceVoltage::nine)==Error::none,"valid configuration rejected"); }
};
void profile_and_faults() {
    Fixture success;
    success.configure();
    const auto operations=success.bus.calls;
    require(success.bus.memory[1]==0x04 && success.bus.memory[2]==0xDD,"VREG big-endian 12.45 V image wrong");
    require(success.bus.memory[3]==0 && success.bus.memory[4]==100,"charge current image wrong");
    require(success.bus.memory[6]==0 && success.bus.memory[7]==10,"input current image wrong");
    require(success.bus.memory[0x17]==0 && success.bus.memory[0x18]==0x44,"JEITA suspend image wrong");
    require(success.bus.memory[0x09]==0x25 && success.bus.memory[0x10]==0x93,"watchdog stop policy missing");
    require(success.bus.memory[0x0F]==0x82 && success.gate.off,"charge-off invariant lost");
    for (unsigned fault=1;fault<=operations;++fault) {
        Fixture f; f.bus.fail_at=fault;
        require(f.device.configure(SourceVoltage::nine)==Error::bus,"injected transfer fault ignored");
        require(!f.device.configured() && f.gate.off && f.gate.requests>=2,"fault left configuration/permission valid");
    }
    for (const auto& reg : profile(SourceVoltage::nine)) {
        Fixture f; f.bus.corrupt_address=reg.address;
        require(f.device.configure(SourceVoltage::nine)!=Error::none,"mutated register readback accepted");
        require(!f.device.configured() && f.gate.off,"readback error kept readiness");
    }
    Fixture identity; identity.bus.memory[0x48]=0x18;
    require(identity.device.configure(SourceVoltage::nine)==Error::identity && identity.bus.writes.empty(),"unknown silicon revision was written");
    Fixture strap; strap.bus.memory[0x0A]=0x63;
    require(strap.device.configure(SourceVoltage::nine)==Error::strap && strap.bus.writes.empty(),"wrong cell strapping was overwritten");
    Fixture frequency; frequency.bus.memory[0x13]=1;
    require(frequency.device.configure(SourceVoltage::nine)==Error::strap,"wrong frequency accepted");
    Fixture blocked; blocked.gate.works=false;
    require(blocked.device.configure(SourceVoltage::nine)==Error::inhibit && !blocked.bus.calls,"failed inhibit still accessed I2C");
    Fixture slow; slow.bus.step_ms=200;
    require(slow.device.configure(SourceVoltage::nine)==Error::timeout,"configuration timeout ignored");
    Fixture fifteen;
    require(fifteen.device.configure(SourceVoltage::fifteen)==Error::none && fifteen.bus.memory[5]==130,"15 V VINDPM profile wrong");
}
void external_ilim_compatibility() {
    for(auto voltage : {SourceVoltage::nine,SourceVoltage::fifteen}) {
        // Every representable 100..300 mA hardware clamp around the existing
        // divider range, plus the chip's minimum, must admit the OFF setting.
        for(unsigned clamp=10;clamp<=30;++clamp) {
            Fixture f;f.bus.ilim_steps=clamp;f.gate.hold_off();
            const std::uint8_t old_request[]{0,150};
            require(f.bus.write(0x06,old_request,2),"clamp test write failed");
            require(((f.bus.memory[6]<<8)|f.bus.memory[7])==static_cast<int>(clamp),
                    "ILIM-aware fake accepted the old 1.5 A setting");
            require(f.device.configure(voltage)==Error::none,"OFF profile exceeds hardware clamp");
            const auto protected_profile=[&] {
                require(f.bus.memory[6]==0 && f.bus.memory[7]==10 && f.bus.memory[0x14]==0x16 &&
                        f.bus.memory[0x0F]==0x82 && f.gate.off,
                        "OFF profile lost minimum current or independent protection");
            };
            protected_profile();
            require(f.device.capture_off().valid(),"OFF capture rejected minimum-current profile");
            Gate motor;
            require(f.device.park_off(motor).valid(),"minimum-current park failed");protected_profile();
            Bq25798 adopted(f.bus,f.gate);f.bus.writes.clear();
            require(adopted.adopt_parked(voltage,motor).valid() && f.bus.writes.empty(),
                    "minimum-current adoption changed parked hardware");
            require(adopted.resume_off(motor).valid(),"minimum-current resume failed");protected_profile();
            require(adopted.capture_off().valid(),"resumed minimum-current capture failed");
        }
    }
}
void captures() {
    Fixture success; success.configure(); success.bus.calls=0;
    const auto report=success.device.capture();
    require(report.valid() && report.vbus_mv()==9000 && report.battery_mv()==11100,"valid fresh capture rejected");
    require(report.finished_ms-report.conversion_started_ms>=216,"capture did not await conversion");
    const auto operations=success.bus.calls;
    for (unsigned fault=1;fault<=operations;++fault) {
        Fixture f; f.configure(); f.bus.calls=0; f.bus.fail_at=fault;
        require(!f.device.capture().valid() && !f.device.configured() && f.gate.off,"capture transfer fault accepted");
    }
    for (auto address : {0x1B,0x20,0x21,0x26,0x27}) {
        Fixture f; f.configure(); f.bus.memory[address]|=(address==0x1B ? 0x20 : 0x04);
        require(!f.device.capture().valid() && !f.device.configured(),"watchdog/fault status ignored");
    }
    for (unsigned temperature_bit : {1,2,4,8}) {
        Fixture f; f.configure(); f.bus.memory[0x1F]=temperature_bit;
        require(f.device.capture().error==Error::temperature,"unsafe TS state accepted");
    }
    Fixture stuck; stuck.configure(); stuck.bus.adc_stuck=true;
    require(stuck.device.capture().error==Error::timeout,"stalled ADC never timed out");
    Fixture frozen; frozen.configure(); frozen.bus.frozen_clock=true; frozen.bus.adc_stuck=true;
    require(frozen.device.capture().error==Error::timeout,"frozen clock allowed unbounded polling");
    Fixture old; old.configure(); old.bus.adc_ignored=true; old.bus.memory[0x1E]=0x20; old.bus.memory[0x24]=0x20;
    require(old.device.capture().error==Error::adc,"old ADC completion accepted as new sample");
    Fixture changed; changed.configure(); changed.bus.memory[0x17]=0x7A;
    require(changed.device.capture().error==Error::readback,"reset JEITA settings accepted");
    require(changed.device.capture().error==Error::unconfigured,"failed capture recovered implicitly");
    Fixture timer; timer.configure(); timer.bus.memory[0x24]=0x08;
    require(timer.device.capture().error==Error::status,"latched fast-charge timer expiry ignored");
    Fixture transition; transition.configure(); transition.bus.memory[0x25]=0x02;
    require(transition.device.capture().error==Error::temperature,"temperature transition history ignored");
    Fixture reversed; reversed.configure(); reversed.bus.time=0;
    require(reversed.device.capture().error==Error::clock,"clock reversal across operations accepted");
    Fixture inhibit_failed; inhibit_failed.configure(); inhibit_failed.gate.works=false;
    require(inhibit_failed.device.capture().error==Error::inhibit,"inhibit failure hidden by valid configuration");
}
void readiness() {
    Fixture f; f.configure(); const auto c=f.device.capture();
    const auto now=f.bus.time;
    PackEvidence p{now,42,true,true,true,true,true,{3700,3700,3700},{250,250}};
    SourceEvidence s{now,51,9000,2500,true,true,true};
    require(assess(c,p,s,true,now)==Readiness::ready_for_review,"complete simulated evidence rejected");
    require(assess(c,{},s,true,now)==Readiness::evidence_missing,"raw/uncommissioned pack became ready");
    require(assess(c,p,s,false,now)==Readiness::motion,"charging assessment allowed moving motor");
    require(assess(c,p,s,true,now+251)==Readiness::stale,"stale evidence accepted");
    s.sampled_ms=now+1;
    require(assess(c,p,s,true,now)==Readiness::stale,"future evidence accepted"); s.sampled_ms=now;
    s.current_ma=1500;
    require(assess(c,p,s,true,now)==Readiness::source,"unqualified source current accepted"); s.current_ma=2500;
    s.voltage_mv=5000;
    require(assess(c,p,s,true,now)==Readiness::source,"5 V fallback accepted"); s.voltage_mv=9000;
    p.cell_mv[0]=4200;
    require(assess(c,p,s,true,now)==Readiness::pack,"high individual cell ignored"); p.cell_mv[0]=3700;
    p.temperature_deci_c[1]=400;
    require(assess(c,p,s,true,now)==Readiness::temperature,"hot pack accepted");
    require(f.gate.off && !(f.bus.memory[0x0F]&0x20),"readiness assessment actuated charge");
}
void battery_only_status() {
    Fixture f; f.configure();
    f.bus.memory[0x1B]=0; f.bus.memory[0x1C]=0; // USB absent; battery remains present.
    f.bus.memory[0x22]=0x0F; // Ordinary removal / power-good transitions.
    f.bus.writes.clear(); f.bus.calls=0;
    const auto off=f.device.capture_off();
    require(off.valid() && !off.source_present(),"unplugged healthy OFF observation rejected");
    require(off.flags[0]==0x0F,"off capture discarded transition history");
    require(f.bus.writes==std::vector<unsigned>{0x10},"off capture started ADC/charge or changed unrelated state");
    require(f.gate.off && f.bus.memory[0x0F]==0x82,"off capture enabled charging");
    const auto calls=f.bus.calls;
    for(unsigned i=1;i<=calls;++i) {
        Fixture bad; bad.configure(); bad.bus.calls=0; bad.bus.fail_at=i;
        require(!bad.device.capture_off().valid() && !bad.device.configured() && bad.gate.off,"off capture transfer error accepted");
    }
    const std::array<std::pair<unsigned,unsigned>,15> faults={{{0x1B,0x20},{0x22,0x20},{0x1C,0x20},
        {0x1C,7<<1},{0x1C,12<<1},{0x1C,9<<1},{0x1D,0},{0x1D,0x05},{0x1D,0x03},
        {0x1E,0x02},{0x24,0x02},{0x20,1},{0x27,1},{0x1F,1},{0x25,1}}};
    for(const auto& item:faults) {
        Fixture bad; bad.configure(); bad.bus.memory[item.first]=item.second;
        require(!bad.device.capture_off().valid() && !bad.device.configured() && bad.gate.off,"off capture unsafe status accepted");
    }
    Fixture changed; changed.configure(); changed.bus.memory[0x12]=0x40;
    require(changed.device.capture_off().error==Error::readback,"OTG setting mismatch accepted");
    Fixture stale; stale.configure(); stale.bus.step_ms=10;
    require(stale.device.capture_off().error==Error::timeout,"slow off observation accepted");
    Fixture unknown;
    require(unknown.device.capture_off().error==Error::unconfigured && unknown.bus.writes.empty(),"unconfigured off capture wrote registers");
}
void first_failure_notice() {
    struct Notice final:FailureSink {
        Error first=Error::none;unsigned calls=0;
        void failed(Error reason) noexcept override { if(!calls) first=reason;++calls; }
    };
    for(unsigned kind=0;kind<6;++kind) {
        Gate gate;FakeBus bus(gate);Notice notice;Bq25798 device(bus,gate,&notice);
        require(device.configure(SourceVoltage::nine)==Error::none && notice.calls==0,
                "healthy configure emitted failure");
        bus.calls=0;
        Error expected=Error::bus;
        if(kind==0) bus.fail_at=1;
        if(kind==1) { bus.memory[0x48]=0;expected=Error::identity; }
        if(kind==2) { bus.memory[0x12]=0x40;expected=Error::readback; }
        if(kind==3) { bus.step_ms=20;expected=Error::timeout; }
        if(kind==4) { bus.time=0;expected=Error::clock; }
        if(kind==5) { gate.works=false;expected=Error::inhibit; }
        bool cleanup_seen=false;
        gate.during=[&]{
            if(notice.calls) {
                cleanup_seen=true;
                require(notice.calls==1 && notice.first==expected && device.first_error()==expected &&
                        !device.configured(),"first notice delayed until after inhibit/return");
                gate.works=false; // Secondary OFF failure is diagnostic, not primary.
            }
        };
        const auto result=device.capture_off();
        require(cleanup_seen && result.error==Error::inhibit && device.inhibit_failed() &&
                device.first_error()==expected && notice.calls==1 && notice.first==expected,
                "secondary inhibit replaced first failure or emitted duplicate notice");
    }
    // With no sink, existing caller-visible inhibit precedence is unchanged.
    Fixture legacy;legacy.configure();legacy.bus.fail_at=legacy.bus.calls+1;
    legacy.gate.during=[&]{if(legacy.bus.calls==legacy.bus.fail_at) legacy.gate.works=false;};
    require(legacy.device.capture_off().error==Error::inhibit && legacy.device.first_error()==Error::bus,
            "optional sink changed legacy error contract");
}

void off_park_transitions() {
    for(bool wake:{false,true}) {
        Fixture good;good.configure();Gate motor;
        if(wake) require(good.device.park_off(motor).valid(),"park setup failed");
        good.bus.calls=0;good.bus.writes.clear();
        // Hours of stationary idle are not a synthetic MCU reset.
        if(wake) good.bus.time+=8*60*60*1000;
        const auto report=wake ? good.device.resume_off(motor):good.device.park_off(motor);
        require(report.valid() && good.device.parked()!=wake && good.device.configured()==wake,
                "valid OFF transition rejected");
        require(good.bus.memory[0x10]==(wake ? 0x93:0x90) &&
                good.bus.writes==std::vector<unsigned>{0x10},"wrong watchdog/image transition");
        require(good.bus.memory[0x0F]==0x82 && good.bus.memory[0x11]==0 &&
                good.bus.memory[0x16]==0x30 && good.bus.memory[0x17]==0 &&
                good.bus.memory[0x18]==0x44 && good.gate.off && motor.off,
                "OFF park changed protections, input detection or permissions");
        const auto calls=good.bus.calls;
        for(unsigned i=1;i<=calls;++i) {
            Fixture f;f.configure();Gate m;
            if(wake) require(f.device.park_off(m).valid(),"fault setup park failed");
            f.bus.calls=0;f.bus.writes.clear();f.bus.fail_at=i;
            const auto bad=wake ? f.device.resume_off(m):f.device.park_off(m);
            require(bad.error==Error::bus && f.device.transition_failure()==Error::bus &&
                    !f.device.configured() && !f.device.parked() && f.gate.off,
                    "park/wake transfer fault accepted");
            const auto prior_writes=f.bus.writes.size();f.bus.fail_at=0;
            require(f.device.configure(SourceVoltage::nine)!=Error::none &&
                    f.bus.writes.size()==prior_writes && f.device.transition_failure()==Error::bus,
                    "later configure repaired failed transition or lost first cause");
        }
        for(const auto& reg:profile(SourceVoltage::nine)) {
            Fixture f;f.configure();Gate m;
            if(wake) require(f.device.park_off(m).valid(),"readback setup failed");
            f.bus.writes.clear();f.bus.corrupt_address=reg.address;
            require(!(wake ? f.device.resume_off(m):f.device.park_off(m)).valid() &&
                    f.bus.writes.empty(),"wrong pre-transition image was overwritten");
        }
        for(const auto& item:std::array<std::pair<unsigned,unsigned>,5>{{
                {0x22,0x20},{0x25,2},{0x26,1},{0x27,1},{0x1F,4}}}) {
            Fixture f;f.configure();Gate m;
            if(wake) require(f.device.park_off(m).valid(),"guard setup failed");
            f.bus.writes.clear();f.bus.memory[item.first]=item.second;
            // A bad configuration must not hide first-read-clear history.
            f.bus.memory[0x17]=0x7A;
            const auto bad=wake ? f.device.resume_off(m):f.device.park_off(m);
            require(!bad.valid() && bad.error!=Error::readback && f.bus.writes.empty(),
                    "history lost behind profile mismatch or transition write");
            if(item.first>=0x22) require(bad.flags[item.first-0x22]==item.second,
                    "returned report discarded clear-on-read evidence");
        }
        // Fail actual motor OFF after a completed SDK read, before next transfer.
        Fixture moved;moved.configure();Gate m;
        if(wake) require(moved.device.park_off(m).valid(),"OFF test setup failed");
        moved.bus.calls=0;moved.bus.writes.clear();
        m.during=[&]{if(moved.bus.calls) m.works=false;};
        require((wake ? moved.device.resume_off(m):moved.device.park_off(m)).error==Error::inhibit &&
                moved.bus.calls==1 && moved.bus.writes.empty(),"motor OFF loss ignored between transfers");
        Fixture ce;ce.configure();Gate cm;
        if(wake) require(ce.device.park_off(cm).valid(),"CE test setup failed");
        ce.bus.calls=0;ce.bus.writes.clear();ce.gate.during=[&]{if(ce.bus.calls) ce.gate.works=false;};
        require((wake ? ce.device.resume_off(cm):ce.device.park_off(cm)).error==Error::inhibit &&
                ce.bus.calls==1 && ce.bus.writes.empty(),"CE OFF loss ignored between transfers");
    }
    // New cold monitoring objects may adopt only a fully verified park image.
    Fixture hardware;hardware.configure();Gate motor_guard;
    require(hardware.device.park_off(motor_guard).valid(),"adopt setup failed");
    Bq25798 adopted(hardware.bus,hardware.gate);
    hardware.bus.calls=0;hardware.bus.writes.clear();
    require(adopted.adopt_parked(SourceVoltage::nine,motor_guard).valid() && adopted.parked() &&
            hardware.bus.writes.empty(),"park adoption wrote or invented state");
    const auto adopt_calls=hardware.bus.calls;
    for(unsigned failure=1;failure<=adopt_calls;++failure) {
        Fixture f;f.configure();Gate m;require(f.device.park_off(m).valid(),"adopt fault setup failed");
        Bq25798 fresh(f.bus,f.gate);f.bus.calls=0;f.bus.fail_at=failure;f.bus.writes.clear();
        require(fresh.adopt_parked(SourceVoltage::nine,m).error==Error::bus &&
                !fresh.configured() && !fresh.parked() && f.bus.writes.empty(),"adopt transfer failure accepted");
        f.bus.fail_at=0;
        require(fresh.configure(SourceVoltage::nine)!=Error::none && f.bus.writes.empty(),"failed adoption auto-repaired");
    }
    Fixture history;history.bus.memory[0x25]=2;
    require(history.device.configure(SourceVoltage::nine)==Error::temperature && history.bus.writes.empty(),
            "initial configure erased TS history before checking it");
    Fixture parked;parked.configure();Gate motor;require(parked.device.park_off(motor).valid(),"park failed");
    require(!parked.device.capture_off().valid(),"parked charger published active evidence");
    Fixture active;active.configure();Gate m;
    require(!active.device.resume_off(m).valid(),"resume without park accepted");
}
int main() {
    profile_and_faults(); external_ilim_compatibility(); captures(); readiness(); battery_only_status();first_failure_notice();off_park_transitions();
    std::cout << "charger profile, every-transfer faults, fresh ADC and readiness boundaries passed\n";
}
