#pragma once
// Host seam for compiling the actual adapter, NOT a model of ESP-IDF timing.
#include <cstddef>
#include <cstdint>
using esp_err_t=std::int32_t;
constexpr esp_err_t ESP_OK=0,ESP_ERR_INVALID_STATE=0x103,ESP_ERR_INVALID_ARG=0x102,
    ESP_ERR_NOT_SUPPORTED=0x106,ESP_ERR_TIMEOUT=0x107;
struct MockBus;
struct MockDevice;
using i2c_master_bus_handle_t=MockBus*;
using i2c_master_dev_handle_t=MockDevice*;
enum i2c_addr_bit_len_t { I2C_ADDR_BIT_LEN_7 };
struct i2c_device_config_t {
    i2c_addr_bit_len_t dev_addr_length{};
    std::uint16_t device_address=0;
    std::uint32_t scl_speed_hz=0;
};
esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t,const i2c_device_config_t*,i2c_master_dev_handle_t*);
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t);
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t,const std::uint8_t*,std::size_t,
                                    std::uint8_t*,std::size_t,int);
