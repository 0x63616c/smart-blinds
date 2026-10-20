#pragma once
#include "smart_blinds/board_io.hpp"
#include "driver/gpio.h"
#include "driver/mcpwm_prelude.h"
#include "driver/pulse_cnt.h"

namespace blinds::c6 {
struct DisabledInputs {
    // driver_fault combines the driver nFAULT and latched thermal gate on GPIO21.
    bool valid=false, up_pressed=false, down_pressed=false, driver_fault=false, reference_low=false;
};
// Compile-only in the shipped bring-up app. Explicit initialize() writes OFF
// levels and allocates stopped peripherals; no API starts them or enables rails.
// Single worker owns lifetime. Do not initialize on unrelated hardware.
class DisabledC6Io final : private io::DisabledBackend {
public:
    DisabledC6Io() : setup_(*this) {}
    ~DisabledC6Io() { shutdown(); }
    DisabledC6Io(const DisabledC6Io&) = delete;
    DisabledC6Io& operator=(const DisabledC6Io&) = delete;
    bool initialize();
    bool shutdown();
    DisabledInputs inputs();
    esp_err_t last_error() const { return last_error_; }
    static constexpr bool motor_ready() { return false; }
private:
    bool output(int pin,bool high) override;
    bool configure_inputs() override;
    bool configure_counter_stopped() override;
    bool configure_pwm_stopped_low() override;
    bool force_pwm_low() override;
    bool outputs_are_off() override;
    bool record(esp_err_t value) { if(value!=ESP_OK) last_error_=value; return value==ESP_OK; }
    bool touched_=false, closed_=false, low_watch_=false, high_watch_=false;
    esp_err_t last_error_=ESP_OK;
    io::DisabledSetup setup_;
    pcnt_unit_handle_t counter_=nullptr;
    pcnt_channel_handle_t channel_a_=nullptr, channel_b_=nullptr;
    mcpwm_timer_handle_t timer_=nullptr;
    mcpwm_oper_handle_t operator_=nullptr;
    mcpwm_gen_handle_t generator_a_=nullptr, generator_b_=nullptr;
};
} // namespace blinds::c6
