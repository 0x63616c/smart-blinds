#pragma once
#include "smart_blinds/motion_session.hpp"
#include "smart_blinds/port_checks.hpp"
#include "smart_blinds/runtime_lifecycle.hpp"
#include "smart_blinds/gauge_continuity.hpp"
#include "smart_blinds/pd_monitor.hpp"
#include <cinttypes>
#include <cstdio>
#include <type_traits>

namespace blinds::runtime {
// Only trusted local commissioning may supply these records. Radio credentials
// are deliberately absent. The application supplies the empty default.
struct Configuration {
    bool task_timing_verified=false, bus_readback_verified=false, sensor_handoff_verified=false;
    std::uint64_t verified_for_boot=0;
    port::Profile port{};
    BenchMotionProfile motion{};
    Calibration calibration{};
    Limits limits{};
    power::continuity::Profile gauge{};
    smart_blinds::ClockModel clock{};
    // Independent board revision qualification, never inferred from chip ACK.
    bool pd_shared_bus_verified=false;
    smart_blinds::pd::FactoryRecord pd_factory{};
    bool valid(std::uint64_t boot) const {
        return boot && verified_for_boot==boot && task_timing_verified && bus_readback_verified && sensor_handoff_verified &&
            port.valid() && motion.bench_qualified && motion.holding_qualified &&
            motion.qualification_id==port.qualification_id && motion.max_duty<=port.max_duty &&
            calibration.valid() && gauge.valid(boot) && clock.validated &&
            clock.growth_ppm<=10000 && clock.stamp_guard_us<=1000;
    }
};
struct Network {
    std::optional<smart_blinds::ClockBounds> clock;
    std::uint64_t connection=0,probe=0;
    bool attached=false,awake=false;
    std::uint32_t revocation=0; // Local asynchronous invalidation generation.
    // Trusted local radio policy holds ownership through terminal sensor park.
    // This is distinct from a new preflight sensing demand, never wire input.
    bool operation=false;
};
inline Network admitted_network(Network value,const Revocation& signals) {
    return value.revocation==signals.generation() && !signals.failed() ? value : Network{};
}
struct Power {
    std::uint32_t window=0; // Local sensing generation, never received over radio.
    power::Report gauge{};
    smart_blinds::charger::OffCapture charger{};
    power::MotionPower at(std::uint64_t now) const { return power::motion_power(gauge,charger,now); }
    Power in_window(std::uint32_t expected) const { return expected && window==expected ? *this : Power{}; }
};
struct Snapshot {
    MotionSession::Status status{};
    std::uint64_t connection=0,probe=0;
    Parked parking{};
};
// The RTOS copies these through length-one queues. No pointers, heap ownership,
// seqlock/data-race assumptions or receipt-time freshness substitution.
static_assert(std::is_trivially_copyable<Network>::value);
static_assert(std::is_trivially_copyable<Power>::value);
static_assert(std::is_trivially_copyable<MotionSession::Status>::value);
static_assert(std::is_trivially_copyable<Snapshot>::value);

// Sole producer is the transport owner. The control worker consumes inbox.
class Ingress {
public:
    enum class Result { queued,malformed,unauthenticated,rejected };
    explicit Ingress(MotionSession::Inbox& inbox) : inbox_(inbox) {}
    bool connected() {
        disconnected();
        if(generation_==UINT32_MAX || !inbox_.connected(++generation_)) return false;
        network_.connection=generation_; return true;
    }
    void disconnected() { inbox_.disconnected(); network_.connection=0; clear_clock(); }
    void radio(bool attached,bool awake,bool operation=false) {
        network_.attached=attached; network_.awake=attached && awake;
        network_.operation=network_.awake && operation;
        if(!network_.awake) clear_clock();
    }
    // A pending new probe does not erase the previously accepted bound. Failed
    // assessment, sleep, detach or a new DTLS connection does erase it.
    bool qualify(std::uint64_t probe,const std::optional<smart_blinds::ClockBounds>& bound,std::uint64_t now) {
        if(!network_.connection || !network_.awake || !probe || probe<=network_.probe ||
           !bound || !bound->device_qualified(now)) { clear_clock(); return false; }
        network_.clock=bound; network_.probe=probe; return true;
    }
    void clear_clock() { network_.clock.reset(); network_.probe=0; }
    Network snapshot(std::uint64_t now) {
        if(network_.clock && !network_.clock->device_qualified(now)) clear_clock();
        return network_;
    }
    Result submit(const std::uint8_t* bytes,std::size_t size,bool authenticated,std::uint64_t now) {
        if(!authenticated || !network_.connection) return Result::unauthenticated;
        const auto request=wire::decode(bytes,size);
        if(!request) return Result::malformed;
        if(!activity_.begin()) return Result::rejected;
        const bool queued=inbox_.push({*request,network_.connection,now,true});
        activity_.end();
        return queued ? Result::queued : Result::rejected;
    }
    std::uint32_t activity() const { return activity_.current(); }
    bool pending() const { return inbox_.pending(); }
    std::uint64_t received_message() const { return inbox_.received_message(); }
private:
    MotionSession::Inbox& inbox_;
    std::uint32_t generation_=0;
    Network network_{};
    Activity activity_;
};
inline SessionInput input(const FastObservation& fast,const Power& power,const Network& network,std::uint64_t now) {
    return {fast,power.at(now),network.clock,network.probe,network.connection,network.attached,network.awake,false};
}
template<class Sample>
FastObservation observe(bool initialized,bool raw_stop,MotionSession::Phase previous,
                        Revocation& signals,Sample sample) {
    const bool stop=signals.take_stop() || raw_stop;
    FastObservation fast{};
    // Do not wait for ADC to issue the first STOP. While already settling the
    // motor is inhibited, so continue sampling to assess the final coordinate.
    if(initialized && (!stop || previous==MotionSession::Phase::settling)) fast=sample();
    fast.stop_pressed=fast.stop_pressed || stop || signals.take_stop();
    return fast;
}
inline const char* name(MotionSession::Phase phase) {
    switch(phase) {
    case MotionSession::Phase::unreferenced:return "unreferenced";
    case MotionSession::Phase::idle:return "idle";
    case MotionSession::Phase::preparing:return "preparing";
    case MotionSession::Phase::ready:return "ready";
    case MotionSession::Phase::committed:return "committed";
    case MotionSession::Phase::moving:return "moving";
    case MotionSession::Phase::settling:return "settling";
    case MotionSession::Phase::fault:return "fault";
    }
    return "invalid";
}
inline const char* name(MotionSession::Result result) {
    switch(result) {
    case MotionSession::Result::none:return "none";
    case MotionSession::Result::accepted:return "accepted";
    case MotionSession::Result::stale:return "stale";
    case MotionSession::Result::invalid:return "invalid";
    case MotionSession::Result::busy:return "busy";
    case MotionSession::Result::unqualified:return "unqualified";
    case MotionSession::Result::reference:return "reference";
    case MotionSession::Result::power:return "power";
    case MotionSession::Result::clock:return "clock";
    case MotionSession::Result::connection:return "connection";
    case MotionSession::Result::deadline:return "deadline";
    case MotionSession::Result::control:return "control";
    case MotionSession::Result::io:return "io";
    case MotionSession::Result::stopped:return "stopped";
    case MotionSession::Result::finished:return "finished";
    }
    return "invalid";
}
inline bool status_json(char* out,std::size_t size,std::uint64_t boot,const Snapshot& snapshot,
                        const Power& power,const Network& network,bool io_qualified,std::uint64_t now) {
    const auto& status=snapshot.status;
    const bool fresh=status.observed_us && status.observed_us<=now && now-status.observed_us<=30000;
    const bool network_ready=network.attached && network.awake && network.connection && network.probe &&
        network.clock && network.clock->device_qualified(now) &&
        snapshot.connection==network.connection && snapshot.probe==network.probe;
    char height[32]="null",soc[24]="null";
    // Stale coordinates remain diagnostic only, with their original observation.
    if(status.height_mm) std::snprintf(height,sizeof(height),"%.3f",*status.height_mm);
    const auto p=power.at(now);
    if(p.ready && power.gauge.soc_percent) std::snprintf(soc,sizeof(soc),"%.2f",*power.gauge.soc_percent);
    const int n=std::snprintf(out,size,
        "{\"boot\":\"%016" PRIx64 "\",\"sampled_us\":\"%016" PRIx64 "\",\"phase\":\"%s\","
        "\"result\":\"%s\",\"command\":\"%016" PRIx64 "\",\"last_message\":\"%016" PRIx64 "\","
        "\"io_qualified\":%s,\"fresh\":%s,\"ready\":%s,\"reference_valid\":%s,\"awake_required\":%s,"
        "\"height_mm\":%s,\"power_ready\":%s,\"power_sampled_us\":\"%016" PRIx64 "\",\"soc_percent\":%s}",
        boot,status.observed_us,name(status.phase),name(status.result),status.command,status.last_message,
        io_qualified ? "true":"false",fresh ? "true":"false",
        fresh && status.ready && p.ready && io_qualified && network_ready ? "true":"false",
        status.reference_valid ? "true":"false",status.awake_required ? "true":"false",height,p.ready ? "true":"false",
        p.observed_us,soc);
    return n>0 && static_cast<std::size_t>(n)<size;
}
} // namespace blinds::runtime
