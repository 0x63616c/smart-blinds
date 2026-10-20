#include "smart_blinds/charger.hpp"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>
#include <utility>
using namespace smart_blinds::charger;
void require(bool value, const char* message) { if (!value) { std::cerr << message << '\n'; std::exit(1); } }

struct Gate final : Inhibit {
    bool off = false, works = true;
    unsigned requests = 0;
    bool hold_off() override { ++requests; off = works; return works; }
};
struct FakeBus final : Bus {
    Gate& gate;
    std::array<std::uint8_t,0x49> memory{};
    std::uint64_t time = 1000, conversion_done = 0;
    unsigned calls = 0, fail_at = 0, step_ms = 1;
    bool adc_stuck = false, adc_ignored = false, frozen_clock = false;
    int corrupt_address = -1;
    std::vector<unsigned> writes;
    explicit FakeBus(Gate& g) : gate(g) {
        memory[0x48]=0x19; memory[0x0A]=0xA3; memory[0x13]=0x21;
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
    require(success.bus.memory[6]==0 && success.bus.memory[7]==150,"input current image wrong");
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
int main() {
    profile_and_faults(); captures(); readiness(); battery_only_status();
    std::cout << "charger profile, every-transfer faults, fresh ADC and readiness boundaries passed\n";
}
