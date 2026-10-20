#pragma once
#include "smart_blinds/gauge_bus_session.hpp"

namespace blinds::power::continuity {
// The platform implementation may protect only fixed-size copy/metadata.
// No user callback, I/O, allocation, logging or waits inside the held gate.
class MailboxGate {
public:
    virtual ~MailboxGate()=default;
    virtual void enter() noexcept=0;
    virtual void leave() noexcept=0;
};
struct Window {
    std::uint32_t value=0;
    explicit operator bool() const { return value!=0; }
};
enum class FailureKind : std::uint8_t { none, gauge, charger, lifecycle };
struct Failure {
    FailureKind kind=FailureKind::none;
    std::uint16_t code=0;
};
enum class Refresh { warming, published, closed, failed };
struct JointRecord {
    Window window{};
    Publication gauge{};
    smart_blinds::charger::OffCapture charger{};
};
class JointRead;

// One sensor producer, any readers; lifetime exceeds the bound session and
// every JointRead. Cannot publish caller-supplied evidence or rebind a session.
class JointMailbox final:public smart_blinds::charger::FailureSink {
public:
    JointMailbox(MailboxGate& gate,BusEpoch& epoch,Context context)
        : gate_(gate),epoch_(epoch),context_(context),expected_(epoch.value()) {}
    JointMailbox(const JointMailbox&)=delete;
    JointMailbox& operator=(const JointMailbox&)=delete;
    Window open_window();
    void close_window(Window window);
    bool closure_acknowledged(Window window);
    std::optional<JointRead> read_latest(Window window,std::uint64_t now_us);
    // Any task; no gate or SDK teardown. The first cause survives later errors.
    void retire(Failure reason={FailureKind::lifecycle,1}) noexcept;
    void failed(smart_blinds::charger::Error reason) noexcept override;
    Failure failure() const;
    bool healthy() const;
    static constexpr std::uint32_t successor(std::uint32_t value) {
        return value==UINT32_MAX ? UINT32_MAX:value+1;
    }
private:
    friend class OwnedSession;
    friend class OwnedWordBus;
    friend class JointRead;
    bool bind(Context context,BusEpoch& epoch,std::uint32_t expected);
    bool begin(Window window);
    void finish(Window window);
    bool parkable();
    bool active(Window window) const;
    bool commit(Window window,const Result& evidence,
                const smart_blinds::charger::OffCapture& charger,std::uint64_t now_us);
    void gauge_failed(Fault fault) noexcept;
    bool fresh(const JointRecord& record,std::uint64_t now_us) const;
    MailboxGate& gate_;
    BusEpoch& epoch_;
    const Context context_;
    const std::uint32_t expected_;
    std::atomic<std::uint32_t> first_failure_{0};
    std::atomic<std::uint32_t> active_window_{0};
    // All fields below are gate-protected; never read with a seqlock.
    bool bound_=false,acquiring_=false;
    std::uint32_t next_window_=0,closed_window_=0,next_serial_=0;
    JointRecord record_{};
};

// Only the mailbox can issue this immediate snapshot. Moving transfers the
// single consumption right. Healthy replacement is not retirement; it cannot
// invalidate an already-linearized read. Close/fault/age always can.
class JointRead {
public:
    JointRead(const JointRead&)=delete;
    JointRead& operator=(const JointRead&)=delete;
    JointRead(JointRead&& other) noexcept
        : mailbox_(other.mailbox_),record_(other.record_),read_us_(other.read_us_) { other.mailbox_=nullptr; }
    JointRead& operator=(JointRead&&)=delete;
    std::optional<JointRecord> consume(std::uint64_t now_us);
private:
    friend class JointMailbox;
    JointRead(JointMailbox& mailbox,JointRecord record,std::uint64_t now)
        : mailbox_(&mailbox),record_(record),read_us_(now) {}
    JointMailbox* mailbox_;
    JointRecord record_;
    std::uint64_t read_us_;
};
} // namespace blinds::power::continuity
