#pragma once
#include "smart_blinds/radio_window.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <limits>

namespace smart_blinds::wifi {
struct Credentials {
    std::array<char,33> ssid{};
    std::array<char,64> password{};
    std::array<char,33> identity{};
    std::array<std::uint8_t,32> key{};
    bool approved=false;
    std::uint8_t board_profile=0;
    bool valid() const {
        const auto length=[](const auto& s) {
            return static_cast<std::size_t>(std::find(s.begin(),s.end(),'\0')-s.begin());
        };
        const auto sn=length(ssid),pn=length(password),in=length(identity);
        if(!approved || board_profile!=1 || !sn || sn>32 || pn<8 || pn>63 || !in || in>32) return false;
        if(std::none_of(key.begin(),key.end(),[](auto b){return b!=0;})) return false;
        for(std::size_t i=0;i<pn;++i)
            if(static_cast<unsigned char>(password[i])<32 || static_cast<unsigned char>(password[i])>126) return false;
        for(std::size_t i=0;i<in;++i) {
            const auto c=identity[i];
            if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='-' || c=='_')) return false;
        }
        return true;
    }
};

// One owner calls this policy. SDK callbacks enqueue events; they never mutate it.
// Network readiness is not motion readiness. No method creates I/O qualification.
class Policy {
public:
    enum class State { unconfigured, offline, associating, idle, awake, operation, fault };
    static constexpr std::uint64_t association_ms=8000,operation_ms=240000;
    explicit Policy(std::uint64_t boot) : boot_(boot),window_(boot) {}
    bool configure(const Credentials& config,std::uint64_t now) {
        if(state_!=State::unconfigured || !boot_ || !config.valid() || !advance(now)) return false;
        state_=State::offline; next_attempt_=now; return true;
    }
    bool begin_association(std::uint64_t now) {
        if(!advance(now) || state_!=State::offline || now<next_attempt_ || attempts_>=3) return false;
        ++attempts_; association_deadline_=now+association_ms; state_=State::associating; return true;
    }
    bool network_ready(std::uint64_t address,std::uint64_t now) {
        if(!advance(now) || !address) return false;
        if(attached_) {
            if(address!=address_) { lost_network(now); return false; }
            return true;
        }
        if(state_!=State::associating || now>=association_deadline_) return false;
        address_=address; attached_=true; state_=State::idle;
        window_.attached(true,now); return true;
    }
    void lost_network(std::uint64_t now) {
        if(!advance(now)) return;
        const bool owned_work=operation_ || window_.rx_on_when_idle();
        invalidate(now);
        if(owned_work) { fail(); return; }
        if(state_==State::unconfigured) return;
        // At most three attempts per boot. A stable association does not reset
        // this counter and permit an unbounded AP-failure scanning loop.
        state_=State::offline;
        next_attempt_=now+(attempts_<=1 ? 30000 : 120000);
    }
    std::uint64_t connected(std::uint64_t now) {
        if(!advance(now) || !attached_ || owner_ || generation_==UINT64_MAX) return 0;
        owner_=++generation_; return owner_;
    }
    void disconnected(std::uint64_t owner,std::uint64_t now) {
        if(!advance(now) || !owner || owner!=owner_) return;
        owner_=0; window_.cancel(now);
        if(operation_) fail();
    }
    bool wake(std::uint64_t owner,std::uint64_t boot,std::uint64_t sequence,std::uint64_t now) {
        return advance(now) && owner && owner==owner_ && window_.wake(boot,sequence,now);
    }
    // Future local control-worker integration only. The Wi-Fi evaluation app
    // never calls this and exposes no remote route to it.
    bool begin_operation(std::uint64_t owner,std::uint64_t now) {
        if(!advance(now) || !owner || owner!=owner_ || operation_ || !window_.rx_on_when_idle()) return false;
        operation_=true; operation_deadline_=now+operation_ms; return true;
    }
    bool settled_off(std::uint64_t owner,bool independently_confirmed,std::uint64_t now) {
        if(!advance(now) || !operation_ || owner!=owner_ || !independently_confirmed) return false;
        operation_=false; window_.cancel(now); return true;
    }
    void buttons(bool pressed,std::uint64_t now) {
        if(advance(now)) buttons_=pressed; // Wakes only; never emits an endpoint command.
    }
    bool advance(std::uint64_t now) {
        if(state_==State::fault) return false;
        if(now<last_now_ || now>UINT64_MAX-operation_ms-120000) { fail(); return false; }
        last_now_=now;
        if(!window_.advance(now)) { fail(); return false; }
        if(operation_ && now>=operation_deadline_) { fail(); return false; }
        if(state_==State::associating && now>=association_deadline_) {
            invalidate(now); state_=State::offline;
            next_attempt_=now+(attempts_<=1 ? 30000 : 120000);
        }
        return true;
    }
    void fail() { state_=State::fault; attached_=false; owner_=0; operation_=false; buttons_=false; }
    State state() const {
        if(state_==State::fault || state_==State::unconfigured || state_==State::offline ||
           state_==State::associating) return state_;
        return operation_ ? State::operation : (awake() ? State::awake : State::idle);
    }
    bool awake() const { return attached_ && (operation_ || buttons_ || window_.rx_on_when_idle()); }
    bool attached() const { return attached_; }
    std::uint64_t owner() const { return owner_; }
    std::uint64_t last_wake() const { return window_.last_sequence(); }
    std::uint64_t boot() const { return boot_; }
    unsigned attempts() const { return attempts_; }
    std::uint32_t wait_ms(std::uint64_t now) const {
        if(buttons_) return 20;
        if(awake()) return 10;
        std::uint64_t deadline=now+60000;
        if(state_==State::associating) deadline=association_deadline_;
        else if(state_==State::offline && attempts_<3) deadline=next_attempt_;
        return static_cast<std::uint32_t>(std::clamp<std::uint64_t>(deadline>now ? deadline-now : 1,1,60000));
    }
private:
    void invalidate(std::uint64_t now) {
        attached_=false; owner_=0; address_=0; window_.attached(false,now);
    }
    const std::uint64_t boot_;
    RadioWindow window_;
    State state_=State::unconfigured;
    std::uint64_t last_now_=0,next_attempt_=0,association_deadline_=0,operation_deadline_=0;
    std::uint64_t owner_=0,generation_=0,address_=0;
    unsigned attempts_=0;
    bool attached_=false,operation_=false,buttons_=false;
};
} // namespace smart_blinds::wifi
