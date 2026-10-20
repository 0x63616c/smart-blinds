#pragma once
#include "smart_blinds/motion_session.hpp"
#include "smart_blinds/port_checks.hpp"
#include "smart_blinds/board_io.hpp"
#include "driver/gpio.h"
#include "driver/mcpwm_prelude.h"
#include "driver/pulse_cnt.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_pm.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace blinds::c6 {
struct FastInputs {
    bool valid=false, count_valid=false, up_pressed=false, down_pressed=false, driver_fault=true, reference_low=false;
    std::uint64_t sequence=0, sampled_us=0, encoder_epoch=0;
    double count=0, current_a=0;
};
// Default uninitialized. Even an explicit initialize() requires both the
// compile-time bench option and a qualified profile with measured polarities.
// One task owns all calls/lifetime; never use alongside DisabledC6Io.
inline FastObservation motion_observation(const FastInputs& f) {
    return {f.valid,f.count_valid,f.driver_fault,f.up_pressed || f.down_pressed,
        f.sequence,f.sampled_us,f.encoder_epoch,f.count,f.current_a};
}
class BenchC6Io final : public MotionIo,public CounterOrigin {
public:
    explicit BenchC6Io(port::Profile profile) : profile_(profile) {}
    ~BenchC6Io() { shutdown(); }
    BenchC6Io(const BenchC6Io&)=delete;
    BenchC6Io& operator=(const BenchC6Io&)=delete;
    bool initialize();
    bool shutdown();
    bool set_counter_origin(std::uint64_t epoch,double normalized_count) override;
    FastInputs sample_fast(); // ADC/PCNT source sampling, <=1 ms checked budget.
    bool faulted() const { return fault_; }
    esp_err_t last_error() const { return last_error_; }
    std::uint64_t now_us() const override;
    bool request_n(bool high) override;
    bool charge_off() override;
    bool coast() override;
    bool wdi_high() override;
    bool encoder_power(bool enabled) override;
    bool counter_start(std::uint64_t epoch) override;
    bool counter_stop() override;
    bool awake_lock(bool held) override;
    bool pwm(int direction,double duty) override;
    bool heartbeat_pulse() override;
private:
    bool owner() const;
    bool ready() const;
    bool record(esp_err_t status);
    bool trip(esp_err_t status=ESP_ERR_INVALID_STATE);
    void emergency_off();
    bool output(int pin,bool high);
    bool digital(int pin,bool high);
    bool configure_counter();
    bool configure_pwm();
    bool configure_adc();
    bool check_counter(bool running);
    bool check_pwm(int physical_direction,std::uint32_t ticks,bool awake);
    port::Profile profile_;
    TaskHandle_t owner_=nullptr;
    bool touched_=false, initialized_=false, fault_=false, closed_=false;
    bool init_apb_held_=false;
    bool awake_=false, counter_enabled_=false, counter_running_=false, timer_enabled_=false;
    bool encoder_on_=false, request_high_=true, low_watch_=false, high_watch_=false, pulse_seen_=false;
    std::uint64_t origin_epoch_=0, epoch_=0, last_epoch_=0, sequence_=0;
    double origin_=0;
    int active_direction_=0;
    std::uint32_t active_ticks_=0, filter_ticks_=0;
    esp_err_t last_error_=ESP_OK;
    esp_pm_lock_handle_t awake_pm_=nullptr, init_apb_pm_=nullptr;
    pcnt_unit_handle_t counter_=nullptr;
    pcnt_channel_handle_t channel_a_=nullptr, channel_b_=nullptr;
    mcpwm_timer_handle_t timer_=nullptr;
    mcpwm_oper_handle_t operator_=nullptr;
    mcpwm_cmpr_handle_t compare_a_=nullptr, compare_b_=nullptr;
    mcpwm_gen_handle_t generator_a_=nullptr, generator_b_=nullptr;
    adc_oneshot_unit_handle_t adc_=nullptr;
    adc_cali_handle_t calibration_=nullptr;
    portMUX_TYPE pulse_mux_=portMUX_INITIALIZER_UNLOCKED;
};
} // namespace blinds::c6
