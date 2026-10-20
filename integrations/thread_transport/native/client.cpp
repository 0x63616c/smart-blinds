#include "common.hpp"
#include <algorithm>
#include <memory>

namespace sbthread {
class Client {
public:
    std::mutex mutex;
    coap_context_t* context = nullptr;
    coap_session_t* session = nullptr;
    std::array<std::uint8_t, 32> key{};
    std::string identity;
    coap_dtls_cpsk_t setup{};
    std::array<std::uint8_t, 8> token{};
    std::size_t token_size = 0;
    std::array<std::uint8_t, 1024> body{};
    std::size_t body_size = 0;
    int code = 0;
    bool done = false, failed = false, authenticated = false;
    unsigned handshakes = 0;
    const bool motion_capable;
    explicit Client(bool motion=false) : motion_capable(motion) {}

    ~Client() { disconnect(); OPENSSL_cleanse(key.data(), key.size()); }
    void disconnect() {
        if (session) { coap_session_release(session); session = nullptr; }
        if (context) { coap_free_context(context); context = nullptr; }
        authenticated = false;
    }
    bool connect(const char* host, std::uint16_t port, const char* id, const std::uint8_t* psk) {
        coap_address_t remote;
        if (!host || !port || !identity_valid(id) || !psk || !address(remote, host, port)) return false;
        bool nonzero = false;
        for (unsigned i = 0; i < 32; ++i) nonzero |= psk[i] != 0;
        if (!nonzero) return false;
        identity = id;
        std::copy_n(psk, 32, key.begin());
        context = coap_new_context(nullptr);
        if (!context) return false;
        coap_register_response_handler(context, response);
        coap_register_nack_handler(context, nack);
        coap_register_event_handler(context, event);
        setup.version = COAP_DTLS_CPSK_SETUP_VERSION;
        setup.psk_info.identity = {identity.size(), reinterpret_cast<const std::uint8_t*>(identity.data())};
        setup.psk_info.key = {key.size(), key.data()};
        session = coap_new_client_session_psk2(context, nullptr, &remote, COAP_PROTO_DTLS, &setup);
        if (!session) return false;
        coap_session_set_app_data(session, this);
        coap_session_set_max_retransmit(session, 1);
        return true;
    }
    static Client* owner(coap_session_t* s) { return static_cast<Client*>(coap_session_get_app_data(s)); }
    static coap_response_t response(coap_session_t* s, const coap_pdu_t*, const coap_pdu_t* incoming, coap_mid_t) {
        auto* self = owner(s);
        if (!self || !self->authenticated || !cipher_matches(s)) return COAP_RESPONSE_FAIL;
        const auto t = coap_pdu_get_token(incoming);
        if (t.length != self->token_size || CRYPTO_memcmp(t.s, self->token.data(), t.length) != 0) return COAP_RESPONSE_FAIL;
        std::size_t size = 0;
        const std::uint8_t* data = nullptr;
        coap_get_data(incoming, &size, &data);
        if (size > self->body.size()) { self->failed = true; return COAP_RESPONSE_FAIL; }
        self->body_size = size;
        if (size) std::copy_n(data, size, self->body.begin());
        self->code = coap_pdu_get_code(incoming);
        self->done = true;
        return COAP_RESPONSE_OK;
    }
    static void nack(coap_session_t* s, const coap_pdu_t*, coap_nack_reason_t, coap_mid_t) {
        if (auto* self = owner(s)) self->failed = true;
    }
    static int event(coap_session_t* s, coap_event_t event) {
        auto* self = owner(s);
        if (!self) return 0;
        if (event == COAP_EVENT_DTLS_CONNECTED) {
            self->authenticated = cipher_matches(s);
            if (self->authenticated) ++self->handshakes;
            else self->failed = true;
        } else if (event == COAP_EVENT_DTLS_ERROR || event == COAP_EVENT_DTLS_CLOSED) {
            self->authenticated = false;
            self->failed = true;
        }
        return 0;
    }
    int request(int kind, const std::uint8_t* payload, std::size_t size, unsigned timeout,
                std::uint8_t* output, std::size_t capacity, std::size_t* received, int* response_code) {
        if (!session || !context) return -4;
        if ((kind < 0 || kind > (motion_capable ? 6 : 4)) || size > (motion_capable ? 80U : 32U) || (size && !payload) ||
            !output || !received || !response_code || timeout < 1 || timeout > 5000) return -1;
        done = failed = false;
        body_size = 0;
        auto* pdu = coap_new_pdu(COAP_MESSAGE_CON, (kind == 0 || kind == 4 || kind == 6) ? COAP_REQUEST_CODE_GET : COAP_REQUEST_CODE_POST, session);
        if (!pdu) return -2;
        token_size = token.size();
        coap_session_new_token(session, &token_size, token.data());
        constexpr const char* resources[] = {"status", "wake", "clock", "qualify", "readiness", "motion", "motion-status"};
        const char* resource = resources[kind];
        if (!coap_add_token(pdu, token_size, token.data()) ||
            !coap_add_option(pdu, COAP_OPTION_URI_PATH, 2, reinterpret_cast<const std::uint8_t*>("v1")) ||
            !coap_add_option(pdu, COAP_OPTION_URI_PATH, std::strlen(resource), reinterpret_cast<const std::uint8_t*>(resource)) ||
            (size && !coap_add_data(pdu, size, payload))) { coap_delete_pdu(pdu); return -2; }
        if (coap_send(session, pdu) == COAP_INVALID_MID) { disconnect(); return -2; }
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout);
        while (!done && !failed && std::chrono::steady_clock::now() < deadline) {
            if (coap_io_process(context, 10) < 0) { failed = true; break; }
        }
        if (!done || failed) { disconnect(); return -2; } // Destroy queues; never replay after reconnect.
        if (body_size > capacity) { disconnect(); return -3; }
        std::copy_n(body.data(), body_size, output);
        *received = body_size;
        *response_code = code;
        return 0;
    }
};
}
extern "C" {
void* sb_client_new(const char* host, std::uint16_t port, const char* identity, const std::uint8_t* key) {
    sbthread::initialize();
    try {
        auto client = std::make_unique<sbthread::Client>();
        if (!client->connect(host, port, identity, key)) return nullptr;
        return client.release();
    } catch (...) { return nullptr; }
}
void* sb_motion_client_new(const char* host, std::uint16_t port, const char* identity, const std::uint8_t* key) {
    sbthread::initialize();
    try {
        auto client = std::make_unique<sbthread::Client>(true);
        if (!client->connect(host, port, identity, key)) return nullptr;
        return client.release();
    } catch (...) { return nullptr; }
}
void sb_client_free(void* handle) { delete static_cast<sbthread::Client*>(handle); }
int sb_client_request(void* handle, int kind, const std::uint8_t* payload, std::size_t size,
                      unsigned timeout, std::uint8_t* output, std::size_t capacity,
                      std::size_t* received, int* code) {
    if (!handle) return -1;
    auto& client = *static_cast<sbthread::Client*>(handle);
    std::lock_guard<std::mutex> guard(client.mutex);
    return client.request(kind, payload, size, timeout, output, capacity, received, code);
}
unsigned sb_client_handshakes(void* handle) {
    if (!handle) return 0;
    auto& client = *static_cast<sbthread::Client*>(handle);
    std::lock_guard<std::mutex> guard(client.mutex);
    return client.handshakes;
}
}
