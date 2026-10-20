// Motor-disabled OpenThread/DTLS evaluation target. No motor GPIO driver exists here.
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "bootloader_random.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_openthread.h"
#include "esp_openthread_lock.h"
#include "esp_openthread_netif_glue.h"
#include "esp_pm.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_vfs_eventfd.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "openthread/coap.h"
#include "openthread/coap_secure.h"
#include "openthread/dataset.h"
#include "openthread/ip6.h"
#include "openthread/link.h"
#include "openthread/thread.h"
#include "smart_blinds/radio_window.hpp"

namespace {
constexpr char tag[] = "thread_motor_disabled";
constexpr std::uint32_t poll_ms = 1000;
constexpr std::uint16_t secure_port = 5684;
std::uint64_t boot_id = 0;
smart_blinds::RadioWindow window(0);
otInstance* instance = nullptr;
TaskHandle_t expiry_task = nullptr;
TimerHandle_t expiry_timer = nullptr;
esp_pm_lock_handle_t awake_lock = nullptr;
esp_pm_lock_handle_t speed_lock = nullptr;
bool locks_held = false;
// The read-only loader retains credentials for the stack lifetime. No credential
// generation, NVS writes, commissioning endpoint or secret logging is present.
struct Credentials { std::uint8_t psk[32]{}; char identity[33]{}; } credentials;

std::uint64_t now_ms() { return static_cast<std::uint64_t>(esp_timer_get_time() / 1000); }
std::uint64_t read_u64(const std::uint8_t* data) {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | data[i];
    return value;
}

bool load_credentials() {
    nvs_handle_t handle;
    if (nvs_open("sb_thread", NVS_READONLY, &handle) != ESP_OK) return false;
    std::uint8_t approved = 0;
    std::size_t psk_size = sizeof(credentials.psk), identity_size = sizeof(credentials.identity);
    const bool valid = nvs_get_u8(handle, "approved", &approved) == ESP_OK && approved == 1 &&
        nvs_get_blob(handle, "psk", credentials.psk, &psk_size) == ESP_OK && psk_size == 32 &&
        nvs_get_str(handle, "identity", credentials.identity, &identity_size) == ESP_OK &&
        identity_size >= 2 && identity_size <= sizeof(credentials.identity);
    nvs_close(handle);
    if (!valid) return false;
    bool nonzero = false;
    for (auto byte : credentials.psk) nonzero |= byte != 0;
    for (std::size_t i = 0; i + 1 < identity_size; ++i) {
        const char c = credentials.identity[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
    }
    return nonzero;
}

// OpenThread lock must already be held (also true inside its resource callbacks).
bool apply_radio_policy() {
    const bool awake = window.rx_on_when_idle();
    if (awake && !locks_held) {
        ESP_ERROR_CHECK(esp_pm_lock_acquire(awake_lock));
        ESP_ERROR_CHECK(esp_pm_lock_acquire(speed_lock));
        locks_held = true;
    }
    otLinkModeConfig mode{};
    mode.mRxOnWhenIdle = awake;
    mode.mDeviceType = false;  // Minimal end device, never a router.
    mode.mNetworkData = false;
    if (otThreadSetLinkMode(instance, mode) != OT_ERROR_NONE) {
        window.attached(false, now_ms());
        otThreadSetEnabled(instance, false);
        if (locks_held) {
            esp_pm_lock_release(speed_lock);
            esp_pm_lock_release(awake_lock);
            locks_held = false;
        }
        return false;
    }
    if (!awake && locks_held) {
        ESP_ERROR_CHECK(esp_pm_lock_release(speed_lock));
        ESP_ERROR_CHECK(esp_pm_lock_release(awake_lock));
        locks_held = false;
    }
    return true;
}

void respond(otMessage* request, const otMessageInfo* info, otCoapCode code, const char* payload) {
    otMessage* response = otCoapNewMessage(instance, nullptr);
    if (!response) return;
    otError result = otCoapMessageInitResponse(response, request, OT_COAP_TYPE_ACKNOWLEDGMENT, code);
    if (result == OT_ERROR_NONE && payload && *payload) {
        result = otCoapMessageAppendContentFormatOption(response, OT_COAP_OPTION_CONTENT_FORMAT_JSON);
        if (result == OT_ERROR_NONE) result = otCoapMessageSetPayloadMarker(response);
        if (result == OT_ERROR_NONE) result = otMessageAppend(response, payload, std::strlen(payload));
    }
    if (result == OT_ERROR_NONE) result = otCoapSecureSendResponse(instance, response, info);
    if (result != OT_ERROR_NONE) otMessageFree(response);
}

bool request_method(otMessage* request, const otMessageInfo* info, otCoapCode method) {
    if (!otCoapSecureIsConnected(instance)) return false;
    if (otCoapMessageGetType(request) != OT_COAP_TYPE_CONFIRMABLE) return false;
    if (otCoapMessageGetCode(request) != method) {
        respond(request, info, OT_COAP_CODE_METHOD_NOT_ALLOWED, nullptr);
        return false;
    }
    return true;
}

void status_handler(void*, otMessage* request, const otMessageInfo* info) {
    if (!request_method(request, info, OT_COAP_CODE_GET)) return;
    if (otMessageGetLength(request) != otMessageGetOffset(request)) {
        respond(request, info, OT_COAP_CODE_BAD_REQUEST, nullptr);
        return;
    }
    window.advance(now_ms());
    if (!apply_radio_policy()) {
        respond(request, info, OT_COAP_CODE_SERVICE_UNAVAILABLE, nullptr);
        return;
    }
    char body[192];
    std::snprintf(body, sizeof(body),
        "{\"boot\":\"%016" PRIx64 "\",\"last_wake\":\"%016" PRIx64
        "\",\"awake\":%s,\"motor_enabled\":false,\"clock_qualified\":false}",
        boot_id, window.last_sequence(), window.rx_on_when_idle() ? "true" : "false");
    respond(request, info, OT_COAP_CODE_CONTENT, body);
}

void wake_handler(void*, otMessage* request, const otMessageInfo* info) {
    if (!request_method(request, info, OT_COAP_CODE_POST)) return;
    std::uint8_t body[16];
    const auto offset = otMessageGetOffset(request);
    if (otMessageGetLength(request) - offset != sizeof(body) ||
        otMessageRead(request, offset, body, sizeof(body)) != sizeof(body) ||
        !window.wake(read_u64(body), read_u64(body + 8), now_ms())) {
        respond(request, info, OT_COAP_CODE_BAD_REQUEST, nullptr);
        return;
    }
    if (!apply_radio_policy() ||
        xTimerChangePeriod(expiry_timer, pdMS_TO_TICKS(smart_blinds::RadioWindow::awake_ms), 0) != pdPASS) {
        window.cancel(now_ms());
        apply_radio_policy();
        respond(request, info, OT_COAP_CODE_SERVICE_UNAVAILABLE, nullptr);
        return;
    }
    respond(request, info, OT_COAP_CODE_CHANGED, "{\"awake_ms\":10000,\"motor_enabled\":false}");
}

otCoapResource status_resource{"v1/status", status_handler, nullptr, nullptr};
otCoapResource wake_resource{"v1/wake", wake_handler, nullptr, nullptr};

void expired(TimerHandle_t) { xTaskNotifyGive(expiry_task); }
void expire_worker(void*) {
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (!esp_openthread_lock_acquire(pdMS_TO_TICKS(100))) {
            ESP_LOGE(tag, "Radio policy lock timed out; aborting evaluation image");
            abort();
        }
        window.advance(now_ms());
        apply_radio_policy();
        esp_openthread_lock_release();
    }
}
void changed(otChangedFlags flags, void*) {
    if (!(flags & OT_CHANGED_THREAD_ROLE)) return;
    const bool attached = otThreadGetDeviceRole(instance) == OT_DEVICE_ROLE_CHILD;
    window.attached(attached, now_ms());
    apply_radio_policy();
    ESP_LOGI(tag, "Thread child attached: %s; motor remains unavailable", attached ? "yes" : "no");
}
void attempts_exhausted(void*) {
    window.cancel(now_ms());
    apply_radio_policy();
    ESP_LOGW(tag, "DTLS attempt budget exhausted; service remains stopped until restart");
}
}  // namespace

