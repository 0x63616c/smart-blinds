#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace smart_blinds::charger {
// Byte addresses/fields from TI BQ25798 SLUSDV2C. This module can only hold
// external CE OFF and program EN_CHG=0. It has no charge-enable operation.
class Bus {
public:
    virtual ~Bus() = default;
    virtual bool read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size) = 0;
    virtual bool write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size) = 0;
    virtual std::uint64_t now_ms() const = 0;
    virtual void wait_ms(unsigned duration) = 0;
};
class Inhibit {
public:
    virtual ~Inhibit() = default;
    // Caller implements reviewed board OFF request/readback. No enable method.
    virtual bool hold_off() = 0;
};
// Existing owner/session identities, not a new counter or source entitlement.
struct ParkIdentity {
    std::uint64_t boot=0, pack=0, qualification=0;
    std::uint32_t epoch=0;
    std::uintptr_t owner=0;
    bool valid() const { return boot && pack && qualification && epoch && owner; }
    bool operator==(const ParkIdentity& other) const {
        return boot==other.boot && pack==other.pack && qualification==other.qualification &&
               epoch==other.epoch && owner==other.owner;
    }
};
class ParkGuard : public Inhibit {
public:
    // Owner supplies current identities and fresh actual settled motor OFF,
    // with no active/settling or queued command authority. Both are rechecked
    // around every transfer. No application currently implements this guard.
    virtual ParkIdentity identity() const = 0;
};
enum class SourceVoltage : std::uint16_t { nine = 9000, fifteen = 15000 };
enum class Error { none, inhibit, identity, strap, bus, timeout, clock, readback,
                   unconfigured, adc, status, fault, temperature };
// Optional synchronous first-failure notice, before independent OFF cleanup.
// Must be bounded/noexcept, and must not call back into charger or bus.
class FailureSink {
public:
    virtual ~FailureSink()=default;
    virtual void failed(Error reason) noexcept=0;
};
struct Register {
    std::uint8_t address, size;
    std::uint16_t value, mask;
};
using Profile = std::array<Register, 23>;
Profile profile(SourceVoltage voltage);

struct Capture {
    Error error = Error::unconfigured;
    std::uint64_t started_ms = 0, conversion_started_ms = 0, finished_ms = 0;
    std::uint16_t source_mv = 0;
    std::array<std::uint8_t, 7> status{}; // 1B..21, nondestructive current status.
    std::array<std::uint8_t, 6> flags{}; // 22..27, read-to-clear history.
    std::array<std::uint16_t, 9> adc{}; // 31..42, big-endian pairs.
    bool valid() const { return error == Error::none; }
    std::uint16_t vbus_mv() const { return adc[2]; }
    std::uint16_t battery_mv() const { return adc[5]; }
    std::uint16_t ts_ratio_1024() const { return adc[7]; }
};

