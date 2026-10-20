#pragma once
#include "smart_blinds/wifi_policy.hpp"
#include "smart_blinds/clock_protocol.hpp"
#include <string_view>

namespace smart_blinds::wifi {
// Shared host/C6 application parser. This checkpoint has no motion authorization
// path: the motion resources explicitly reject, even with valid credentials.
class Evaluation {
public:
    struct Reply { std::uint8_t code=163; std::array<char,512> body{}; }; // 5.03
    explicit Evaluation(std::uint64_t boot) : policy(boot),probes(boot) {}
    Policy policy;
    ClockProbes probes; // Unvalidated physical clock model, intentionally permanent here.
    void invalidate() { probes.invalidate(); }
    Reply request(std::uint64_t owner,std::string_view path,std::uint8_t method,
                  const std::uint8_t* body,std::size_t size,std::uint64_t received_us,std::uint64_t sent_us) {
        Reply r;
        if(!policy.advance(received_us/1000) || sent_us<received_us ||
           !owner || owner!=policy.owner() || !policy.attached()) { r.code=129; return r; }
        const bool get=path=="v1/status" || path=="v1/readiness" || path=="v1/motion-status";
        const bool known=get || path=="v1/wake" || path=="v1/clock" || path=="v1/qualify" || path=="v1/motion";
        if(!known) { r.code=132; return r; }
        if(method!=(get ? 1 : 2)) { r.code=133; return r; }
        if((size && !body) || (get && size)) { r.code=128; return r; }
        const bool awake=policy.awake();
        probes.advance(received_us,awake);
        if(path=="v1/motion" || path=="v1/motion-status") return r; // No fake worker/power report.
        if(path=="v1/status") {
            std::snprintf(r.body.data(),r.body.size(),
                "{\"boot\":\"%016" PRIx64 "\",\"last_wake\":\"%016" PRIx64
                "\",\"awake\":%s,\"io_qualified\":false,\"clock_qualified\":false}",
                policy.boot(),policy.last_wake(),awake ? "true":"false");
            r.code=69;
        } else if(path=="v1/wake") {
            if(size!=16 || !policy.wake(owner,read(body),read(body+8),received_us/1000)) { r.code=128; return r; }
            std::snprintf(r.body.data(),r.body.size(),"{\"awake_ms\":10000,\"io_qualified\":false}"); r.code=68;
        } else if(path=="v1/clock") {
            if(size!=16 || !probes.begin(read(body),read(body+8),received_us,awake) || !probes.sent(sent_us,awake)) {
                r.code=128; return r;
            }
            std::snprintf(r.body.data(),r.body.size(),
                "{\"boot\":\"%016" PRIx64 "\",\"probe\":\"%016" PRIx64
                "\",\"received_us\":\"%016" PRIx64 "\",\"sent_us\":\"%016" PRIx64 "\"}",
                policy.boot(),probes.sequence(),received_us,sent_us); r.code=69;
        } else {
            if(path=="v1/qualify") {
                if(size!=32 || !probes.assess(read(body),read(body+8),read(body+16),read(body+24),received_us,awake)) {
                    r.code=128; return r;
                }
                r.code=68;
            } else r.code=69;
            if(!clock_readiness_json(r.body.data(),r.body.size(),policy.boot(),probes,sent_us,awake)) r.code=160;
        }
        return r;
    }
private:
    static std::uint64_t read(const std::uint8_t* p) {
        std::uint64_t value=0; for(unsigned i=0;i<8;++i) value=(value<<8)|p[i]; return value;
    }
};
} // namespace smart_blinds::wifi
