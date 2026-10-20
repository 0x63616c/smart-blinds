#pragma once
#include "smart_blinds/charger.hpp"
#include "driver/i2c_master.h"

namespace blinds::c6 {
// Single-worker component. Caller supplies a reviewed bus and independent OFF
// implementation that outlive this object. No GPIO is configured here and no
// method can enable CE or EN_CHG. The bring-up app does not instantiate it.
class Bq25798Config final : private smart_blinds::charger::Bus {
public:
    explicit Bq25798Config(smart_blinds::charger::Inhibit& inhibit) : policy_(*this, inhibit) {}
    ~Bq25798Config() { detach(); }
    Bq25798Config(const Bq25798Config&) = delete;
    Bq25798Config& operator=(const Bq25798Config&) = delete;
    esp_err_t attach(i2c_master_bus_handle_t bus);
    void detach();
    smart_blinds::charger::Error configure(smart_blinds::charger::SourceVoltage voltage) { return policy_.configure(voltage); }
    smart_blinds::charger::Capture capture() { return policy_.capture(); }
    esp_err_t last_bus_error() const { return last_error_; }
private:
    bool read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size) override;
    bool write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size) override;
    std::uint64_t now_ms() const override;
    void wait_ms(unsigned duration) override;
    i2c_master_dev_handle_t device_ = nullptr;
    esp_err_t last_error_ = ESP_ERR_INVALID_STATE;
    smart_blinds::charger::Bq25798 policy_;
};
} // namespace blinds::c6
