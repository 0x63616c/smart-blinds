#pragma once
#include "smart_blinds/wifi_policy.hpp"
#include "smart_blinds/clock_protocol.hpp"
#include "smart_blinds/motion_runtime.hpp"
#include <string_view>

namespace smart_blinds::wifi {
// The transport owner implements this with copied worker publications. No
// packet, credential or radio state can manufacture physical qualification.
class MotionPort {
public:
    virtual ~MotionPort()=default;
    virtual blinds::runtime::Ingress& ingress()=0;
    virtual void publish(std::uint64_t now)=0;
    virtual void notify()=0;
    virtual void revoke()=0;
    virtual bool qualified() const=0;
    virtual bool parked(std::uint64_t now) const=0;
    virtual bool status(char*,std::size_t,std::uint64_t now)=0;
};
class MotionBinding {
public:
    struct Reply { std::uint8_t code=163; std::array<char,768> body{}; };
    MotionBinding(std::uint64_t boot,MotionPort& port,ClockModel clock={})
        : policy(boot),probes(boot,clock),port_(port) {}
    Policy policy;
    ClockProbes probes;
    std::uint64_t connected(std::uint64_t now) {
        const auto owner=policy.connected(now/1000);
        if(!owner || !port_.ingress().connected()) {
            policy.fail(); invalidate(now); return 0;
        }
        owner_=owner; connection_=port_.ingress().snapshot(now).connection;
        probes.invalidate(); sync(now); return owner_;
    }
    void disconnected(std::uint64_t owner,std::uint64_t now) {
        if(!owner || owner!=owner_) return;
        port_.revoke(); // Visible to control before the copied network update.
        policy.disconnected(owner,now/1000);
        port_.ingress().disconnected(); owner_=connection_=0;
        invalidate(now);
    }
    void invalidate(std::uint64_t now) {
        probes.invalidate(); port_.ingress().clear_clock(); sync(now);
    }
    void sync(std::uint64_t now) {
        port_.ingress().radio(policy.attached(),policy.awake());
        port_.publish(now);
    }
    // A parked publication must be fresh AND bound to every queued request.
    // The runtime's activity fence excludes an old idle observation.
    void tick(std::uint64_t now) {
        const auto before=policy.state();
        policy.advance(now/1000);
        if(policy.state()==Policy::State::operation && port_.parked(now))
            policy.settled_off(owner_,true,now/1000);
        if(before!=policy.state()) {
            if(!policy.awake()) probes.invalidate();
            sync(now);
        }
    }
    Reply request(std::uint64_t owner,std::string_view path,std::uint8_t method,
                  const std::uint8_t* body,std::size_t size,std::uint64_t received,std::uint64_t sent) {
        Reply r;
        tick(received);
        if(sent<received || !owner || owner!=owner_ || owner!=policy.owner() ||
           !policy.attached() || port_.ingress().snapshot(received).connection!=connection_) {
            r.code=129; return r;
        }
        const bool get=path=="v1/status" || path=="v1/readiness" || path=="v1/motion-status";
        const bool known=get || path=="v1/wake" || path=="v1/clock" || path=="v1/qualify" || path=="v1/motion";
        if(!known) { r.code=132; return r; }
        if(method!=(get ? 1 : 2)) { r.code=133; return r; }
        if((size && !body) || (get && size)) { r.code=128; return r; }
        probes.advance(received,policy.awake());
        if(path=="v1/status") {
            std::snprintf(r.body.data(),r.body.size(),
                "{\"boot\":\"%016" PRIx64 "\",\"last_wake\":\"%016" PRIx64
                "\",\"awake\":%s,\"io_qualified\":%s,\"clock_qualified\":%s}",
                policy.boot(),policy.last_wake(),policy.awake() ? "true":"false",
                port_.qualified() ? "true":"false",probes.qualified(received) ? "true":"false");
            r.code=69;
        } else if(path=="v1/motion-status") {
            r.code=port_.status(r.body.data(),r.body.size(),sent) ? 69 : 163;
        } else if(path=="v1/motion") {
            const auto request=blinds::wire::decode(body,size);
            if(!request) { r.code=128; return r; }
            const bool stop=request->kind==blinds::wire::Kind::stop;
            if(!stop && (!port_.qualified() || !policy.awake())) return r;
            // Reserve awake ownership BEFORE publishing work. Failed queueing
            // cannot release it using a prior idle publication.
            if(!stop && policy.state()!=Policy::State::operation &&
               !policy.begin_operation(owner,received/1000)) return r;
            sync(received);
            const auto result=port_.ingress().submit(body,size,true,received);
            port_.notify();
            if(result!=blinds::runtime::Ingress::Result::queued) { r.code=128; return r; }
            r.code=68; std::snprintf(r.body.data(),r.body.size(),"{\"queued\":true}");
        } else if(path=="v1/wake") {
            if(size!=16 || !policy.wake(owner,read(body),read(body+8),received/1000)) { r.code=128; return r; }
            sync(received);
            std::snprintf(r.body.data(),r.body.size(),"{\"awake_ms\":10000,\"io_qualified\":%s}",
                port_.qualified() ? "true":"false"); r.code=68;
        } else if(path=="v1/clock") {
            if(size!=16 || !probes.begin(read(body),read(body+8),received,policy.awake()) ||
               !probes.sent(sent,policy.awake())) { r.code=128; return r; }
            std::snprintf(r.body.data(),r.body.size(),
                "{\"boot\":\"%016" PRIx64 "\",\"probe\":\"%016" PRIx64
                "\",\"received_us\":\"%016" PRIx64 "\",\"sent_us\":\"%016" PRIx64 "\"}",
                policy.boot(),probes.sequence(),received,sent); r.code=69;
        } else {
            if(path=="v1/qualify") {
                const bool assessed=size==32 &&
                    probes.assess(read(body),read(body+8),read(body+16),read(body+24),received,policy.awake());
                // A diagnostic unvalidated model never enters the motion ingress.
                const bool qualified=assessed &&
                    port_.ingress().qualify(probes.sequence(),probes.bounds(),received);
                if(!qualified) port_.ingress().clear_clock();
                sync(received);
                if(!assessed) { r.code=128; return r; }
                r.code=68;
            } else r.code=69;
            if(!clock_readiness_json(r.body.data(),r.body.size(),policy.boot(),probes,sent,policy.awake())) r.code=160;
        }
        return r;
    }
private:
    static std::uint64_t read(const std::uint8_t* p) { return blinds::wire::read_be(p,8); }
    MotionPort& port_;
    std::uint64_t owner_=0,connection_=0;
};
} // namespace smart_blinds::wifi
