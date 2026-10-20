#pragma once
#include "smart_blinds/charger.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>

namespace blinds::power {
// Transport data only. Read timestamps are not ADC conversion timestamps.
struct GaugeCapture {
    bool valid=false;
    std::int64_t read_started_us=0, read_finished_us=0;
    std::uint16_t dev_name=0, status=0, protection_status=0, battery_status=0;
    std::uint16_t soc=0, pack_voltage=0, current=0, temperature=0;
    std::array<std::uint16_t,3> cells{};
    std::uint16_t pack_config=0, nv_config0=0, nv_config1=0, sense_resistor=0;
    std::uint16_t status2=0, fstat=0, fet_status=0, hibernate_config=0, thermistor_config=0, protected_voltage=0;
    std::array<std::uint16_t,2> thermistors{};
};
struct PackProfile {
    // Issued only by the trusted local commissioning/verification path. There
    // is no network operation to set these, nor a production profile supplied.
    bool full_profile_verified=false, timing_verified=false, sensor_placement_verified=false;
    std::uint64_t verified_for_boot=0, qualification_id=0, pack_binding=0;
    std::uint16_t dev_name=0, pack_config=0, nv_config0=0, nv_config1=0, sense_resistor=0;
    std::uint16_t hibernate_config=0, thermistor_config=0;
    // 351.5 ms active tasks and 1.4 s * 2 thermistors are nominal source timing,
    // not guaranteed worst-case bounds. Explicit bench qualification is required.
    std::uint64_t voltage_period_bound_us=400000, temperature_period_bound_us=3200000;
    bool valid(std::uint64_t boot) const {
        return boot && verified_for_boot==boot && qualification_id && pack_binding && dev_name &&
            full_profile_verified && timing_verified && sensor_placement_verified &&
            (pack_config&0x281F)==0x2009 && // BtPkEn, exactly 3S + TH1/TH2.
            (nv_config1&0x0140)==0x0140 && !(hibernate_config&0x8000) && sense_resistor==1000 && thermistor_config==0x91C3 &&
            voltage_period_bound_us>=351500 && voltage_period_bound_us<=500000 &&
            temperature_period_bound_us>=2800000 && temperature_period_bound_us<=4000000;
    }
};
enum class State { unqualified, bus, clock, profile, protection, warming, cells, temperature, ready };
// Shared by complete and incremental gauge validation. These predicates must
// not diverge when an unfinished refresh retains the previous observation.
namespace limits {
inline bool no_por(std::uint16_t raw) { return !(raw&2); }
inline bool active(std::uint16_t raw) { return !(raw&1); }
inline bool protection(std::uint16_t raw) { return !(raw&0xDFFF); }
inline bool battery_status(std::uint16_t raw) { return !(raw&0xFF00); }
inline bool fets(std::uint16_t raw) { return (raw&3)==3; }
inline bool cell(double v) { return v>=3.2 && v<=4.2; }
inline bool pack(double v) { return v>=9.6 && v<=12.6; }
inline bool spread(double a,double b) { return std::abs(a-b)<=.15; }
inline bool sum(double cells,double pack_v) { return std::abs(cells-pack_v)<=.15; }
inline bool protected_output(double protected_v,double pack_v) { return std::abs(protected_v-pack_v)<=.2; }
inline bool current(std::uint16_t raw) { return raw!=0x7FFF && raw!=0x8000; }
inline bool temperature(double c) { return c>=10 && c<40; }
} // namespace limits
struct Report {
    State state=State::unqualified;
    std::uint64_t observed_us=0, voltage_earliest_us=0, temperature_earliest_us=0;
    std::uint64_t pack_binding=0, qualification_id=0;
    double pack_v=0, protected_v=0;
    std::optional<double> current_a;
    std::array<double,3> cells_v{};
    std::array<double,2> temperature_c{};
    std::optional<double> soc_percent;
    bool ready() const { return state==State::ready; }
};
class GaugeMonitor {
public:
    GaugeMonitor(std::uint64_t boot,PackProfile profile) : boot_(boot),profile_(profile) {}
    Report observe(const GaugeCapture& c,std::uint64_t now) {
        Report r;
        if(now<last_now_) { clock_fault_=true; active_since_.reset(); }
        last_now_=now;
        if(clock_fault_) { r.state=State::clock; return r; }
        if(!c.valid) { active_since_.reset(); r.state=State::bus; return r; }
        if(c.read_started_us<0 || c.read_finished_us<c.read_started_us ||
            static_cast<std::uint64_t>(c.read_finished_us)>now ||
            c.read_finished_us-c.read_started_us>250000) { active_since_.reset(); r.state=State::clock; return r; }
        const auto start=static_cast<std::uint64_t>(c.read_started_us);
        if(start<last_capture_) { active_since_.reset(); r.state=State::clock; return r; }
        last_capture_=start;
        r.observed_us=start;
        r.pack_v=c.pack_voltage*.0003125;
        r.protected_v=c.protected_voltage*.0003125;
        if(c.sense_resistor) r.current_a=static_cast<std::int16_t>(c.current)*.15625/c.sense_resistor;
        for(std::size_t i=0;i<3;++i) r.cells_v[i]=c.cells[i]*.000078125;
        for(std::size_t i=0;i<2;++i) r.temperature_c[i]=static_cast<std::int16_t>(c.thermistors[i])/256.;
        if(c.soc<=25600) r.soc_percent=c.soc/256.;
        if(!profile_.valid(boot_)) return r;
        if(c.dev_name!=profile_.dev_name || c.pack_config!=profile_.pack_config || c.nv_config0!=profile_.nv_config0 ||
           c.nv_config1!=profile_.nv_config1 || c.sense_resistor!=profile_.sense_resistor ||
           c.hibernate_config!=profile_.hibernate_config || c.thermistor_config!=profile_.thermistor_config) {
            active_since_.reset(); r.state=State::profile; return r;
        }
        // POR requires explicit supervised recovery. No clear/write is hidden in
        // this reader. Full is the only permitted ProtStatus bit for motion.
        if(!limits::no_por(c.status) || !limits::no_por(c.status2) || !limits::active(c.fstat) ||
           !limits::protection(c.protection_status) || !limits::battery_status(c.battery_status) || !limits::fets(c.fet_status)) {
            active_since_.reset(); r.state=State::protection; return r;
        }
        if(!active_since_) active_since_=start;
        if(start<*active_since_ || start-*active_since_<profile_.temperature_period_bound_us ||
           start<profile_.temperature_period_bound_us) { r.state=State::warming; return r; }
        r.voltage_earliest_us=start-profile_.voltage_period_bound_us;
        r.temperature_earliest_us=start-profile_.temperature_period_bound_us;
        const auto sum=r.cells_v[0]+r.cells_v[1]+r.cells_v[2];
        const auto range=std::minmax_element(r.cells_v.begin(),r.cells_v.end());
        if(!limits::cell(*range.first) || !limits::cell(*range.second) || !limits::spread(*range.first,*range.second) ||
           !limits::pack(r.pack_v) || !limits::sum(sum,r.pack_v) || !limits::protected_output(r.protected_v,r.pack_v) ||
           !limits::current(c.current)) { r.state=State::cells; return r; }
        for(double t:r.temperature_c) if(!limits::temperature(t)) { r.state=State::temperature; return r; }
        // Reject stale status even when slower ADC age bounds remain plausible.
        if(now-start>250000) { r.state=State::clock; return r; }
        r.pack_binding=profile_.pack_binding; r.qualification_id=profile_.qualification_id;
        r.state=State::ready;
        return r;
    }
private:
    std::uint64_t boot_,last_now_=0,last_capture_=0;
    PackProfile profile_;
    std::optional<std::uint64_t> active_since_;
    bool clock_fault_=false;
};
struct MotionPower {
    bool ready=false;
    // Observation age is distinct from the earlier ADC bounds in Report. The
    // executor uses this status observation for its 250 ms bus/protection check.
    std::uint64_t observed_us=0, pack_binding=0;
    double pack_v=0;
};
inline MotionPower motion_power(const Report& gauge,const smart_blinds::charger::OffCapture& charger,std::uint64_t now) {
    if(!gauge.ready() || !charger.valid() || charger.finished_ms<charger.started_ms ||
       charger.finished_ms-charger.started_ms>250 || charger.finished_ms>now/1000 ||
       gauge.observed_us>now || now-gauge.observed_us>250000 ||
       gauge.voltage_earliest_us>now || now-gauge.voltage_earliest_us>750000 ||
       gauge.temperature_earliest_us>now || now-gauge.temperature_earliest_us>4250000 ||
       now/1000-charger.started_ms>250) return {};
    return {true,std::min(gauge.observed_us,charger.started_ms*1000),gauge.pack_binding,gauge.pack_v};
}
} // namespace blinds::power
