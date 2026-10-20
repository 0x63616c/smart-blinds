// Separate motion-binding target. Empty physical records keep the shipped image OFF.
#include "smart_blinds/wifi_motion.hpp"
#include "c6_motion_runtime.hpp"
#include "smart_blinds/board_io.hpp"
#include <atomic>
#include <cerrno>
#include <cstring>
#include <string_view>
#include <unistd.h>
#include <sys/select.h>
#include "coap_config.h" // Vendor port's address/config ABI must precede public headers.
#include "coap3/coap.h"
#include "mbedtls/platform_util.h"
#include "mbedtls/ssl.h"
#include "bootloader_random.h"
#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_flash_encrypt.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_partition.h"
#include "esp_pm.h"
#include "esp_random.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "esp_vfs_eventfd.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "soc/gpio_struct.h"
#include "soc/gpio_sig_map.h"

namespace {
using P=blinds::io::Pins;
using Policy=smart_blinds::wifi::Policy;
constexpr char tag[]="wifi_motion_unqualified";
constexpr int off_pins[]={P::request_n,P::charge_n,P::encoder_n,P::wdi,P::in1,P::in2};
constexpr bool off_levels[]={true,true,true,true,false,false};
smart_blinds::wifi::Credentials credentials;
blinds::c6::MotionRuntime* motion=nullptr;
smart_blinds::wifi::MotionBinding* app=nullptr;
bool qualified_boot=false;
bool pending_network_event();
class MotionPort final : public smart_blinds::wifi::MotionPort {
public:
    blinds::runtime::Ingress& ingress() override { return motion->ingress(); }
    void publish(std::uint64_t now) override {
        // Capture BEFORE checking the SDK queue boundary. A callback that races
        // after this point advances the epoch, invalidating this publication.
        const auto acknowledged=motion->revocation_generation();
        if(pending_network_event()) motion->ingress().radio(false,false);
        motion->publish_network(now,acknowledged);
    }
    void notify() override { motion->notify_request(); }
    void revoke() override { motion->revoke(); }
    bool qualified() const override { return motion->io_qualified(); }
    bool parked(std::uint64_t now) const override { return motion->parked_off(now); }
    bool status(char* out,std::size_t size,std::uint64_t now) override { return motion->status(out,size,now); }
    bool handoff(char* out,std::size_t size,std::uint64_t nonce) override { return motion->handoff(out,size,nonce); }
    bool telemetry(char* out,std::size_t size,std::uint64_t nonce,std::uint64_t) override {
        return motion->telemetry(out,size,nonce);
    }
};
coap_context_t* context=nullptr;
coap_session_t* peer=nullptr;
coap_dtls_spsk_t psk_setup{};
std::uint64_t peer_owner=0;
unsigned authentication_failures=0;
int wake_fd=-1;
QueueHandle_t events=nullptr;
TaskHandle_t wake_relay_task=nullptr;
std::atomic<bool> event_fault{false};
std::atomic<std::uint32_t> network_revision{0};
std::uint32_t processed_network_revision=0;
esp_pm_lock_handle_t no_sleep=nullptr,max_speed=nullptr;
bool held=false,wifi_started=false;
wifi_ps_type_t power_save=WIFI_PS_MIN_MODEM;
enum class EventKind { started, ready, lost };
struct Event { EventKind kind; std::uint32_t address; std::uint32_t revision; };
std::uint64_t now_us() { return static_cast<std::uint64_t>(esp_timer_get_time()); }
std::uint64_t now_ms() { return now_us()/1000; }

bool signal() {
    const std::uint64_t one=1;
    const bool ok=write(wake_fd,&one,sizeof(one))==static_cast<ssize_t>(sizeof(one));
    if(!ok) event_fault.store(true,std::memory_order_release);
    return ok;
}
bool notify_relay(void*) {
    if(!wake_relay_task || event_fault.load(std::memory_order_acquire)) return false;
    if(xPortInIsrContext()) {
        BaseType_t wake=pdFALSE;
        vTaskNotifyGiveFromISR(wake_relay_task,&wake);
        if(wake) portYIELD_FROM_ISR();
        return true;
    }
    return xTaskNotifyGive(wake_relay_task)==pdPASS;
}
void wake_relay(void*) {
    for(;;) {
        ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
        // IDF eventfd task writes acquire a recursive VFS lock. Keep that
        // possible wait outside the control owner and outside button ISRs.
        if(!signal()) motion->transport_fault();
    }
}
void button_irq(void*) { motion->local_stop_from_isr(); } // OFF-only branch; qualified owner installs its own ISR.
void network_event(void*,esp_event_base_t base,std::int32_t id,void* data) {
    Event e{};
    if(base==WIFI_EVENT && id==WIFI_EVENT_STA_START) e.kind=EventKind::started;
    else if(base==IP_EVENT && id==IP_EVENT_STA_GOT_IP) {
        e.kind=EventKind::ready;e.address=static_cast<ip_event_got_ip_t*>(data)->ip_info.ip.addr;
    } else if((base==WIFI_EVENT && id==WIFI_EVENT_STA_DISCONNECTED) ||
              (base==IP_EVENT && id==IP_EVENT_STA_LOST_IP)) e.kind=EventKind::lost;
    else return;
    e.revision=network_revision.fetch_add(1,std::memory_order_acq_rel)+1;
    // Publish pending-event status BEFORE revocation. The owner must never
    // acknowledge a new epoch while still observing the prior SDK queue state.
    motion->revoke(); // Atomic only: the SDK task never owns ingress or GPIO.
    if(!e.revision) event_fault.store(true,std::memory_order_release);
    if(xQueueSend(events,&e,0)!=pdPASS) event_fault.store(true,std::memory_order_release);
    signal();
}

bool load_credentials() {
    nvs_handle_t nvs;
    if(nvs_open("sb_wifi",NVS_READONLY,&nvs)!=ESP_OK) return false;
    std::uint8_t approved=0;
    auto sn=credentials.ssid.size(),pn=credentials.password.size(),in=credentials.identity.size(),kn=credentials.key.size();
    const bool read=nvs_get_u8(nvs,"approved",&approved)==ESP_OK &&
        nvs_get_u8(nvs,"board",&credentials.board_profile)==ESP_OK &&
        nvs_get_str(nvs,"ssid",credentials.ssid.data(),&sn)==ESP_OK &&
        nvs_get_str(nvs,"password",credentials.password.data(),&pn)==ESP_OK &&
        nvs_get_str(nvs,"identity",credentials.identity.data(),&in)==ESP_OK &&
        nvs_get_blob(nvs,"psk",credentials.key.data(),&kn)==ESP_OK && kn==credentials.key.size();
    nvs_close(nvs);
    credentials.approved=approved==1;
    const bool valid=read && credentials.valid();
    if(!valid) mbedtls_platform_zeroize(&credentials,sizeof(credentials));
    return valid;
}

bool verify_off() {
    for(std::size_t i=0;i<sizeof(off_pins)/sizeof(off_pins[0]);++i) {
        const auto pin=off_pins[i];
        if(GPIO.func_out_sel_cfg[pin].out_sel!=SIG_GPIO_OUT_IDX ||
           GPIO.func_out_sel_cfg[pin].out_inv_sel || GPIO.func_out_sel_cfg[pin].oen_inv_sel ||
           !(GPIO.enable.val&(1U<<pin)) ||
           gpio_get_level(static_cast<gpio_num_t>(pin))!=off_levels[i]) return false;
    }
    return true;
}
void initialize_off_pads() {
    // Explicit board selection required before entry. Preload OFF before enable.
    // There is intentionally no gpio_hold_dis, PWM, I2C or WDI pulse code.
    for(std::size_t i=0;i<sizeof(off_pins)/sizeof(off_pins[0]);++i) {
        const auto pin=static_cast<gpio_num_t>(off_pins[i]);
        ESP_ERROR_CHECK(gpio_set_level(pin,off_levels[i]));
        ESP_ERROR_CHECK(gpio_set_direction(pin,GPIO_MODE_INPUT_OUTPUT));
        ESP_ERROR_CHECK(gpio_set_pull_mode(pin,GPIO_FLOATING));
        ESP_ERROR_CHECK(gpio_sleep_sel_dis(pin));
        ESP_ERROR_CHECK(gpio_hold_en(pin));
    }
    if(!verify_off()) abort();
    gpio_config_t buttons{};
    buttons.pin_bit_mask=(1ULL<<P::up)|(1ULL<<P::down);
    buttons.mode=GPIO_MODE_INPUT;
    buttons.intr_type=GPIO_INTR_ANYEDGE;
    ESP_ERROR_CHECK(gpio_config(&buttons)); // External board pullups.
    ESP_ERROR_CHECK(gpio_install_isr_service(0));
    for(const auto number : {P::up,P::down}) {
        const auto pin=static_cast<gpio_num_t>(number);
        ESP_ERROR_CHECK(gpio_sleep_sel_dis(pin)); // Keep button input/wakeup during automatic sleep.
        ESP_ERROR_CHECK(gpio_isr_handler_add(pin,button_irq,nullptr));
        ESP_ERROR_CHECK(gpio_wakeup_enable(pin,GPIO_INTR_LOW_LEVEL));
    }
    ESP_ERROR_CHECK(esp_sleep_enable_gpio_wakeup());
}

bool apply_power() {
    if((!qualified_boot && !verify_off()) || event_fault.load(std::memory_order_acquire)) {
        motion->revoke(); app->policy.fail();
    }
    const bool awake=app->policy.awake();
    if(!awake) app->invalidate(now_us());
    if(awake && !held) {
        if(esp_pm_lock_acquire(no_sleep)!=ESP_OK) { app->policy.fail();return false; }
        if(esp_pm_lock_acquire(max_speed)!=ESP_OK) {
            esp_pm_lock_release(no_sleep);app->policy.fail();return false;
        }
        held=true;
    }
    const auto desired=awake ? WIFI_PS_NONE : WIFI_PS_MIN_MODEM;
    if(desired!=power_save) {
        if(esp_wifi_set_ps(desired)!=ESP_OK) { app->policy.fail();return false; }
        power_save=desired;
    }
    if(!awake && held) {
        if(esp_pm_lock_release(max_speed)!=ESP_OK || esp_pm_lock_release(no_sleep)!=ESP_OK) {
            app->policy.fail();return false;
        }
        held=false;
    }
    return app->policy.state()!=Policy::State::fault;
}

bool cipher_matches(coap_session_t* session) {
    coap_tls_library_t kind=COAP_TLS_LIBRARY_NOTLS;
    auto* ssl=static_cast<mbedtls_ssl_context*>(coap_session_get_tls(session,&kind));
    if(kind!=COAP_TLS_LIBRARY_MBEDTLS || !ssl) return false;
    const auto* version=mbedtls_ssl_get_version(ssl);
    const auto* cipher=mbedtls_ssl_get_ciphersuite(ssl);
    return version && cipher && std::strcmp(version,"DTLSv1.2")==0 &&
        std::strcmp(cipher,"TLS-PSK-WITH-AES-128-CCM-8")==0;
}
bool pending_network_event() {
    return event_fault.load(std::memory_order_acquire) ||
        network_revision.load(std::memory_order_acquire)!=processed_network_revision;
}
const coap_bin_const_t* identity(coap_bin_const_t* offered,coap_session_t*,void*) {
    const auto n=std::strlen(credentials.identity.data());
    if(!offered || offered->length!=n) return nullptr;
    unsigned difference=0;
    for(std::size_t i=0;i<n;++i) difference|=offered->s[i]^static_cast<unsigned char>(credentials.identity[i]);
    return difference ? nullptr : &psk_setup.psk_info.key;
}
int secure_event(coap_session_t* session,coap_event_t event) {
    if(event==COAP_EVENT_DTLS_CONNECTED) {
        if(peer || pending_network_event() || !cipher_matches(session) ||
           !(peer_owner=app->connected(now_us()))) {
            coap_session_disconnected(session,COAP_NACK_NOT_DELIVERABLE);return 0;
        }
        peer=session;app->invalidate(now_us());
    } else if((event==COAP_EVENT_DTLS_CLOSED || event==COAP_EVENT_DTLS_ERROR ||
               event==COAP_EVENT_DTLS_RENEGOTIATE) && session==peer) {
        app->disconnected(peer_owner,now_us());peer=nullptr;peer_owner=0;app->invalidate(now_us());
    }
    if(event==COAP_EVENT_DTLS_RENEGOTIATE)
        coap_session_disconnected(session,COAP_NACK_NOT_DELIVERABLE);
    if(event==COAP_EVENT_DTLS_ERROR && ++authentication_failures>=5) app->policy.fail();
    return 0;
}
void resource(coap_resource_t* r,coap_session_t* session,const coap_pdu_t* request,
              const coap_string_t*,coap_pdu_t* response) {
    const auto received=now_us();
    // An SDK callback can run while select/libcoap is processing a datagram.
    // Revoke permission immediately, before the owner drains its event queue.
    if(pending_network_event()) {
        app->invalidate(now_us());
        coap_pdu_set_code(response,COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);return;
    }
    if(session!=peer || !peer_owner || !cipher_matches(session) ||
       coap_pdu_get_type(request)!=COAP_MESSAGE_CON) {
        coap_pdu_set_code(response,COAP_RESPONSE_CODE_UNAUTHORIZED);return;
    }
    std::size_t size=0;const std::uint8_t* body=nullptr;
    coap_get_data(request,&size,&body);
    const auto* uri=coap_resource_get_uri_path(r);
    const std::string_view path(reinterpret_cast<const char*>(uri->s),uri->length);
    auto reply=app->request(peer_owner,path,static_cast<std::uint8_t>(coap_pdu_get_code(request)),
                           body,size,received,now_us());
    if(!apply_power()) { coap_pdu_set_code(response,COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);return; }
    coap_pdu_set_code(response,static_cast<coap_pdu_code_t>(reply.code));
    if(reply.body[0]) {
        const std::uint8_t json=COAP_MEDIATYPE_APPLICATION_JSON;
        coap_add_option(response,COAP_OPTION_CONTENT_FORMAT,1,&json);
        coap_add_data(response,std::strlen(reply.body.data()),reinterpret_cast<const std::uint8_t*>(reply.body.data()));
    }
}
bool start_server(std::uint32_t address) {
    context=coap_new_context(nullptr);
    if(!context) return false;
    coap_context_set_max_idle_sessions(context,1);
    coap_context_set_max_handshake_sessions(context,1);
    coap_context_set_session_timeout(context,60); // No idle keepalive/poll loop.
    coap_register_event_handler(context,secure_event);
    psk_setup.version=COAP_DTLS_SPSK_SETUP_VERSION;
    psk_setup.psk_info.key={credentials.key.size(),credentials.key.data()};
    psk_setup.validate_id_call_back=identity;
    if(!coap_context_set_psk2(context,&psk_setup)) return false;
    coap_address_t bind{};coap_address_init(&bind);
    bind.size=sizeof(bind.addr.sin);bind.addr.sin.sin_family=AF_INET;
    bind.addr.sin.sin_addr.s_addr=address;bind.addr.sin.sin_port=htons(5684);
    if(!coap_new_endpoint(context,&bind,COAP_PROTO_DTLS)) return false;
    for(const char* name : {"v1/status","v1/wake","v1/clock","v1/qualify","v1/readiness","v1/motion","v1/motion-status","v1/telemetry","v1/handoff"}) {
        auto* r=coap_resource_init(coap_make_str_const(name),0);
        if(!r) return false;
        const bool get=std::strcmp(name,"v1/status")==0 || std::strcmp(name,"v1/readiness")==0 ||
                       std::strcmp(name,"v1/motion-status")==0;
        coap_register_handler(r,get ? COAP_REQUEST_GET : COAP_REQUEST_POST,resource);
        coap_add_resource(context,r);
    }
    return true;
}
void stop_server() {
    // Clear local authority before freeing sessions/callbacks. No reconnect.
    if(peer_owner) app->disconnected(peer_owner,now_us());
    peer=nullptr;peer_owner=0;app->invalidate(now_us());
    if(context) {coap_free_context(context);context=nullptr;}
}
} // namespace

