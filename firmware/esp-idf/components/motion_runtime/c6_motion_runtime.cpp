#include "c6_motion_runtime.hpp"
#include "bench_c6_io.hpp"
#include "max17320_reader.hpp"
#include "bq25798_config.hpp"
#include "esp_timer.h"
#include "esp_pm.h"
#include "esp_sleep.h"
#include "soc/gpio_struct.h"
#include "soc/gpio_sig_map.h"
#include <cstdlib>

namespace blinds::c6 {
namespace {
std::uint64_t now_us() { return static_cast<std::uint64_t>(esp_timer_get_time()); }
// The control owner has configured charge OFF and is its ONLY writer. This
// worker can only verify that independent inhibit, including output route/pad.
// No I2C failure or source condition can turn charging on in this application.
class ReadOnlyChargeInhibit final : public smart_blinds::charger::Inhibit {
public:
    explicit ReadOnlyChargeInhibit(const std::atomic<bool>& enabled) : enabled_(enabled) {}
    bool hold_off() override {
        constexpr auto pin=io::Pins::charge_n;
        return enabled_.load(std::memory_order_acquire) &&
            GPIO.func_out_sel_cfg[pin].out_sel==SIG_GPIO_OUT_IDX &&
            !GPIO.func_out_sel_cfg[pin].out_inv_sel && !GPIO.func_out_sel_cfg[pin].oen_inv_sel &&
            (GPIO.enable.val&(1U<<pin)) && gpio_get_level(static_cast<gpio_num_t>(pin));
    }
private:
    const std::atomic<bool>& enabled_;
};
}
bool MotionRuntime::start(TaskHandle_t radio_policy_worker) {
    if(!radio_policy_worker) return false;
    radio_task_=radio_policy_worker;
    return start({radio_policy_worker,[](void* task) {
        xTaskNotifyGive(static_cast<TaskHandle_t>(task)); return true;
    }},false);
}
bool MotionRuntime::start(runtime::WakeSink sink,bool local_buttons) {
    if(control_task_ || network_queue_ || !boot_ || !sink.signal) return false;
    wake_sink_=sink; local_buttons_=local_buttons;
    network_queue_=xQueueCreate(1,sizeof(runtime::Network));
    power_queue_=xQueueCreate(1,sizeof(runtime::Power));
    status_queue_=xQueueCreate(1,sizeof(runtime::Snapshot));
    reference_queue_=xQueueCreate(1,sizeof(PhysicalReference));
    if(!network_queue_ || !power_queue_ || !status_queue_ || !reference_queue_) return false;
    // Lower-priority I2C work cannot block the only motor owner. Hardware enable
    // still requires CONFIG_BLINDS_BENCH_MOTION and all local records.
    if(xTaskCreate(power_entry,"blind_power",6144,this,3,&power_task_)!=pdPASS) return false;
    return xTaskCreate(control_entry,"blind_control",8192,this,8,&control_task_)==pdPASS;
}
void MotionRuntime::publish_network(std::uint64_t now) {
    publish_network(now,signals_.generation());
}
void MotionRuntime::publish_network(std::uint64_t now,std::uint32_t acknowledged_revocation) {
    auto value=ingress_.snapshot(now);
    value.revocation=acknowledged_revocation;
    if(xQueueOverwrite(network_queue_,&value)!=pdPASS) abort();
    notify_request();
}
void MotionRuntime::notify_request() { if(control_task_) xTaskNotifyGive(control_task_); }
void MotionRuntime::revoke() { signals_.revoke(); notify_request(); }
void MotionRuntime::transport_fault() {
    signals_.fail(); io_ready_.store(false,std::memory_order_release); notify_request();
}
void MotionRuntime::button_irq(void* context) { static_cast<MotionRuntime*>(context)->local_stop_from_isr(); }
void MotionRuntime::local_stop_from_isr() {
    signals_.local_stop();
    BaseType_t wake=pdFALSE;
    if(control_task_) vTaskNotifyGiveFromISR(control_task_,&wake);
    // Wi-Fi uses a nonblocking notification relay. No eventfd mutex in this ISR.
    if(!wake_sink_.notify()) signals_.fail();
    if(wake) portYIELD_FROM_ISR();
}
bool MotionRuntime::wake_radio() {
    if(wake_sink_.notify()) return true;
    signals_.fail(); io_ready_.store(false,std::memory_order_release); return false;
}
bool MotionRuntime::parked_off(std::uint64_t now) const {
    runtime::Snapshot snapshot{};
    return status_queue_ && xQueuePeek(status_queue_,&snapshot,0)==pdPASS &&
        snapshot.parking.current(now,ingress_.activity(),signals_);
}
bool MotionRuntime::reference(const PhysicalReference& reference) {
    if(!io_qualified() || xQueueSend(reference_queue_,&reference,0)!=pdPASS) return false;
    notify_request(); return true;
}
bool MotionRuntime::status(char* output,std::size_t size,std::uint64_t now) {
    runtime::Snapshot status{};
    runtime::Power power{};
    xQueuePeek(status_queue_,&status,0);
    xQueuePeek(power_queue_,&power,0);
    power=sampling_.load(std::memory_order_acquire) ?
        power.in_window(sensing_window_.load(std::memory_order_acquire)) : runtime::Power{};
    // Called by the OpenThread owner: consult its current evidence directly,
    // not only the last worker status, after failed qualification/disconnect.
    const bool current=status.parking.revocation==signals_.generation() &&
        !signals_.failed() && !signals_.stop_pending();
    return runtime::status_json(output,size,boot_,status,power,ingress_.snapshot(now),io_qualified() && current,now);
}
void MotionRuntime::control_entry(void* c) { static_cast<MotionRuntime*>(c)->control(); }
void MotionRuntime::power_entry(void* c) { static_cast<MotionRuntime*>(c)->power(); }
void MotionRuntime::control() {
    const bool qualified=config_.valid(boot_);
    // Independent of radio locks and MotionExecutor's narrower sensing lock.
    // Owned only here; no SDK callback, disconnect or network task can release.
    esp_pm_lock_handle_t no_sleep=nullptr,max_speed=nullptr;
    bool held=false;
    const auto acquire=[&] {
        if(held) return true;
        if(!no_sleep || !max_speed || esp_pm_lock_acquire(no_sleep)!=ESP_OK) return false;
        if(esp_pm_lock_acquire(max_speed)!=ESP_OK) {
            // Keep NO_LIGHT_SLEEP owned on a partial failure.
            signals_.fail(); return false;
        }
        held=true; return true;
    };
    const bool locks=qualified &&
        esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP,0,"control-owner",&no_sleep)==ESP_OK &&
        esp_pm_lock_create(ESP_PM_CPU_FREQ_MAX,0,"control-speed",&max_speed)==ESP_OK && acquire();
    BenchC6Io io(config_.port);
    // An invalid application-level record cannot instantiate an otherwise
    // individually valid motion profile through the session constructor.
    const auto profile=qualified ? config_.motion : BenchMotionProfile{};
    MotionSession session(io,io,config_.calibration,config_.limits,profile,boot_);
    bool initialized=qualified && locks && io.initialize();
    if(initialized && local_buttons_) {
        bool ok=gpio_install_isr_service(0)==ESP_OK;
        for(const int number:{io::Pins::up,io::Pins::down}) {
            const auto pin=static_cast<gpio_num_t>(number);
            ok=(gpio_set_intr_type(pin,GPIO_INTR_ANYEDGE)==ESP_OK) && ok;
            ok=(gpio_isr_handler_add(pin,button_irq,this)==ESP_OK) && ok;
            ok=(gpio_wakeup_enable(pin,GPIO_INTR_LOW_LEVEL)==ESP_OK) && ok;
        }
        ok=(esp_sleep_enable_gpio_wakeup()==ESP_OK) && ok;
        if(!ok) { signals_.fail(); io.shutdown(); initialized=false; }
    }
    if(qualified && !initialized) signals_.fail();
    io_ready_.store(initialized,std::memory_order_release);
    auto previous=session.status();
    runtime::Parked prior_parking{};
    const auto sampling=[&](bool enabled) {
        const auto prior=sampling_.load(std::memory_order_acquire);
        if(enabled==prior) return;
        if(enabled) {
            const auto generation=sensing_window_.load(std::memory_order_relaxed);
            if(generation==UINT32_MAX) abort();
            sensing_window_.store(generation+1,std::memory_order_release);
        }
        sampling_.store(enabled,std::memory_order_release);
        xTaskNotifyGive(power_task_);
    };
    for(;;) {
        runtime::Network network{};
        runtime::Power evidence{};
        xQueuePeek(network_queue_,&network,0);
        const auto revocation=signals_.generation();
        network=runtime::admitted_network(network,signals_);
        if(initialized && (network.awake || previous.awake_required) && !acquire()) signals_.fail();
        sampling(initialized && (network.awake || previous.awake_required));
        xQueuePeek(power_queue_,&evidence,0);
        evidence=sampling_.load(std::memory_order_acquire) ?
            evidence.in_window(sensing_window_.load(std::memory_order_acquire)) : runtime::Power{};
        PhysicalReference ref{};
        if(xQueueReceive(reference_queue_,&ref,0)==pdPASS && initialized) session.establish_reference(ref);
        const auto activity=ingress_.activity();
        const auto fast=runtime::observe(initialized,initialized && io.stop_pressed(),
            previous.phase,signals_,[&]{ return motion_observation(io.sample_fast()); });
        network=runtime::admitted_network(network,signals_);
        auto input=runtime::input(fast,evidence,network,now_us());
        if(signals_.failed()) input.manual_intervention=true;
        const auto status=session.cycle(inbox_,input);
        if(initialized && io.faulted()) {
            // Permanent discrepancy; no remote recovery/reinitialize.
            io_ready_.store(false,std::memory_order_release);
            initialized=false; io.shutdown();
        }
        const bool off=initialized && !status.awake_required && io.parked_off();
        if(initialized && !status.awake_required && !off) {
            signals_.fail(); io_ready_.store(false,std::memory_order_release);
        }
        const auto parking=runtime::parked(now_us(),activity,ingress_.activity(),revocation,
                                           signals_,!status.awake_required,off,initialized && !io.faulted());
        const runtime::Snapshot publication{status,network.connection,network.probe,parking};
        if(xQueueOverwrite(status_queue_,&publication)!=pdPASS) abort();
        awake_.store(status.awake_required,std::memory_order_release);
        // Wake after publishing. A sink failure revokes and retains owner locks.
        const bool changed=status.awake_required!=previous.awake_required ||
            status.phase!=previous.phase || parking.activity!=prior_parking.activity ||
            parking.revocation!=prior_parking.revocation || parking.off!=prior_parking.off ||
            parking.healthy!=prior_parking.healthy;
        const bool notified=!changed || wake_radio();
        if(held && !network.awake && parking.current(now_us(),ingress_.activity(),signals_) && notified) {
            if(esp_pm_lock_release(max_speed)!=ESP_OK || esp_pm_lock_release(no_sleep)!=ESP_OK)
                signals_.fail(); // Failed teardown never creates another OFF grant.
            else held=false;
        }
        sampling(initialized && (network.awake || status.awake_required));
        previous=status;
        prior_parking=parking;
        // No catch-up control iterations or background watchdog feeds. Active
        // commands are checked against their own <=20 ms real-time deadline.
        // Idle uses notifications; default/unqualified operation never polls ADC.
        const auto timeout=(initialized && (network.awake || status.awake_required)) ? pdMS_TO_TICKS(10) : portMAX_DELAY;
        ulTaskNotifyTake(pdTRUE,timeout);
    }
}
void MotionRuntime::power() {
    i2c_master_bus_handle_t bus=nullptr;
    ReadOnlyChargeInhibit inhibit(io_ready_);
    Max17320Reader gauge;
    Bq25798Config charger(inhibit);
    power::GaugeMonitor monitor(boot_,config_.pack);
    bool attempted=false,configured=false,failed=false;
    std::uint32_t window=0;
    for(;;) {
        if(!sampling_.load(std::memory_order_acquire)) {
            const runtime::Power absent{};
            xQueueOverwrite(power_queue_,&absent);
            // Re-warm the qualification after every idle gap. Old captures are
            // never resurrected when the radio or sensor worker wakes again.
            monitor=power::GaugeMonitor(boot_,config_.pack);
            ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
            continue;
        }
        const auto current=sensing_window_.load(std::memory_order_acquire);
        if(current!=window) {
            window=current;
            monitor=power::GaugeMonitor(boot_,config_.pack);
            const runtime::Power absent{};
            xQueueOverwrite(power_queue_,&absent);
        }
        if(!attempted) {
            attempted=true;
            i2c_master_bus_config_t cfg{};
            cfg.i2c_port=I2C_NUM_0; cfg.sda_io_num=static_cast<gpio_num_t>(io::Pins::sda);
            cfg.scl_io_num=static_cast<gpio_num_t>(io::Pins::scl);
            cfg.clk_source=I2C_CLK_SRC_DEFAULT; cfg.glitch_ignore_cnt=7;
            cfg.flags.enable_internal_pullup=false; // Physical reviewed pullups.
            configured=config_.valid(boot_) && inhibit.hold_off() &&
                i2c_new_master_bus(&cfg,&bus)==ESP_OK && gauge.attach(bus)==ESP_OK && charger.attach(bus)==ESP_OK &&
                charger.configure(smart_blinds::charger::SourceVoltage::nine)==smart_blinds::charger::Error::none;
            failed=!configured;
        }
        runtime::Power evidence{};
        evidence.window=window;
        if(configured && !failed) {
            const auto capture=gauge.read();
            evidence.gauge=monitor.observe(capture,now_us());
            // Publish a bus/protection failure immediately before another I2C
            // operation. The last good observation must not mask this failure.
            if(!capture.valid || (evidence.gauge.state!=power::State::ready && evidence.gauge.state!=power::State::warming)) {
                failed=true;
                xQueueOverwrite(power_queue_,&evidence);
                notify_request();
            } else {
                evidence.charger=charger.capture_off();
                if(!evidence.charger.valid()) failed=true;
            }
        }
        if(failed || !sampling_.load(std::memory_order_acquire) ||
           sensing_window_.load(std::memory_order_acquire)!=window) evidence={};
        if(xQueueOverwrite(power_queue_,&evidence)!=pdPASS) abort();
        notify_request();
        // A failed physical read/configuration is latched to this boot; no
        // auto-bus recovery writes and no repeated stale-good publication.
        ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(100));
    }
}
} // namespace blinds::c6
