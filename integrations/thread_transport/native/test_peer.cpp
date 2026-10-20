// Localhost protocol fixture only. This is not the C6/OpenThread network stack.
#include "common.hpp"
#include "smart_blinds/radio_window.hpp"
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
    std::thread worker;
    std::uint64_t boot;
    smart_blinds::RadioWindow window;
    explicit Peer(std::uint64_t nonce) : boot(nonce), window(nonce) { window.attached(true, 0); }
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
        char reply[192];
        if (coap_pdu_get_code(request) == COAP_REQUEST_CODE_GET) {
            if (size) { coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST); return; }
            std::snprintf(reply, sizeof(reply), "{\"boot\":\"%016llx\",\"last_wake\":\"%016llx\",\"awake\":%s,\"motor_enabled\":false,\"clock_qualified\":false}",
                static_cast<unsigned long long>(self.boot), static_cast<unsigned long long>(self.window.last_sequence()),
                self.window.rx_on_when_idle() ? "true" : "false");
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CONTENT);
        } else {
            if (size != 16 || !self.window.wake(read64(body), read64(body + 8), now)) {
                coap_pdu_set_code(response, COAP_RESPONSE_CODE_BAD_REQUEST);
                return;
            }
            std::snprintf(reply, sizeof(reply), "{\"awake_ms\":10000,\"motor_enabled\":false}");
            coap_pdu_set_code(response, COAP_RESPONSE_CODE_CHANGED);
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
        for (bool wake : {false, true}) {
            auto* resource = coap_resource_init(coap_make_str_const(wake ? "v1/wake" : "v1/status"), 0);
            if (!resource) return false;
            coap_resource_set_userdata(resource, this);
            coap_register_handler(resource, wake ? COAP_REQUEST_POST : COAP_REQUEST_GET, handler);
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
unsigned sb_test_peer_requests(void* handle) { return static_cast<sbthread::Peer*>(handle)->requests; }
}
