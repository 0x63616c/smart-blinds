#pragma once
#include <array>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstdint>

namespace blinds::telemetry {
// Informational copies only. No type in this header is accepted by the control,
// power, clock, charging or reference admission interfaces.
struct Battery {
    std::uint64_t sample_us=0,pack=0;
    std::uint32_t epoch=0,serial=0;
    double soc=0;
    bool present=false,soc_present=false;
};
struct Charger {
    std::uint64_t sample_us=0;
    std::uint32_t epoch=0;
    bool present=false,input_present=false;
};
enum class Source { unavailable,detached,negotiating,unapproved,policy_observed,fault };
struct Pd {
    std::uint64_t sample_us=0;
    std::uint32_t bus_epoch=0,epoch=0,serial=0;
    std::uint16_t current_ma=0;
    Source state=Source::unavailable;
    bool present=false,attached=false;
};
enum class Fault { none,gauge,charger,lifecycle,runtime };
struct Samples {
    Battery battery{};
    Charger charger{};
    Pd pd{};
    std::uint32_t source_event=0;
    Fault fault=Fault::none;
    std::uint16_t fault_code=0;
};
inline const char* name(Source s) {
    switch(s) {
    case Source::detached:return "detached";
    case Source::negotiating:return "negotiating";
    case Source::unapproved:return "unapproved";
    case Source::policy_observed:return "policy_observed";
    case Source::fault:return "fault";
    default:return "unavailable";
    }
}
inline const char* name(Fault f) {
    switch(f) {
    case Fault::gauge:return "gauge";
    case Fault::charger:return "charger";
    case Fault::lifecycle:return "lifecycle";
    case Fault::runtime:return "runtime";
    default:return "none";
    }
}
// The caller checks the asynchronous lifecycle fences around its fixed-size
// queue copy. A retained sample is never restamped here or turned into ready.
inline bool json(char* out,std::size_t capacity,std::uint64_t boot,std::uint64_t nonce,
                 std::uint64_t now,const Samples& s,bool failed,bool pending,
                 std::uint32_t current_epoch) {
    if(!out || !capacity || !boot || !nonce) return false;
    const auto stamp=[](char* b,std::size_t n,bool present,std::uint64_t value) {
        if(present) std::snprintf(b,n,"\"%016" PRIx64 "\"",value);
        else std::snprintf(b,n,"null");
    };
    std::array<char,20> bs{},cs{},ps{},pack{};
    stamp(bs.data(),bs.size(),s.battery.present,s.battery.sample_us);
    stamp(cs.data(),cs.size(),s.charger.present,s.charger.sample_us);
    stamp(ps.data(),ps.size(),s.pd.present,s.pd.sample_us);
    stamp(pack.data(),pack.size(),s.battery.present,s.battery.pack);
    const bool bvalid=s.battery.present && !failed && s.fault==Fault::none &&
        s.battery.sample_us<=now && s.battery.epoch && s.battery.serial && s.battery.pack;
    const bool cvalid=s.charger.present && !failed && !pending && s.fault==Fault::none &&
        s.charger.sample_us<=now && s.charger.epoch==current_epoch;
    const bool pvalid=s.pd.present && !failed && !pending && s.fault==Fault::none &&
        s.pd.sample_us<=now && s.pd.bus_epoch==current_epoch;
    std::array<char,16> soc{};
    if(s.battery.soc_present && std::isfinite(s.battery.soc) && s.battery.soc>=0 && s.battery.soc<=100)
        std::snprintf(soc.data(),soc.size(),"%.3f",s.battery.soc);
    else std::snprintf(soc.data(),soc.size(),"null");
    const auto fault=s.fault==Fault::none && failed ? Fault::runtime:s.fault;
    const auto written=std::snprintf(out,capacity,
        "{\"schema\":1,\"boot\":\"%016" PRIx64 "\",\"nonce\":\"%016" PRIx64 "\",\"sent_us\":\"%016" PRIx64 "\","
        "\"battery\":{\"sample_us\":%s,\"bus_epoch\":%" PRIu32 ",\"serial\":%" PRIu32 ",\"pack\":%s,\"soc_pct\":%s,\"state\":\"%s\"},"
        "\"charger\":{\"sample_us\":%s,\"bus_epoch\":%" PRIu32 ",\"state\":\"%s\",\"input_present\":%s},"
        "\"pd\":{\"sample_us\":%s,\"bus_epoch\":%" PRIu32 ",\"epoch\":%" PRIu32 ",\"serial\":%" PRIu32 ",\"state\":\"%s\",\"current_ma\":%u,\"attached\":%s},"
        "\"pending\":%s,\"fault\":{\"kind\":\"%s\",\"code\":%u},\"charge_authorized\":false}",
        boot,nonce,now,bs.data(),s.battery.epoch,s.battery.serial,pack.data(),soc.data(),
        !s.battery.present ? "absent":bvalid ? "retained":"invalid",
        cs.data(),s.charger.epoch,cvalid ? "not_charging":"unknown",
        cvalid ? (s.charger.input_present ? "true":"false"):"null",
        ps.data(),s.pd.bus_epoch,s.pd.epoch,s.pd.serial,
        pvalid ? name(s.pd.state):"unavailable",unsigned(s.pd.current_ma),
        pvalid ? (s.pd.attached ? "true":"false"):"null",
        pending ? "true":"false",name(fault),unsigned(s.fault_code));
    return written>0 && static_cast<std::size_t>(written)<capacity;
}
} // namespace blinds::telemetry