extern "C" void app_main() {
#if CONFIG_SB_WIFI_PLAINTEXT_DISPOSABLE_BENCH
    // Null security config explicitly disables encryption for disposable bench
    // data. nvs_flash_init() is avoided: it can generate keys when configured.
    const auto storage=nvs_flash_secure_init(nullptr);
#else
    if(!esp_flash_encryption_enabled()) {
        ESP_LOGW(tag,"Storage is not provisioned; network and GPIO remain untouched");return;
    }
    const auto* keys=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_NVS_KEYS,"nvs_keys");
    nvs_sec_cfg_t security{};
    if(!keys || !keys->encrypted || nvs_flash_read_security_cfg(keys,&security)!=ESP_OK) {
        mbedtls_platform_zeroize(&security,sizeof(security));
        ESP_LOGW(tag,"NVS keys absent or invalid; evaluation remains stopped");return;
    }
    const auto storage=nvs_flash_secure_init(&security);
    mbedtls_platform_zeroize(&security,sizeof(security));
#endif
    if(storage!=ESP_OK) { ESP_LOGW(tag,"NVS unavailable; no erase or key generation");return; }
    if(!load_credentials()) {
        ESP_LOGW(tag,"Unconfigured: network and board GPIO remain untouched");return;
    }
    bootloader_random_enable();
    std::uint64_t boot=0;while(!boot) esp_fill_random(&boot,sizeof(boot));
    bootloader_random_disable();
    // No persisted record loader or path from radio approval to these records.
    // Even the bench compile flag cannot fill measured data or establish reference.
    const blinds::runtime::Configuration records{};
    static blinds::c6::MotionRuntime runtime(boot,records);motion=&runtime;
    static MotionPort port;
    static smart_blinds::wifi::MotionBinding binding(boot,port,records.clock);app=&binding;
