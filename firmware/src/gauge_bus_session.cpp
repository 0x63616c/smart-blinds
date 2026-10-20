#include "smart_blinds/gauge_bus_session.hpp"
#include "smart_blinds/power_mailbox.hpp"

namespace blinds::power::continuity {
bool read_address(std::uint16_t reg,WordAddress& out) {
    // Exact read-only register allowlist for the reviewed continuity capture.
    // Do not broaden to arbitrary RAM, authentication, commands or NVM access.
    switch(reg) {
    case 0x000:case 0x006:case 0x00B:case 0x01B:case 0x01C:case 0x021:case 0x03D:
    case 0x0AB:case 0x0AF:case 0x0B0:case 0x0D6:case 0x0D7:case 0x0D8:
    case 0x0D9:case 0x0DA:case 0x0DB:case 0x0F1:
    case 0x139:case 0x13A:case 0x1A8:case 0x1B0:case 0x1B5:case 0x1B8:
    case 0x1B9:case 0x1BB:case 0x1BC:case 0x1BD:case 0x1BE:case 0x1BF:
    case 0x1CA:case 0x1CF:
        out={static_cast<std::uint8_t>(reg<0x100 ? 0x36:0x0B),static_cast<std::uint8_t>(reg)};
        return true;
    default:out={};return false;
    }
}
bool OwnedWordBus::reject(Fault fault) {
    auto empty=Fault::none;
    failure_->compare_exchange_strong(empty,fault,std::memory_order_acq_rel,std::memory_order_acquire);
    if(joint_) joint_->gauge_failed(failure_->load(std::memory_order_acquire));
    epoch_.retire_if(expected_);return false;
}
bool OwnedWordBus::read_word(std::uint16_t reg,std::uint16_t& value,std::uint32_t timeout) {
    WordAddress address;
    if(!accessible() || timeout!=10 || !read_address(reg,address)) {
        return reject(Fault::context);
    }
    std::array<std::uint8_t,2> bytes{};
    const bool ok=transport_.transfer(address.device,address.pointer,bytes,timeout);
    if(!ok) return reject(Fault::bus);
    if(!accessible()) return reject(Fault::context);
    value=static_cast<std::uint16_t>(bytes[0] | (static_cast<std::uint16_t>(bytes[1])<<8));
    return true;
}
bool OwnedSession::can_attach(Context context) const {
    // Invoked on the creating task only; don't inspect monitor from consumers.
    return bus_.accessible() && context==context_ && monitor_.phase()==Phase::warming;
}
OwnedSession::OwnedSession(Profile profile,Context context,WordTransport& transport,
                           BusEpoch& epoch,Owner owner,JointMailbox& joint,
                           smart_blinds::charger::Bq25798& charger)
    : context_(context),transport_(transport),epoch_(epoch),expected_(epoch.value()),
      bus_(transport,epoch,expected_,owner,&failure_,&joint),
      monitor_(profile,context),validation_(profile),joint_(&joint),charger_(&charger) {
    if(!charger.reports_to(joint) || !joint.bind(context,epoch,expected_)) failed(Fault::context);
}
bool OwnedSession::allowed(Context context) {
    // Never touch the single-owner monitor from a wrong task.
    if(!bus_.accessible() || !(context==context_)) { retire();return false; }
    return true;
}
Publication OwnedSession::fail(Fault fault) {
    failed(fault);
    return {{{},Phase::invalid,failure_.load(std::memory_order_acquire)},0,0};
}
void OwnedSession::failed(Fault fault) noexcept {
    auto empty=Fault::none;
    failure_.compare_exchange_strong(empty,fault==Fault::none ? Fault::context:fault,
                                    std::memory_order_acq_rel,std::memory_order_acquire);
    if(joint_) joint_->gauge_failed(failure_.load(std::memory_order_acquire));
    published_.store(0,std::memory_order_release);
    epoch_.retire_if(expected_);
}
Fault OwnedSession::begin(std::int64_t started) noexcept {
    if(joint_ && (started<0 || static_cast<std::uint64_t>(started)<joint_started_us_)) return Fault::clock;
    return monitor_.capture_start(context_,started);
}
Fault OwnedSession::word(std::uint16_t reg,std::uint16_t raw) noexcept {
    return validation_.word(reg,raw);
}
Result OwnedSession::capture(Context context,std::uint64_t* completed) {
    if(!allowed(context)) return fail(Fault::context).evidence;
    if(monitor_.phase()==Phase::invalid) return fail(monitor_.fault()).evidence;
    // Only an ordinary active refresh retains the last completed serial.
    // Its immutable report keeps its original source/ADC age bounds.
    const bool active=monitor_.phase()==Phase::active;
    if(!active) published_.store(0,std::memory_order_release);
    validation_.reset();
    const auto capture=read_capture(bus_,this);
    if(!allowed(context)) return fail(Fault::context).evidence;
    const auto now=transport_.now_us();
    if(now<0) return fail(Fault::clock).evidence;
    auto evidence=monitor_.observe(capture,context,static_cast<std::uint64_t>(now));
    if(evidence.phase==Phase::invalid) return fail(evidence.fault).evidence;
    if(active && !evidence.report.ready()) return fail(Fault::transition).evidence;
    // Cancellation during capture or interpretation cannot publish a good read.
    if(!allowed(context)) return fail(Fault::context).evidence;
    if(completed) *completed=static_cast<std::uint64_t>(now);
    return evidence;
}
Publication OwnedSession::read(Context context) {
    if(joint_) return fail(Fault::context); // Never create a second serial authority.
    const auto evidence=capture(context);
    if(evidence.phase==Phase::invalid) return {evidence,0,0};
    if(evidence.report.ready()) {
        if(next_serial_==UINT32_MAX) return fail(Fault::expired);
        ++next_serial_;
        published_.store(next_serial_,std::memory_order_release);
        return {evidence,expected_,next_serial_};
    }
    return {evidence,expected_,0};
}
Refresh OwnedSession::refresh(Context context,Window window) {
    if(!joint_ || !charger_ || !allowed(context)) { failed(Fault::context);return Refresh::failed; }
    if(monitor_.phase()==Phase::invalid) { failed(monitor_.fault());return Refresh::failed; }
    if(!joint_->begin(window)) return joint_->healthy() ? Refresh::closed:Refresh::failed;
    const auto acquire=[&]() {
        const auto charger=charger_->capture_off();
        if(!charger.valid()) { joint_->failed(charger_->first_error());return Refresh::failed; }
        if(!joint_->healthy()) return Refresh::failed;
        if(!joint_->active(window)) return Refresh::closed;
        const auto now=transport_.now_us();
        if(now<0 || charger.finished_ms>static_cast<std::uint64_t>(now)/1000 ||
           static_cast<std::uint64_t>(now)/1000-charger.started_ms>250) {
            failed(Fault::clock);return Refresh::failed;
        }
        joint_started_us_=static_cast<std::uint64_t>(now);
        std::uint64_t finished=0;
        const auto result=capture(context,&finished);
        if(!joint_->healthy() || result.phase==Phase::invalid) return Refresh::failed;
        if(!joint_->active(window)) return Refresh::closed;
        if(!result.report.ready()) return Refresh::warming;
        if(joint_->commit(window,result,charger,finished)) return Refresh::published;
        return joint_->healthy() ? Refresh::closed:Refresh::failed;
    };
    const auto result=acquire();
    joint_->finish(window);
    return result;
}
bool OwnedSession::park_light_sleep(Context context) {
    published_.store(0,std::memory_order_release);
    if(joint_ && !joint_->parkable()) { retire();return false; }
    if(!allowed(context)) return false;
    const auto now=transport_.now_us();
    if(now<0 || !monitor_.park_light_sleep(context,static_cast<std::uint64_t>(now))) {
        retire();return false;
    }
    return allowed(context);
}
bool OwnedSession::resume_light_sleep(Context context) {
    published_.store(0,std::memory_order_release);
    if(joint_ && !joint_->parkable()) { retire();return false; }
    if(!allowed(context)) return false;
    const auto now=transport_.now_us();
    if(now<0 || !monitor_.resume_light_sleep(context,static_cast<std::uint64_t>(now))) {
        retire();return false;
    }
    return allowed(context);
}
bool OwnedSession::current(const Publication& p,std::uint64_t now) const {
    if(joint_) return false;
    const auto& report=p.evidence.report;
    return p.serial && published_.load(std::memory_order_acquire)==p.serial &&
        p.epoch==expected_ && epoch_.matches(expected_) && p.evidence.phase==Phase::active &&
        p.evidence.fault==Fault::none && report.ready() && report.observed_us<=now &&
        now-report.observed_us<=250000 && report.pack_binding==context_.pack_binding &&
        report.qualification_id==context_.qualification_id;
}
} // namespace blinds::power::continuity
