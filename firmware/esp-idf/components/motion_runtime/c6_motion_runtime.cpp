#include "c6_motion_runtime.hpp"
#include "bench_c6_io.hpp"
#include "c6_gauge_continuity.hpp"
#include <optional>
#include "bq25798_config.hpp"
#include "c6_pd_monitor.hpp"
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
    source_queue_=xQueueCreate(1,sizeof(SourceStatus));
    telemetry_queue_=xQueueCreate(1,sizeof(telemetry::Samples));
    if(!network_queue_ || !sensor_request_queue_ || !sensor_park_queue_ || !physical_off_queue_ || !status_queue_ || !reference_queue_ || !source_queue_ || !telemetry_queue_) return false;
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
void MotionRuntime::source_irq(void* context) { static_cast<MotionRuntime*>(context)->source_irq_from_isr(); }
void MotionRuntime::source_irq_from_isr() {
    auto old=source_event_.load(std::memory_order_acquire);
    while(old!=UINT32_MAX && !source_event_.compare_exchange_weak(old,old+1,std::memory_order_acq_rel)) {}
    if(old==UINT32_MAX) signals_.fail();
    BaseType_t wake=pdFALSE;
    if(control_task_) vTaskNotifyGiveFromISR(control_task_,&wake);
    if(wake) portYIELD_FROM_ISR();
}
bool MotionRuntime::source_status(smart_blinds::pd::Observation& out,std::uint64_t now) const {
    SourceStatus source{};
    if(!source_queue_ || xQueuePeek(source_queue_,&source,0)!=pdPASS ||
       source.event!=source_event_.load(std::memory_order_acquire) || source_busy_.load(std::memory_order_acquire) ||
       !bus_epoch_.matches(source.bus_epoch) || !io_qualified()) return false;
    const auto& o=source.observation;
    if(o.error!=smart_blinds::pd::Error::none || !o.serial || o.started_ms>o.finished_ms ||
       o.finished_ms>now/1000 || now/1000-o.started_ms>smart_blinds::pd::Monitor::max_age_ms) return false;
    out=o;return true;
}
bool MotionRuntime::telemetry(char* out,std::size_t size,std::uint64_t nonce) const {
    const auto event=source_event_.load(std::memory_order_acquire);
    const auto epoch=bus_epoch_.value();
    telemetry::Samples copy{};
    if(telemetry_queue_) xQueuePeek(telemetry_queue_,&copy,0);
    // A fault/event may arrive during the copy. No queue read is permission to
    // sense or move, and no network reader consumes the control publication.
    const bool pending=source_busy_.load(std::memory_order_acquire) ||
        event!=source_event_.load(std::memory_order_acquire) || copy.source_event!=event ||
        source_ack_.load(std::memory_order_acquire)!=event || epoch!=bus_epoch_.value();
    // Timestamp the completed copy, not entry to the request handler: a healthy
    // producer may have published a newer observation during xQueuePeek.
    return telemetry::json(out,size,boot_,nonce,now_us(),copy,signals_.failed(),pending,epoch);
}
bool MotionRuntime::wake_radio() {
    if(wake_sink_.notify()) return true;
    signals_.fail(); io_ready_.store(false,std::memory_order_release); return false;
}
bool MotionRuntime::parked_off(std::uint64_t now) const {
    runtime::Snapshot snapshot{};
    return status_queue_ && xQueuePeek(status_queue_,&snapshot,0)==pdPASS &&
        snapshot.parking.current(now,ingress_.activity(),signals_) && !ingress_.pending() && sensor_closed();
}
bool MotionRuntime::handoff(char* out,std::size_t size,std::uint64_t nonce) {
    // Only control can renew its physical observation. An HTTP/CoAP request
    // cannot restamp an old queue value or make a sensor closure acknowledgment.
    notify_request();
    const auto activity=ingress_.activity(),revocation=signals_.generation();
    const auto source=source_event_.load(std::memory_order_acquire),epoch=bus_epoch_.value();
    runtime::Snapshot copy{};
    const bool copied=status_queue_ && xQueuePeek(status_queue_,&copy,0)==pdPASS;
    const bool closed=sensor_closed();
    const auto now=now_us(); // After completed copies, including a racing producer.
    const auto network=ingress_.snapshot(now);
    const auto& status=copy.status;
    const bool terminal=status.phase==MotionSession::Phase::idle &&
        (status.result==MotionSession::Result::finished || status.result==MotionSession::Result::stopped);
    const bool settled=copied && terminal && io_qualified() && closed && !ingress_.pending() &&
        network.connection && copy.connection==network.connection &&
        copy.parking.current(now,activity,signals_) && activity==ingress_.activity() &&
        revocation==signals_.generation() && source==source_event_.load(std::memory_order_acquire) &&
        source==source_ack_.load(std::memory_order_acquire) && !source_busy_.load(std::memory_order_acquire) &&
        epoch==bus_epoch_.value();
    char height[32]="null";
    if(status.height_mm) std::snprintf(height,sizeof(height),"%.3f",*status.height_mm);
    const int n=std::snprintf(out,size,
        "{\"version\":1,\"boot\":\"%016" PRIx64 "\",\"nonce\":\"%016" PRIx64
        "\",\"responded_us\":\"%016" PRIx64 "\",\"sampled_us\":\"%016" PRIx64
        "\",\"command\":\"%016" PRIx64 "\",\"received_message\":\"%016" PRIx64
        "\",\"phase\":\"%s\",\"result\":\"%s\",\"reference_valid\":%s,\"height_mm\":%s,\"settled_off\":%s}",
        boot_,nonce,now,copy.parking.observed_us,status.command,ingress_.received_message(),
        runtime::name(status.phase),runtime::name(status.result),status.reference_valid ? "true":"false",height,
        settled ? "true":"false");
    return n>0 && static_cast<std::size_t>(n)<size;
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
    return off_transaction_.idle() && !sampling_.load(std::memory_order_acquire) &&
        xQueuePeek(sensor_request_queue_,&request,0)==pdPASS && !request.enabled && request.sequence &&
        xQueuePeek(sensor_park_queue_,&parked,0)==pdPASS && parked.clean &&
        request.sequence==parked.request.sequence && request.activity==parked.request.activity &&
        request.revocation==parked.request.revocation && request.activity==ingress_.activity() &&
        request.revocation==signals_.generation() && bus_epoch_.matches(parked.epoch) &&
        request.source_event==source_event_.load(std::memory_order_acquire) &&
        request.source_event==source_ack_.load(std::memory_order_acquire);
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
    if(initialized && (local_buttons_ || config_.pd_shared_bus_verified)) {
        bool ok=gpio_install_isr_service(0)==ESP_OK;
        for(const int number:{io::Pins::up,io::Pins::down}) {
            if(!local_buttons_) continue;
            const auto pin=static_cast<gpio_num_t>(number);
            ok=(gpio_set_intr_type(pin,GPIO_INTR_ANYEDGE)==ESP_OK) && ok;
            ok=(gpio_isr_handler_add(pin,button_irq,this)==ESP_OK) && ok;
            ok=(gpio_wakeup_enable(pin,GPIO_INTR_LOW_LEVEL)==ESP_OK) && ok;
        }
        if(config_.pd_shared_bus_verified) {
            const auto pin=static_cast<gpio_num_t>(io::Pins::charger_int);
            gpio_config_t input{};input.pin_bit_mask=1ULL<<io::Pins::charger_int;
            input.mode=GPIO_MODE_INPUT;input.intr_type=GPIO_INTR_DISABLE;
            input.pull_up_en=GPIO_PULLUP_DISABLE;input.pull_down_en=GPIO_PULLDOWN_DISABLE;
            ok=(gpio_config(&input)==ESP_OK) && ok;
            ok=((GPIO.enable.val&(1U<<io::Pins::charger_int))==0) && ok;
            ok=(gpio_set_intr_type(pin,GPIO_INTR_NEGEDGE)==ESP_OK) && ok;
            ok=(gpio_isr_handler_add(pin,source_irq,this)==ESP_OK) && ok;
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
    std::uint64_t source_poll_us=0,hold_started_us=0;
    std::uint32_t previous_hold=0,hold_revocation=0;
    if(initialized && config_.pd_shared_bus_verified) source_event_.store(1,std::memory_order_release);
    const auto sampling=[&](bool enabled) {
        const auto activity=ingress_.activity(),revocation=signals_.generation();
        const auto source=source_event_.load(std::memory_order_acquire);
        if(requested.sequence && (source==requested.source_event || enabled) && enabled==requested.enabled &&
           (enabled || (activity==requested.activity && revocation==requested.revocation))) return;
        if(requested.sequence==UINT32_MAX) { signals_.fail();return; }
        requested={requested.sequence+1,activity,revocation,enabled,source};
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
        const auto poll_now=now_us();
        if(initialized && config_.pd_shared_bus_verified &&
           source_event_.load(std::memory_order_acquire)==source_ack_.load(std::memory_order_acquire) &&
           (!source_poll_us || poll_now-source_poll_us>=5000000)) {
            auto old=source_event_.load(std::memory_order_acquire);
            if(old==UINT32_MAX) signals_.fail();
            else source_event_.compare_exchange_strong(old,old+1,std::memory_order_acq_rel);
            source_poll_us=poll_now;
        }
        const bool source_pending=source_event_.load(std::memory_order_acquire)!=source_ack_.load(std::memory_order_acquire);
        network=runtime::admitted_network(network,signals_);
        const auto held_transaction=off_transaction_.held();
        if(held_transaction!=previous_hold) { previous_hold=held_transaction;hold_started_us=poll_now; }
        // Individual bus/report deadlines remain shorter and unchanged. This
        // independent ceiling prevents a lost owner keeping admission forever.
        if(held_transaction && (poll_now<hold_started_us || poll_now-hold_started_us>1000000)) signals_.fail();
        if(initialized && (network.awake || previous.awake_required || source_pending || !off_transaction_.idle()) && !acquire()) signals_.fail();
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
        const auto transaction=held_transaction ? held_transaction:off_transaction_.pending();
        const bool deferred=held_transaction || (transaction && !previous.awake_required);
        // No local endpoint admission exists in this application. Raw local
        // STOP and all fault paths remain inside cycle, ahead of this deferral.
        const auto status=session.cycle(inbox_,input,{},deferred);
        if(initialized && io.faulted()) {
            // Permanent discrepancy; no remote recovery/reinitialize.
            signals_.fail();io_ready_.store(false,std::memory_order_release);
            initialized=false; io.shutdown();
        }
        const bool off=initialized && !status.awake_required && io.parked_off();
        if(initialized && !status.awake_required && !off) {
            signals_.fail(); io_ready_.store(false,std::memory_order_release);
        }
        const auto transaction_revocation=held_transaction ? hold_revocation:revocation;
        const bool held_off=transaction && deferred && off && !signals_.failed() &&
            transaction_revocation==signals_.generation();
        const PhysicalOff physical{now_us(),off && (held_off || activity==ingress_.activity()),activity,signals_.generation(),held_off?transaction:0};
        if(xQueueOverwrite(physical_off_queue_,&physical)!=pdPASS) abort();
        if(transaction && off_transaction_.pending()==transaction) {
            if(off_transaction_.answer(transaction,held_off) && held_off) {
                previous_hold=transaction;hold_started_us=physical.sampled_us;hold_revocation=revocation;
            }
            xTaskNotifyGive(power_task_);
        }
        // No sensor lifetime exists before qualified I/O initialization. An
        // OFF-only boot cannot prove the qualified owner's park condition.
        // Existing requests still transition/retire after I/O qualification loss.
        // After a definitive terminal result, the radio can stay owned/awake
        // while the sensor owner closes. Requiring radio sleep first would
        // deadlock Policy::operation, which correctly waits for our OFF ACK.
        const bool terminal_idle=status.phase==MotionSession::Phase::idle &&
            (status.result==MotionSession::Result::finished || status.result==MotionSession::Result::stopped);
        const bool sensing=status.awake_required || (network.awake && !(network.operation && terminal_idle));
        // A request may have arrived after this iteration captured activity.
        // Its intentionally invalid OFF publication is not permission to post
        // a new sensor transition using the newer generation. Wait for a real
        // stable OFF observation; do not weaken the sensor owner's guard.
        if(!initialized || signals_.failed()) {
            if(requested.sequence) sampling(false); // Retire existing ownership on real faults.
        } else if(physical.off && !(physical.activity&1U) &&
                  physical.activity==ingress_.activity() && physical.revocation==signals_.generation() &&
                  (sensing || !inbox_.pending())) sampling(sensing);
        const auto parking=runtime::parked(now_us(),activity,ingress_.activity(),revocation,
                                           signals_,!status.awake_required,off && !inbox_.pending() && sensor_closed(),initialized && !io.faulted());
        const runtime::Snapshot publication{status,network.connection,network.probe,parking};
        if(xQueueOverwrite(status_queue_,&publication)!=pdPASS) abort();
        awake_.store(status.awake_required,std::memory_order_release);
        // Wake after publishing. A sink failure revokes and retains owner locks.
        const bool changed=status.awake_required!=previous.awake_required ||
            status.phase!=previous.phase || parking.activity!=prior_parking.activity ||
            parking.revocation!=prior_parking.revocation || parking.off!=prior_parking.off ||
            parking.healthy!=prior_parking.healthy;
        const bool notified=!changed || wake_radio();
        if(held && !network.awake && !source_pending && parking.current(now_us(),ingress_.activity(),signals_) && notified) {
            if(esp_pm_lock_release(max_speed)!=ESP_OK || esp_pm_lock_release(no_sleep)!=ESP_OK)
                signals_.fail(); // Failed teardown never creates another OFF grant.
            else held=false;
        }
        previous=status;
        prior_parking=parking;
        // No catch-up control iterations or background watchdog feeds. Active
        // commands are checked against their own <=20 ms real-time deadline.
        // Idle uses notifications; default/unqualified operation never polls ADC.
        const auto timeout=(initialized && (network.awake || status.awake_required || !sensor_closed() || source_pending)) ? pdMS_TO_TICKS(10) :
            (initialized && config_.pd_shared_bus_verified ? pdMS_TO_TICKS(5000):portMAX_DELAY);
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
    class MotorOff final:public ch::ParkGuard {
    public:
        MotorOff(MotionRuntime& runtime):runtime_(runtime),queue_(runtime.physical_off_queue_),ready_(runtime.io_ready_) {}
        ch::ParkIdentity identity() const override {
            return {runtime_.boot_,runtime_.config_.gauge.pack.pack_binding,
                    runtime_.config_.gauge.pack.qualification_id,runtime_.bus_epoch_.value(),
                    reinterpret_cast<std::uintptr_t>(xTaskGetCurrentTaskHandle())};
        }
        bool hold_off() override {
            PhysicalOff value{};
            const bool copied=ready_.load(std::memory_order_acquire) && xQueuePeek(queue_,&value,0)==pdPASS;
            // The control owner may publish while this task copies. Sample age
            // AFTER the completed copy so a healthy newer report is not future.
            const auto now=now_us();
            const auto transaction=runtime_.off_transaction_.held();
            const bool result=copied && transaction && value.transaction==transaction &&
                value.off &&
                value.revocation==runtime_.signals_.generation() && !runtime_.signals_.failed() && value.sampled_us && value.sampled_us<=now && now-value.sampled_us<=30000 &&
                gpio_get_level(static_cast<gpio_num_t>(io::Pins::request_n)) &&
                !gpio_get_level(static_cast<gpio_num_t>(io::Pins::in1)) &&
                !gpio_get_level(static_cast<gpio_num_t>(io::Pins::in2));
#ifndef ESP_PLATFORM
            if(!result) std::fprintf(stderr,"OFF refusal now=%" PRIu64 " sampled=%" PRIu64 " delta=%" PRId64 " off=%u activity=%u/%u revocation=%u/%u transaction=%u/%u ready=%u failed=%u\n",
                now,value.sampled_us,static_cast<std::int64_t>(now)-static_cast<std::int64_t>(value.sampled_us),unsigned(value.off),
                value.activity,runtime_.ingress_.activity(),value.revocation,runtime_.signals_.generation(),value.transaction,transaction,
                unsigned(ready_.load()),unsigned(runtime_.signals_.failed()));
#endif
            return result;
        }
    private: MotionRuntime& runtime_;QueueHandle_t queue_;const std::atomic<bool>& ready_;
    } motor_off(*this);
    struct Session {
        const gc::Context context;
        gc::JointMailbox box;
        Bq25798Config charger;
        GaugeContinuity gauge;
        PdMonitor pd;
        gc::Window window{};
        ch::OffCapture transition{}; // Retained on terminal failure; raw clear-on-read flags survive.
        bool ticket=false;
        std::uint64_t parked_us=0,last_ready_us=0;
        Session(gc::Profile profile,gc::Context c,PowerMailboxGate& gate,gc::BusEpoch& epoch,ch::Inhibit& inhibit,smart_blinds::pd::FactoryRecord record)
            :context(c),box(gate,epoch,c),charger(inhibit,box,epoch),gauge(profile,c,epoch,box,charger.policy()),pd(record,epoch) {}
    };
    std::optional<Session> session;
    std::optional<ch::ParkedImage> parked_image;
    std::optional<std::uint8_t> pd_alert_mask;
    bool failed=false,attempted=false,hardware_parked=false;
    std::uint32_t active_request=0;
    std::optional<std::uint64_t> alert_drain_started;
    gc::Failure first_failure{};
    telemetry::Samples information{}; // Sensor-owned, across clean session replacement.
    const auto publish_information=[&]() {
        if(xQueueOverwrite(telemetry_queue_,&information)!=pdPASS) abort();
    };
    const auto copy_charger=[&](const ch::OffCapture& observation) {
        if(observation.valid()) information.charger={observation.started_ms*1000,
            bus_epoch_.value(),true,observation.source_present()};
    };
    const auto terminal=[&](gc::Failure failure) {
        if(failure.kind==gc::FailureKind::none) failure={gc::FailureKind::lifecycle,19};
        if(first_failure.kind==gc::FailureKind::none) { first_failure=failure;
#ifndef ESP_PLATFORM
            std::fprintf(stderr,"sensor first failure %u/%u BQ=%u PD=%u\n",unsigned(failure.kind),failure.code,session?unsigned(session->charger.policy().first_error()):999,session?unsigned(session->pd.policy().first_error()):999);
#endif
        }
        information.fault=first_failure.kind==gc::FailureKind::gauge ? telemetry::Fault::gauge:
            first_failure.kind==gc::FailureKind::charger ? telemetry::Fault::charger:telemetry::Fault::lifecycle;
        information.fault_code=first_failure.code;publish_information();
        failed=true;sensors_.withdraw();
        if(session) session->box.retire(first_failure);
        signals_.fail();notify_request();
    };
    const auto discard=[&]() {
        sensors_.withdraw();
        if(session) {
            session->box.close_window(session->window);
            if(!session->box.healthy()) { terminal(session->box.failure());return false; }
            parked_image=session->charger.policy().release_parked(motor_off);
            if(!parked_image) { terminal(session->box.failure());return false; }
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
        if(session && (session->pd.close()!=ESP_OK || session->gauge.close()!=ESP_OK || session->charger.detach()!=ESP_OK)) {
            terminal({gc::FailureKind::lifecycle,12});return false;
        }
        session.reset();return true;
    };
    const auto park_session=[&]() {
        if(!session || hardware_parked) return true;
        sensors_.withdraw();
        if(session->window) {
            session->box.close_window(session->window);
            if(!session->box.closure_acknowledged(session->window)) {
                terminal(session->box.failure());return false;
            }
        } else if(!session->box.healthy()) { terminal(session->box.failure());return false; }
        session->transition=session->charger.policy().capture_stationary_off(motor_off);
        if(!session->transition.valid()) { terminal(session->box.failure());return false; }
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
    const auto alert_clear=[&]() {
        if(!config_.pd_shared_bus_verified || gpio_get_level(static_cast<gpio_num_t>(io::Pins::charger_int))) {
            alert_drain_started.reset();return true;
        }
        // A shared line may reassert as another normal PD message arrives.
        // Preserve the first pending time; repeated events cannot extend it.
        const auto now=now_us();
        if(!alert_drain_started) alert_drain_started=now;
        else if(now<*alert_drain_started || now-*alert_drain_started>=500000)
            terminal({gc::FailureKind::lifecycle,42});
        return false;
    };
    const auto source_poll=[&]() {
        if(!config_.pd_shared_bus_verified || !session) return true;
        const auto event=source_event_.load(std::memory_order_acquire);
        source_busy_.store(true,std::memory_order_release);
        const auto previous_source=session->pd.policy().last();
        const auto value=session->pd.policy().poll();
        if(value.error!=smart_blinds::pd::Error::none) {
            terminal({gc::FailureKind::lifecycle,static_cast<std::uint16_t>(30+static_cast<unsigned>(value.error))});return false;
        }
        const bool changed=smart_blinds::pd::discontinuity(previous_source,value);
        if(changed && !motor_off.hold_off()) {
            // An actual source discontinuity outside a settled OFF boundary
            // requests the global STOP path, including local execution. A
            // normal received PD message alone is not a movement cancellation.
            signals_.local_stop();notify_request();
        }
        information.pd={value.started_ms*1000,bus_epoch_.value(),value.epoch,value.serial,
            value.current_ma,[&] {
                switch(value.state) {
                case smart_blinds::pd::State::detached:return telemetry::Source::detached;
                case smart_blinds::pd::State::negotiating:return telemetry::Source::negotiating;
                case smart_blinds::pd::State::unapproved:return telemetry::Source::unapproved;
                case smart_blinds::pd::State::ready:return telemetry::Source::policy_observed;
                case smart_blinds::pd::State::fault:return telemetry::Source::fault;
                default:return telemetry::Source::unavailable;
                }
            }(),true,bool(value.port&1)};
        const SourceStatus report{value,event,bus_epoch_.value()};
        if(xQueueOverwrite(source_queue_,&report)!=pdPASS) abort();
        return true;
    };
    for(;;) {
        if(signals_.failed() && !failed) terminal({gc::FailureKind::lifecycle,20});
        SensorRequest request{};
        if(xQueuePeek(sensor_request_queue_,&request,0)!=pdPASS || !request.sequence || failed) {
            ulTaskNotifyTake(pdTRUE,portMAX_DELAY);continue;
        }
        struct Hold {
            MotionRuntime& runtime;std::uint32_t token=0;
            void release() { if(token) { runtime.off_transaction_.release(token);token=0;runtime.notify_request(); } }
            ~Hold() { release(); }
        } hold{*this,off_transaction_.request()};
        if(!hold.token) { terminal({gc::FailureKind::lifecycle,45});continue; }
        notify_request();
        const auto wait_started=now_us();
        while(off_transaction_.state(hold.token)==runtime::OffTransaction::State::requested) {
            const auto current=now_us();
            if(signals_.failed() || current<wait_started || current-wait_started>100000) {
                terminal({gc::FailureKind::lifecycle,46});break;
            }
            ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(1));
        }
        if(failed) continue;
        const bool stationary_hold=off_transaction_.state(hold.token)==runtime::OffTransaction::State::granted;
        if(!stationary_hold && (!request.enabled || request.sequence!=active_request)) {
            hold.release();ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(10));continue;
        }
        if(!request.enabled && (session || !config_.pd_shared_bus_verified)) {
            sensors_.withdraw();
            if(!park_session()) continue;
            const auto serviced=source_event_.load(std::memory_order_acquire);
            if(session) {
                const auto reconciled=session->charger.policy().reconcile_parked(motor_off);
                session->transition=reconciled.observation;
                if(!reconciled.valid() || !source_poll()) { if(!failed) terminal(session->box.failure());continue; }
            }
            // Both owners were serviced. A still-low shared line means another
            // pending/fault condition; do not acknowledge it or release PM.
            if(!alert_clear()) { hold.release();if(!failed) ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(10));continue; }
            if(session) copy_charger(session->transition);
            information.source_event=serviced;publish_information();
            source_ack_.store(serviced,std::memory_order_release);
            source_busy_.store(false,std::memory_order_release);
            if(!motor_off.hold_off() || !inhibit.hold_off()) {
                terminal({gc::FailureKind::lifecycle,13});continue;
            }
            const SensorPark ack{request,bus_epoch_.value(),session ? session->parked_us:0,
                                 true,session && session->ticket};
            if(xQueueOverwrite(sensor_park_queue_,&ack)!=pdPASS) abort();
            active_request=0;hold.release();notify_request();
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
                auto record=config_.pd_factory;
                if(record.boot!=boot_ || record.qualification!=config_.port.qualification_id) record={};
                session.emplace(config_.gauge,context,mailbox_gate_,bus_epoch_,inhibit,record);
                if(session->gauge.attach(bus,context)!=ESP_OK || session->charger.attach(bus)!=ESP_OK) {
                    terminal(session->box.failure());continue;
                }
                ch::Error result;
                if(hardware_parked) {
                    if(!parked_image) { terminal({gc::FailureKind::lifecycle,43});continue; }
                    session->transition=session->charger.policy().adopt_parked(*parked_image,motor_off);
                    parked_image.reset();
                    result=session->transition.error;
                } else result=session->charger.configure(ch::SourceVoltage::nine);
                if(result!=ch::Error::none) { terminal(session->box.failure());continue; }
                if(config_.pd_shared_bus_verified) {
                    if(session->pd.attach(bus)!=ESP_OK ||
                       session->pd.policy().initialize(0,pd_alert_mask).error!=smart_blinds::pd::Error::none) {
                        terminal({gc::FailureKind::lifecycle,44});continue;
                    }
                    pd_alert_mask=session->pd.policy().configured_mask();
                }
            }
            if(!request.enabled) { if(!park_session()) continue;continue; }
            if(hardware_parked) {
                const auto reconciled=session->charger.policy().reconcile_parked(motor_off);
                session->transition=reconciled.observation;
                if(!reconciled.valid()) { terminal(session->box.failure());continue; }
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
        const auto source_event=source_event_.load(std::memory_order_acquire);
        if(!source_poll()) continue;
        const auto stationary=stationary_hold && motor_off.hold_off();
        const auto result=session->gauge.refresh(session->context,session->window,stationary?&motor_off:nullptr);
        if(result==gc::Refresh::failed) { terminal(session->box.failure());continue; }
        if(result==gc::Refresh::published) {
            auto read=session->box.read_latest(session->window,now_us());
            const auto record=read ? read->consume(now_us()):std::optional<gc::JointRecord>{};
            if(!record) { terminal({gc::FailureKind::lifecycle,18});continue; }
            const auto& measured=record->gauge.evidence.report;
            session->last_ready_us=measured.observed_us;
            information.battery={measured.observed_us,measured.pack_binding,record->gauge.epoch,
                record->gauge.serial,measured.soc_percent.value_or(0),true,measured.soc_percent.has_value()};
            copy_charger(record->charger);
        }
        if(!alert_clear()) { hold.release();if(!failed) ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(10));continue; }
        information.source_event=source_event;publish_information();
        source_ack_.store(source_event,std::memory_order_release);
        source_busy_.store(false,std::memory_order_release);
        hold.release();notify_request();
        ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(100));
    }
}
} // namespace blinds::c6