#ifdef CONFIG_BLINDS_BENCH_MOTION
    qualified_boot=records.valid(boot);
#endif
    if(!app->policy.configure(credentials,now_ms())) abort();
    const esp_vfs_eventfd_config_t efds{.max_fds=1};
    ESP_ERROR_CHECK(esp_vfs_eventfd_register(&efds));
    wake_fd=eventfd(0,EFD_SUPPORT_ISR);
    events=xQueueCreate(16,sizeof(Event));
    if(wake_fd<0 || !events) abort();

    esp_pm_config_t pm{};pm.max_freq_mhz=CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ;pm.min_freq_mhz=40;pm.light_sleep_enable=true;
    ESP_ERROR_CHECK(esp_pm_configure(&pm));
    ESP_ERROR_CHECK(esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP,0,"wifi_eval",&no_sleep));
    ESP_ERROR_CHECK(esp_pm_lock_create(ESP_PM_CPU_FREQ_MAX,0,"wifi_clock",&max_speed));
    if(xTaskCreate(wake_relay,"motion_wake",3072,nullptr,4,&wake_relay_task)!=pdPASS) abort();
    if(!motion->start({nullptr,notify_relay},qualified_boot)) abort();
    // Mutually exclusive boot ownership. Never release or inherit evaluation holds.
    if(!qualified_boot) initialize_off_pads();
    ESP_ERROR_CHECK(esp_event_loop_create_default());ESP_ERROR_CHECK(esp_netif_init());
    if(!esp_netif_create_default_wifi_sta()) abort();
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,network_event,nullptr));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,ESP_EVENT_ANY_ID,network_event,nullptr));
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM)); // No SDK credential writes.
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    wifi_config_t wifi{};
    std::memcpy(wifi.sta.ssid,credentials.ssid.data(),std::strlen(credentials.ssid.data()));
    std::memcpy(wifi.sta.password,credentials.password.data(),std::strlen(credentials.password.data()));
    wifi.sta.threshold.authmode=WIFI_AUTH_WPA2_PSK;
    wifi.sta.pmf_cfg.capable=true;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&wifi));
    mbedtls_platform_zeroize(&wifi,sizeof(wifi));
    mbedtls_platform_zeroize(credentials.password.data(),credentials.password.size());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_MIN_MODEM));
    coap_startup();coap_set_log_level(COAP_LOG_EMERG);coap_dtls_set_log_level(COAP_LOG_EMERG);
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGW(tag,"Wi-Fi motion target: empty qualification, no charge/OTA/commissioning path");
    for(;;) {
        const auto prior=app->policy.state();
        Event event{};
        while(xQueueReceive(events,&event,0)==pdPASS) {
            if(event.kind==EventKind::started) wifi_started=true;
            else if(event.kind==EventKind::lost) { app->policy.lost_network(now_ms());stop_server(); }
            else if(app->policy.network_ready(event.address,now_ms())) {
                if(!context && !start_server(event.address)) app->policy.fail();
            } else { stop_server();esp_wifi_disconnect(); }
            processed_network_revision=event.revision;
        }
        app->tick(now_us());
        if(prior==Policy::State::associating && app->policy.state()==Policy::State::offline) esp_wifi_disconnect();
        if(wifi_started && app->policy.begin_association(now_ms()) && esp_wifi_connect()!=ESP_OK) app->policy.lost_network(now_ms());
        app->policy.buttons((!qualified_boot || motion->io_qualified()) && (!gpio_get_level(static_cast<gpio_num_t>(P::up)) ||
                            !gpio_get_level(static_cast<gpio_num_t>(P::down))),now_ms());
        app->sync(now_us());
        if(!apply_power()) {
            stop_server();esp_wifi_stop();
            ESP_LOGE(tag,"Transport fault latched; control owner retains independent OFF responsibility");return;
        }
        fd_set reads;FD_ZERO(&reads);FD_SET(wake_fd,&reads);
        const auto timeout=app->policy.wait_ms(now_ms());
        int result;
        if(context) result=coap_io_process_with_fds(context,timeout,wake_fd+1,&reads,nullptr,nullptr);
        else {
            timeval wait{static_cast<long>(timeout/1000),static_cast<long>((timeout%1000)*1000)};
            result=select(wake_fd+1,&reads,nullptr,nullptr,&wait);
        }
        if(result<0 && errno!=EINTR) app->policy.fail();
        if(result>=0 && FD_ISSET(wake_fd,&reads)) {
            std::uint64_t count=0;if(read(wake_fd,&count,sizeof(count))!=static_cast<ssize_t>(sizeof(count))) app->policy.fail();
        }
    }
}
