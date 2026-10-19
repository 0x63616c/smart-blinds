#include "smart_blinds/control.hpp"
#include "smart_blinds/platform.hpp"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {
constexpr const char* tag = "blinds_bringup";
// No GPIO assumptions, radio credentials or pretend sensor readings. A separate,
// reviewed board driver must replace this before any output can be energized.
class UnconfiguredBoard final : public blinds::BoardPort {
public:
    bool configured() const override { return false; }
    blinds::Measurement read() override { return {}; }
    void disable_motor() override {} // actual board requires an external default-off pull
    bool set_fabric_velocity(double) override { return false; }
};
}

extern "C" void app_main() {
    UnconfiguredBoard board;
    blinds::ActuatorGate gate(board);
    blinds::Calibration no_calibration;
    // Zero boot ID and absent calibration make the core itself unconfigured too.
    blinds::Controller controller(no_calibration, {}, 0);
    ESP_LOGW(tag, "MOTOR DISABLED: no configured board, calibration or transport");
    ESP_LOGI(tag, "Portable core linked; native USB console available. No GPIO outputs configured.");
    while (true) {
        const auto now = static_cast<std::uint64_t>(esp_timer_get_time() / 1000);
        gate.apply(controller.tick(board.read(), now, 0));
        ESP_LOGI(tag, "uptime_ms=%llu state=%s reason=%s motor_enabled=false",
                 static_cast<unsigned long long>(now), blinds::name(controller.state()),
                 blinds::name(controller.reason()));
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
