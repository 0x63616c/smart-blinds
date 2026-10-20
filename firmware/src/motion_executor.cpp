#include "smart_blinds/motion_executor.hpp"
#include <algorithm>
#include <cmath>

namespace blinds {
MotionExecutor::MotionExecutor(MotionIo& io,Calibration calibration,BenchMotionProfile profile,std::uint64_t boot)
    : io_(io),calibration_(calibration),profile_(profile),heartbeat_(boot),boot_(boot) {
    qualified_=profile_.bench_qualified && profile_.qualification_id && boot && calibration_.valid();
    const double positive[]={profile_.max_duty,profile_.max_count_rate,profile_.max_fabric_rate,
        profile_.kp,profile_.ki,profile_.feedforward,profile_.current_trip_a,profile_.minimum_pack_v,
        profile_.reversal_speed_counts_s,profile_.reversal_current_a};
    for(auto value:positive) qualified_ &= std::isfinite(value) && value>0 && value<1e6;
    qualified_ &= profile_.max_duty<=1 && profile_.encoder_settle_us>=1000 && profile_.encoder_settle_us<=100000 &&
        profile_.reversal_coast_us>=1000 && profile_.reversal_timeout_us>profile_.reversal_coast_us &&
        profile_.reversal_timeout_us<=1000000 && profile_.no_progress_us>=20000 && profile_.no_progress_us<=1000000;
}
bool MotionExecutor::time() {
    const auto now=io_.now_us();
    if(now<last_now_) return fail(Fault::clock);
    last_now_=now;
    return true;
}
bool MotionExecutor::power_valid(const MotionEvidence& e) const {
    return e.power_ready && !e.driver_fault && !e.stop_pressed &&
        e.power_sampled_us<=last_now_ && last_now_-e.power_sampled_us<=250000 &&
        e.sampled_us<=last_now_ && last_now_-e.sampled_us<=10000 &&
        std::isfinite(e.pack_v) && e.pack_v>=profile_.minimum_pack_v && e.pack_v<=13 &&
        std::isfinite(e.current_a) && std::abs(e.current_a)<profile_.current_trip_a;
}
bool MotionExecutor::evidence_valid(const MotionEvidence& e) const {
    return power_valid(e) && e.reference_valid && e.encoder_epoch==command_ &&
        e.calibration_revision==calibration_.revision() && e.sequence>last_sequence_ &&
        e.sampled_us>last_sample_us_ && e.sampled_us>=counter_on_us_ &&
        // Leave enough local validity for the next control deadline plus this
        // iteration's bounded I/O. Never extend a received lease in this layer.
        e.control_valid_until_us>last_now_ &&
        e.control_valid_until_us-last_now_>cycle_max_us+cycle_budget_us &&
        calibration_.height_at(e.count).has_value();
}
bool MotionExecutor::safe_off() {
    if(!touched_) return true;
    // Do not short-circuit cleanup. A blocked task still needs the independent
    // hardware watchdog; a return value is not a proof of terminal voltage.
    const auto cleanup=[&](auto call) {
        const auto before=io_.now_us();
        const bool ok=call(); // Even a broken clock must not suppress OFF writes.
        const auto after=io_.now_us();
        return ok && after>=before && after-before<=io_budget_us;
    };
    bool ok=cleanup([&]{return io_.request_n(true);});
    ok=cleanup([&]{return io_.coast();}) && ok;
    ok=cleanup([&]{return io_.wdi_high();}) && ok;
    ok=cleanup([&]{return io_.charge_off();}) && ok;
    ok=cleanup([&]{return io_.counter_stop();}) && ok;
    ok=cleanup([&]{return io_.encoder_power(false);}) && ok;
    ok=cleanup([&]{return io_.awake_lock(false);}) && ok;
    applied_duty_=0; integral_=0; direction_=0; reversing_=false;
    return ok;
}
bool MotionExecutor::fail(Fault fault) {
    settled_count_.reset();
    state_=State::fault; fault_=fault;
    if(!safe_off()) fault_=Fault::io;
    return false;
}
bool MotionExecutor::open_sensing(std::uint64_t boot,std::uint64_t command,const MotionEvidence& power) {
    if(state_!=State::idle) return false;
    if(!qualified_) return fail(Fault::unqualified);
    if(boot!=boot_ || !command || command<=last_command_) return fail(Fault::command);
    if(!time()) return false;
    if(!power_valid(power)) return fail(Fault::evidence);
    command_=last_command_=command;
    settled_count_.reset();
    touched_=true;
    if(!operation([&]{return io_.request_n(true);}) || !operation([&]{return io_.coast();}) ||
       !operation([&]{return io_.wdi_high();}) || !operation([&]{return io_.charge_off();}) ||
       !operation([&]{return io_.awake_lock(true);}) || !operation([&]{return io_.encoder_power(true);})) return fail(Fault::io);
    rail_on_us_=last_now_;
    last_sequence_=last_sample_us_=0;
    state_=State::encoder_warming;
    return true;
}
bool MotionExecutor::poll_sensing(const MotionEvidence& power) {
    if(state_!=State::encoder_warming && state_!=State::sensing) return false;
    if(!time()) return false;
    if(!power_valid(power)) return fail(Fault::evidence);
    if(last_now_-rail_on_us_>=5000000) return fail(Fault::command);
    if(state_==State::encoder_warming && last_now_-rail_on_us_>=profile_.encoder_settle_us) {
        if(!operation([&]{return io_.counter_start(command_);})) return fail(Fault::io);
        counter_on_us_=last_now_; state_=State::sensing;
    }
    return state_==State::sensing;
}
bool MotionExecutor::arm(const MotionEvidence& e) {
    if(state_!=State::sensing) return false;
    if(!time()) return false;
    if(last_now_-rail_on_us_>=5000000) return fail(Fault::command);
    if(!evidence_valid(e)) return fail(Fault::evidence);
    if(!operation([&]{return io_.coast();}) || !operation([&]{return io_.wdi_high();})) return fail(Fault::io);
    if(!heartbeat_.arm(boot_,command_,{e.sequence,e.sampled_us,true,true},last_now_)) return fail(Fault::heartbeat);
    if(!operation([&]{return io_.request_n(false);}) || !heartbeat_.request_applied(last_now_)) return fail(Fault::io);
    last_cycle_us_=last_now_; last_sequence_=e.sequence; last_sample_us_=e.sampled_us; last_count_=e.count;
    last_progress_us_=last_now_; state_=State::arming;
    return true;
}
bool MotionExecutor::feed(const MotionEvidence& e,bool coasting) {
    const bool pulse=heartbeat_.cycle({e.sequence,e.sampled_us,true,coasting},last_now_);
    if(heartbeat_.state()==smart_blinds::Heartbeat::State::fault) return fail(Fault::heartbeat);
    if(pulse && (!operation([&]{return io_.heartbeat_pulse();}) || !heartbeat_.edge_applied(last_now_))) return fail(Fault::heartbeat);
    return true;
}
bool MotionExecutor::update(const Output& output,const MotionEvidence& e) {
    if(state_!=State::arming && state_!=State::running) return false;
    if(e.stop_pressed) return stop();
    if(!time()) return false;
    if(!evidence_valid(e)) return fail(Fault::evidence);
    if(last_now_<=last_cycle_us_ || last_now_-last_cycle_us_>cycle_max_us) return fail(Fault::clock);
    if(!heartbeat_.advance(last_now_)) return fail(Fault::heartbeat);
    if(output.state==blinds::State::idle || output.state==blinds::State::unreferenced || output.state==blinds::State::fault) return stop();
    if((output.state!=blinds::State::prepared && output.state!=blinds::State::armed && output.state!=blinds::State::moving) ||
       output.reason!=Reason::ok || !std::isfinite(output.velocity_mm_s) ||
       std::abs(output.velocity_mm_s)>profile_.max_fabric_rate ||
       (output.state!=blinds::State::moving && (output.motor_enable || output.velocity_mm_s!=0)) ||
       (!output.motor_enable && output.velocity_mm_s!=0)) return fail(Fault::output);
    const bool moving=output.state==blinds::State::moving && output.motor_enable;
    const auto desired=calibration_.count_rate(e.count,moving ? output.velocity_mm_s : 0);
    const double dt=static_cast<double>(e.sampled_us-last_sample_us_)/1e6;
    const double measured=(e.count-last_count_)/dt;
    if(!desired || std::abs(*desired)>profile_.max_count_rate || !std::isfinite(measured) ||
       std::abs(measured)>profile_.max_count_rate) return fail(Fault::evidence);
    if(e.count!=last_count_) last_progress_us_=last_now_;
    if(state_==State::arming) {
        if(!operation([&]{return io_.coast();})) return fail(Fault::io);
        if(!feed(e,true)) return false;
        if(heartbeat_.pwm_allowed()) state_=State::running;
    } else {
        const int wanted=(*desired>0) ? 1 : ((*desired<0) ? -1 : 0);
        if(wanted && direction_ && wanted!=direction_ && !reversing_) {
            reversing_=true; reverse_since_=last_now_; integral_=0;
        }
        if(reversing_ && last_now_-reverse_since_>=profile_.reversal_timeout_us) return fail(Fault::reversal);
        if(reversing_ && last_now_-reverse_since_>=profile_.reversal_coast_us &&
           std::abs(measured)<=profile_.reversal_speed_counts_s && std::abs(e.current_a)<=profile_.reversal_current_a) {
            reversing_=false; direction_=wanted;
        }
        if(!wanted || reversing_) {
            if(!operation([&]{return io_.coast();})) return fail(Fault::io);
            applied_duty_=0; integral_=0; last_progress_us_=last_now_;
        } else {
            if(!direction_) direction_=wanted;
            const auto error=*desired-measured;
            const auto trial=std::clamp(integral_+profile_.ki*error*dt,-profile_.max_duty,profile_.max_duty);
            const auto requested=profile_.feedforward*(*desired)+profile_.kp*error+trial;
            const auto signed_duty=wanted*std::clamp(wanted*requested,0.,profile_.max_duty);
            // Conditional integration includes the coast boundary, not only
            // maximum duty: do not wind up an opposing, disallowed drive.
            if(requested==signed_duty || (requested-signed_duty)*error<0) integral_=trial;
            const auto duty=std::abs(signed_duty);
            if(duty>0 && applied_duty_==0) last_progress_us_=last_now_;
            if(duty>0 && last_now_-last_progress_us_>=profile_.no_progress_us) return fail(Fault::stalled);
            if(!operation([&]{return duty>0 ? io_.pwm(direction_,duty) : io_.coast();})) return fail(Fault::io);
            applied_duty_=duty;
        }
        // Feed follows a successful current output operation and fresh evidence.
        if(!feed(e,applied_duty_==0)) return false;
    }
    last_cycle_us_=last_now_; last_sequence_=e.sequence; last_sample_us_=e.sampled_us; last_count_=e.count;
    return true;
}
bool MotionExecutor::begin_settling() {
    if(state_!=State::arming && state_!=State::running) return false;
    if(!profile_.holding_qualified) return fail(Fault::unqualified);
    if(!time()) return false;
    // Turn the motor/watchdog permission OFF before cancelling the software
    // heartbeat. Counting continues; this state can never issue PWM or WDI.
    if(!operation([&]{return io_.request_n(true);}) || !operation([&]{return io_.coast();}) ||
       !operation([&]{return io_.wdi_high();}) || !operation([&]{return io_.charge_off();})) return fail(Fault::io);
    heartbeat_.stop(last_now_);
    if(heartbeat_.state()!=smart_blinds::Heartbeat::State::idle) return fail(Fault::heartbeat);
    applied_duty_=0; integral_=0; direction_=0; reversing_=false;
    settling_started_us_=quiet_since_us_=last_now_;
    last_cycle_us_=last_now_;
    settled_count_.reset();
    state_=State::settling;
    return true;
}
bool MotionExecutor::poll_settling(const MotionEvidence& evidence) {
    if(state_!=State::settling) return false;
    if(!time()) return false;
    // A held local STOP is allowed during an already disabled coast. All other
    // live health, sample/epoch and timing checks still apply. No lease is needed
    // to keep observing an inhibited motor, and none is extended here.
    auto e=evidence; e.stop_pressed=false;
    if(!power_valid(e) || !e.reference_valid || e.encoder_epoch!=command_ || e.calibration_revision!=calibration_.revision() ||
       e.sequence<=last_sequence_ || e.sampled_us<=last_sample_us_ || !calibration_.height_at(e.count) ||
       last_now_<=last_cycle_us_ || last_now_-last_cycle_us_>cycle_max_us) return fail(Fault::evidence);
    if(last_now_-settling_started_us_>=500000) return fail(Fault::stalled);
    if(e.count!=last_count_ || std::abs(e.current_a)>profile_.reversal_current_a) quiet_since_us_=last_now_;
    last_count_=e.count; last_sequence_=e.sequence; last_sample_us_=e.sampled_us; last_cycle_us_=last_now_;
    if(last_now_-quiet_since_us_<100000) return false;
    const auto final_count=e.count;
    if(!stop()) return false;
    settled_count_=final_count;
    return true;
}
bool MotionExecutor::stop() {
    settled_count_.reset();
    const bool was_fault=state_==State::fault;
    const bool ok=safe_off();
    const auto now=io_.now_us();
    heartbeat_.stop(now);
    if(!ok) { state_=State::fault; fault_=Fault::io; return false; }
    if(was_fault) return false;
    if(now<last_now_) { state_=State::fault; fault_=Fault::clock; return false; }
    if(heartbeat_.state()==smart_blinds::Heartbeat::State::fault) { state_=State::fault; fault_=Fault::heartbeat; return false; }
    state_=State::idle;
    return true;
}
} // namespace blinds
