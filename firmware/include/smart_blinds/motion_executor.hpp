#pragma once
#include "smart_blinds/control.hpp"
#include "smart_blinds/heartbeat.hpp"

namespace blinds {
// Provisional defaults are useful for host tests, never a hardware approval.
// A future commissioning record supplies the explicit bench qualification.
struct BenchMotionProfile {
    bool bench_qualified=false;
    std::uint64_t qualification_id=0;
    double max_duty=.5, max_count_rate=20000, max_fabric_rate=30;
    double kp=.0001, ki=.0002, feedforward=.00005;
    double current_trip_a=3, minimum_pack_v=9.6;
    double reversal_speed_counts_s=20, reversal_current_a=.2;
    std::uint64_t encoder_settle_us=5000, reversal_coast_us=20000, reversal_timeout_us=500000;
    std::uint64_t no_progress_us=400000;
};
struct MotionEvidence {
    std::uint64_t sequence=0, sampled_us=0, power_sampled_us=0, encoder_epoch=0, control_valid_until_us=0;
    std::uint32_t calibration_revision=0;
    double count=0, current_a=0, pack_v=0;
    // GPIO21 is shared: LOW can mean DRV8874 or the independent thermal latch.
    bool power_ready=false, reference_valid=false, driver_fault=true, stop_pressed=false;
};
class MotionIo {
public:
    virtual ~MotionIo() = default;
    virtual std::uint64_t now_us() const = 0;
    // All operations are synchronous/nonblocking with <=100 us budget. No I2C,
    // allocation, logging, flash or networking belongs in these operations.
    virtual bool request_n(bool high) = 0;
    virtual bool charge_off() = 0;
    virtual bool coast() = 0; // Force both inputs LOW and verify the request.
    virtual bool wdi_high() = 0;
    virtual bool encoder_power(bool enabled) = 0;
    virtual bool counter_start(std::uint64_t epoch) = 0;
    virtual bool counter_stop() = 0;
    virtual bool awake_lock(bool held) = 0;
    // Must hold the opposite input LOW, apply bounded duty, and read back the
    // applied command. Never use 11/brake. Direction is normalized in the port.
    virtual bool pwm(int direction,double duty) = 0;
    // Owning control task only: LOW >=1 us then HIGH, total <=100 us. No ISR,
    // autonomous timer or repeating peripheral feed can implement this method.
    virtual bool heartbeat_pulse() = 0;
};
class MotionExecutor {
public:
    static constexpr std::uint64_t io_budget_us=100, cycle_max_us=20000, cycle_budget_us=500;
    enum class State { idle, encoder_warming, sensing, arming, running, fault };
    enum class Fault { none, unqualified, command, evidence, clock, io, heartbeat, output, reversal, stalled };
    MotionExecutor(MotionIo& io,Calibration calibration,BenchMotionProfile profile,std::uint64_t boot);
    MotionExecutor(const MotionExecutor&)=delete;
    MotionExecutor& operator=(const MotionExecutor&)=delete;
    // Explicit new command opens a fresh encoder epoch. No command is restored
    // on reboot; unknown position still requires independent physical reference.
    bool open_sensing(std::uint64_t boot,std::uint64_t command,const MotionEvidence& power);
    bool poll_sensing(const MotionEvidence& power);
    bool arm(const MotionEvidence& evidence);
    bool update(const Output& output,const MotionEvidence& evidence);
    // The owning task must stop and inspect the result before backend teardown.
    bool stop(); // Request HIGH first; stops counter before gating encoder rail.
    State state() const { return state_; }
    Fault fault() const { return fault_; }
    double applied_duty() const { return applied_duty_; }
    std::uint64_t encoder_epoch() const { return command_; }
private:
    template<class F> bool operation(F call) {
        const auto before=io_.now_us();
        if(before<last_now_) return false;
        const bool ok=call();
        const auto after=io_.now_us();
        if(after<before) return false;
        last_now_=after;
        return ok && after-before<=io_budget_us;
    }
    bool time();
    bool power_valid(const MotionEvidence& e) const;
    bool evidence_valid(const MotionEvidence& e) const;
    bool safe_off();
    bool fail(Fault fault);
    bool feed(const MotionEvidence& e,bool coasting);
    MotionIo& io_;
    Calibration calibration_;
    BenchMotionProfile profile_;
    smart_blinds::Heartbeat heartbeat_;
    std::uint64_t boot_, command_=0, last_command_=0, last_now_=0, rail_on_us_=0, counter_on_us_=0;
    std::uint64_t last_cycle_us_=0, last_sequence_=0, last_sample_us_=0, reverse_since_=0, last_progress_us_=0;
    double last_count_=0, integral_=0, applied_duty_=0;
    int direction_=0;
    bool qualified_=false, touched_=false, reversing_=false;
    State state_=State::idle;
    Fault fault_=Fault::none;
};
} // namespace blinds
