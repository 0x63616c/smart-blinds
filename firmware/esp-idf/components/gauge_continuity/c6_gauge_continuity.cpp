#include "c6_gauge_continuity.hpp"
#include "esp_timer.h"
#include "sdkconfig.h"

namespace blinds::c6 {
GaugeContinuity::GaugeContinuity(power::continuity::Profile profile,Context context,
                                 power::continuity::BusEpoch& epoch)
    : owner_(xTaskGetCurrentTaskHandle()),
      session_(profile,context,*this,epoch,reinterpret_cast<power::continuity::Owner>(owner_)) {}
GaugeContinuity::~GaugeContinuity() {
    // Destruction must be after all users stop and on the owning task. A
    // wrong-task close only cancels evidence and leaves handles for the owner;
    // destroying there would leak them. Concurrent destruction is unsupported.
    close();
}
power::continuity::Owner GaugeContinuity::current_owner() const {
    return reinterpret_cast<power::continuity::Owner>(xTaskGetCurrentTaskHandle());
}
std::int64_t GaugeContinuity::now_us() { return esp_timer_get_time(); }
esp_err_t GaugeContinuity::attach(i2c_master_bus_handle_t bus,Context context) {
#if !CONFIG_BLINDS_GAUGE_CONTINUITY_BENCH
    (void)bus;(void)context;
    return ESP_ERR_NOT_SUPPORTED; // No handles/reads in default configuration.
#else
    if(xTaskGetCurrentTaskHandle()!=owner_) { retire();return ESP_ERR_INVALID_STATE; }
    if(attempted_ || !bus || !session_.can_attach(context)) {
        retire();return ESP_ERR_INVALID_STATE;
    }
    attempted_=true;
    i2c_device_config_t cfg{};
    cfg.dev_addr_length=I2C_ADDR_BIT_LEN_7;cfg.device_address=0x36;
    cfg.scl_speed_hz=100000; // External reviewed pullups; rise time unvalidated.
    last_error_=i2c_master_bus_add_device(bus,&cfg,&normal_);
    if(last_error_==ESP_OK) {
        cfg.device_address=0x0B;
        last_error_=i2c_master_bus_add_device(bus,&cfg,&shadow_);
    }
    if(last_error_!=ESP_OK) {
        const auto original=last_error_;
        close();
        last_error_=original;
        return original;
    }
    // Recheck retirement even when both SDK operations succeeded.
    if(!session_.can_attach(context)) { close();return ESP_ERR_INVALID_STATE; }
    attached_=true;
    return ESP_OK;
#endif
}
esp_err_t GaugeContinuity::close() {
    retire();
    if(xTaskGetCurrentTaskHandle()!=owner_) return ESP_ERR_INVALID_STATE;
    attached_=false;
    auto error=ESP_OK;
    if(shadow_) {
        const auto result=i2c_master_bus_rm_device(shadow_);
        if(result==ESP_OK) shadow_=nullptr;
        else error=result;
    }
    if(normal_) {
        const auto result=i2c_master_bus_rm_device(normal_);
        if(result==ESP_OK) normal_=nullptr;
        else if(error==ESP_OK) error=result;
    }
    last_error_=error;return error;
}
bool GaugeContinuity::transfer(std::uint8_t address,std::uint8_t pointer,
                               std::array<std::uint8_t,2>& bytes,std::uint32_t timeout) {
    // Session checks owner/epoch around every transfer. The SDK seam checks
    // again before calling the synchronous API; no async callbacks are used.
    if(xTaskGetCurrentTaskHandle()!=owner_) return false;
    if(!attached_ || timeout!=10) { last_error_=ESP_ERR_INVALID_STATE;return false; }
    const auto device=address==0x36 ? normal_:(address==0x0B ? shadow_:nullptr);
    if(!device) { last_error_=ESP_ERR_INVALID_ARG;return false; }
    last_error_=i2c_master_transmit_receive(device,&pointer,1,bytes.data(),bytes.size(),10);
    return last_error_==ESP_OK;
}
GaugeContinuity::Publication GaugeContinuity::read(Context context) {
    if(xTaskGetCurrentTaskHandle()!=owner_) { retire();return {}; }
    if(!attached_) { retire();return {}; }
    return session_.read(context);
}
bool GaugeContinuity::park_light_sleep(Context context) {
    if(xTaskGetCurrentTaskHandle()!=owner_) { retire();return false; }
    if(!attached_) { retire();return false; }
    return session_.park_light_sleep(context);
}
bool GaugeContinuity::resume_light_sleep(Context context) {
    if(xTaskGetCurrentTaskHandle()!=owner_) { retire();return false; }
    if(!attached_) { retire();return false; }
    return session_.resume_light_sleep(context);
}
} // namespace blinds::c6
