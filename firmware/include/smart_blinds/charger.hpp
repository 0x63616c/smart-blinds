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
class Bq25798 {
public:
    static constexpr std::uint8_t address = 0x6B;
    static constexpr std::uint64_t operation_budget_ms = 750;
    Bq25798(Bus& bus, Inhibit& inhibit,FailureSink* sink=nullptr)
        : bus_(bus), inhibit_(inhibit),sink_(sink) {}
    Error configure(SourceVoltage voltage);
    Capture capture();
    OffCapture capture_off();
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
    Bus& bus_;
    Inhibit& inhibit_;
    FailureSink* const sink_;
    Profile profile_{};
    SourceVoltage source_ = SourceVoltage::nine;
    Error error_ = Error::unconfigured;
    Error first_error_=Error::none;
    bool inhibit_failed_=false;
    std::uint64_t started_ms_ = 0, last_ms_ = 0;
    bool configured_ = false;
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
