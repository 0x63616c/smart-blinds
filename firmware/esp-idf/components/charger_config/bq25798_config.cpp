#include "bq25798_config.hpp"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>

namespace blinds::c6 {
namespace { constexpr int timeout_ms = 10; }
esp_err_t Bq25798Config::attach(i2c_master_bus_handle_t bus) {
    if (!bus) return ESP_ERR_INVALID_ARG;
    if (device_) return ESP_ERR_INVALID_STATE;
    policy_.invalidate();
    i2c_device_config_t cfg{};
    cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    cfg.device_address = smart_blinds::charger::Bq25798::address;
    cfg.scl_speed_hz = 100000;
    last_error_ = i2c_master_bus_add_device(bus, &cfg, &device_);
    return last_error_;
}
void Bq25798Config::detach() {
    policy_.invalidate();
    if (device_) { i2c_master_bus_rm_device(device_); device_ = nullptr; }
}
bool Bq25798Config::read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size) {
    if (!device_) { last_error_ = ESP_ERR_INVALID_STATE; return false; }
    if (!bytes || !size || size > 18 || static_cast<std::size_t>(reg)+size > 0x49) {
        last_error_ = ESP_ERR_INVALID_ARG; return false;
    }
    last_error_ = i2c_master_transmit_receive(device_, &reg, 1, bytes, size, timeout_ms);
    return last_error_ == ESP_OK;
}
bool Bq25798Config::write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size) {
    if (!device_) { last_error_ = ESP_ERR_INVALID_STATE; return false; }
    if (!bytes || !size || size > 2 || static_cast<std::size_t>(reg)+size > 0x49) {
        last_error_ = ESP_ERR_INVALID_ARG; return false;
    }
    std::uint8_t packet[3] = {reg,0,0};
    std::memcpy(packet+1,bytes,size);
    last_error_ = i2c_master_transmit(device_, packet, size+1, timeout_ms);
    return last_error_ == ESP_OK;
}
std::uint64_t Bq25798Config::now_ms() const { return static_cast<std::uint64_t>(esp_timer_get_time()/1000); }
void Bq25798Config::wait_ms(unsigned duration) {
    const auto ticks = pdMS_TO_TICKS(duration);
    vTaskDelay(ticks ? ticks : 1);
}
} // namespace blinds::c6
