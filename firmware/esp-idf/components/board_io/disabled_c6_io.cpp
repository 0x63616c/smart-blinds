#include "disabled_c6_io.hpp"

namespace blinds::c6 {
namespace { using P=io::Pins; constexpr int count_limit=30000; }
bool DisabledC6Io::initialize() {
    if(touched_) return record(ESP_ERR_INVALID_STATE);
    touched_=true;
    if(setup_.initialize()) return true;
    shutdown();
    return false;
}
bool DisabledC6Io::output(int pin,bool high) {
    // Preload before output enable. INPUT_OUTPUT permits pad readback too.
    const auto gpio=static_cast<gpio_num_t>(pin);
    return record(gpio_set_level(gpio,high ? 1 : 0)) &&
           record(gpio_set_direction(gpio,GPIO_MODE_INPUT_OUTPUT)) &&
           record(gpio_set_pull_mode(gpio,GPIO_FLOATING));
}
bool DisabledC6Io::configure_inputs() {
    gpio_config_t config{};
    config.pin_bit_mask=(1ULL<<P::up)|(1ULL<<P::down)|(1ULL<<P::fault_n)|(1ULL<<P::reference);
    config.mode=GPIO_MODE_INPUT;
    config.pull_up_en=GPIO_PULLUP_DISABLE;
    config.pull_down_en=GPIO_PULLDOWN_DISABLE;
    config.intr_type=GPIO_INTR_DISABLE;
    return record(gpio_config(&config)); // Reviewed circuit supplies external pulls.
}
bool DisabledC6Io::configure_counter_stopped() {
    pcnt_unit_config_t config{};
    config.low_limit=-count_limit;
    config.high_limit=count_limit;
    config.flags.accum_count=true;
    if(!record(pcnt_new_unit(&config,&counter_))) return false;
    pcnt_glitch_filter_config_t filter{};
    filter.max_glitch_ns=1000; // Provisional; maximum encoder edge-rate test required.
    if(!record(pcnt_unit_set_glitch_filter(counter_,&filter))) return false;
    pcnt_chan_config_t channel{};
    channel.edge_gpio_num=P::encoder_a; channel.level_gpio_num=P::encoder_b;
    if(!record(pcnt_new_channel(counter_,&channel,&channel_a_))) return false;
    channel.edge_gpio_num=P::encoder_b; channel.level_gpio_num=P::encoder_a;
    if(!record(pcnt_new_channel(counter_,&channel,&channel_b_))) return false;
    if(!record(pcnt_channel_set_edge_action(channel_a_,PCNT_CHANNEL_EDGE_ACTION_DECREASE,PCNT_CHANNEL_EDGE_ACTION_INCREASE)) ||
       !record(pcnt_channel_set_level_action(channel_a_,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE)) ||
       !record(pcnt_channel_set_edge_action(channel_b_,PCNT_CHANNEL_EDGE_ACTION_INCREASE,PCNT_CHANNEL_EDGE_ACTION_DECREASE)) ||
       !record(pcnt_channel_set_level_action(channel_b_,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE))) return false;
    // PCNT allocation enables pull-ups; return to the board's externally driven inputs.
    if(!record(gpio_set_pull_mode(static_cast<gpio_num_t>(P::encoder_a),GPIO_FLOATING)) ||
       !record(gpio_set_pull_mode(static_cast<gpio_num_t>(P::encoder_b),GPIO_FLOATING))) return false;
    if(!record(pcnt_unit_add_watch_point(counter_,-count_limit))) return false;
    low_watch_=true;
    if(!record(pcnt_unit_add_watch_point(counter_,count_limit))) return false;
    high_watch_=true;
    return record(pcnt_unit_clear_count(counter_));
    // Intentionally no pcnt_unit_enable/start: no powered encoder or valid count.
}
bool DisabledC6Io::configure_pwm_stopped_low() {
    mcpwm_timer_config_t config{};
    config.group_id=0;
    config.clk_src=MCPWM_TIMER_CLK_SRC_DEFAULT;
    config.resolution_hz=1000000;
    config.count_mode=MCPWM_TIMER_COUNT_MODE_UP;
    config.period_ticks=50; // 20 kHz proposal, never started by this component.
    if(!record(mcpwm_new_timer(&config,&timer_))) return false;
    mcpwm_operator_config_t oper{}; oper.group_id=0;
    if(!record(mcpwm_new_operator(&oper,&operator_)) ||
       !record(mcpwm_operator_connect_timer(operator_,timer_))) return false;
    mcpwm_generator_config_t generator{};
    generator.gen_gpio_num=P::in1; generator.flags.io_loop_back=true;
    if(!record(mcpwm_new_generator(operator_,&generator,&generator_a_)) ||
       !record(mcpwm_generator_set_force_level(generator_a_,0,true))) return false;
    generator.gen_gpio_num=P::in2;
    if(!record(mcpwm_new_generator(operator_,&generator,&generator_b_)) ||
       !record(mcpwm_generator_set_force_level(generator_b_,0,true))) return false;
    return true;
    // No comparator waveform, timer enable/start or force-release operation.
}
bool DisabledC6Io::force_pwm_low() {
    bool ok=true;
    if(generator_a_) ok=record(mcpwm_generator_set_force_level(generator_a_,0,true)) && ok;
    if(generator_b_) ok=record(mcpwm_generator_set_force_level(generator_b_,0,true)) && ok;
    return ok;
}
bool DisabledC6Io::outputs_are_off() {
    const bool off=gpio_get_level(static_cast<gpio_num_t>(P::request_n)) &&
        gpio_get_level(static_cast<gpio_num_t>(P::charge_n)) &&
        gpio_get_level(static_cast<gpio_num_t>(P::encoder_n)) &&
        gpio_get_level(static_cast<gpio_num_t>(P::wdi)) &&
        !gpio_get_level(static_cast<gpio_num_t>(P::in1)) && !gpio_get_level(static_cast<gpio_num_t>(P::in2));
    return off || record(ESP_ERR_INVALID_STATE);
}
DisabledInputs DisabledC6Io::inputs() {
    if(closed_ || !setup_.verify_off()) return {};
    return {true, !gpio_get_level(static_cast<gpio_num_t>(P::up)),
            !gpio_get_level(static_cast<gpio_num_t>(P::down)),
            !gpio_get_level(static_cast<gpio_num_t>(P::fault_n)),
            !gpio_get_level(static_cast<gpio_num_t>(P::reference))};
}
bool DisabledC6Io::shutdown() {
    if(!touched_) return true; // Destruction of an unused component has no pin side effects.
    closed_=true;
    bool ok=setup_.hold_off();
    if(generator_a_ && record(mcpwm_del_generator(generator_a_))) generator_a_=nullptr; else if(generator_a_) ok=false;
    if(generator_b_ && record(mcpwm_del_generator(generator_b_))) generator_b_=nullptr; else if(generator_b_) ok=false;
    if(operator_ && !generator_a_ && !generator_b_ && record(mcpwm_del_operator(operator_))) operator_=nullptr; else if(operator_) ok=false;
    if(timer_ && !operator_ && record(mcpwm_del_timer(timer_))) timer_=nullptr; else if(timer_) ok=false;
    if(channel_a_ && record(pcnt_del_channel(channel_a_))) channel_a_=nullptr; else if(channel_a_) ok=false;
    if(channel_b_ && record(pcnt_del_channel(channel_b_))) channel_b_=nullptr; else if(channel_b_) ok=false;
    if(low_watch_ && record(pcnt_unit_remove_watch_point(counter_,-count_limit))) low_watch_=false; else if(low_watch_) ok=false;
    if(high_watch_ && record(pcnt_unit_remove_watch_point(counter_,count_limit))) high_watch_=false; else if(high_watch_) ok=false;
    if(counter_ && !channel_a_ && !channel_b_ && !low_watch_ && !high_watch_ && record(pcnt_del_unit(counter_))) counter_=nullptr; else if(counter_) ok=false;
    return ok;
}
} // namespace blinds::c6