// Configuration/protection observation while charging stays OFF. No USB source
// or ADC conversion is asserted by this report; unplugged operation is allowed.
struct OffCapture {
    Error error=Error::unconfigured;
    std::uint64_t started_ms=0, finished_ms=0;
    std::array<std::uint8_t,7> status{};
    std::array<std::uint8_t,6> flags{};
    bool valid() const { return error==Error::none; }
    bool source_present() const { return status[0]&0x01; }
};
struct ParkReconciliation {
    OffCapture observation{};
    std::uint8_t previous_vindpm=0, observed_vindpm=0;
    bool source_event=false;
    bool valid() const { return observation.valid(); }
    // VINDPM is an opaque OFF-monitor value, never an inferred USB contract.
};
class Bq25798 {
public:
    static constexpr std::uint8_t address = 0x6B;
    static constexpr std::uint64_t operation_budget_ms = 750;
    Bq25798(Bus& bus, Inhibit& inhibit,FailureSink* sink=nullptr)
        : bus_(bus), inhibit_(inhibit),sink_(sink) {}
    Error configure(SourceVoltage voltage);
    Capture capture();
    OffCapture capture_off();
    // Owner-only transitions. The second independent guard must verify actual
    // motor OFF; both guards are checked around each synchronous transfer.
    // A failed transition is terminal for this object, even if configure() is
    // called later. A clean cold session may use a new object, never this one.
    OffCapture park_off(Inhibit& motor_off);
    // Only this successful, explicitly bound park grants same-object
    // reconciliation authority. Enum-only adoption and ordinary park do not.
    OffCapture park_off(ParkGuard& guard);
    // No writes. Chatter/incoherent observation is a terminal refusal; there
    // are no internal retries. Cannot revive an object after a real failure.
    ParkReconciliation reconcile_parked(ParkGuard& guard);
    // New owner-session object, same proven stationary hardware park. Read-only
    // adoption; never accepts a watchdog-reset/default image as parked.
    OffCapture adopt_parked(SourceVoltage voltage,Inhibit& motor_off);
    OffCapture resume_off(Inhibit& motor_off);
    // Bound parks require the same current guard through watchdog restoration.
    // The unbound Inhibit overload cannot bypass that requirement.
    OffCapture resume_off(ParkGuard& guard);
    bool parked() const { return parked_; }
    Error transition_failure() const { return transition_failure_; }
    bool configured() const { return configured_; }
    bool reports_to(const FailureSink& sink) const { return sink_==&sink; }
    // Owner-only diagnostics; primary cause remains separate from OFF failure.
    Error first_error() const { return first_error_; }
    bool inhibit_failed() const { return inhibit_failed_; }
    void invalidate() { fail(Error::unconfigured); }
private:
    bool begin();
    bool within_budget();
    bool read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size);
    bool write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size);
    bool write_register(const Register& reg);
    bool verify_register(const Register& reg);
    bool verify_profile();
    bool fail(Error error);
    bool off_guards();
    bool inspect_off(OffCapture& result,std::array<std::uint8_t,6>* latest_flags=nullptr);
    bool verify_parked_source(std::uint8_t& vindpm);
    OffCapture transition_off(Inhibit& motor_off,bool park);
    Bus& bus_;
    Inhibit& inhibit_;
    FailureSink* const sink_;
    Profile profile_{};
    SourceVoltage source_ = SourceVoltage::nine;
    Error error_ = Error::unconfigured;
    Error first_error_=Error::none;
    bool inhibit_failed_=false;
    std::uint64_t started_ms_ = 0, last_ms_ = 0;
    bool configured_ = false,parked_=false;
    Inhibit* transition_guard_=nullptr;
    ParkGuard* park_guard_=nullptr;
    ParkIdentity operation_identity_{},parked_identity_{};
    std::uint8_t parked_source_=0;
    bool reconciliation_authorized_=false;
    Error transition_failure_=Error::none;
};

// These are evidence contracts for future integration, not booleans derived
// automatically from a raw MAX17320 read. Defaults deliberately fail closed.
struct PackEvidence {
    std::uint64_t sampled_ms = 0, pack_identity = 0;
    bool commissioned_protection = false, healthy_protection = false, cells_present = false;
    bool sensor_placement_verified = false, conversions_fresh = false;
    std::array<std::uint16_t, 3> cell_mv{};
    std::array<std::int16_t, 2> temperature_deci_c{};
};
struct SourceEvidence {
    std::uint64_t sampled_ms = 0, contract_epoch = 0;
    std::uint16_t voltage_mv = 0, current_ma = 0;
    bool fixed_contract = false, factory_image_verified = false, hardware_path_qualified = false;
};
enum class Readiness { evidence_missing, stale, source, pack, temperature, motion, charger, ready_for_review };
Readiness assess(const Capture& charger, const PackEvidence& pack, const SourceEvidence& source,
                 bool motor_stopped, std::uint64_t now_ms);
} // namespace smart_blinds::charger
