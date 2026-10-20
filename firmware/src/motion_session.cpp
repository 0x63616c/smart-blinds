#include "smart_blinds/motion_session.hpp"
#include <algorithm>
#include <cmath>
#include <limits>

namespace blinds {
namespace {
std::uint64_t error_ms(std::uint64_t us) { return (us+999)/1000+1; } // Includes integer clock quantization.
}
MotionSession::MotionSession(MotionIo& io,CounterOrigin& origin,Calibration calibration,Limits limits,
                             BenchMotionProfile profile,std::uint64_t boot)
    : io_(io),origin_(origin),calibration_(calibration),limits_(limits),controller_(calibration,limits,boot),
      executor_(io,calibration,profile,boot),boot_(boot) {
    qualified_=boot && profile.bench_qualified && profile.holding_qualified && profile.qualification_id &&
        calibration.valid() && executor_.qualified() && controller_.state()!=State::fault && limits.lease_ms==300 && limits.max_clock_error_ms==10;
}
bool MotionSession::active() const {
    return phase_==Phase::preparing || phase_==Phase::ready || phase_==Phase::committed ||
        phase_==Phase::moving || phase_==Phase::settling;
}
bool MotionSession::establish_reference(const PhysicalReference& r) {
    const auto now=io_.now_us();
    if(!qualified_ || active() || phase_==Phase::fault || !r.independently_observed || r.boot!=boot_ ||
       !r.record || r.record<=reference_record_ || !r.pack_binding || r.calibration!=calibration_.revision() ||
       r.observed_us>now || now-r.observed_us>100000 || !calibration_.height_at(r.count) || now<last_now_) return false;
    last_now_=now; reference_record_=r.record; saved_count_=last_count_=r.count; pack_binding_=r.pack_binding;
    referenced_=true; phase_=Phase::idle; result_=Result::accepted;
    return true;
}
bool MotionSession::healthy(const SessionInput& in,std::uint64_t now,bool count) const {
    const auto& f=in.fast;
    return in.power.ready && in.power.pack_binding==pack_binding_ && in.power.observed_us<=now &&
        now-in.power.observed_us<=250000 && std::isfinite(in.power.pack_v) &&
        in.power.pack_v>=limits_.min_pack_v && in.power.pack_v<=12.6 &&
        f.valid && f.sequence && !f.driver_fault && f.sampled_us<=now && now-f.sampled_us<=10000 &&
        std::isfinite(f.current_a) && std::abs(f.current_a)<limits_.current_trip_a &&
        (!count || (f.count_valid && f.encoder_epoch==epochs_.value() && calibration_.height_at(f.count)));
}
Measurement MotionSession::measurement(const SessionInput& in) const {
    return {in.fast.count,in.fast.current_a,in.power.pack_v,in.fast.driver_fault,in.power.ready};
}
MotionEvidence MotionSession::evidence(const SessionInput& in) const {
    const auto authority_until=owner_==Owner::local ? deadline_us_ : lease_until_us_;
    return {in.fast.sequence,in.fast.sampled_us,in.power.observed_us,in.fast.encoder_epoch,authority_until,
        calibration_.revision(),in.fast.count,in.fast.current_a,in.power.pack_v,in.power.ready,referenced_,
        in.fast.driver_fault,in.fast.stop_pressed};
}
std::optional<wire::Projection::Time> MotionSession::clock(const SessionInput& in,std::uint64_t now) const {
    if(!in.clock || !in.clock_probe || in.clock_connection!=connection_ || in.clock_probe<last_probe_ ||
       in.clock->device_reference_us()<last_clock_reference_) return {};
    auto time=projection_.at(*in.clock,now);
    if(!time || error_ms(time->error_us)>limits_.max_clock_error_ms) return {};
    return time;
}
bool MotionSession::lease(const wire::Request& r,const wire::Projection::Time& time,const smart_blinds::ClockBounds& bounds,
                          std::uint64_t now,bool apply) {
    // Freshness is measured at the source; queue receipt never renews a lease.
    if(r.sent_us<=last_sent_us_ || (r.sent_us>time.host_us && r.sent_us-time.host_us>time.error_us)) return false;
    // Cover an old packet's 100 ms source-age allowance plus the complete 300 ms
    // lease. This also forces refresh before the clock model ages out; a later
    // receive timestamp never supplies validity. ClockBounds caps model drift.
    const auto lifetime=projection_.at(bounds,now+message_age_us+300000);
    if(!lifetime || error_ms(lifetime->error_us)>limits_.max_clock_error_ms) return false;
    const auto local=projection_.local(r.sent_us);
    if(!local || *local<lifetime->error_us) return false;
    const auto earliest=*local-lifetime->error_us;
    if(earliest>std::numeric_limits<std::uint64_t>::max()-300000) return false;
    const auto until=earliest+300000;
    if(until<=now || until-now<=MotionExecutor::cycle_max_us+MotionExecutor::cycle_budget_us) return false;
    if(apply && controller_.renew_lease(boot_,last_command_,r.sent_us/1000,time.host_us/1000,
                                     error_ms(lifetime->error_us))!=Reason::ok) return false;
    lease_until_us_=until; last_sent_us_=r.sent_us; lease_origin_us_=*local; lease_error_us_=lifetime->error_us;
    return true;
}
bool MotionSession::fail(Result result) {
    // Fault/unknown transport loss never preserves an unobserved final count.
    executor_.stop(); controller_.lose_reference(); projection_.invalidate();
    referenced_=false; phase_=Phase::fault; result_=result; controller_prepared_=false;
    if(owner_==Owner::local) local_result_=result;
    return false;
}
void MotionSession::controlled_stop(Result result) {
    if(phase_==Phase::settling || phase_==Phase::fault) return;
    if(!active()) { result_=result; return; }
    controller_.stop();
    if(!executor_.begin_settling()) { fail(Result::io); return; }
    phase_=Phase::settling; result_=result;
    if(owner_==Owner::local) local_result_=result;
}
bool MotionSession::parked() {
    return executor_.verify_parked(last_now_);
}
bool MotionSession::begin_execution(Owner owner,const SessionInput& in) {
    // No external sequence can allocate or exhaust the physical execution space.
    // Even failed OFF/origin/setup attempts consume this epoch before any I/O.
    owner_=owner; controller_prepared_=local_started_=false;
    const auto epoch=epochs_.take();
    if(!epoch) return fail(Result::deadline);
    if(!parked()) return fail(Result::io);
    const auto before=io_.now_us();
    const bool installed=origin_.set_counter_origin(*epoch,saved_count_);
    const auto after=io_.now_us();
    if(!installed || after<before || after-before>MotionExecutor::io_budget_us) return fail(Result::io);
    if(!executor_.open_sensing(boot_,*epoch,evidence(in))) return fail(Result::io);
    phase_=Phase::preparing;
    return true;
}
MotionSession::Result MotionSession::local_request(const LocalIntent& intent,const SessionInput& in,std::uint64_t now) {
    if(intent.boot!=boot_ || !intent.gesture) return Result::invalid;
    if(intent.gesture<=last_gesture_) return Result::stale;
    last_gesture_=intent.gesture; // Refused/cold gestures cannot execute after warmup.
    if(intent.issued_us>now || now-intent.issued_us>queue_age_us || intent.expires_us<=now ||
       intent.expires_us<=intent.issued_us || intent.expires_us-intent.issued_us>local_intent_lifetime_us)
        return Result::stale;
    if(intent.endpoint!=LocalIntent::Endpoint::up && intent.endpoint!=LocalIntent::Endpoint::down) return Result::invalid;
    if(!qualified_) return Result::unqualified;
    if(!referenced_ || intent.reference!=reference_record_ || intent.calibration!=calibration_.revision()) return Result::reference;
    if(phase_==Phase::fault) return result_;
    if(active()) {
        // A fresh gesture during any operation is consumed as STOP, not takeover.
        controlled_stop(Result::stopped);
        return phase_==Phase::fault ? result_ : Result::stopped;
    }
    if(!healthy(in,now,false)) return Result::power;
    const auto origin=calibration_.height_at(saved_count_);
    const double target=intent.endpoint==LocalIntent::Endpoint::up ? calibration_.high() : calibration_.low();
    Trajectory trajectory;
    if(!origin || !trajectory.configure(*origin,target,limits_.max_speed_mm_s,limits_.max_accel_mm_s2)) return Result::invalid;
    if(std::abs(*origin-target)<=limits_.endpoint_tolerance_mm) {
        // The independently referenced or previously settled coordinate already
        // satisfies this endpoint. Qualified passive holding remains required.
        // Verify OFF, retain that exact count, and do not arm/count/feed at all.
        owner_=Owner::local;
        if(!parked()) { fail(Result::io); return Result::io; }
        remote_after_us_=io_.now_us();
        result_=Result::finished;
        return Result::finished;
    }
    const double duration=trajectory.duration_s()*1e6;
    if(!std::isfinite(duration) || duration>static_cast<double>(max_session_us-2500000)) return Result::deadline;
    const auto span=static_cast<std::uint64_t>(std::ceil(duration))+2500000;
    if(now>std::numeric_limits<std::uint64_t>::max()-span) return Result::deadline;
    // This is a local monotonic authority deadline, not a network lease. It
    // includes bounded encoder/driver startup and settling and is never renewed.
    deadline_us_=now+span; local_endpoint_=intent.endpoint; projection_.invalidate();
    if(!begin_execution(Owner::local,in)) return result_;
    result_=Result::accepted;
    return Result::accepted;
}
MotionSession::Result MotionSession::request(const wire::Envelope& envelope,const SessionInput& in,std::uint64_t now) {
    const auto& r=envelope.request;
    if(!envelope.authenticated || r.boot!=boot_ || !envelope.connection || envelope.connection!=connection_)
        return Result::connection;
    if(r.message<=last_message_) return Result::stale;
    last_message_=r.message; // A rejected authenticated request cannot become executable later.
    const auto bytes=wire::encode(r);
    if(!wire::decode(bytes.data(),bytes.size()) || envelope.received_us>now || now-envelope.received_us>queue_age_us)
        return Result::invalid;
    if(!qualified_) return Result::unqualified;
    if(!referenced_) return Result::reference;
    if(phase_==Phase::settling || phase_==Phase::fault) return Result::busy;
    if(owner_==Owner::local && active()) return Result::busy;
    if(r.kind==wire::Kind::prepare && remote_after_us_ && envelope.received_us<=*remote_after_us_) return Result::stale;
    if(r.kind!=wire::Kind::prepare && owner_!=Owner::remote) return Result::invalid;
    if(!in.attached || !in.radio_awake) return Result::connection;
    if(r.kind==wire::Kind::prepare && !active()) {
        if(!in.clock || in.clock_connection!=connection_ || !projection_.bind(*in.clock,now)) return Result::clock;
        last_probe_=last_clock_reference_=0;
    }
    const auto time=clock(in,now);
    if(!time || r.probe!=in.clock_probe) return Result::clock;
    if((r.sent_us>time->host_us && r.sent_us-time->host_us>time->error_us) ||
       (r.sent_us<=time->host_us && time->host_us-r.sent_us>message_age_us-time->error_us)) return Result::stale;
    if(r.calibration!=calibration_.revision()) return Result::invalid;
    if(r.kind!=wire::Kind::prepare) {
        if(!controller_prepared_ || r.command!=last_command_) return Result::invalid;
        if(r.kind==wire::Kind::lease) return lease(r,*time,*in.clock,now,true) ? Result::accepted : Result::stale;
        if(r.kind!=wire::Kind::commit || phase_!=Phase::ready) return Result::busy;
        if(lease_until_us_<=now || lease_until_us_-now<=MotionExecutor::cycle_max_us+MotionExecutor::cycle_budget_us)
            return Result::deadline;
        if(controller_.commit(boot_,last_command_,time->host_us/1000)!=Reason::ok) return Result::deadline;
        phase_=Phase::committed; return Result::accepted;
    }
    if(active()) return Result::busy;
    if(r.command<=last_command_) return Result::stale;
    if(!healthy(in,now,false)) return Result::power;
    const auto origin=calibration_.height_at(saved_count_);
    const double start=r.origin_um/1000.,target=r.target_um/1000.,speed=r.speed_um_s/1000.,accel=r.acceleration_um_s2/1000.;
    if(!origin || !calibration_.count_at(start) || !calibration_.count_at(target) ||
       std::abs(*origin-start)>limits_.start_tolerance_mm || speed>limits_.max_speed_mm_s || accel>limits_.max_accel_mm_s2)
        return Result::invalid;
    const auto start_ms=(r.start_us+999)/1000,now_ms=time->host_us/1000;
    if(start_ms<=now_ms || start_ms-now_ms<limits_.min_prepare_lead_ms+30 ||
       start_ms-now_ms>limits_.max_prepare_lead_ms) return Result::deadline;
    Trajectory trajectory;
    if(!trajectory.configure(start,target,speed,accel)) return Result::invalid;
    const double duration=trajectory.duration_s()*1e6;
    const auto start_local=projection_.local(start_ms*1000);
    if(!start_local || *start_local<now || duration>static_cast<double>(max_session_us) ||
       *start_local-now+static_cast<std::uint64_t>(std::ceil(duration))+2500000>max_session_us) return Result::deadline;
    last_sent_us_=0;
    if(!lease(r,*time,*in.clock,now,false)) return Result::stale;
    last_command_=r.command; pending_=r;
    deadline_us_=*start_local+static_cast<std::uint64_t>(std::ceil(duration))+2500000;
    if(!begin_execution(Owner::remote,in)) return result_;
    return Result::accepted;
}
void MotionSession::advance_local(const SessionInput& in,std::uint64_t now) {
    if(deadline_us_-now<=MotionExecutor::cycle_max_us+MotionExecutor::cycle_budget_us) { fail(Result::deadline); return; }
    const bool warming=executor_.state()==MotionExecutor::State::encoder_warming;
    if(!healthy(in,now,!warming)) { fail(Result::power); return; }
    if(warming) {
        executor_.poll_sensing(evidence(in));
        if(executor_.state()==MotionExecutor::State::fault) fail(Result::io);
        return;
    }
    last_count_=in.fast.count;
    if(executor_.state()==MotionExecutor::State::sensing) {
        if(controller_.establish_reference(measurement(in))!=Reason::ok) { fail(Result::control); return; }
        if(!executor_.arm(evidence(in))) fail(Result::io);
        return;
    }
    if(executor_.state()==MotionExecutor::State::arming) {
        // Supervised coast only: no trajectory has started, no remote command
        // or lease is manufactured to obtain the first checked heartbeat.
        if(!executor_.update({false,0,*calibration_.height_at(in.fast.count),State::armed,Reason::ok},evidence(in))) fail(Result::io);
        return;
    }
    if(!local_started_) {
        if(controller_.local_move(local_endpoint_==LocalIntent::Endpoint::up,measurement(in),now/1000)!=Reason::ok) {
            fail(Result::control); return;
        }
        local_started_=true;
    }
    const auto output=controller_.tick(measurement(in),now/1000,0); // Local clock; no remote clock model required.
    if(output.state==State::idle) { controlled_stop(Result::finished); return; }
    if(output.state==State::fault || output.state==State::unreferenced) { fail(Result::control); return; }
    if(!executor_.update(output,evidence(in))) { fail(Result::io); return; }
    if(output.state==State::moving) phase_=Phase::moving;
}
void MotionSession::advance(const SessionInput& in,std::uint64_t now) {
    if(!active()) return;
    if(now>=deadline_us_) { fail(Result::deadline); return; }
    if(phase_==Phase::settling) {
        if(!healthy(in,now,true)) { fail(Result::power); return; }
        if(executor_.poll_settling(evidence(in))) {
            const auto final=executor_.settled_count();
            if(!final || !parked()) { fail(Result::io); return; }
            saved_count_=last_count_=*final; controller_prepared_=false;
            phase_=Phase::idle; projection_.invalidate();
            if(owner_==Owner::local) remote_after_us_=io_.now_us();
        } else if(executor_.state()==MotionExecutor::State::fault) fail(Result::io);
        return;
    }
    if(owner_==Owner::local) { advance_local(in,now); return; }
    if(!in.attached || !in.radio_awake) { fail(Result::connection); return; }
    const auto time=clock(in,now);
    if(!time) { fail(Result::clock); return; }
    last_probe_=in.clock_probe; last_clock_reference_=in.clock->device_reference_us();
    // A wider newly qualified bound can shorten outstanding permission. It can
    // never extend it without a new authenticated source timestamp.
    const auto lifetime=projection_.at(*in.clock,now+message_age_us+300000);
    if(!lifetime || error_ms(lifetime->error_us)>limits_.max_clock_error_ms || lease_origin_us_<lifetime->error_us) {
        fail(Result::clock); return;
    }
    lease_error_us_=std::max(lease_error_us_,lifetime->error_us);
    lease_until_us_=std::min(lease_until_us_,lease_origin_us_-lease_error_us_+300000);
    if(now>=deadline_us_ || lease_until_us_<=now ||
       lease_until_us_-now<=MotionExecutor::cycle_max_us+MotionExecutor::cycle_budget_us) { fail(Result::deadline); return; }
    const bool warming=executor_.state()==MotionExecutor::State::encoder_warming;
    if(!healthy(in,now,!warming)) { fail(Result::power); return; }
    if(warming) {
        executor_.poll_sensing(evidence(in));
        if(executor_.state()==MotionExecutor::State::fault) fail(Result::io);
        return; // A sample taken before counter_start cannot arm the motor.
    }
    last_count_=in.fast.count;
    if(executor_.state()==MotionExecutor::State::sensing) {
        const auto& r=pending_;
        const Command command{boot_,last_command_,r.calibration,(r.start_us+999)/1000,
            r.origin_um/1000.,r.target_um/1000.,r.speed_um_s/1000.,r.acceleration_um_s2/1000.};
        if(controller_.establish_reference(measurement(in))!=Reason::ok ||
           controller_.prepare(command,measurement(in),time->host_us/1000,error_ms(time->error_us))!=Reason::ok ||
           controller_.renew_lease(boot_,last_command_,r.sent_us/1000,time->host_us/1000,error_ms(lease_error_us_))!=Reason::ok) {
            fail(Result::control); return;
        }
        controller_prepared_=true;
        if(!executor_.arm(evidence(in))) fail(Result::io);
        return;
    }
    const auto output=controller_.tick(measurement(in),time->host_us/1000,error_ms(time->error_us));
    if(output.state==State::idle) { controlled_stop(Result::finished); return; }
    if(output.state==State::fault || output.state==State::unreferenced) { fail(Result::control); return; }
    if(!executor_.update(output,evidence(in))) { fail(Result::io); return; }
    if(phase_==Phase::preparing && executor_.state()==MotionExecutor::State::running) phase_=Phase::ready;
    if(output.state==State::moving) phase_=Phase::moving;
}
MotionSession::Status MotionSession::cycle(Inbox& inbox,const SessionInput& in,std::optional<LocalIntent> local) {
    const auto now=io_.now_us();
    const auto release_before=remote_after_us_;
    if(active() && !executor_.check_cadence(last_now_)) { fail(Result::io); return status(); }
    if(now<last_now_) { fail(Result::clock); return status(); }
    last_now_=now;
    // STOP dominates queued commit/lease/prepare. A held button keeps draining
    // commands while the already-inhibited motor settles; it cannot restart.
    const bool remote_stop=inbox.stop_pending();
    if(in.manual_intervention || in.global_fault) {
        inbox.discard(); fail(in.manual_intervention ? Result::reference : Result::io); return status();
    }
    // Physical evidence loss outranks either authority and a simultaneous STOP.
    // fail() inhibits immediately, but never retains an uncertain final count.
    // Raw STOP may intentionally bypass ADC on its first iteration. Do not
    // mistake that omitted observation for a reported physical fault; the
    // following settling iteration still requires the complete fresh sample.
    if(active() && ((!in.fast.stop_pressed && !remote_stop) || in.fast.valid) &&
       !healthy(in,now,executor_.state()!=MotionExecutor::State::encoder_warming)) {
        inbox.discard(); fail(Result::power); return status();
    }
    if(in.fast.stop_pressed || remote_stop) {
        if(local && local->boot==boot_ && local->gesture>last_gesture_) {
            last_gesture_=local->gesture; local_result_=Result::stopped;
        }
        local.reset();
        const bool already_settling=phase_==Phase::settling;
        inbox.discard(); controlled_stop(Result::stopped);
        if(!already_settling) return status();
    }
    const auto connection=inbox.connection();
    if(active() && owner_==Owner::remote && phase_!=Phase::settling && connection!=connection_) {
        inbox.discard(); fail(Result::connection); return status();
    }
    if(!active() || owner_==Owner::local) connection_=connection;
    if(local && phase_!=Phase::fault) {
        const bool already_settling=phase_==Phase::settling;
        local_result_=local_request(*local,in,now);
        // Never leave an older queued remote intent to execute when local
        // motion finishes. Producer replay floors remain consumed.
        inbox.discard();
        // A newly requested STOP must not poll settling twice at one timestamp.
        if(phase_==Phase::fault || (local_result_==Result::stopped && !already_settling)) return status();
    }
    if(!local && !in.fast.stop_pressed && !remote_stop && phase_!=Phase::fault) {
        const auto next=inbox.pop();
        if(next) {
            // A late ordinary message must still consume its replay sequence,
            // but cannot erase the settled endpoint/STOP outcome. In particular
            // an in-flight lease can arrive after the last moving observation.
            const auto prior=result_;
            const bool terminal=(phase_==Phase::settling || phase_==Phase::idle) &&
                (prior==Result::finished || prior==Result::stopped);
            const auto result=request(*next,in,now);
            const bool new_prepare=next->request.kind==wire::Kind::prepare &&
                result==Result::accepted && phase_==Phase::preparing;
            if(phase_!=Phase::fault && !(owner_==Owner::local && active()))
                result_=terminal && !new_prepare ? prior : result;
        }
    }
    advance(in,now);
    // Close the backlog at local release. A producer that publishes afterward
    // with a pre-release receive stamp is rejected by request(), not relabelled.
    if(remote_after_us_!=release_before) inbox.discard();
    return status();
}
MotionSession::Status MotionSession::status() const {
    return {phase_,result_,owner_==Owner::local ? 0 : last_command_,last_message_,last_now_,
        owner_==Owner::remote && phase_==Phase::ready,referenced_,active(),
        referenced_ ? calibration_.height_at(last_count_) : std::nullopt,controller_.reason()};
}
} // namespace blinds
