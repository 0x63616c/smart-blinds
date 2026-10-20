#pragma once
#include "smart_blinds/clock_bounds.hpp"
#include <cinttypes>
#include <cstdio>

namespace smart_blinds {
// Shared by the motor-disabled C6 target and the host protocol fixture. These
// diagnostics never become an authorization or configure any hardware.
inline bool clock_readiness_json(char* output, std::size_t size, std::uint64_t boot,
                                 ClockProbes& probes, std::uint64_t sampled_us, bool awake) {
    probes.advance(sampled_us, awake);
    const auto error = probes.bounds() ? probes.bounds()->device_error(sampled_us) : std::nullopt;
    char error_text[24] = "null";
    if (error) std::snprintf(error_text, sizeof(error_text), "%" PRIu64, *error);
    const auto written = std::snprintf(output, size,
        "{\"boot\":\"%016" PRIx64 "\",\"last_probe\":\"%016" PRIx64
        "\",\"sampled_us\":\"%016" PRIx64 "\",\"awake\":%s,\"clock_assessed\":%s,"
        "\"clock_model_validated\":%s,\"clock_qualified\":%s,\"clock_error_us\":%s,"
        "\"motor_ready\":false,\"reason\":\"hardware_unconfigured\"}",
        boot, probes.sequence(), sampled_us, awake ? "true" : "false", error ? "true" : "false",
        probes.model_validated() ? "true" : "false", probes.qualified(sampled_us) ? "true" : "false", error_text);
    return written > 0 && static_cast<std::size_t>(written) < size;
}
}
