#include "smart_blinds/power_mailbox.hpp"
#include <type_traits>

namespace blinds::power::continuity {
namespace {
class Held {
public:
    explicit Held(MailboxGate& gate):gate_(gate) { gate_.enter(); }
    ~Held() { gate_.leave(); }
    Held(const Held&)=delete;
    Held& operator=(const Held&)=delete;
private:
    MailboxGate& gate_;
};
static_assert(std::is_trivially_copyable_v<JointRecord>);
static_assert(sizeof(JointRecord)<=384,"Requalify critical-section copy size");
}
Failure JointMailbox::failure() const {
    const auto raw=first_failure_.load(std::memory_order_acquire);
    return {static_cast<FailureKind>(raw>>16),static_cast<std::uint16_t>(raw)};
}
bool JointMailbox::healthy() const {
    return first_failure_.load(std::memory_order_acquire)==0 && epoch_.matches(expected_);
}
void JointMailbox::retire(Failure reason) noexcept {
    if(reason.kind==FailureKind::none) reason={FailureKind::lifecycle,1};
    const auto raw=(static_cast<std::uint32_t>(reason.kind)<<16)|reason.code;
    std::uint32_t empty=0;
    first_failure_.compare_exchange_strong(empty,raw,std::memory_order_acq_rel,std::memory_order_acquire);
    epoch_.retire_if(expected_);
}
void JointMailbox::failed(smart_blinds::charger::Error reason) noexcept {
    retire({FailureKind::charger,static_cast<std::uint16_t>(reason)});
}
void JointMailbox::gauge_failed(Fault fault) noexcept {
    retire({FailureKind::gauge,static_cast<std::uint16_t>(fault)});
}
bool JointMailbox::bind(Context context,BusEpoch& epoch,std::uint32_t expected) {
    bool ok=false;
    {
        Held held(gate_);
        ok=!bound_ && context==context_ && &epoch==&epoch_ && expected==expected_ && healthy();
        if(ok) bound_=true;
    }
    if(!ok) retire();
    return ok;
}
Window JointMailbox::open_window() {
    Window result;
    bool exhausted=false;
    {
        Held held(gate_);
        if(bound_ && healthy() && !acquiring_ && active_window_.load(std::memory_order_relaxed)==0) {
            const auto next=successor(next_window_);
            exhausted=next==UINT32_MAX;
            if(!exhausted) {
                next_window_=next;record_.gauge.serial=0;
                active_window_.store(next,std::memory_order_release);result={next};
            }
        }
    }
    if(exhausted) retire({FailureKind::lifecycle,2});
    return result;
}
bool JointMailbox::active(Window window) const {
    return window && healthy() && active_window_.load(std::memory_order_acquire)==window.value;
}
void JointMailbox::close_window(Window window) {
    Held held(gate_);
    if(window && active_window_.load(std::memory_order_relaxed)==window.value) {
        active_window_.store(0,std::memory_order_release);
        closed_window_=window.value;record_.gauge.serial=0;
    }
}
bool JointMailbox::closure_acknowledged(Window window) {
    Held held(gate_);
    return window && healthy() && closed_window_==window.value && !acquiring_ &&
        active_window_.load(std::memory_order_relaxed)==0;
}
bool JointMailbox::begin(Window window) {
    Held held(gate_);
    if(!active(window) || acquiring_) return false;
    acquiring_=true;return true;
}
void JointMailbox::finish(Window) {
    Held held(gate_);
    acquiring_=false;
}
bool JointMailbox::parkable() {
    Held held(gate_);
    return healthy() && bound_ && closed_window_ && !acquiring_ &&
        active_window_.load(std::memory_order_relaxed)==0;
}
bool JointMailbox::fresh(const JointRecord& r,std::uint64_t now) const {
    return r.gauge.serial && r.gauge.epoch==expected_ &&
        r.gauge.evidence.phase==Phase::active && r.gauge.evidence.fault==Fault::none &&
        r.gauge.evidence.report.pack_binding==context_.pack_binding &&
        r.gauge.evidence.report.qualification_id==context_.qualification_id &&
        motion_power(r.gauge.evidence.report,r.charger,now).ready;
}
bool JointMailbox::commit(Window window,const Result& evidence,
                          const smart_blinds::charger::OffCapture& charger,std::uint64_t now) {
    // One candidate on the owner stack; readiness arithmetic stays outside gate.
    JointRecord candidate{window,{evidence,expected_,1},charger};
    if(!fresh(candidate,now)) { retire({FailureKind::lifecycle,3});return false; }
    bool committed=false,exhausted=false;
    {
        Held held(gate_);
        if(acquiring_ && active(window)) {
            exhausted=successor(next_serial_)==UINT32_MAX;
            if(!exhausted) {
                candidate.gauge.serial=++next_serial_;
                record_=candidate; // Body and sole accepted serial are one commit.
                committed=healthy();
            }
        }
    }
    if(exhausted) retire({FailureKind::lifecycle,2});
    return committed && active(window);
}
std::optional<JointRead> JointMailbox::read_latest(Window window,std::uint64_t now) {
    JointRecord copy;
    {
        Held held(gate_);
        if(!active(window) || !record_.gauge.serial) return {};
        copy=record_;
    }
    if(copy.window.value!=window.value || !active(window) || !fresh(copy,now)) return {};
    return JointRead(*this,copy,now);
}
std::optional<JointRecord> JointRead::consume(std::uint64_t now) {
    auto* mailbox=mailbox_;mailbox_=nullptr; // Failed attempts also consume the right.
    if(!mailbox || now<read_us_ || now-read_us_>20000 ||
       !mailbox->active(record_.window) || !mailbox->fresh(record_,now)) return {};
    return record_;
}
} // namespace blinds::power::continuity
