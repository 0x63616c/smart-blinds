#include "smart_blinds/gauge_continuity.hpp"

namespace blinds::power::continuity {
namespace {
constexpr std::int64_t capture_budget_us=250000,transfer_budget_us=10000;
struct Request { std::uint16_t address;std::uint16_t* value; };
class Reader {
public:
    Reader(ReadOnlyBus& bus,Capture& capture,CaptureObserver* observer)
        : bus_(bus),capture_(capture),observer_(observer) {
        started_=last_=bus_.now_us();
        capture_.gauge.read_started_us=started_;
        capture_.error=ReadError::none;
        if(started_<0) fail(ReadError::clock,Fault::clock);
        else if(observer_) reject(observer_->begin(started_));
    }
    void word(Request r) {
        if(capture_.error!=ReadError::none) return;
        const auto before=bus_.now_us();
        if(!time(before)) return;
        if(before-started_>=capture_budget_us) { fail(ReadError::timeout,Fault::clock); return; }
        const bool ok=bus_.read_word(r.address,*r.value,10);
        // Report the first returned bus error before another clock call can
        // block or produce a later error. Ownership may already be retired.
        if(!ok) { fail(ReadError::bus,bus_.read_failure());return; }
        const auto after=bus_.now_us();
        if(!time(after)) return;
        if(after-before>transfer_budget_us || after-started_>capture_budget_us)
            fail(ReadError::timeout,Fault::clock);
        else if(observer_) reject(observer_->word(r.address,*r.value));
    }
    void guard(Guard& g) {
        const Request requests[]={
            {0x000,&g.status},{0x0AF,&g.alerts},{0x0D9,&g.protection},{0x0B0,&g.status2},
            {0x03D,&g.fstat},{0x0F1,&g.fets},{0x1A8,&g.battery_status},
            {0x00B,&g.config},{0x0AB,&g.config2},{0x1B0,&g.nv_config},{0x1BB,&g.hibernate},
            {0x1BC,&g.rom[0]},{0x1BD,&g.rom[1]},{0x1BE,&g.rom[2]},{0x1BF,&g.rom[3]},
            {0x021,&g.dev_name},{0x1B5,&g.pack_config},{0x1B8,&g.nv_config0},
            {0x1B9,&g.nv_config1},{0x1CF,&g.sense},{0x1CA,&g.thermistor}
        };
        for(auto r:requests) word(r);
    }
    void finish() {
        const auto end=bus_.now_us();
        // A failed transfer remains invalid even if the final clock is benign.
        if(capture_.error==ReadError::none && time(end) && end-started_>capture_budget_us)
            fail(ReadError::timeout,Fault::clock);
        capture_.gauge.read_finished_us=end;
        capture_.gauge.valid=capture_.error==ReadError::none;
    }
private:
    void fail(ReadError error,Fault cause) {
        if(capture_.error!=ReadError::none) return;
        capture_.error=error;
        if(observer_) observer_->failed(cause==Fault::none ? Fault::bus:cause);
    }
    void reject(Fault reason) { if(reason!=Fault::none) fail(ReadError::rejected,reason); }
    bool time(std::int64_t now) {
        if(now<0 || now<last_) { fail(ReadError::clock,Fault::clock);return false; }
        last_=now;return true;
    }
    ReadOnlyBus& bus_;
    Capture& capture_;
    CaptureObserver* observer_;
    std::int64_t started_=0,last_=0;
};
Fault guard_fault(const Guard& g,const Profile& p) {
    // Same word policy as incremental capture; no separate masks/thresholds.
    const std::pair<std::uint16_t,std::uint16_t> words[]={
        {0x000,g.status},{0x0AF,g.alerts},{0x0D9,g.protection},{0x0B0,g.status2},
        {0x03D,g.fstat},{0x0F1,g.fets},{0x1A8,g.battery_status},
        {0x00B,g.config},{0x0AB,g.config2},{0x1B0,g.nv_config},{0x1BB,g.hibernate},
        {0x1BC,g.rom[0]},{0x1BD,g.rom[1]},{0x1BE,g.rom[2]},{0x1BF,g.rom[3]},
        {0x021,g.dev_name},{0x1B5,g.pack_config},{0x1B8,g.nv_config0},
        {0x1B9,g.nv_config1},{0x1CF,g.sense},{0x1CA,g.thermistor}
    };
    CaptureValidation validation(p);
    for(auto w:words) {
        const auto fault=validation.word(w.first,w.second);
        if(fault!=Fault::none) return fault;
    }
    return Fault::none;
}
} // namespace

Fault CaptureValidation::word(std::uint16_t reg,std::uint16_t raw) noexcept {
    bool good=true;
    switch(reg) {
    case 0x000:case 0x0B0:good=limits::no_por(raw);break;
    case 0x0AF:case 0x0D9:good=limits::protection(raw);break;
    case 0x03D:good=limits::active(raw);break;
    case 0x0F1:good=limits::fets(raw);break;
    case 0x1A8:good=limits::battery_status(raw);break;
    default:break;
    }
    if(!good) return Fault::protection;
    switch(reg) {
    case 0x00B:good=raw==profile_.config;break;
    case 0x0AB:good=raw==profile_.config2;break;
    case 0x1B0:good=raw==profile_.nv_config;break;
    case 0x1BB:good=raw==profile_.pack.hibernate_config;break;
    case 0x1BC:case 0x1BD:case 0x1BE:case 0x1BF:good=raw==profile_.rom[reg-0x1BC];break;
    case 0x021:good=raw==profile_.pack.dev_name;break;
    case 0x1B5:good=raw==profile_.pack.pack_config;break;
    case 0x1B8:good=raw==profile_.pack.nv_config0;break;
    case 0x1B9:good=raw==profile_.pack.nv_config1;break;
    case 0x1CF:good=raw==profile_.pack.sense_resistor;break;
    case 0x1CA:good=raw==profile_.pack.thermistor_config;break;
    default:break;
    }
    if(!good) return Fault::profile;
    switch(reg) {
    case 0x0DA:pack_=raw*.0003125;present_|=8;good=limits::pack(pack_);break;
    case 0x0DB:protected_=raw*.0003125;present_|=16;break;
    case 0x0D6:case 0x0D7:case 0x0D8: {
        const auto i=0x0D8-reg;cells_[i]=raw*.000078125;present_|=1u<<i;
        good=limits::cell(cells_[i]);break;
    }
    case 0x01C:good=limits::current(raw);break;
    case 0x139:case 0x13A:good=limits::temperature(static_cast<std::int16_t>(raw)/256.);break;
    default:break; // SOC is optional; die temperature is not the TH1/TH2 gate.
    }
    if(!good) return Fault::values;
    for(unsigned i=0;i<3;++i) for(unsigned j=i+1;j<3;++j)
        if((present_&(1u<<i)) && (present_&(1u<<j)) && !limits::spread(cells_[i],cells_[j]))
            return Fault::values;
    if((present_&15)==15 && !limits::sum(cells_[0]+cells_[1]+cells_[2],pack_)) return Fault::values;
    if((present_&24)==24 && !limits::protected_output(protected_,pack_)) return Fault::values;
    return Fault::none;
}
Capture read_capture(ReadOnlyBus& bus,CaptureObserver* observer) {
    Capture c;
    Reader reader(bus,c,observer);
    reader.guard(c.before);
    const Request payload[]={
        {0x006,&c.gauge.soc},{0x0DA,&c.gauge.pack_voltage},{0x01C,&c.gauge.current},
        {0x01B,&c.gauge.temperature},{0x0D8,&c.gauge.cells[0]},{0x0D7,&c.gauge.cells[1]},
        {0x0D6,&c.gauge.cells[2]},{0x0DB,&c.gauge.protected_voltage},
        {0x13A,&c.gauge.thermistors[0]},{0x139,&c.gauge.thermistors[1]}
    };
    for(auto r:payload) reader.word(r);
    reader.guard(c.after);
    const auto& a=c.before;
    const auto& b=c.after;
    c.gauge.dev_name=a.dev_name;c.gauge.pack_config=a.pack_config;
    c.gauge.nv_config0=a.nv_config0;c.gauge.nv_config1=a.nv_config1;
    c.gauge.sense_resistor=a.sense;c.gauge.hibernate_config=a.hibernate;
    c.gauge.thermistor_config=a.thermistor;
    c.gauge.status=a.status|b.status;c.gauge.status2=a.status2|b.status2;
    c.gauge.protection_status=a.protection|b.protection|a.alerts|b.alerts;
    c.gauge.battery_status=a.battery_status|b.battery_status;
    c.gauge.fstat=a.fstat|b.fstat;c.gauge.fet_status=a.fets&b.fets;
    reader.finish();
    return c;
}
bool Profile::valid(std::uint64_t boot) const {
    const bool has_rom=std::any_of(rom.begin(),rom.end(),[](auto v){return v!=0;}) &&
        std::any_of(rom.begin(),rom.end(),[](auto v){return v!=0xFFFF;});
    // Rev12 tables67-69: fixed reserved bits plus disabled SHIP/COMMSH/ALSH/
    // forced thermistor modes; automatic thermistor bias remains enabled.
    return pack.valid(boot) && has_rom && mode_continuity_verified && exclusive_access_verified &&
        max_light_sleep_us>0 && max_light_sleep_us<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) &&
        !(nv_config&0x0168) && (nv_config&0x10) &&
        !(config&0x81EA) && (config&0x10) &&
        !(config2&0xC023) && (config2&0x10);
}
Monitor::Monitor(Profile profile,Context context)
    : profile_(profile),context_(context),monitor_(context.boot,profile.pack) {
    if(!profile.valid(context.boot) || !context.bus_generation || !context.monitoring_session ||
       context.pack_binding!=profile.pack.pack_binding || context.qualification_id!=profile.pack.qualification_id)
        invalidate(Fault::qualification);
}
void Monitor::invalidate(Fault reason) {
    if(phase_!=Phase::invalid) fault_=reason==Fault::none ? Fault::context:reason;
    phase_=Phase::invalid;
    last_ready_=0; // A previous report cannot issue a ticket.
}
bool Monitor::check_context_time(Context context,std::uint64_t now) {
    if(phase_==Phase::invalid) return false;
    if(!(context==context_)) { invalidate(Fault::context);return false; }
    if(now<last_now_ || now>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        invalidate(Fault::clock);return false;
    }
    last_now_=now;return true;
}
Result Monitor::failed(Fault fault) {
    invalidate(fault);
    return {{},phase_,fault_};
}
Result Monitor::observe(const Capture& c,Context context,std::uint64_t now) {
    if(!check_context_time(context,now)) return {{},phase_,fault_};
    if(phase_==Phase::parked) return failed(Fault::transition);
    if(c.error!=ReadError::none || !c.gauge.valid)
        return failed(c.error==ReadError::clock || c.error==ReadError::timeout ? Fault::clock:Fault::bus);
    if(c.gauge.read_started_us<0 || c.gauge.read_finished_us<c.gauge.read_started_us)
        return failed(Fault::clock);
    const auto start=static_cast<std::uint64_t>(c.gauge.read_started_us);
    if(static_cast<std::uint64_t>(c.gauge.read_finished_us)>now || now<start ||
       now-start>250000 || c.gauge.read_finished_us-c.gauge.read_started_us>250000 ||
       (seen_capture_ && (start<=last_capture_ || start<last_finished_)) ||
       (phase_==Phase::awaiting_capture && start<resumed_at_)) return failed(Fault::clock);
    for(const auto* guard:{&c.before,&c.after}) {
        const auto fault=guard_fault(*guard,profile_);
        if(fault!=Fault::none) return failed(fault);
    }
    auto report=monitor_.observe(c.gauge,now);
    if(report.state!=State::warming && !report.ready()) {
        const auto cause=report.state==State::clock ? Fault::clock:
            report.state==State::protection ? Fault::protection:
            report.state==State::profile ? Fault::profile:Fault::values;
        return failed(cause);
    }
    seen_capture_=true;last_capture_=start;
    last_finished_=static_cast<std::uint64_t>(c.gauge.read_finished_us);
    phase_=report.ready() ? Phase::active:Phase::warming;
    last_ready_=report.ready() ? start:0;
    return {report,phase_,fault_};
}
Fault Monitor::capture_start(Context context,std::int64_t started) const {
    if(phase_==Phase::invalid) return fault_;
    if(!(context==context_)) return Fault::context;
    if(phase_==Phase::parked) return Fault::transition;
    if(started<0) return Fault::clock;
    const auto start=static_cast<std::uint64_t>(started);
    if(start<last_now_ || (seen_capture_ && (start<=last_capture_ || start<last_finished_)) ||
       (phase_==Phase::awaiting_capture && start<resumed_at_)) return Fault::clock;
    return Fault::none;
}
bool Monitor::park_light_sleep(Context context,std::uint64_t now) {
    if(!check_context_time(context,now)) return false;
    if(phase_!=Phase::active || !last_ready_ || now-last_ready_>250000) {
        invalidate(Fault::transition);return false;
    }
    parked_at_=now;last_ready_=0;phase_=Phase::parked;
    return true;
}
bool Monitor::resume_light_sleep(Context context,std::uint64_t now) {
    if(!check_context_time(context,now)) return false;
    if(phase_!=Phase::parked) { invalidate(Fault::transition);return false; }
    if(now-parked_at_>profile_.max_light_sleep_us) { invalidate(Fault::expired);return false; }
    resumed_at_=now;phase_=Phase::awaiting_capture;
    return true;
}
} // namespace blinds::power::continuity
