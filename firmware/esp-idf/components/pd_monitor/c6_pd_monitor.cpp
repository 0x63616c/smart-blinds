#include "c6_pd_monitor.hpp"
#include "esp_timer.h"
namespace blinds::c6 {
bool PdMonitor::accessible() const { return owner_ && xTaskGetCurrentTaskHandle()==owner_ && epoch_.matches(expected_); }
esp_err_t PdMonitor::attach(i2c_master_bus_handle_t bus) {
    if(attempted_ || !bus || !accessible()) { policy_.invalidate(smart_blinds::pd::Error::bus);return ESP_ERR_INVALID_STATE; }
    attempted_=true;i2c_device_config_t c{};
    c.dev_addr_length=I2C_ADDR_BIT_LEN_7;c.device_address=0x28;c.scl_speed_hz=100000;
    const auto result=i2c_master_bus_add_device(bus,&c,&device_);
    if(result!=ESP_OK || !accessible()) { policy_.invalidate(smart_blinds::pd::Error::bus);return result==ESP_OK?ESP_ERR_INVALID_STATE:result; }
    return ESP_OK;
}
esp_err_t PdMonitor::close() {
    policy_.invalidate(smart_blinds::pd::Error::uninitialized);
    if(xTaskGetCurrentTaskHandle()!=owner_) return ESP_ERR_INVALID_STATE;
    if(!device_) return ESP_OK;
    const auto result=i2c_master_bus_rm_device(device_);
    if(result==ESP_OK) device_=nullptr;
    return result;
}
bool PdMonitor::read(std::uint8_t r,std::uint8_t* p,std::size_t n) {
    // A finite allowlist excludes undocumented/RX/NVM/command addresses.
    const bool allowed=(r==0x0B && n==12) || ((r==0x29 || r==0x2F || r==0x70) && n==1) ||
        (r==0x85 && n==12) || (r==0x91 && n==4);
    return p && allowed && device_ && accessible() &&
        i2c_master_transmit_receive(device_,&r,1,p,n,10)==ESP_OK && accessible();
}
bool PdMonitor::alert_mask(std::uint8_t value) {
    const std::uint8_t packet[]{0x0C,value};
    return device_ && accessible() && !(value&0x72) &&
        i2c_master_transmit(device_,packet,sizeof(packet),10)==ESP_OK && accessible();
}
std::uint64_t PdMonitor::now_ms() const { return static_cast<std::uint64_t>(esp_timer_get_time()/1000); }
}
