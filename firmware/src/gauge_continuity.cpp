#include "smart_blinds/gauge_continuity.hpp"

namespace blinds::power::continuity {
namespace {
constexpr std::int64_t capture_budget_us=250000,transfer_budget_us=10000;
struct Request { std::uint16_t address;std::uint16_t* value; };
class Reader {
public:
    Reader(ReadOnlyBus& bus,Capture& capture) : bus_(bus),capture_(capture) {
        started_=last_=bus_.now_us();
        capture_.gauge.read_started_us=started_;
        capture_.error=started_<0 ? ReadError::clock:ReadError::none;
    }
    void word(Request r) {
        if(capture_.error!=ReadError::none) return;
        const auto before=bus_.now_us();
        if(!time(before)) return;
        if(before-started_>=capture_budget_us) { capture_.error=ReadError::timeout; return; }
        const bool ok=bus_.read_word(r.address,*r.value,10);
        const auto after=bus_.now_us();
        if(!time(after)) return;
        if(after-before>transfer_budget_us || after-started_>capture_budget_us)
            capture_.error=ReadError::timeout;
        else if(!ok) capture_.error=ReadError::bus;
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
        if(started_<0) capture_.error=ReadError::clock;
        else if(time(end) && end-started_>capture_budget_us) capture_.error=ReadError::timeout;
        capture_.gauge.read_finished_us=end;
        capture_.gauge.valid=capture_.error==ReadError::none;
    }
private:
    bool time(std::int64_t now) {
        if(now<0 || now<last_) { capture_.error=ReadError::clock;return false; }
        last_=now;return true;
    }
    ReadOnlyBus& bus_;
    Capture& capture_;
    std::int64_t started_=0,last_=0;
};
bool profile_matches(const Guard& g,const Profile& p) {
    return g.config==p.config && g.config2==p.config2 && g.nv_config==p.nv_config &&
        g.rom==p.rom && g.dev_name==p.pack.dev_name && g.pack_config==p.pack.pack_config &&
        g.nv_config0==p.pack.nv_config0 && g.nv_config1==p.pack.nv_config1 &&
        g.sense==p.pack.sense_resistor && g.hibernate==p.pack.hibernate_config &&
        g.thermistor==p.pack.thermistor_config;
}
bool protected_or_inactive(const Guard& g) {
    return (g.status&2) || (g.status2&2) || (g.fstat&1) ||
        ((g.protection|g.alerts)&0xDFFF) || (g.battery_status&0xFF00) || (g.fets&3)!=3;
}
} // namespace

Capture read_capture(ReadOnlyBus& bus) {
    Capture c;
    Reader reader(bus,c);
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
    if(!profile_matches(c.before,profile_) || !profile_matches(c.after,profile_))
        return failed(Fault::profile);
    if(protected_or_inactive(c.before) || protected_or_inactive(c.after)) return failed(Fault::protection);
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
