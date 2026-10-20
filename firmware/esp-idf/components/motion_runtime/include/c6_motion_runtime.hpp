#pragma once
#include "smart_blinds/motion_runtime.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <atomic>

namespace blinds::c6 {
// Lifetime is the application lifetime. No destructor can race running workers.
// OpenThread callbacks call only ingress()/publish_network()/status(); they do
// not touch GPIO, I2C or the session. All ingress calls hold the OpenThread lock.
class MotionRuntime {
public:
    MotionRuntime(std::uint64_t boot,runtime::Configuration configuration)
        : boot_(boot),config_(configuration),inbox_(boot),ingress_(inbox_) {}
    bool start(TaskHandle_t radio_policy_worker);
    runtime::Ingress& ingress() { return ingress_; }
    void publish_network(std::uint64_t now);
    void notify_request();
    bool status(char* output,std::size_t size,std::uint64_t now);
    bool awake_required() const { return awake_.load(std::memory_order_acquire); }
    bool io_qualified() const { return io_ready_.load(std::memory_order_acquire); }
    // Trusted LOCAL workflow only, never exposed as a CoAP resource. A full
    // recovery workflow must supply independent physical evidence.
    bool reference(const PhysicalReference& reference);
private:
    static void control_entry(void* context);
    static void power_entry(void* context);
    void control();
    void power();
    const std::uint64_t boot_;
    const runtime::Configuration config_;
    MotionSession::Inbox inbox_;
    runtime::Ingress ingress_;
    TaskHandle_t control_task_=nullptr,power_task_=nullptr,radio_task_=nullptr;
    QueueHandle_t network_queue_=nullptr,power_queue_=nullptr,status_queue_=nullptr,reference_queue_=nullptr;
    std::atomic<bool> awake_{false},io_ready_{false},sampling_{false};
    std::atomic<std::uint32_t> sensing_window_{0};
};
} // namespace blinds::c6
