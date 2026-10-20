#pragma once
#include <coap3/coap.h>
#include <openssl/ssl.h>
#include <openssl/crypto.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <arpa/inet.h>

namespace sbthread {
inline void initialize() {
    static std::once_flag once;
    std::call_once(once, [] { coap_startup(); coap_set_log_level(COAP_LOG_CRIT); coap_dtls_set_log_level(COAP_LOG_CRIT); });
}
inline bool address(coap_address_t& result, const char* literal, std::uint16_t port) {
    coap_address_init(&result);
    if (inet_pton(AF_INET6, literal, &result.addr.sin6.sin6_addr) == 1) {
        result.size = sizeof(result.addr.sin6);
        result.addr.sin6.sin6_family = AF_INET6;
        result.addr.sin6.sin6_port = htons(port);
        return true;
    }
    if (inet_pton(AF_INET, literal, &result.addr.sin.sin_addr) == 1) {
        result.size = sizeof(result.addr.sin);
        result.addr.sin.sin_family = AF_INET;
        result.addr.sin.sin_port = htons(port);
        return true;
    }
    return false; // No potentially blocking DNS or implicit discovery.
}
inline bool identity_valid(const char* identity) {
    if (!identity) return false;
    const auto size = std::strlen(identity);
    if (size == 0 || size > 32) return false;
    for (std::size_t i = 0; i < size; ++i) {
        const auto c = identity[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
    }
    return true;
}
inline bool cipher_matches(coap_session_t* session) {
    coap_tls_library_t type = COAP_TLS_LIBRARY_NOTLS;
    auto* ssl = static_cast<SSL*>(coap_session_get_tls(session, &type));
    return type == COAP_TLS_LIBRARY_OPENSSL && ssl && SSL_is_init_finished(ssl) &&
        std::strcmp(SSL_get_cipher_name(ssl), "PSK-AES128-CCM8") == 0 &&
        SSL_version(ssl) == DTLS1_2_VERSION;
}
inline std::uint64_t read64(const std::uint8_t* data) {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value = (value << 8) | data[i];
    return value;
}
}
