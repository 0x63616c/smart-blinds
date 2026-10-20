// Localhost protocol fixture only. This is not the C6/OpenThread network stack.
#include "common.hpp"
#include "smart_blinds/radio_window.hpp"
#include "smart_blinds/clock_protocol.hpp"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <thread>
#include <memory>

namespace sbthread {
class Peer {
public:
    coap_context_t* context = nullptr;
    std::array<std::uint8_t, 32> key{};
    std::string identity;
    coap_dtls_spsk_t setup{};
    std::atomic<bool> stop{false};
    std::atomic<std::uint64_t> clock_ms{0};
    std::atomic<unsigned> requests{0};
    std::atomic<std::int64_t> clock_shift_us{0};
    std::thread worker;
    std::uint64_t boot;
    smart_blinds::RadioWindow window;
    smart_blinds::ClockProbes probes;
    explicit Peer(std::uint64_t nonce) : boot(nonce), window(nonce), probes(nonce) { window.attached(true, 0); }
    std::uint64_t now_us() const {
        const auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        return static_cast<std::uint64_t>(now + clock_shift_us.load());
    }
    ~Peer() {
        stop = true;
        if (worker.joinable()) worker.join();
        if (context) coap_free_context(context);
        OPENSSL_cleanse(key.data(), key.size());
    }
    static const coap_bin_const_t* validate_identity(coap_bin_const_t* id, coap_session_t*, void* arg) {
        auto& self = *static_cast<Peer*>(arg);
        if (id->length != self.identity.size() || CRYPTO_memcmp(id->s, self.identity.data(), id->length) != 0) return nullptr;
        return &self.setup.psk_info.key;
    }
    static void handler(coap_resource_t* resource, coap_session_t* session, const coap_pdu_t* request,
                        const coap_string_t*, coap_pdu_t* response) {
        auto& self = *static_cast<Peer*>(coap_resource_get_userdata(resource));
        if (!cipher_matches(session) || coap_pdu_get_type(request) != COAP_MESSAGE_CON) {
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_UNAUTHORIZED);
            return;
        }
        ++self.requests;
        const auto now = self.clock_ms.load();
        self.window.advance(now);
        std::size_t size = 0;
        const std::uint8_t* body = nullptr;
        coap_get_data(request, &size, &body);
        const auto received_us = self.now_us();
        self.probes.advance(received_us, self.window.rx_on_when_idle());
        const auto* path = coap_resource_get_uri_path(resource);
        const std::string name(reinterpret_cast<const char*>(path->s), path->length);
        char reply[512];
        if (name == "v1/status") {
            if (size) { coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return; }
            std::snprintf(reply, sizeof(reply), "{\"boot\":\"%016llx\",\"last_wake\":\"%016llx\",\"awake\":%s,\"motor_enabled\":false,\"clock_qualified\":false}",
                static_cast<unsigned long long>(self.boot), static_cast<unsigned long long>(self.window.last_sequence()),
                self.window.rx_on_when_idle() ? "true" : "false");
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CONTENT);
        } else if (name == "v1/wake") {
            if (size != 16 || !self.window.wake(read64(body), read64(body + 8), now)) {
                coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST);
                return;
            }
            std::snprintf(reply, sizeof(reply), "{\"awake_ms\":10000,\"motor_enabled\":false}");
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CHANGED);
        } else if (name == "v1/clock") {
            if (size != 16 || !self.probes.begin(read64(body), read64(body + 8), received_us,
                                                 self.window.rx_on_when_idle())) {
                coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return;
            }
            const auto sent_us = self.now_us();
            if (!self.probes.sent(sent_us, self.window.rx_on_when_idle())) {
                coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return;
            }
            std::snprintf(reply, sizeof(reply), "{\"boot\":\"%016llx\",\"probe\":\"%016llx\",\"received_us\":\"%016llx\",\"sent_us\":\"%016llx\"}",
                static_cast<unsigned long long>(self.boot), static_cast<unsigned long long>(self.probes.sequence()),
                static_cast<unsigned long long>(received_us), static_cast<unsigned long long>(sent_us));
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CONTENT);
        } else if (name == "v1/qualify") {
            if (size != 32 || !self.probes.assess(read64(body), read64(body + 8), read64(body + 16),
                read64(body + 24), received_us, self.window.rx_on_when_idle())) {
                coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return;
            }
            if (!smart_blinds::clock_readiness_json(reply, sizeof(reply), self.boot, self.probes,
                    self.now_us(), self.window.rx_on_when_idle())) return;
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CHANGED);
        } else {
            if (size) { coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return; }
            if (!smart_blinds::clock_readiness_json(reply, sizeof(reply), self.boot, self.probes,
                    self.now_us(), self.window.rx_on_when_idle())) return;
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CONTENT);
        }
        const std::uint8_t json = COAP_MEDIATYPE_APPLICATION_JSON;
        coap_add_option(response, COAP_OPTION_CONTENT_FORMAT, 1, &json);
        coap_add_data(response, std::strlen(reply), reinterpret_cast<const std::uint8_t*>(reply));
    }
    bool start(std::uint16_t port, const char* id, const std::uint8_t* psk) {
        if (!port || !boot || !identity_valid(id) || !psk) return false;
        identity = id;
        std::copy_n(psk, 32, key.begin());
        context = coap_new_context(nullptr);
        if (!context) return false;
        setup.version = COAP_DTLS_SPSK_SETUP_VERSION;
        setup.psk_info.key = {key.size(), key.data()};
        setup.validate_id_call_back = validate_identity;
        setup.id_call_back_arg = this;
        if (!coap_context_set_psk2(context, &setup)) return false;
        coap_address_t local;
        address(local, "::1", port);
        if (!coap_new_endpoint(context, &local, COAP_PROTO_DTLS)) return false;
        for (const char* name : {"v1/status", "v1/wake", "v1/clock", "v1/qualify", "v1/readiness"}) {
            auto* resource = coap_resource_init(coap_make_str_const(name), 0);
            if (!resource) return false;
            coap_resource_set_userdata(resource, this);
            const bool get = std::strcmp(name, "v1/status") == 0 || std::strcmp(name, "v1/readiness") == 0;
            coap_register_handler(resource, get ? COAP_REQUEST_GET : COAP_REQUEST_POST, handler);
            coap_add_resource(context, resource);
        }
        worker = std::thread([this] { while (!stop) if (coap_io_process(context, 10) < 0) break; });
        return true;
    }
};
}
extern "C" {
void* sb_test_peer_new(std::uint16_t port, const char* identity, const std::uint8_t* key, std::uint64_t boot) {
    sbthread::initialize();
    try {
        auto peer = std::make_unique<sbthread::Peer>(boot);
        if (!peer->start(port, identity, key)) return nullptr;
        return peer.release();
    } catch (...) { return nullptr; }
}
void sb_test_peer_free(void* handle) { delete static_cast<sbthread::Peer*>(handle); }
void sb_test_peer_clock(void* handle, std::uint64_t ms) { static_cast<sbthread::Peer*>(handle)->clock_ms = ms; }
void sb_test_peer_shift_clock(void* handle, std::int64_t us) { static_cast<sbthread::Peer*>(handle)->clock_shift_us += us; }
unsigned sb_test_peer_requests(void* handle) { return static_cast<sbthread::Peer*>(handle)->requests; }
}
