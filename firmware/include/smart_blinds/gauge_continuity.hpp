#pragma once
#include "smart_blinds/power_evidence.hpp"
#include <limits>

namespace blinds::power::continuity {
enum class Fault { none, qualification, context, transition, expired, bus, clock, profile, protection, values };
// MAX17320 Rev12, pp91-94,108-109,113,120-121. Logical 9-bit register
// addresses: normal <0x100 at I2C0x36; shadow at I2C0x0B, low pointer byte.
struct Guard {
    std::uint16_t status=0, alerts=0, protection=0, status2=0, fstat=0, fets=0, battery_status=0;
    std::uint16_t config=0, config2=0, nv_config=0, hibernate=0;
    std::array<std::uint16_t,4> rom{};
    std::uint16_t dev_name=0, pack_config=0, nv_config0=0, nv_config1=0, sense=0, thermistor=0;
};
enum class ReadError { none, bus, clock, timeout, rejected };
struct Capture {
    GaugeCapture gauge{};
    Guard before{},after{};
    ReadError error=ReadError::bus;
};
class ReadOnlyBus {
public:
    virtual ~ReadOnlyBus()=default;
    virtual std::int64_t now_us()=0;
    // Must obey timeout; no retries, writes, flag clearing or gauge wake here.
    virtual bool read_word(std::uint16_t logical_register,std::uint16_t& value,
                           std::uint32_t timeout_ms)=0;
    virtual Fault read_failure() const { return Fault::bus; }
};
// Synchronous owner-only callbacks: no bus access, publication or reentrancy.
class CaptureObserver {
public:
    virtual ~CaptureObserver()=default;
    virtual Fault begin(std::int64_t started_us) noexcept=0;
    virtual Fault word(std::uint16_t reg,std::uint16_t raw) noexcept=0;
    virtual void failed(Fault reason) noexcept=0;
};
Capture read_capture(ReadOnlyBus& bus,CaptureObserver* observer=nullptr);

struct Profile {
    PackProfile pack{};
    std::array<std::uint16_t,4> rom{};
    std::uint16_t config=0,config2=0,nv_config=0;
    // Trusted local physical qualification, never a network-supplied approval.
    // Includes autonomous mode transitions, conversion timing, and no other
    // writer capable of changing modes/config or clearing sticky evidence.
    bool mode_continuity_verified=false,exclusive_access_verified=false;
    std::uint64_t max_light_sleep_us=0;
    bool valid(std::uint64_t boot) const;
};
// Rejects only violations proved by operands received in this capture.
// This shares the full monitor's guard and numeric predicates.
class CaptureValidation {
public:
    explicit CaptureValidation(Profile profile) : profile_(profile) {}
    void reset() { cells_={};present_=0;pack_=protected_=0; }
    Fault word(std::uint16_t reg,std::uint16_t raw) noexcept;
private:
    Profile profile_;
    std::array<double,3> cells_{};
    unsigned present_=0;
    double pack_=0,protected_=0;
};
struct Context {
    std::uint64_t boot=0,bus_generation=0,monitoring_session=0;
    std::uint64_t pack_binding=0,qualification_id=0;
    bool operator==(const Context& b) const {
        return boot==b.boot && bus_generation==b.bus_generation &&
            monitoring_session==b.monitoring_session && pack_binding==b.pack_binding &&
            qualification_id==b.qualification_id;
    }
};
enum class Phase { warming, active, parked, awaiting_capture, invalid };
struct Result {
    Report report{};
    Phase phase=Phase::invalid;
    Fault fault=Fault::qualification;
};

// A private RAM continuity ticket, NOT cached measurements. No restore/import,
// copy, reset or approval API; an invalid instance requires a new trusted
// session and the original cold warmup. Not connected to either C6 app.
class Monitor {
public:
    Monitor(Profile profile,Context context);
    Monitor(const Monitor&)=delete;
    Monitor& operator=(const Monitor&)=delete;
    Monitor(Monitor&&)=delete;
    Monitor& operator=(Monitor&&)=delete;
    Result observe(const Capture& capture,Context context,std::uint64_t now_us);
    Fault capture_start(Context context,std::int64_t started_us) const;
    // Caller must establish that only MCU light sleep occurs while the
    // independently powered gauge continues in the qualified active mode.
    bool park_light_sleep(Context context,std::uint64_t now_us);
    bool resume_light_sleep(Context context,std::uint64_t now_us);
    void invalidate(Fault reason=Fault::context);
    Phase phase() const { return phase_; }
    Fault fault() const { return fault_; }
private:
    bool check_context_time(Context context,std::uint64_t now_us);
    Result failed(Fault fault);
    Profile profile_;
    Context context_;
    GaugeMonitor monitor_;
    Phase phase_=Phase::warming;
    Fault fault_=Fault::none;
    std::uint64_t last_now_=0,last_capture_=0,last_finished_=0,last_ready_=0,parked_at_=0,resumed_at_=0;
    bool seen_capture_=false;
};
} // namespace blinds::power::continuity
