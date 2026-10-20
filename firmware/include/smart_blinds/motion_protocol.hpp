#pragma once
#include "smart_blinds/clock_bounds.hpp"
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>

namespace blinds::wire {
// Fixed 80-byte network-order frame. No heap, JSON number conversion, extension
// fields, implicit retry or session resumption exists on this control boundary.
enum class Kind : std::uint8_t { prepare=1, commit=2, lease=3, stop=4 };
struct Request {
    Kind kind=Kind::stop;
    std::uint32_t calibration=0;
    std::uint64_t boot=0, message=0, command=0, probe=0, sent_us=0, start_us=0;
    std::int64_t origin_um=0,target_um=0;
    std::uint32_t speed_um_s=0,acceleration_um_s2=0;
};
constexpr std::size_t frame_size=80;
inline std::uint64_t read_be(const std::uint8_t* p,unsigned bytes) {
    std::uint64_t n=0; for(unsigned i=0;i<bytes;++i) n=(n<<8)|p[i]; return n;
}
inline std::int64_t signed_be(const std::uint8_t* p) {
    const auto n=read_be(p,8);
    if(n<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return static_cast<std::int64_t>(n);
    return -1-static_cast<std::int64_t>(~n); // Avoid implementation-defined unsigned narrowing.
}
inline std::optional<Request> decode(const std::uint8_t* p,std::size_t size) {
    if(!p || size!=frame_size || p[0]!=1 || p[1]<1 || p[1]>4 || p[2] || p[3]) return {};
    Request r;
    r.kind=static_cast<Kind>(p[1]); r.calibration=static_cast<std::uint32_t>(read_be(p+4,4));
    r.boot=read_be(p+8,8); r.message=read_be(p+16,8); r.command=read_be(p+24,8); r.probe=read_be(p+32,8);
    r.sent_us=read_be(p+40,8); r.start_us=read_be(p+48,8); r.origin_um=signed_be(p+56); r.target_um=signed_be(p+64);
    r.speed_um_s=static_cast<std::uint32_t>(read_be(p+72,4)); r.acceleration_um_s2=static_cast<std::uint32_t>(read_be(p+76,4));
    constexpr auto max_time=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
    if(!r.boot || !r.message || !r.command || !r.sent_us || r.sent_us>max_time) return {};
    if(r.kind==Kind::prepare) {
        if(!r.calibration || !r.probe || !r.start_us || r.start_us>max_time ||
           r.origin_um < -1000000000LL || r.origin_um>1000000000LL || r.target_um < -1000000000LL || r.target_um>1000000000LL ||
           !r.speed_um_s || r.speed_um_s>30000 || !r.acceleration_um_s2 || r.acceleration_um_s2>60000) return {};
    } else {
        if(r.start_us || r.origin_um || r.target_um || r.speed_um_s || r.acceleration_um_s2) return {};
        if(r.kind!=Kind::stop && (!r.calibration || !r.probe)) return {};
    }
    return r;
}
inline std::array<std::uint8_t,frame_size> encode(const Request& r) {
    std::array<std::uint8_t,frame_size> p{}; p[0]=1; p[1]=static_cast<std::uint8_t>(r.kind);
    const auto put=[&](std::size_t at,std::uint64_t n,unsigned bytes) {
        for(unsigned i=0;i<bytes;++i) p[at+bytes-1-i]=static_cast<std::uint8_t>(n>>(8*i));
    };
    put(4,r.calibration,4); put(8,r.boot,8); put(16,r.message,8); put(24,r.command,8); put(32,r.probe,8);
    put(40,r.sent_us,8); put(48,r.start_us,8); put(56,static_cast<std::uint64_t>(r.origin_um),8);
    put(64,static_cast<std::uint64_t>(r.target_um),8); put(72,r.speed_um_s,4); put(76,r.acceleration_um_s2,4);
    return p;
}
struct Envelope {
    Request request{};
    std::uint64_t connection=0, received_us=0;
    bool authenticated=false; // Set by DTLS adapter, never read from request bytes.
};
// Single producer (DTLS resource owner), single consumer (control task).
// STOP bypasses backlog only after authenticated boot/session/sequence checks.
// Queue overflow is explicit rejection; no dynamic allocation or dropped-oldest.
template<std::size_t Capacity=4> class Inbox {
    static_assert(Capacity>0 && Capacity<16);
public:
    explicit Inbox(std::uint64_t boot) : boot_(boot) {}
    // Producer-only. A generation is allocated locally after a completed DTLS
    // handshake; it is never taken from the packet. Never reuse a generation.
    bool connected(std::uint64_t generation) {
        if(!generation || generation>UINT32_MAX || generation<=last_connection_) return false;
        last_connection_=generation; connection_.store(static_cast<std::uint32_t>(generation),std::memory_order_release); return true;
    }
    void disconnected() { connection_.store(0,std::memory_order_release); }
    std::uint64_t connection() const { return connection_.load(std::memory_order_acquire); }
    bool push(const Envelope& e) {
        const auto bytes=encode(e.request);
        if(!decode(bytes.data(),bytes.size())) return false;
        if(!boot_ || e.request.boot!=boot_ || !e.authenticated || !e.connection ||
           e.connection!=connection() || e.request.message<=last_message_) return false;
        if(e.request.kind==Kind::stop) {
            last_message_=e.request.message;
            stop_.store(true,std::memory_order_release); return true;
        }
        const auto head=head_.load(std::memory_order_relaxed), next=(head+1)%slots;
        if(next==tail_.load(std::memory_order_acquire)) return false;
        queue_[head]=e; last_message_=e.request.message; head_.store(next,std::memory_order_release); return true;
    }
    // Read-only observation; unlike stop_pending(), this never consumes STOP.
    bool pending() const {
        return stop_.load(std::memory_order_acquire) ||
            head_.load(std::memory_order_acquire)!=tail_.load(std::memory_order_acquire);
    }
    // Sole producer only; includes queued STOP and discarded ordinary records.
    std::uint64_t received_message() const { return last_message_; }
    bool stop_pending() { return stop_.exchange(false,std::memory_order_acq_rel); }
    std::optional<Envelope> pop() {
        const auto tail=tail_.load(std::memory_order_relaxed);
        if(tail==head_.load(std::memory_order_acquire)) return {};
        const auto value=queue_[tail]; tail_.store((tail+1)%slots,std::memory_order_release); return value;
    }
    // Consumer-only: captures a boundary. Frames published afterward remain
    // queued and still face connection/message/command checks in the session.
    void discard() { tail_.store(head_.load(std::memory_order_acquire),std::memory_order_release); }
private:
    static constexpr std::size_t slots=Capacity+1;
    const std::uint64_t boot_;
    std::uint64_t last_connection_=0,last_message_=0; // Producer only.
    std::atomic<std::uint32_t> connection_{0};
    static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
    std::array<Envelope,slots> queue_{};
    std::atomic<std::size_t> head_{0},tail_{0};
    std::atomic<bool> stop_{false};
};
// A fixed offset preserves monotonic trajectory time across requalification.
// New bounds must continue to contain this chosen mapping within the allowed
// uncertainty. Excess drift stops motion instead of stepping the control clock.
class Projection {
public:
    struct Time { std::uint64_t host_us=0,error_us=0; };
    bool bind(const smart_blinds::ClockBounds& b,std::uint64_t now) {
        if(!b.device_qualified(now)) return false;
        offset_=midpoint(b); bound_=true; return true;
    }
    std::optional<Time> at(const smart_blinds::ClockBounds& b,std::uint64_t now) const {
        if(!bound_ || !b.device_qualified(now) || now>max_time) return {};
        const auto error=b.device_error(now);
        const auto center=midpoint(b);
        // Both offsets may be near int64 extremes; compare without subtraction.
        const auto distance=center>=offset_ ? static_cast<std::uint64_t>(center)-static_cast<std::uint64_t>(offset_) :
            static_cast<std::uint64_t>(offset_)-static_cast<std::uint64_t>(center);
        if(!error || distance>10000 || *error>10000-distance) return {};
        const auto host=shift(now,-1);
        if(!host) return {};
        return Time{*host,*error+distance};
    }
    std::optional<std::uint64_t> local(std::uint64_t host) const { return bound_ ? shift(host,1) : std::nullopt; }
    void invalidate() { bound_=false; }
private:
    static constexpr auto max_time=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
    static std::int64_t midpoint(const smart_blinds::ClockBounds& b) { return b.lower_us()+(b.upper_us()-b.lower_us())/2; }
    std::optional<std::uint64_t> shift(std::uint64_t value,int direction) const {
        if(value>max_time) return {};
        const bool subtract=(direction>0 ? offset_<0 : offset_>=0);
        const auto magnitude=offset_<0 ? static_cast<std::uint64_t>(-(offset_+1))+1 : static_cast<std::uint64_t>(offset_);
        if(magnitude>max_time) return {};
        if(subtract) { if(value<magnitude) return {}; return value-magnitude; }
        if(value>max_time-magnitude) return {};
        return value+magnitude;
    }
    std::int64_t offset_=0;
    bool bound_=false;
};
} // namespace blinds::wire
