#pragma once
#include <cmath>
#include <cstdint>
#include <optional>

namespace blinds::port {
struct Profile {
    bool bench_qualified=false;
    std::uint64_t qualification_id=0;
    int encoder_sign=0, motor_sign=0; // Measured normalized physical polarity.
    double max_duty=.5, current_mv_per_a=540, current_zero_mv=0;
    bool valid() const {
        return bench_qualified && qualification_id && (encoder_sign==1 || encoder_sign==-1) &&
            (motor_sign==1 || motor_sign==-1) && std::isfinite(max_duty) && max_duty>0 && max_duty<=.8 &&
            std::isfinite(current_mv_per_a) && current_mv_per_a>=100 && current_mv_per_a<=2000 &&
            std::isfinite(current_zero_mv) && std::abs(current_zero_mv)<=100;
    }
};
inline std::optional<double> current(const Profile& p,int raw,int mv) {
    if(!p.valid() || raw<0 || raw>=4090 || mv<0 || mv>3000 || mv-p.current_zero_mv < -20) return {};
    return std::fmax(0.,(mv-p.current_zero_mv)/p.current_mv_per_a);
}
inline std::optional<double> normalized_count(const Profile& p,int raw,double origin) {
    if(!p.valid() || raw<=-100000000 || raw>=100000000 || !std::isfinite(origin) || std::abs(origin)>1e12) return {};
    const double result=origin+static_cast<double>(raw)*p.encoder_sign;
    if(std::abs(result)>1e12) return {};
    return result;
}
struct CounterReadback {
    bool routes_correct=false, pads_input_only=false, clock_enabled=false;
    bool reset=true, paused=true, edge_actions=false, level_actions=false, filter=false, limit_events=false;
    int high_limit=0, low_limit=0;
};
inline bool counter_valid(const CounterReadback& r,bool running) {
    return r.routes_correct && r.pads_input_only && r.clock_enabled && !r.reset && r.paused!=running &&
        r.edge_actions && r.level_actions && r.filter && r.limit_events && r.high_limit==30000 && r.low_limit==-30000;
}
struct PwmReadback {
    bool routes_correct=false, outputs_enabled=false, uninverted=false, plain_paths=false;
    bool timer_up=false, timer_running=false, timer_stopped=false, timer_select_zero=false, clock_divider_valid=false;
    bool immediate_force=false, comparator_tez=false, compare_pending=true;
    std::uint32_t period=0, action_a=0, action_b=0, force_a=0, force_b=0, compare_a=0, compare_b=0;
    bool pad_a=false, pad_b=false;
};
// Pinned C6 register semantics: action2 HIGH at TEZ, action1 LOW at compare.
// Only group0/operator0/timer0/generators0,1 are accepted; concurrent MCPWM
// allocation is rejected by actual routing/timer-selection readback.
inline bool pwm_valid(const PwmReadback& r,int direction,std::uint32_t ticks,bool awake) {
    if(!r.routes_correct || !r.outputs_enabled || !r.uninverted || !r.plain_paths ||
       !r.timer_up || !r.timer_select_zero || !r.clock_divider_valid || !r.immediate_force || !r.comparator_tez ||
       r.period!=500 || r.action_a!=0x12 || r.action_b!=0x42 || (awake ? !r.timer_running : !r.timer_stopped)) return false;
    if(direction==0) return r.force_a==1 && r.force_b==1 && !r.pad_a && !r.pad_b;
    if(!awake || ticks==0 || ticks>=500 || r.compare_pending) return false;
    if(direction==1) return r.force_a==0 && r.force_b==1 && r.compare_a==ticks && !r.pad_b;
    if(direction==-1) return r.force_a==1 && r.force_b==0 && r.compare_b==ticks && !r.pad_a;
    return false;
}
} // namespace blinds::port
