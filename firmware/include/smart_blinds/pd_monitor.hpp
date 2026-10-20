#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace smart_blinds::pd {
// ST UM2650 Rev2: no NVM, PDO, command, soft/hard reset or RX-buffer writes.
class Bus {
public:
    virtual ~Bus()=default;
    virtual bool read(std::uint8_t pointer,std::uint8_t* data,std::size_t size)=0;
    virtual bool alert_mask(std::uint8_t value)=0; // ONLY register 0x0C.
    virtual std::uint64_t now_ms() const=0;
};
struct FactoryRecord {
    std::uint64_t board=0,qualification=0,boot=0;
    bool exact_nvm_verified=false,above_5v_gate_verified=false,shared_bus_verified=false;
    bool req_src_current_zero=false,source_path_verified=false;
    std::uint8_t device_id=0;
    std::array<std::uint32_t,3> live_pdos{};
    bool valid() const {
        return board && qualification && boot && exact_nvm_verified && above_5v_gate_verified &&
            shared_bus_verified && req_src_current_zero && source_path_verified &&
            (device_id==0x21 || device_id==0x25) &&
            (live_pdos[0]&0xCC0FFFFFU)==0x04019096 &&
            (live_pdos[1]&0xC00FFFFFU)==0x0002D0FA &&
            (live_pdos[2]&0xC00FFFFFU)==0x0004B0FA;
    }
};
enum class Error { none,bus,clock,timeout,identity,mask,fault,policy,exhausted,uninitialized };
enum class State { unavailable,detached,negotiating,unapproved,ready,fault };
struct Observation {
    std::uint64_t started_ms=0,finished_ms=0;
    std::uint32_t serial=0,epoch=0,rdo=0;
    std::uint16_t current_ma=0;
    std::uint8_t device_id=0,pe=0,port=0,monitor=0;
    // OR of all read-clear evidence in this operation; never overwritten by a later clear read.
    std::array<std::uint8_t,5> history{}; // 0D,0F,12,14,16.
    State state=State::unavailable;
    Error error=Error::uninitialized;
};
class Monitor {
public:
    static constexpr std::uint8_t address=0x28;
    static constexpr std::uint64_t max_age_ms=250,operation_ms=100,settle_ms=500;
    Monitor(Bus& bus,FactoryRecord record):bus_(bus),record_(record) {}
    // Board supply must have been continuously valid >=30 ms before call.
    // Reads clear-on-read fault evidence BEFORE the sole allowlisted write.
    Observation initialize(std::uint64_t supply_stable_since_ms,std::optional<std::uint8_t> prior_mask={});
    std::uint8_t configured_mask() const { return mask_; }
    Observation poll();
    void invalidate(Error error);
    bool current(const Observation& value,std::uint64_t now) const;
    bool authority(const Observation& value,std::uint64_t now) const {
        return current(value,now) && value.state==State::ready && value.current_ma==2500;
    }
    Error first_error() const { return first_; }
    const Observation& last() const { return last_; } // owner only.
private:
    struct Image {
        std::array<std::uint8_t,12> status{}; // 0B..16; includes all documented history.
        std::array<std::uint8_t,12> pdos{};
        std::uint32_t rdo=0;
        std::uint8_t id=0,count=0,pe=0;
    };
    bool read(std::uint8_t,std::uint8_t*,std::size_t);
    bool budget();
    bool history(Image&,Observation&);
    bool image(Image&,Observation&);
    bool exact_policy(const Image&) const;
    bool bump();
    Observation finish(Observation);
    Bus& bus_;
    const FactoryRecord record_;
    Observation last_{};
    std::optional<Observation> first_failure_;
    std::uint64_t started_=0,last_clock_=0,quiet_since_=0;
    std::uint32_t serial_=0,epoch_=1;
    std::uint8_t mask_=0;
    bool initialized_=false,quiet_=false;
    Error first_=Error::none;
};
bool discontinuity(const Observation& previous,const Observation& current);
const char* name(State state);
} // namespace smart_blinds::pd
