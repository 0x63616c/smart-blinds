#pragma once
#include "smart_blinds/motion_runtime.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <atomic>
#include "c6_power_mailbox.hpp"
#include "smart_blinds/sensor_access.hpp"

namespace blinds::c6 {
// Lifetime is the application lifetime. No destructor can race running workers.
// OpenThread callbacks call only ingress()/publish_network()/status(); they do
// not touch GPIO, I2C or the session. All ingress calls hold the OpenThread lock.
class MotionRuntime {
public:
    MotionRuntime(std::uint64_t boot,runtime::Configuration configuration)
        : boot_(boot),config_(configuration),inbox_(boot),ingress_(inbox_) {}
    bool start(TaskHandle_t radio_policy_worker);
    bool start(runtime::WakeSink sink,bool install_local_buttons);
    runtime::Ingress& ingress() { return ingress_; }
    void publish_network(std::uint64_t now);
    void publish_network(std::uint64_t now,std::uint32_t acknowledged_revocation);
    void notify_request();
    bool status(char* output,std::size_t size,std::uint64_t now);
    bool awake_required() const { return awake_.load(std::memory_order_acquire); }
    bool io_qualified() const { return io_ready_.load(std::memory_order_acquire) && !signals_.failed(); }
    std::uint32_t revocation_generation() const { return signals_.generation(); }
    void revoke(); // Any task; never calls inbox/ingress or I/O.
    void transport_fault(); // Permanent asynchronous delivery/ownership failure.
    void local_stop_from_isr();
    void source_irq_from_isr();
    bool source_status(smart_blinds::pd::Observation& out,std::uint64_t now) const;
    bool parked_off(std::uint64_t now) const;
    // Trusted LOCAL workflow only, never exposed as a CoAP resource. A full
    // recovery workflow must supply independent physical evidence.
    bool reference(const PhysicalReference& reference);
private:
    struct SensorRequest {
        std::uint32_t sequence=0,activity=0,revocation=0;
        bool enabled=false;
        std::uint32_t source_event=0;
    };
    struct SensorPark {
        SensorRequest request{};
        std::uint32_t epoch=0;
        std::uint64_t parked_us=0;
        bool clean=false,continuity=false;
    };
    struct PhysicalOff { std::uint64_t sampled_us=0;bool off=false;std::uint32_t activity=0,revocation=0; };
    struct SourceStatus { smart_blinds::pd::Observation observation{};std::uint32_t event=0,bus_epoch=0; };
    runtime::Power power_snapshot();
    bool sensor_closed() const;
    static void control_entry(void* context);
    static void power_entry(void* context);
    void control();
    void power();
    bool wake_radio();
    static void button_irq(void* context);
    static void source_irq(void* context);
    const std::uint64_t boot_;
    const runtime::Configuration config_;
    MotionSession::Inbox inbox_;
    runtime::Ingress ingress_;
    TaskHandle_t control_task_=nullptr,power_task_=nullptr,radio_task_=nullptr;
    QueueHandle_t network_queue_=nullptr,status_queue_=nullptr,reference_queue_=nullptr;
    QueueHandle_t source_queue_=nullptr;
    std::atomic<std::uint32_t> source_event_{0},source_ack_{0};
    std::atomic<bool> source_busy_{false};
    QueueHandle_t sensor_request_queue_=nullptr,sensor_park_queue_=nullptr,physical_off_queue_=nullptr;
    power::continuity::BusEpoch bus_epoch_;
    PowerMailboxGate selector_gate_,mailbox_gate_;
    power::continuity::SensorAccess sensors_{selector_gate_,bus_epoch_};
    std::atomic<bool> awake_{false},io_ready_{false},sampling_{false};
    std::atomic<std::uint32_t> sensing_window_{0};
    runtime::Revocation signals_;
    runtime::WakeSink wake_sink_{};
    bool local_buttons_=false;
};
} // namespace blinds::c6
