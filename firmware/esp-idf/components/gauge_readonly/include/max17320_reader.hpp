#pragma once
#include <array>
#include <cstdint>
#include "driver/i2c_master.h"
#include "smart_blinds/power_evidence.hpp"

namespace blinds::c6 {

// Raw diagnostic capture, not evidence of a commissioned or healthy pack.
// Host receipt times do not imply that the gauge ADC just converted the value.
struct GaugeReadback : power::GaugeCapture {
    esp_err_t error = ESP_ERR_INVALID_STATE;
};

// Single worker/task owns this object. The caller owns the reviewed I2C bus and
// external pullups. This reader never configures pins or writes a data register.
class Max17320Reader {
public:
    ~Max17320Reader();
    Max17320Reader() = default;
    Max17320Reader(const Max17320Reader&) = delete;
    Max17320Reader& operator=(const Max17320Reader&) = delete;
    esp_err_t attach(i2c_master_bus_handle_t bus);
    void detach();
    GaugeReadback read();
private:
    esp_err_t read_word(std::uint16_t reg, std::uint16_t& value);
    i2c_master_dev_handle_t normal_ = nullptr, shadow_ = nullptr;
};
} // namespace blinds::c6
