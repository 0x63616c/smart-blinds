#pragma once
#include <array>
#include <cstdint>
#include "driver/i2c_master.h"

namespace blinds::c6 {

// Raw diagnostic capture, not evidence of a commissioned or healthy pack.
// Host receipt times do not imply that the gauge ADC just converted the value.
struct GaugeReadback {
    bool valid = false;
    esp_err_t error = ESP_ERR_INVALID_STATE;
    std::int64_t read_started_us = 0, read_finished_us = 0;
    std::uint16_t dev_name = 0, status = 0, protection_status = 0, battery_status = 0;
    std::uint16_t soc = 0, pack_voltage = 0, current = 0, temperature = 0;
    std::array<std::uint16_t, 3> cells{};
    std::uint16_t pack_config = 0, nv_config0 = 0, nv_config1 = 0, sense_resistor = 0;
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
