#include "max17320_reader.hpp"
#include "esp_timer.h"

namespace blinds::c6 {
namespace {
constexpr int transfer_timeout_ms = 10;
constexpr std::int64_t capture_budget_us = 250000;
}

Max17320Reader::~Max17320Reader() { detach(); }

esp_err_t Max17320Reader::attach(i2c_master_bus_handle_t bus) {
    if (!bus) return ESP_ERR_INVALID_ARG;
    if (normal_ || shadow_) return ESP_ERR_INVALID_STATE;
    i2c_device_config_t cfg{};
    cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    cfg.device_address = 0x36;
    cfg.scl_speed_hz = 100000; // Initial carrier-bus setting; verify rise time physically.
    auto error = i2c_master_bus_add_device(bus, &cfg, &normal_);
    if (error != ESP_OK) return error;
    cfg.device_address = 0x0B;
    error = i2c_master_bus_add_device(bus, &cfg, &shadow_);
    if (error != ESP_OK) detach();
    return error;
}

void Max17320Reader::detach() {
    if (normal_) { i2c_master_bus_rm_device(normal_); normal_ = nullptr; }
    if (shadow_) { i2c_master_bus_rm_device(shadow_); shadow_ = nullptr; }
}

esp_err_t Max17320Reader::read_word(std::uint16_t reg, std::uint16_t& value) {
    if (!normal_ || !shadow_) return ESP_ERR_INVALID_STATE;
    if (reg > 0x1FF || (reg >= 0x100 && reg < 0x180)) return ESP_ERR_INVALID_ARG;
    auto device = reg < 0x100 ? normal_ : shadow_;
    const auto pointer = static_cast<std::uint8_t>(reg & 0xFF);
    std::uint8_t bytes[2]{};
    const auto error = i2c_master_transmit_receive(device, &pointer, 1, bytes, sizeof(bytes),
                                                transfer_timeout_ms);
    if (error == ESP_OK) value = static_cast<std::uint16_t>(bytes[0] | (bytes[1] << 8));
    return error;
}

GaugeReadback Max17320Reader::read() {
    GaugeReadback sample;
    sample.read_started_us = esp_timer_get_time();
    // A first error invalidates the entire capture; partially read fields remain
    // diagnostic only. The application must never map this alone to power_ready.
    struct Request { std::uint16_t reg; std::uint16_t* destination; };
    const Request requests[] = {
        {0x021, &sample.dev_name}, {0x000, &sample.status}, {0x0D9, &sample.protection_status},
        {0x1A8, &sample.battery_status}, {0x006, &sample.soc}, {0x0DA, &sample.pack_voltage},
        {0x01C, &sample.current}, {0x01B, &sample.temperature},
        {0x0D8, &sample.cells[0]}, {0x0D7, &sample.cells[1]}, {0x0D6, &sample.cells[2]},
        {0x1B5, &sample.pack_config}, {0x1B8, &sample.nv_config0},
        {0x1B9, &sample.nv_config1}, {0x1CF, &sample.sense_resistor},
    };
    for (const auto& request : requests) {
        if (esp_timer_get_time() - sample.read_started_us >= capture_budget_us) {
            sample.error = ESP_ERR_TIMEOUT;
            break;
        }
        sample.error = read_word(request.reg, *request.destination);
        if (sample.error != ESP_OK) break;
    }
    sample.read_finished_us = esp_timer_get_time();
    if (sample.read_finished_us - sample.read_started_us > capture_budget_us)
        sample.error = ESP_ERR_TIMEOUT;
    sample.valid = sample.error == ESP_OK;
    return sample;
}
} // namespace blinds::c6
