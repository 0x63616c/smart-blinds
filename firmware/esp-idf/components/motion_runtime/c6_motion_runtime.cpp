#include "c6_motion_runtime.hpp"
#include "bench_c6_io.hpp"
#include "c6_gauge_continuity.hpp"
#include <optional>
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
    sensor_request_queue_=xQueueCreate(1,sizeof(SensorRequest));
    sensor_park_queue_=xQueueCreate(1,sizeof(SensorPark));
    physical_off_queue_=xQueueCreate(1,sizeof(PhysicalOff));
    status_queue_=xQueueCreate(1,sizeof(runtime::Snapshot));
    reference_queue_=xQueueCreate(1,sizeof(PhysicalReference));
    if(!network_queue_ || !sensor_request_queue_ || !sensor_park_queue_ || !physical_off_queue_ || !status_queue_ || !reference_queue_) return false;
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
        snapshot.parking.current(now,ingress_.activity(),signals_) && sensor_closed();
}
bool MotionRuntime::reference(const PhysicalReference& reference) {
    if(!io_qualified() || xQueueSend(reference_queue_,&reference,0)!=pdPASS) return false;
    notify_request(); return true;
}
bool MotionRuntime::status(char* output,std::size_t size,std::uint64_t now) {
    runtime::Snapshot status{};
    const auto power=power_snapshot();
    xQueuePeek(status_queue_,&status,0);
    // Called by the OpenThread owner: consult its current evidence directly,
    // not only the last worker status, after failed qualification/disconnect.
    const bool current=status.parking.revocation==signals_.generation() &&
        !signals_.failed() && !signals_.stop_pending();
    return runtime::status_json(output,size,boot_,status,power,ingress_.snapshot(now),io_qualified() && current,now);
}
bool MotionRuntime::sensor_closed() const {
    SensorRequest request{};SensorPark parked{};
    return !sampling_.load(std::memory_order_acquire) &&
        xQueuePeek(sensor_request_queue_,&request,0)==pdPASS && !request.enabled && request.sequence &&
        xQueuePeek(sensor_park_queue_,&parked,0)==pdPASS && parked.clean &&
        request.sequence==parked.request.sequence && request.activity==parked.request.activity &&
        request.revocation==parked.request.revocation && request.activity==ingress_.activity() &&
        request.revocation==signals_.generation() && bus_epoch_.matches(parked.epoch);
}
runtime::Power MotionRuntime::power_snapshot() {
    if(!sampling_.load(std::memory_order_acquire)) return {};
    const auto request=sensing_window_.load(std::memory_order_acquire);
    const auto record=sensors_.snapshot(request,now_us);
    if(!record || !sampling_.load(std::memory_order_acquire) ||
       sensing_window_.load(std::memory_order_acquire)!=request || !sensors_.current(*record,request)) return {};
    return {request,record->gauge.evidence.report,record->charger};
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
    SensorRequest requested{};
    const auto sampling=[&](bool enabled) {
        const auto activity=ingress_.activity(),revocation=signals_.generation();
        if(requested.sequence && enabled==requested.enabled &&
           (enabled || (activity==requested.activity && revocation==requested.revocation))) return;
        if(requested.sequence==UINT32_MAX) { signals_.fail();return; }
        requested={requested.sequence+1,activity,revocation,enabled};
        sensing_window_.store(requested.sequence,std::memory_order_release);
        sampling_.store(enabled,std::memory_order_release);
        // Withdraw before another control iteration can consume old evidence.
        sensors_.withdraw();
        if(xQueueOverwrite(sensor_request_queue_,&requested)!=pdPASS) abort();
        xTaskNotifyGive(power_task_);
    };
    for(;;) {
        runtime::Network network{};
        runtime::Power evidence{};
        xQueuePeek(network_queue_,&network,0);
        const auto revocation=signals_.generation();
        network=runtime::admitted_network(network,signals_);
        if(initialized && (network.awake || previous.awake_required) && !acquire()) signals_.fail();
        // Request a sensor transition only after this iteration publishes fresh
        // physical OFF below. SDK calls can yield even on the priority-8 owner.
        PhysicalReference ref{};
        if(xQueueReceive(reference_queue_,&ref,0)==pdPASS && initialized) session.establish_reference(ref);
        const auto activity=ingress_.activity();
        const auto fast=runtime::observe(initialized,initialized && io.stop_pressed(),
            previous.phase,signals_,[&]{ return motion_observation(io.sample_fast()); });
        network=runtime::admitted_network(network,signals_);
        evidence=power_snapshot(); // Fast STOP/actual I/O always precedes this independent copy.
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
        const PhysicalOff physical{now_us(),off};
        if(xQueueOverwrite(physical_off_queue_,&physical)!=pdPASS) abort();
        sampling(initialized && (network.awake || status.awake_required));
        const auto parking=runtime::parked(now_us(),activity,ingress_.activity(),revocation,
                                           signals_,!status.awake_required,off && sensor_closed(),initialized && !io.faulted());
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
        previous=status;
        prior_parking=parking;
        // No catch-up control iterations or background watchdog feeds. Active
        // commands are checked against their own <=20 ms real-time deadline.
        // Idle uses notifications; default/unqualified operation never polls ADC.
        const auto timeout=(initialized && (network.awake || status.awake_required || !sensor_closed())) ? pdMS_TO_TICKS(10) : portMAX_DELAY;
        ulTaskNotifyTake(pdTRUE,timeout);
    }
}
void MotionRuntime::power() {
    namespace gc=power::continuity;
    namespace ch=smart_blinds::charger;
    i2c_master_bus_handle_t bus=nullptr;
    ReadOnlyChargeInhibit inhibit(io_ready_);
    // The control owner supplies fresh full peripheral OFF readback. Verify the
    // physical permission/pads again here around each charger transition.
    class MotorOff final:public ch::Inhibit {
    public:
        MotorOff(QueueHandle_t queue,const std::atomic<bool>& ready):queue_(queue),ready_(ready) {}
        bool hold_off() override {
            PhysicalOff value{};const auto now=now_us();
            return ready_.load(std::memory_order_acquire) && xQueuePeek(queue_,&value,0)==pdPASS &&
                value.off && value.sampled_us && value.sampled_us<=now && now-value.sampled_us<=30000 &&
                gpio_get_level(static_cast<gpio_num_t>(io::Pins::request_n)) &&
                !gpio_get_level(static_cast<gpio_num_t>(io::Pins::in1)) &&
                !gpio_get_level(static_cast<gpio_num_t>(io::Pins::in2));
        }
    private: QueueHandle_t queue_;const std::atomic<bool>& ready_;
    } motor_off(physical_off_queue_,io_ready_);
    struct Session {
        const gc::Context context;
        gc::JointMailbox box;
        Bq25798Config charger;
        GaugeContinuity gauge;
        gc::Window window{};
        ch::OffCapture transition{}; // Retained on terminal failure; raw clear-on-read flags survive.
        bool ticket=false;
        std::uint64_t parked_us=0,last_ready_us=0;
        Session(gc::Profile profile,gc::Context c,PowerMailboxGate& gate,gc::BusEpoch& epoch,ch::Inhibit& inhibit)
            :context(c),box(gate,epoch,c),charger(inhibit,box,epoch),gauge(profile,c,epoch,box,charger.policy()) {}
    };
    std::optional<Session> session;
    bool failed=false,attempted=false,hardware_parked=false;
    std::uint32_t active_request=0;
    gc::Failure first_failure{};
    const auto terminal=[&](gc::Failure failure) {
        if(failure.kind==gc::FailureKind::none) failure={gc::FailureKind::lifecycle,19};
        if(first_failure.kind==gc::FailureKind::none) first_failure=failure;
        failed=true;sensors_.withdraw();
        if(session) session->box.retire(first_failure);
        signals_.fail();notify_request();
    };
    const auto discard=[&]() {
        sensors_.withdraw();
        if(session) {
            session->box.close_window(session->window);
            if(!session->box.healthy()) { terminal(session->box.failure());return false; }
            // This expected lifecycle retirement occurs only after owner I/O is
            // complete, so it cannot outrun a failure still returning from I2C.
            session->box.retire({gc::FailureKind::lifecycle,10});
        }
        const auto began=now_us();
        while(!sensors_.quiescent()) {
            const auto now=now_us();
            if(now<began || now-began>20000) { terminal({gc::FailureKind::lifecycle,11});return false; }
            vTaskDelay(1); // No busy wait and no control-owner wait.
        }
        if(session && (session->gauge.close()!=ESP_OK || session->charger.detach()!=ESP_OK)) {
            terminal({gc::FailureKind::lifecycle,12});return false;
        }
        session.reset();return true;
    };
    const auto park_session=[&]() {
        if(!session || hardware_parked) return true;
        sensors_.withdraw();session->box.close_window(session->window);
        if(!session->box.closure_acknowledged(session->window)) {
            terminal(session->box.failure());return false;
        }
        session->transition=session->charger.policy().park_off(motor_off);
        if(!session->transition.valid()) { terminal(session->box.failure());return false; }
        hardware_parked=true;
        const auto now=now_us();
        session->ticket=session->last_ready_us && now>=session->last_ready_us &&
            now-session->last_ready_us<=250000;
        if(session->ticket && !session->gauge.park_light_sleep(session->context)) {
            terminal(session->box.failure());return false;
        }
        session->parked_us=now; // Once per real park, never renewed by DTIM/status wakes.
        return true;
    };
    for(;;) {
        if(signals_.failed() && !failed) terminal({gc::FailureKind::lifecycle,20});
        SensorRequest request{};
        if(xQueuePeek(sensor_request_queue_,&request,0)!=pdPASS || !request.sequence || failed) {
            ulTaskNotifyTake(pdTRUE,portMAX_DELAY);continue;
        }
        if(!request.enabled) {
            sensors_.withdraw();
            if(!park_session()) continue;
            if(!motor_off.hold_off() || !inhibit.hold_off()) {
                terminal({gc::FailureKind::lifecycle,13});continue;
            }
            const SensorPark ack{request,bus_epoch_.value(),session ? session->parked_us:0,
                                 true,session && session->ticket};
            if(xQueueOverwrite(sensor_park_queue_,&ack)!=pdPASS) abort();
            active_request=0;notify_request();
            ulTaskNotifyTake(pdTRUE,portMAX_DELAY);continue;
        }
        if(request.sequence!=active_request) {
            // A close/wake can arrive while one synchronous read is returning.
            // Even if the owner did not observe the short disabled request,
            // close the old active window through the normal OFF park path.
            if(active_request && !park_session()) continue;
            const auto now=now_us();
            if(session && (!session->ticket || now<session->parked_us ||
                           now-session->parked_us>config_.gauge.max_light_sleep_us)) {
                if(now<session->parked_us) { terminal({gc::FailureKind::lifecycle,14});continue; }
                if(!discard()) continue;
            }
            if(!session) {
                if(!config_.valid(boot_) || !motor_off.hold_off() || !inhibit.hold_off() ||
                   bus_epoch_.value()==UINT32_MAX) {
                    terminal({gc::FailureKind::lifecycle,15});continue;
                }
                if(!attempted) {
                    attempted=true;i2c_master_bus_config_t cfg{};
                    cfg.i2c_port=I2C_NUM_0;cfg.sda_io_num=static_cast<gpio_num_t>(io::Pins::sda);
                    cfg.scl_io_num=static_cast<gpio_num_t>(io::Pins::scl);
                    cfg.clk_source=I2C_CLK_SRC_DEFAULT;cfg.glitch_ignore_cnt=7;cfg.flags.enable_internal_pullup=false;
                    if(i2c_new_master_bus(&cfg,&bus)!=ESP_OK) { terminal({gc::FailureKind::lifecycle,16});continue; }
                }
                const auto epoch=bus_epoch_.value();
                const gc::Context context{boot_,epoch,epoch,config_.gauge.pack.pack_binding,config_.gauge.pack.qualification_id};
                session.emplace(config_.gauge,context,mailbox_gate_,bus_epoch_,inhibit);
                if(session->gauge.attach(bus,context)!=ESP_OK || session->charger.attach(bus)!=ESP_OK) {
                    terminal(session->box.failure());continue;
                }
                ch::Error result;
                if(hardware_parked) {
                    session->transition=session->charger.policy().adopt_parked(ch::SourceVoltage::nine,motor_off);
                    result=session->transition.error;
                } else result=session->charger.configure(ch::SourceVoltage::nine);
                if(result!=ch::Error::none) { terminal(session->box.failure());continue; }
            }
            if(hardware_parked) {
                session->transition=session->charger.policy().resume_off(motor_off);
                if(!session->transition.valid() ||
                   (session->ticket && !session->gauge.resume_light_sleep(session->context))) {
                    terminal(session->box.failure());continue;
                }
                hardware_parked=false;session->ticket=false;
            }
            const auto began=now_us();
            while(!sensors_.quiescent()) {
                const auto current=now_us();
                if(current<began || current-began>20000) {
                    terminal({gc::FailureKind::lifecycle,11});break;
                }
                vTaskDelay(1);
            }
            if(failed) continue;
            session->window=session->box.open_window();
            if(!session->window || !sensors_.install(session->box,session->window,request.sequence)) {
                terminal({gc::FailureKind::lifecycle,17});continue;
            }
            active_request=request.sequence;
        }
        const auto result=session->gauge.refresh(session->context,session->window);
        if(result==gc::Refresh::failed) { terminal(session->box.failure());continue; }
        if(result==gc::Refresh::published) {
            auto read=session->box.read_latest(session->window,now_us());
            const auto record=read ? read->consume(now_us()):std::optional<gc::JointRecord>{};
            if(!record) { terminal({gc::FailureKind::lifecycle,18});continue; }
            session->last_ready_us=record->gauge.evidence.report.observed_us;
        }
        notify_request();
        ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(100));
    }
}
} // namespace blinds::c6
