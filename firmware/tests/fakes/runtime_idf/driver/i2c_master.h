#pragma once
#include <cstdint>
#include <cstddef>
#include "driver/gpio.h"
using esp_err_t=int;
constexpr esp_err_t ESP_OK=0,ESP_ERR_INVALID_STATE=0x103,ESP_ERR_INVALID_ARG=0x102,
    ESP_ERR_NOT_SUPPORTED=0x106,ESP_ERR_TIMEOUT=0x107;
struct MockBus;struct MockDevice;
using i2c_master_bus_handle_t=MockBus*;
using i2c_master_dev_handle_t=MockDevice*;
constexpr int I2C_NUM_0=0,I2C_CLK_SRC_DEFAULT=0,I2C_ADDR_BIT_LEN_7=0;
struct i2c_master_bus_config_t {
 int i2c_port=0;gpio_num_t sda_io_num=0,scl_io_num=0;int clk_source=0,glitch_ignore_cnt=0;
 struct { bool enable_internal_pullup=false; } flags;
};
struct i2c_device_config_t { int dev_addr_length=0;std::uint16_t device_address=0;unsigned scl_speed_hz=0; };
esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t*,i2c_master_bus_handle_t*);
esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t,const i2c_device_config_t*,i2c_master_dev_handle_t*);
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t);
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t,const std::uint8_t*,std::size_t,std::uint8_t*,std::size_t,int);
esp_err_t i2c_master_transmit(i2c_master_dev_handle_t,const std::uint8_t*,std::size_t,int);
