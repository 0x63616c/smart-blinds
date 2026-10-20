#pragma once
#include "smart_blinds/motion_executor.hpp"
#include "smart_blinds/motion_protocol.hpp"
#include "smart_blinds/power_evidence.hpp"

namespace blinds {
// A separate interface makes counter origin installation explicit and testable.
// It does not establish a physical reference and must not restart a live counter.
class CounterOrigin {
public:
    virtual ~CounterOrigin() = default;
    virtual bool set_counter_origin(std::uint64_t epoch,double count) = 0;
};
struct FastObservation {
    bool valid=false,count_valid=false,driver_fault=true,stop_pressed=false;
    std::uint64_t sequence=0,sampled_us=0,encoder_epoch=0;
    double count=0,current_a=0;
};
struct SessionInput {
    FastObservation fast{};
    power::MotionPower power{}; // Assessed from actual gauge + charger captures.
    std::optional<smart_blinds::ClockBounds> clock;
    std::uint64_t clock_probe=0,clock_connection=0;
    bool attached=false,radio_awake=false,manual_intervention=false;
};
// Supplied only by a trusted local physical-reference workflow. No network
// resource can create this record. A saved count or periodic chain index alone
// does not satisfy independently_observed.
struct PhysicalReference {
    bool independently_observed=false;
    std::uint64_t boot=0,record=0,observed_us=0,pack_binding=0;
    std::uint32_t calibration=0;
    double count=0;
};
class MotionSession {
public:
    using Inbox=wire::Inbox<4>;
    enum class Phase { unreferenced,idle,preparing,ready,committed,moving,settling,fault };
    enum class Result { none,accepted,stale,invalid,busy,unqualified,reference,power,clock,connection,deadline,control,io,stopped,finished };
    struct Status {
        Phase phase=Phase::unreferenced;
        Result result=Result::none;
        std::uint64_t command=0,last_message=0,observed_us=0;
        bool ready=false,reference_valid=false,awake_required=false;
        std::optional<double> height_mm;
        Reason controller_reason=Reason::unreferenced;
    };
    static constexpr std::uint64_t message_age_us=100000,queue_age_us=40000;
    // Hard ceiling independent of lease refreshes and radio wake requests. A
    // slower/longer installation needs a reviewed profile, not a remote override.
    static constexpr std::uint64_t max_session_us=240000000;
    MotionSession(MotionIo& io,CounterOrigin& origin,Calibration calibration,Limits limits,
                  BenchMotionProfile profile,std::uint64_t boot);
    MotionSession(const MotionSession&)=delete;
    MotionSession& operator=(const MotionSession&)=delete;
    bool establish_reference(const PhysicalReference& reference);
    // Exactly one owning task calls this at 10 ms cadence while awake. It handles
    // at most one queued request. Raw STOP is inspected before any command work.
    // No I2C, transport calls, persistence, allocation or logging belongs here.
    Status cycle(Inbox& inbox,const SessionInput& input);
    Status status() const;
private:
    bool active() const;
    bool healthy(const SessionInput& in,std::uint64_t now,bool need_count) const;
    MotionEvidence evidence(const SessionInput& in) const;
    Measurement measurement(const SessionInput& in) const;
    std::optional<wire::Projection::Time> clock(const SessionInput& in,std::uint64_t now) const;
    Result request(const wire::Envelope& envelope,const SessionInput& in,std::uint64_t now);
    bool lease(const wire::Request& request,const wire::Projection::Time& time,const smart_blinds::ClockBounds& bounds,
               std::uint64_t now,bool apply_controller);
    bool fail(Result result);
    void controlled_stop(Result result);
    void advance(const SessionInput& in,std::uint64_t now);
    MotionIo& io_;
    CounterOrigin& origin_;
    Calibration calibration_;
    Limits limits_;
    Controller controller_;
    MotionExecutor executor_;
    wire::Projection projection_;
    wire::Request pending_{};
    std::uint64_t boot_,connection_=0,last_command_=0,last_message_=0,last_now_=0;
    std::uint64_t deadline_us_=0,lease_until_us_=0,last_sent_us_=0,pack_binding_=0,reference_record_=0;
    std::uint64_t last_probe_=0,last_clock_reference_=0,lease_origin_us_=0,lease_error_us_=0;
    double saved_count_=0,last_count_=0;
    bool qualified_=false,referenced_=false,controller_prepared_=false;
    Phase phase_=Phase::unreferenced;
    Result result_=Result::none;
};
} // namespace blinds
