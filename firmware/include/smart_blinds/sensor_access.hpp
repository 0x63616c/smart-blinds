#pragma once
#include "smart_blinds/power_mailbox.hpp"

namespace blinds::power::continuity {
// Fixed application-lifetime selector for one immutable sensor-session slot.
// Only the sensor owner installs; cancellation may withdraw from another task.
// Readers immediately copy/consume. Withdrawal does not perform I/O or teardown.
// A withdrawn object must remain alive until quiescent(). No raw read escapes.
class SensorAccess {
public:
    SensorAccess(MailboxGate& gate,BusEpoch& epoch):gate_(gate),epoch_(epoch) {}
    bool install(JointMailbox& box,Window window,std::uint32_t request) {
        Held held(gate_);
        if(box_ || readers_ || !request || !window || !box.healthy()) return false;
        box_=&box;window_=window;request_=request;expected_=epoch_.value();return true;
    }
    // The only injected operation is monotonic time, always outside the gate.
    template<class Clock>
    std::optional<JointRecord> snapshot(std::uint32_t request,Clock now) {
        JointMailbox* box=nullptr;Window window{};std::uint32_t expected=0;
        {
            Held held(gate_);
            if(!box_ || request!=request_ || !epoch_.matches(expected_) || readers_==UINT32_MAX) return {};
            ++readers_;box=box_;window=window_;expected=expected_;
        }
        auto read=box->read_latest(window,now());
        auto value=read ? read->consume(now()):std::optional<JointRecord>{};
        {
            Held held(gate_);
            --readers_;
            if(box_!=box || request_!=request || !epoch_.matches(expected)) return {};
        }
        return value;
    }
    // Closing stops new and in-progress snapshot grants immediately. The owner
    // holds the actual mailbox/session objects and closes their window itself.
    void withdraw() { Held held(gate_);box_=nullptr;request_=0;window_={}; }
    bool quiescent() { Held held(gate_);return !box_ && readers_==0; }
    bool current(const JointRecord& value,std::uint32_t request) {
        Held held(gate_);
        return box_ && request_==request && window_.value==value.window.value &&
            epoch_.matches(expected_) && value.gauge.epoch==expected_ && box_->healthy();
    }
private:
    class Held {
    public:
        explicit Held(MailboxGate& gate):gate_(gate) { gate_.enter(); }
        ~Held() { gate_.leave(); }
    private: MailboxGate& gate_;
    };
    MailboxGate& gate_;
    BusEpoch& epoch_;
    JointMailbox* box_=nullptr;
    Window window_{};
    std::uint32_t request_=0,expected_=0,readers_=0;
};
} // namespace blinds::power::continuity
