#include "bench_c6_io.hpp"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_idf_version.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "esp_private/esp_clk.h"
#include "soc/gpio_struct.h"
#include "soc/gpio_sig_map.h"
#include "soc/mcpwm_struct.h"
#include "soc/pcnt_struct.h"
#include "soc/pcr_struct.h"
#include <cmath>
#include <initializer_list>

#if !CONFIG_IDF_TARGET_ESP32C6 || ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5,5,4)
#error "Review C6 register readback against the selected ESP-IDF version before building"
#endif

namespace blinds::c6 {
namespace {
using P=io::Pins;
constexpr int count_limit=30000;
bool level(int pin) { return gpio_get_level(static_cast<gpio_num_t>(pin)); }
bool input_route(int signal,int pin) {
    const auto& route=GPIO.func_in_sel_cfg[signal];
    return route.sig_in_sel && !route.in_inv_sel && route.in_sel==static_cast<unsigned>(pin);
}
bool digital_matches(int pin,bool high) {
    return GPIO.func_out_sel_cfg[pin].out_sel==SIG_GPIO_OUT_IDX && !GPIO.func_out_sel_cfg[pin].out_inv_sel &&
        !GPIO.func_out_sel_cfg[pin].oen_inv_sel && (GPIO.enable.val & (1U<<pin)) && level(pin)==high;
}
}
std::uint64_t BenchC6Io::now_us() const { const auto t=esp_timer_get_time(); return t<0 ? 0 : static_cast<std::uint64_t>(t); }
bool BenchC6Io::owner() const { return !xPortInIsrContext() && owner_==xTaskGetCurrentTaskHandle(); }
bool BenchC6Io::ready() const { return initialized_ && !closed_ && !fault_ && owner(); }
void BenchC6Io::emergency_off() {
    if(!touched_) return;
    // Independent best-effort writes; never recursively invoke record()/trip().
    gpio_set_level(static_cast<gpio_num_t>(P::request_n),1);
    if(generator_a_) mcpwm_generator_set_force_level(generator_a_,0,true);
    if(generator_b_) mcpwm_generator_set_force_level(generator_b_,0,true);
    gpio_set_level(static_cast<gpio_num_t>(P::charge_n),1);
    active_direction_=0; active_ticks_=0; request_high_=true;
}
bool BenchC6Io::trip(esp_err_t error) { fault_=true; last_error_=error; emergency_off(); return false; }
bool BenchC6Io::record(esp_err_t error) { return error==ESP_OK || trip(error); }
bool BenchC6Io::output(int pin,bool high) {
    const auto gpio=static_cast<gpio_num_t>(pin);
    return record(gpio_set_level(gpio,high)) && record(gpio_set_direction(gpio,GPIO_MODE_INPUT_OUTPUT)) &&
        record(gpio_set_pull_mode(gpio,GPIO_FLOATING)) && (digital_matches(pin,high) || trip());
}
bool BenchC6Io::digital(int pin,bool high) {
    if(!touched_ || !owner()) return trip();
    return record(gpio_set_level(static_cast<gpio_num_t>(pin),high)) &&
        (digital_matches(pin,high) || trip());
}
bool BenchC6Io::initialize() {
#ifndef CONFIG_BLINDS_BENCH_MOTION
    return false; // Compile-default refusal has zero GPIO/peripheral side effects.
#endif
    if(touched_ || closed_ || !profile_.valid() || xPortInIsrContext()) return false;
    owner_=xTaskGetCurrentTaskHandle(); touched_=true;
    if(!output(P::request_n,true) || !output(P::charge_n,true) || !output(P::encoder_n,true) ||
       !output(P::wdi,true) || !output(P::in1,false) || !output(P::in2,false)) { shutdown(); return false; }
    gpio_config_t inputs{};
    inputs.pin_bit_mask=(1ULL<<P::up)|(1ULL<<P::down)|(1ULL<<P::fault_n)|(1ULL<<P::reference);
    inputs.mode=GPIO_MODE_INPUT; inputs.intr_type=GPIO_INTR_DISABLE;
    if(!record(gpio_config(&inputs)) || !record(esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP,0,"blind-motion",&awake_pm_)) ||
       !record(esp_pm_lock_create(ESP_PM_APB_FREQ_MAX,0,"blind-pcnt-init",&init_apb_pm_))) { shutdown(); return false; }
    if(!record(esp_pm_lock_acquire(init_apb_pm_))) { shutdown(); return false; }
    init_apb_held_=true;
    if(!configure_counter()) { shutdown(); return false; }
    if(!record(esp_pm_lock_release(init_apb_pm_))) { shutdown(); return false; }
    init_apb_held_=false;
    if(!configure_pwm() || !configure_adc() || !check_pwm(0,0,false)) { shutdown(); return false; }
    initialized_=true;
    return true;
}
bool BenchC6Io::configure_counter() {
    pcnt_unit_config_t unit{};
    unit.low_limit=-count_limit; unit.high_limit=count_limit; unit.flags.accum_count=true;
    if(!record(pcnt_new_unit(&unit,&counter_))) return false;
    pcnt_glitch_filter_config_t filter{}; filter.max_glitch_ns=1000;
    filter_ticks_=static_cast<std::uint32_t>(esp_clk_apb_freq()/1000000);
    if(!record(pcnt_unit_set_glitch_filter(counter_,&filter))) return false;
    pcnt_chan_config_t channel{}; channel.edge_gpio_num=P::encoder_a; channel.level_gpio_num=P::encoder_b;
    if(!record(pcnt_new_channel(counter_,&channel,&channel_a_))) return false;
    channel.edge_gpio_num=P::encoder_b; channel.level_gpio_num=P::encoder_a;
    if(!record(pcnt_new_channel(counter_,&channel,&channel_b_))) return false;
    if(!record(pcnt_channel_set_edge_action(channel_a_,PCNT_CHANNEL_EDGE_ACTION_DECREASE,PCNT_CHANNEL_EDGE_ACTION_INCREASE)) ||
       !record(pcnt_channel_set_level_action(channel_a_,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE)) ||
       !record(pcnt_channel_set_edge_action(channel_b_,PCNT_CHANNEL_EDGE_ACTION_INCREASE,PCNT_CHANNEL_EDGE_ACTION_DECREASE)) ||
       !record(pcnt_channel_set_level_action(channel_b_,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE)) ||
       !record(gpio_set_pull_mode(static_cast<gpio_num_t>(P::encoder_a),GPIO_FLOATING)) ||
       !record(gpio_set_pull_mode(static_cast<gpio_num_t>(P::encoder_b),GPIO_FLOATING))) return false;
    if(!record(pcnt_unit_add_watch_point(counter_,-count_limit))) return false;
    low_watch_=true;
    if(!record(pcnt_unit_add_watch_point(counter_,count_limit))) return false;
    high_watch_=true;
    return record(pcnt_unit_clear_count(counter_)) && check_counter(false);
}
bool BenchC6Io::configure_pwm() {
    mcpwm_timer_config_t timer{};
    timer.group_id=0; timer.clk_src=MCPWM_TIMER_CLK_SRC_DEFAULT;
    timer.resolution_hz=10000000; timer.count_mode=MCPWM_TIMER_COUNT_MODE_UP; timer.period_ticks=500;
    if(!record(mcpwm_new_timer(&timer,&timer_))) return false;
    mcpwm_operator_config_t oper{}; oper.group_id=0;
    if(!record(mcpwm_new_operator(&oper,&operator_)) || !record(mcpwm_operator_connect_timer(operator_,timer_))) return false;
    mcpwm_comparator_config_t compare{}; compare.flags.update_cmp_on_tez=true;
    if(!record(mcpwm_new_comparator(operator_,&compare,&compare_a_)) ||
       !record(mcpwm_new_comparator(operator_,&compare,&compare_b_))) return false;
    mcpwm_generator_config_t gen{}; gen.flags.io_loop_back=true; gen.gen_gpio_num=P::in1;
    if(!record(mcpwm_new_generator(operator_,&gen,&generator_a_)) ||
       !record(mcpwm_generator_set_force_level(generator_a_,0,true))) return false;
    gen.gen_gpio_num=P::in2;
    if(!record(mcpwm_new_generator(operator_,&gen,&generator_b_)) ||
       !record(mcpwm_generator_set_force_level(generator_b_,0,true))) return false;
    for(auto generator:{generator_a_,generator_b_}) {
        if(!record(mcpwm_generator_set_action_on_timer_event(generator,
            MCPWM_GEN_TIMER_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP,MCPWM_TIMER_EVENT_EMPTY,MCPWM_GEN_ACTION_HIGH)))) return false;
    }
    if(!record(mcpwm_generator_set_action_on_compare_event(generator_a_,
        MCPWM_GEN_COMPARE_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP,compare_a_,MCPWM_GEN_ACTION_LOW))) ||
       !record(mcpwm_generator_set_action_on_compare_event(generator_b_,
        MCPWM_GEN_COMPARE_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP,compare_b_,MCPWM_GEN_ACTION_LOW)))) return false;
    // No timer enable/start here. GPIO route/action readback rejects a conflicting
    // MCPWM allocation instead of assuming returned opaque handles are slot zero.
    return true;
}
bool BenchC6Io::configure_adc() {
    adc_oneshot_unit_init_cfg_t unit{}; unit.unit_id=ADC_UNIT_1;
    if(!record(adc_oneshot_new_unit(&unit,&adc_))) return false;
    adc_oneshot_chan_cfg_t channel{}; channel.bitwidth=ADC_BITWIDTH_12; channel.atten=ADC_ATTEN_DB_12;
    if(!record(adc_oneshot_config_channel(adc_,ADC_CHANNEL_2,&channel))) return false;
    adc_cali_curve_fitting_config_t cal{};
    cal.unit_id=ADC_UNIT_1; cal.chan=ADC_CHANNEL_2; cal.atten=ADC_ATTEN_DB_12; cal.bitwidth=ADC_BITWIDTH_12;
    // Missing eFuse/calibration support fails; there is no uncalibrated fallback.
    return record(adc_cali_create_scheme_curve_fitting(&cal,&calibration_));
}
bool BenchC6Io::check_pwm(int direction,std::uint32_t ticks,bool awake) {
    const auto& op=MCPWM0.operators[0];
    port::PwmReadback r;
    r.routes_correct=GPIO.func_out_sel_cfg[P::in1].out_sel==PWM0_OUT0A_IDX && GPIO.func_out_sel_cfg[P::in2].out_sel==PWM0_OUT0B_IDX;
    const auto enabled=(1U<<P::in1)|(1U<<P::in2);
    r.outputs_enabled=(GPIO.enable.val & enabled)==enabled;
    r.uninverted=!GPIO.func_out_sel_cfg[P::in1].out_inv_sel && !GPIO.func_out_sel_cfg[P::in2].out_inv_sel &&
        !GPIO.func_out_sel_cfg[P::in1].oen_inv_sel && !GPIO.func_out_sel_cfg[P::in2].oen_inv_sel;
    r.plain_paths=op.dt_cfg.db_a_outbypass && op.dt_cfg.db_b_outbypass && !op.dt_cfg.db_a_outswap &&
        !op.dt_cfg.db_b_outswap && !op.dt_cfg.db_red_outinvert && !op.dt_cfg.db_fed_outinvert && !op.carrier_cfg.chopper_en &&
        !op.carrier_cfg.chopper_out_invert && !op.carrier_cfg.chopper_in_invert;
    r.timer_up=MCPWM0.timer[0].timer_cfg1.timer_mod==1;
    r.timer_running=MCPWM0.timer[0].timer_cfg1.timer_start==2;
    r.timer_stopped=MCPWM0.timer[0].timer_cfg1.timer_start==0 && MCPWM0.timer[0].timer_status.timer_value==0;
    r.timer_select_zero=MCPWM0.operator_timersel.operator0_timersel==0;
    // C6 DEFAULT source is PLL160M. The complete divider must yield 10 MHz.
    r.clock_divider_valid=PCR.pwm_conf.pwm_clk_en && !PCR.pwm_conf.pwm_rst_en && PCR.pwm_clk_conf.pwm_clkm_en &&
        PCR.pwm_clk_conf.pwm_clkm_sel==1 &&
        (PCR.pwm_clk_conf.pwm_div_num+1)*(MCPWM0.timer[0].timer_cfg0.timer_prescale+1)==16;
    r.period=MCPWM0.timer[0].timer_cfg0.timer_period+1;
    r.immediate_force=op.gen_force.gen_cntuforce_upmethod==0 && MCPWM0.update_cfg.global_up_en && MCPWM0.update_cfg.op0_up_en;
    r.comparator_tez=op.gen_stmp_cfg.cmpr_a_upmethod==1 && op.gen_stmp_cfg.cmpr_b_upmethod==1;
    r.compare_pending=op.gen_stmp_cfg.cmpr_a_shdw_full || op.gen_stmp_cfg.cmpr_b_shdw_full;
    r.action_a=op.generator[0].val; r.action_b=op.generator[1].val;
    r.force_a=op.gen_force.gen_a_cntuforce_mode; r.force_b=op.gen_force.gen_b_cntuforce_mode;
    r.compare_a=op.timestamp[0].cmpr; r.compare_b=op.timestamp[1].cmpr;
    r.pad_a=level(P::in1); r.pad_b=level(P::in2);
    return port::pwm_valid(r,direction,ticks,awake) || trip();
}
bool BenchC6Io::check_counter(bool running) {
    const auto& config=PCNT.conf_unit[0];
    port::CounterReadback r;
    r.routes_correct=input_route(PCNT_SIG_CH0_IN0_IDX,P::encoder_a) && input_route(PCNT_CTRL_CH0_IN0_IDX,P::encoder_b) &&
        input_route(PCNT_SIG_CH1_IN0_IDX,P::encoder_b) && input_route(PCNT_CTRL_CH1_IN0_IDX,P::encoder_a);
    r.pads_input_only=(GPIO.enable.val & ((1U<<P::encoder_a)|(1U<<P::encoder_b)))==0;
    r.clock_enabled=PCR.pcnt_conf.pcnt_clk_en && !PCR.pcnt_conf.pcnt_rst_en;
    r.reset=PCNT.ctrl.pulse_cnt_rst_u0; r.paused=PCNT.ctrl.cnt_pause_u0;
    r.edge_actions=config.conf0.ch0_pos_mode==2 && config.conf0.ch0_neg_mode==1 &&
        config.conf0.ch1_pos_mode==1 && config.conf0.ch1_neg_mode==2;
    r.level_actions=config.conf0.ch0_hctrl_mode==0 && config.conf0.ch0_lctrl_mode==1 &&
        config.conf0.ch1_hctrl_mode==0 && config.conf0.ch1_lctrl_mode==1;
    r.filter=config.conf0.filter_en && filter_ticks_>0 && config.conf0.filter_thres==filter_ticks_ &&
        (!running || filter_ticks_==static_cast<std::uint32_t>(esp_clk_apb_freq()/1000000));
    r.limit_events=config.conf0.thr_h_lim_en && config.conf0.thr_l_lim_en && PCNT.int_ena.cnt_thr_event_u0_int_ena;
    r.high_limit=config.conf2.cnt_h_lim;
    r.low_limit=static_cast<std::int16_t>(config.conf2.cnt_l_lim);
    return port::counter_valid(r,running) || trip();
}
bool BenchC6Io::request_n(bool high) {
    if(!high && (!ready() || !awake_ || !counter_running_ || !encoder_on_ || !level(P::fault_n) ||
                 !check_counter(true) || !check_pwm(0,0,true) || !digital_matches(P::wdi,true) ||
                 !digital_matches(P::charge_n,true) || !digital_matches(P::encoder_n,false))) return trip();
    if(high) pulse_seen_=false;
    if(!digital(P::request_n,high)) return false;
    request_high_=high;
    return true;
}
bool BenchC6Io::charge_off() { return digital(P::charge_n,true); }
bool BenchC6Io::coast() {
    if(!touched_ || !owner()) return trip();
    bool ok=true;
    if(generator_a_) ok=record(mcpwm_generator_set_force_level(generator_a_,0,true)) && ok;
    if(generator_b_) ok=record(mcpwm_generator_set_force_level(generator_b_,0,true)) && ok;
    active_direction_=0; active_ticks_=0;
    if(!generator_a_ || !generator_b_) return ok && !level(P::in1) && !level(P::in2);
    return check_pwm(0,0,awake_) && ok;
}
bool BenchC6Io::wdi_high() { return digital(P::wdi,true); }
bool BenchC6Io::encoder_power(bool enabled) {
    if(enabled && (!ready() || !awake_ || !level(P::request_n) || counter_running_)) return trip();
    if(!enabled && counter_running_) return trip();
    if(!digital(P::encoder_n,!enabled)) return false;
    encoder_on_=enabled;
    return true;
}
bool BenchC6Io::set_counter_origin(std::uint64_t epoch,double origin) {
    if(!ready() || !level(P::request_n) || counter_running_ || !epoch || epoch<=last_epoch_ ||
       !std::isfinite(origin) || std::abs(origin)>1e12) return trip();
    origin_epoch_=epoch; origin_=origin;
    return true; // This sets a coordinate, never a physical-reference-valid flag.
}
bool BenchC6Io::counter_start(std::uint64_t epoch) {
    if(!ready() || !awake_ || !encoder_on_ || !level(P::request_n) || counter_running_ ||
       epoch!=origin_epoch_ || !epoch || epoch<=last_epoch_) return trip();
    if(!record(pcnt_unit_clear_count(counter_)) || !record(pcnt_unit_enable(counter_))) return false;
    counter_enabled_=true;
    if(!record(pcnt_unit_start(counter_))) return false;
    counter_running_=true; epoch_=last_epoch_=epoch;
    int value=0;
    if(!record(pcnt_unit_get_count(counter_,&value)) || value < -2 || value > 2) return trip();
    return check_counter(true);
}
bool BenchC6Io::counter_stop() {
    if(!touched_ || !owner()) return trip();
    bool ok=true;
    if(counter_running_) {
        if(record(pcnt_unit_stop(counter_))) { counter_running_=false; ok=check_counter(false) && ok; } else ok=false;
    }
    if(counter_enabled_ && !counter_running_) {
        if(record(pcnt_unit_disable(counter_))) counter_enabled_=false; else ok=false;
    }
    return ok;
}
bool BenchC6Io::awake_lock(bool held) {
    if(!touched_ || !owner()) return trip();
    if(held) {
        if(!ready() || awake_ || !level(P::request_n)) return trip();
        if(!record(esp_pm_lock_acquire(awake_pm_))) return false;
        awake_=true;
        if(!record(mcpwm_timer_enable(timer_))) return false;
        timer_enabled_=true;
        return record(mcpwm_timer_start_stop(timer_,MCPWM_TIMER_START_NO_STOP)) && check_pwm(0,0,true);
    }
    if(counter_running_ || encoder_on_ || !level(P::request_n)) return trip();
    bool ok=true;
    if(timer_enabled_) {
        if(record(mcpwm_timer_start_stop(timer_,MCPWM_TIMER_STOP_EMPTY))) {
            // At 20 kHz, zero occurs within 50 us. Bounded wait with no heartbeat.
            const auto began=now_us();
            while(MCPWM0.timer[0].timer_status.timer_value!=0 && now_us()>=began && now_us()-began<60) esp_rom_delay_us(1);
            if(now_us()<began || MCPWM0.timer[0].timer_status.timer_value!=0) ok=trip(ESP_ERR_TIMEOUT);
            if(ok && record(mcpwm_timer_disable(timer_))) timer_enabled_=false; else ok=false;
        } else ok=false;
    }
    if(awake_ && !timer_enabled_) {
        if(record(esp_pm_lock_release(awake_pm_))) awake_=false; else ok=false;
    }
    return ok;
}
bool BenchC6Io::pwm(int direction,double duty) {
    if(!ready() || !awake_ || !counter_running_ || !encoder_on_ || !pulse_seen_ || !digital_matches(P::request_n,false) ||
       !digital_matches(P::charge_n,true) || !digital_matches(P::encoder_n,false) || !digital_matches(P::wdi,true) ||
       !check_counter(true) || !level(P::fault_n) || !std::isfinite(duty) || duty<=0 || duty>profile_.max_duty ||
       (direction!=1 && direction!=-1)) return trip();
    const int physical=direction*profile_.motor_sign;
    if(active_direction_ && active_direction_!=physical) return trip(); // Explicit coast required first.
    const auto ticks=static_cast<std::uint32_t>(std::floor(duty*500));
    if(ticks==0) return coast(); // Never round a small demand up to an unrequested pulse.
    auto active=physical>0 ? generator_a_ : generator_b_;
    auto inactive=physical>0 ? generator_b_ : generator_a_;
    auto compare=physical>0 ? compare_a_ : compare_b_;
    if(!record(mcpwm_generator_set_force_level(inactive,0,true)) ||
       !record(mcpwm_comparator_set_compare_value(compare,ticks))) return false;
    const auto began=now_us();
    while((MCPWM0.operators[0].gen_stmp_cfg.cmpr_a_shdw_full || MCPWM0.operators[0].gen_stmp_cfg.cmpr_b_shdw_full) &&
          now_us()>=began && now_us()-began<60) esp_rom_delay_us(1);
    if(now_us()<began || MCPWM0.operators[0].gen_stmp_cfg.cmpr_a_shdw_full || MCPWM0.operators[0].gen_stmp_cfg.cmpr_b_shdw_full) return trip(ESP_ERR_TIMEOUT);
    if(!record(mcpwm_generator_set_force_level(active,-1,true))) return false;
    active_direction_=physical; active_ticks_=ticks;
    return check_pwm(physical,ticks,true);
}
bool BenchC6Io::heartbeat_pulse() {
    if(!ready() || !awake_ || !counter_running_ || !encoder_on_ || !digital_matches(P::request_n,false) || !digital_matches(P::wdi,true) ||
       !digital_matches(P::charge_n,true) || !digital_matches(P::encoder_n,false) ||
       !check_counter(true) || !level(P::fault_n) || !check_pwm(active_direction_,active_ticks_,true)) return trip();
    const auto began=now_us();
    portENTER_CRITICAL(&pulse_mux_);
    const auto low=gpio_set_level(static_cast<gpio_num_t>(P::wdi),0);
    const bool low_seen=!level(P::wdi);
    esp_rom_delay_us(2);
    const auto high=gpio_set_level(static_cast<gpio_num_t>(P::wdi),1);
    const bool high_seen=level(P::wdi);
    portEXIT_CRITICAL(&pulse_mux_);
    if(low!=ESP_OK || high!=ESP_OK || !low_seen || !high_seen || now_us()<began || now_us()-began>100) return trip();
    pulse_seen_=true;
    return true;
}
FastInputs BenchC6Io::sample_fast() {
    if(!ready()) return {};
    const auto began=now_us();
    if(!check_counter(counter_running_) || !check_pwm(active_direction_,active_ticks_,awake_) || !digital_matches(P::charge_n,true) ||
       !digital_matches(P::encoder_n,!encoder_on_) || !digital_matches(P::request_n,request_high_) ||
       !digital_matches(P::wdi,true)) { trip(); return {}; }
    int raw=0, mv=0, count=0;
    double normalized=0;
    if(counter_running_) {
        if(!record(pcnt_unit_get_count(counter_,&count))) return {};
        const auto value=port::normalized_count(profile_,count,origin_);
        if(!value) { trip(); return {}; }
        normalized=*value;
    }
    if(!record(adc_oneshot_read(adc_,ADC_CHANNEL_2,&raw)) || !record(adc_cali_raw_to_voltage(calibration_,raw,&mv))) return {};
    const auto amps=port::current(profile_,raw,mv);
    if(!amps) { trip(); return {}; }
    if(now_us()<began || now_us()-began>1000 || sequence_==UINT64_MAX) { trip(ESP_ERR_TIMEOUT); return {}; }
    return {true,counter_running_,!level(P::up),!level(P::down),!level(P::fault_n),!level(P::reference),
            ++sequence_,began,epoch_,normalized,*amps};
}
bool BenchC6Io::shutdown() {
    if(!touched_) return true;
    if(!owner()) return trip();
    closed_=true;
    bool ok=request_n(true);
    ok=coast() && ok; ok=wdi_high() && ok; ok=charge_off() && ok;
    ok=counter_stop() && ok; ok=encoder_power(false) && ok; ok=awake_lock(false) && ok;
    // Preserve handles after delete failures; callers must inspect this result.
    if(generator_a_ && record(mcpwm_del_generator(generator_a_))) generator_a_=nullptr; else if(generator_a_) ok=false;
    if(generator_b_ && record(mcpwm_del_generator(generator_b_))) generator_b_=nullptr; else if(generator_b_) ok=false;
    if(compare_a_ && record(mcpwm_del_comparator(compare_a_))) compare_a_=nullptr; else if(compare_a_) ok=false;
    if(compare_b_ && record(mcpwm_del_comparator(compare_b_))) compare_b_=nullptr; else if(compare_b_) ok=false;
    if(operator_ && !generator_a_ && !generator_b_ && !compare_a_ && !compare_b_ && record(mcpwm_del_operator(operator_))) operator_=nullptr; else if(operator_) ok=false;
    if(timer_ && !timer_enabled_ && !operator_ && record(mcpwm_del_timer(timer_))) timer_=nullptr; else if(timer_) ok=false;
    if(channel_a_ && !counter_enabled_ && record(pcnt_del_channel(channel_a_))) channel_a_=nullptr; else if(channel_a_) ok=false;
    if(channel_b_ && !counter_enabled_ && record(pcnt_del_channel(channel_b_))) channel_b_=nullptr; else if(channel_b_) ok=false;
    if(low_watch_ && record(pcnt_unit_remove_watch_point(counter_,-count_limit))) low_watch_=false; else if(low_watch_) ok=false;
    if(high_watch_ && record(pcnt_unit_remove_watch_point(counter_,count_limit))) high_watch_=false; else if(high_watch_) ok=false;
    if(counter_ && !counter_enabled_ && !channel_a_ && !channel_b_ && !low_watch_ && !high_watch_ && record(pcnt_del_unit(counter_))) counter_=nullptr; else if(counter_) ok=false;
    if(calibration_ && record(adc_cali_delete_scheme_curve_fitting(calibration_))) calibration_=nullptr; else if(calibration_) ok=false;
    if(adc_ && !calibration_ && record(adc_oneshot_del_unit(adc_))) adc_=nullptr; else if(adc_) ok=false;
    if(init_apb_held_ && record(esp_pm_lock_release(init_apb_pm_))) init_apb_held_=false; else if(init_apb_held_) ok=false;
    if(init_apb_pm_ && !init_apb_held_ && record(esp_pm_lock_delete(init_apb_pm_))) init_apb_pm_=nullptr; else if(init_apb_pm_) ok=false;
    if(awake_pm_ && !awake_ && record(esp_pm_lock_delete(awake_pm_))) awake_pm_=nullptr; else if(awake_pm_) ok=false;
    initialized_=false;
    return ok;
}
} // namespace blinds::c6
