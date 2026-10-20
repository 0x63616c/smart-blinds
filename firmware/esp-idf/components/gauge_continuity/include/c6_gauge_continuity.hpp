#pragma once
#include "driver/i2c_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "smart_blinds/gauge_bus_session.hpp"

namespace blinds::c6 {
// Create/use/destroy on one dedicated sensor task. Does NOT create/delete the
// bus, configure pins, attach automatically, write registers or approve motion.
// BusEpoch outlives this object and all consumers of its publications.
class GaugeContinuity final:private power::continuity::WordTransport {
public:
    using Context=power::continuity::Context;
    using Publication=power::continuity::Publication;
    GaugeContinuity(power::continuity::Profile profile,Context context,power::continuity::BusEpoch& epoch);
    GaugeContinuity(power::continuity::Profile profile,Context context,power::continuity::BusEpoch& epoch,
                    power::continuity::JointMailbox& joint,smart_blinds::charger::Bq25798& charger);
    ~GaugeContinuity();
    GaugeContinuity(const GaugeContinuity&)=delete;
    GaugeContinuity& operator=(const GaugeContinuity&)=delete;
    esp_err_t attach(i2c_master_bus_handle_t bus,Context context);
    esp_err_t close(); // Only owner removes handles; wrong-task call retires.
    Publication read(Context context);
    power::continuity::Refresh refresh(Context context,power::continuity::Window window,smart_blinds::charger::ParkGuard* stationary=nullptr);
    bool park_light_sleep(Context context);
    bool resume_light_sleep(Context context);
    void retire() { session_.retire(); } // Atomic cancellation, any task.
    bool current(const Publication& p,std::uint64_t now_us) const { return session_.current(p,now_us); }
    // Last SDK diagnostic is single-owner only, not a cross-task status API.
    esp_err_t last_error() const { return last_error_; }
private:
    power::continuity::Owner current_owner() const override;
    std::int64_t now_us() override;
    bool transfer(std::uint8_t address,std::uint8_t pointer,std::array<std::uint8_t,2>& bytes,
                  std::uint32_t timeout_ms) override;
    const TaskHandle_t owner_;
    power::continuity::OwnedSession session_;
    i2c_master_dev_handle_t normal_=nullptr,shadow_=nullptr;
    esp_err_t last_error_=ESP_ERR_INVALID_STATE;
    [[maybe_unused]] bool attempted_=false; // Used only in the bench-enabled build.
    bool attached_=false;
};
} // namespace blinds::c6