extern "C" void app_main() {
    ESP_LOGW(tag, "RADIO EVALUATION ONLY: no motor, charger, encoder or watchdog GPIO configured");
    // Fail without erasing storage if NVS cannot initialize. No default network.
    ESP_ERROR_CHECK(nvs_flash_init());
    if (!load_credentials()) {
        ESP_LOGW(tag, "Unprovisioned: radio stack, Thread joining and DTLS service disabled");
        return;
    }
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());
    const esp_vfs_eventfd_config_t eventfds{.max_fds = 3};
    ESP_ERROR_CHECK(esp_vfs_eventfd_register(&eventfds));
    // Seed boot identity from the documented internal entropy source before
    // starting RF or any application ADC. Never persist or reuse a boot nonce.
    bootloader_random_enable();
    do { esp_fill_random(&boot_id, sizeof(boot_id)); } while (boot_id == 0);
    bootloader_random_disable();
    esp_pm_config_t power{};
    power.max_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ;
    power.min_freq_mhz = 40;
    power.light_sleep_enable = true;
    ESP_ERROR_CHECK(esp_pm_configure(&power));
    ESP_ERROR_CHECK(esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "radio_awake", &awake_lock));
    ESP_ERROR_CHECK(esp_pm_lock_create(ESP_PM_CPU_FREQ_MAX, 0, "radio_speed", &speed_lock));

    esp_openthread_config_t config{};
    config.netif_config = ESP_NETIF_DEFAULT_OPENTHREAD();
    config.platform_config.radio_config.radio_mode = RADIO_MODE_NATIVE;
    config.platform_config.host_config.host_connection_mode = HOST_CONNECTION_MODE_NONE;
    config.platform_config.port_config.storage_partition_name = "nvs";
    config.platform_config.port_config.netif_queue_size = 10;
    config.platform_config.port_config.task_queue_size = 10;
    ESP_ERROR_CHECK(esp_openthread_start(&config));
    instance = esp_openthread_get_instance();
    // Pinned IDF start() initializes the worker/netif only; it does not call
    // auto_start() or enable IPv6/Thread. Check that invariant before proceeding.
    if (!esp_openthread_lock_acquire(pdMS_TO_TICKS(1000))) abort();
    if (otIp6IsEnabled(instance) || otThreadGetDeviceRole(instance) != OT_DEVICE_ROLE_DISABLED) abort();
    if (!otDatasetIsCommissioned(instance)) {
        esp_openthread_lock_release();
        ESP_LOGW(tag, "Unprovisioned: Thread joining and DTLS service disabled");
        return;
    }
    window = smart_blinds::RadioWindow(boot_id);
    if (xTaskCreate(expire_worker, "radio_expiry", 3072, nullptr, 4, &expiry_task) != pdPASS) abort();
    expiry_timer = xTimerCreate("awake_deadline", pdMS_TO_TICKS(10000), pdFALSE, nullptr, expired);
    if (!expiry_timer) abort();
    if (otLinkSetPollPeriod(instance, poll_ms) != OT_ERROR_NONE || !apply_radio_policy()) abort();
    otSetStateChangedCallback(instance, changed, nullptr);
    otCoapSecureSetPsk(instance, credentials.psk, sizeof(credentials.psk),
        reinterpret_cast<const std::uint8_t*>(credentials.identity), std::strlen(credentials.identity));
    if (otCoapSecureStartWithMaxConnAttempts(instance, secure_port, 5, attempts_exhausted, nullptr) != OT_ERROR_NONE) abort();
    otCoapSecureAddResource(instance, &status_resource);
    otCoapSecureAddResource(instance, &wake_resource);
    if (otIp6SetEnabled(instance, true) != OT_ERROR_NONE ||
        otThreadSetEnabled(instance, true) != OT_ERROR_NONE) abort();
    esp_openthread_lock_release();
    ESP_LOGI(tag, "Commissioned dataset loaded; SED/DTLS evaluation started with actuation disabled");
}
