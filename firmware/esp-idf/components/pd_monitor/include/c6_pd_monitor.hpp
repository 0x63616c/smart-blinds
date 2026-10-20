#pragma once
#include "smart_blinds/pd_monitor.hpp"
#include "smart_blinds/gauge_bus_session.hpp"
#include "driver/i2c_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
namespace blinds::c6 {
// Same sensor task/bus/epoch as BQ/MAX. The sole data write is ALERT_MASK;
// no register-pointer API is exposed to the application or network.
class PdMonitor final:private smart_blinds::pd::Bus {
public:
    PdMonitor(smart_blinds::pd::FactoryRecord record,power::continuity::BusEpoch& epoch)
      :owner_(xTaskGetCurrentTaskHandle()),epoch_(epoch),expected_(epoch.value()),policy_(*this,record) {}
    ~PdMonitor() { close(); }
    PdMonitor(const PdMonitor&)=delete;
    PdMonitor& operator=(const PdMonitor&)=delete;
    esp_err_t attach(i2c_master_bus_handle_t bus);
    esp_err_t close();
    smart_blinds::pd::Monitor& policy() { return policy_; }
private:
    bool accessible() const;
    bool read(std::uint8_t,std::uint8_t*,std::size_t) override;
    bool alert_mask(std::uint8_t) override;
    std::uint64_t now_ms() const override;
    const TaskHandle_t owner_;
    power::continuity::BusEpoch& epoch_;
    const std::uint32_t expected_;
    i2c_master_dev_handle_t device_=nullptr;
    bool attempted_=false;
    smart_blinds::pd::Monitor policy_;
};
}
