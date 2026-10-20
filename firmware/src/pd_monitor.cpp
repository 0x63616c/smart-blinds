#include "smart_blinds/pd_monitor.hpp"
#include <algorithm>
namespace smart_blinds::pd {
namespace {
std::uint32_t le32(const std::uint8_t* p) {
    return std::uint32_t{p[0]}|(std::uint32_t{p[1]}<<8)|(std::uint32_t{p[2]}<<16)|(std::uint32_t{p[3]}<<24);
}
bool event(const Observation& o) {
    return (o.history[0]&1) || (o.history[1]&0x3E) || (o.history[2]&0x30) ||
           (o.history[3]&0x0F) || (o.history[4]&0x05);
}
}
bool discontinuity(const Observation& prior,const Observation& value) {
    return (value.history[0]&1) || (value.history[1]&0x3E) ||
        (value.history[3]&0x0F) || (value.history[4]&1) ||
        ((prior.port^value.port)&0xED) || (prior.pe==0x18 && value.pe!=0x18) ||
        (prior.rdo && prior.rdo!=value.rdo);
}
const char* name(State s) {
    switch(s) {
    case State::detached:return "detached";case State::negotiating:return "negotiating";
    case State::unapproved:return "unapproved";case State::ready:return "current-qualified";
    case State::fault:return "fault";default:return "unavailable";
    }
}
void Monitor::invalidate(Error e) {
    if(first_==Error::none) first_=e;
    initialized_=false;quiet_=false;
    last_.state=State::fault;last_.current_ma=0;last_.error=first_;
}
bool Monitor::bump() {
    if(epoch_==UINT32_MAX) { invalidate(Error::exhausted);return false; }
    ++epoch_;quiet_=false;return true;
}
bool Monitor::budget() {
    const auto now=bus_.now_ms();
    if(now<last_clock_) { invalidate(Error::clock);return false; }
    last_clock_=now;
    if(now-started_>operation_ms) { invalidate(Error::timeout);return false; }
    return first_==Error::none;
}
bool Monitor::read(std::uint8_t reg,std::uint8_t* p,std::size_t n) {
    if(!budget()) return false;
    if(!bus_.read(reg,p,n)) { invalidate(Error::bus);return false; }
    return budget();
}
bool Monitor::history(Image& i,Observation& out) {
    if(!read(0x0B,i.status.data(),i.status.size())) return false;
    constexpr std::array<unsigned,5> index{2,4,7,9,11};
    for(unsigned n=0;n<index.size();++n) out.history[n]|=i.status[index[n]];
    // VPU overvoltage/discharge fault or overvoltage transition is never an attach event.
    // VPU_VALID is for pull-up/source mode; do not require it in sink mode.
    if((i.status[8]&0x90) || (out.history[2]&0x20)) { invalidate(Error::fault);return false; }
    return true;
}
bool Monitor::image(Image& i,Observation& out) {
    std::array<std::uint8_t,4> rdo{};
    if(!history(i,out) || !read(0x2F,&i.id,1) || !read(0x29,&i.pe,1) ||
       !read(0x70,&i.count,1) || !read(0x85,i.pdos.data(),i.pdos.size()) ||
       !read(0x91,rdo.data(),rdo.size())) return false;
    i.rdo=le32(rdo.data());
    if(i.id!=0x21 && i.id!=0x25) { invalidate(Error::identity);return false; }
    if(i.status[1]!=mask_) { invalidate(Error::mask);return false; }
    return true;
}
bool Monitor::exact_policy(const Image& i) const {
    // Exact fixed sink PDO images, including USB flags; approved factory image
    // is a separate prerequisite and cannot be reconstructed from these alone.
    constexpr std::array<std::uint32_t,3> approved{0x04019096,0x0002D0FA,0x0004B0FA};
    if(i.count!=3) return false;
    for(unsigned n=0;n<3;++n) {
        const auto actual=le32(i.pdos.data()+4*n);
        const auto mask=n==0 ? 0xCC0FFFFFU:0xC00FFFFFU;
        if((actual&mask)!=approved[n] || (record_.valid() && actual!=record_.live_pdos[n])) return false;
    }
    return true;
}
Observation Monitor::finish(Observation out) {
    if(first_failure_) return *first_failure_;
    out.finished_ms=last_clock_;
    out.epoch=epoch_;
    if(serial_==UINT32_MAX) invalidate(Error::exhausted);
    else out.serial=++serial_;
    out.error=first_;
    if(first_!=Error::none) { out.state=State::fault;out.current_ma=0;first_failure_=out; }
    last_=out;return out;
}
Observation Monitor::initialize(std::uint64_t stable,std::optional<std::uint8_t> prior_mask) {
    Observation out;started_=bus_.now_ms();out.started_ms=started_;
    if(initialized_ || first_!=Error::none || stable>started_ || started_-stable<30) {
        invalidate(Error::uninitialized);return finish(out);
    }
    Image initial;
    if(!history(initial,out)) return finish(out);
    if(!read(0x2F,&initial.id,1)) return finish(out);
    if(initial.id!=0x21 && initial.id!=0x25) { invalidate(Error::identity);return finish(out); }
    mask_=initial.status[1]&static_cast<std::uint8_t>(~0x72U);
    if(!budget()) return finish(out);
    if(prior_mask) {
        // A clean owner replacement may keep an already configured mask. A POR
        // in the gap is NOT an invitation to initialize/erase its evidence.
        if((*prior_mask&0x72) || initial.status[1]!=*prior_mask) { invalidate(Error::mask);return finish(out); }
        mask_=*prior_mask;
    } else if(!bus_.alert_mask(mask_)) { invalidate(Error::bus);return finish(out); }
    if(!budget()) return finish(out);
    Image checked;
    if(!image(checked,out) || !history(checked,out)) return finish(out);
    if(checked.status[1]!=mask_) { invalidate(Error::mask);return finish(out); }
    initialized_=true;quiet_=false;
    out.state=State::negotiating;out.device_id=initial.id;
    return finish(out); // Initialization never grants authority or consumes warmup.
}
Observation Monitor::poll() {
    Observation out;started_=bus_.now_ms();out.started_ms=started_;
    if(!initialized_ || first_!=Error::none) { invalidate(Error::uninitialized);return finish(out); }
    Image a,b;
    if(!image(a,out) || !image(b,out)) return finish(out);
    // Final history cut catches reset/attach while PDO/RDO/PE words were read.
    Image tail;std::uint8_t final_pe=0;
    if(!read(0x29,&final_pe,1) || !history(tail,out)) return finish(out);
    if(tail.status[1]!=mask_) { invalidate(Error::mask);return finish(out); }
    if(!exact_policy(a) || !exact_policy(b)) { invalidate(Error::policy);return finish(out); }
    const bool same=a.id==b.id && a.count==b.count && a.pe==b.pe && b.pe==final_pe && a.rdo==b.rdo && a.pdos==b.pdos &&
        a.status[3]==b.status[3] && b.status[3]==tail.status[3] &&
        a.status[5]==b.status[5] && b.status[5]==tail.status[5] &&
        (a.status[10]&0x1F)==(b.status[10]&0x1F) && (b.status[10]&0x1F)==(tail.status[10]&0x1F);
    out.device_id=b.id;out.pe=final_pe;out.port=tail.status[3];out.monitor=tail.status[5];out.rdo=b.rdo;
    const bool attached=(out.port&0xED)==0x21 && (tail.status[10]&0x1F)==2;
    const bool detached=!(out.port&1) && !(tail.status[10]&0x1F);
    const auto op=(b.rdo>>10)&0x3FF,maximum=b.rdo&0x3FF;
    // RDO object position selects a SOURCE PDO; no mapping to local PDO2/3.
    const bool rdo=((b.rdo>>28)&7)!=0 && !(b.rdo&0x8C700000U) && op==250 && maximum>=op;
    const bool ready=same && attached && (out.monitor&0x0E)==0x0A && b.pe==0x18 && rdo;
    if(event(out) || !same || !ready) { if(!bump()) return finish(out); }
    if(!ready || event(out)) out.state=detached?State::detached:State::negotiating;
    else {
        if(!quiet_) { quiet_=true;quiet_since_=started_; }
        if(started_<quiet_since_) { invalidate(Error::clock);return finish(out); }
        if(started_-quiet_since_<settle_ms) out.state=State::negotiating;
        else if(!record_.valid() || record_.device_id!=out.device_id) out.state=State::unapproved;
        else { out.state=State::ready;out.current_ma=2500; }
    }
    return finish(out);
}
bool Monitor::current(const Observation& o,std::uint64_t now) const {
    return initialized_ && first_==Error::none && o.error==Error::none && o.serial &&
        o.serial==last_.serial && o.epoch==epoch_ && o.started_ms==last_.started_ms &&
        o.finished_ms==last_.finished_ms && o.rdo==last_.rdo && o.current_ma==last_.current_ma &&
        o.device_id==last_.device_id && o.pe==last_.pe && o.port==last_.port && o.monitor==last_.monitor &&
        o.history==last_.history && o.state==last_.state && o.started_ms<=o.finished_ms &&
        o.finished_ms<=now && now-o.started_ms<=max_age_ms;
}
} // namespace smart_blinds::pd
