#pragma once
#include "smart_blinds/power_mailbox.hpp"
#include <algorithm>
#include <condition_variable>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <mutex>
#include <thread>
#include <type_traits>
#include <vector>
namespace gc=blinds::power::continuity;
namespace ch=smart_blinds::charger;
namespace sensor_fixture {
void check(bool ok,const char* why) { if(!ok) { std::cerr<<why<<'\n';std::exit(1); } }
struct Gate final:gc::MailboxGate {
    std::mutex mutex;
    static thread_local bool held;
    // Test-only scheduling seam in backend; no such callback in C6 backend.
    std::function<void()> before_lock,before_unlock;
    void enter() noexcept override { if(before_lock) before_lock();mutex.lock();check(!held,"recursive gate");held=true; }
    void leave() noexcept override { if(before_unlock) before_unlock();held=false;mutex.unlock(); }
};
thread_local bool Gate::held=false;
struct Time { std::int64_t us=1000000; };
gc::Context context() { return {99,17,2,7,10}; }
gc::Profile profile() {
    gc::Profile p;auto& pack=p.pack;
    pack.full_profile_verified=pack.timing_verified=pack.sensor_placement_verified=true;
    pack.verified_for_boot=99;pack.qualification_id=10;pack.pack_binding=7;
    pack.dev_name=0x420A;pack.pack_config=0x2009;pack.nv_config1=0x0140;
    pack.sense_resistor=1000;pack.thermistor_config=0x91C3;
    p.rom={0x1234,0x5678,0x9ABC,0xDEF0};p.nv_config=0x2290;p.config=0x2210;p.config2=0x2010;
    p.mode_continuity_verified=p.exclusive_access_verified=true;p.max_light_sleep_us=60000000;
    return p; // Synthetic fixture only, never a board record.
}
struct Inhibit final:ch::Inhibit {
    bool works=true;
    std::function<void()> callback;
    bool hold_off() override { check(!Gate::held,"inhibit inside gate");if(callback) callback();return works; }
};
struct ChargerBus final:ch::Bus {
    Time& time;std::array<std::uint8_t,0x49> memory{};
    unsigned calls=0,fail_at=0;std::int64_t step=100;
    std::function<void()> during;
    explicit ChargerBus(Time& t):time(t) { memory[0x48]=0x19;memory[0x0A]=0xA3;memory[0x13]=0x21;memory[0x1D]=1;memory[0x14]=0x16;memory[0x07]=10; }
    bool advance() {
        check(!Gate::held,"charger I/O inside gate");++calls;time.us+=step;if(during) during();return calls!=fail_at;
    }
    bool read(std::uint8_t reg,std::uint8_t* bytes,std::size_t size) override {
        if(!advance()) return false;
        std::copy_n(memory.data()+reg,size,bytes);
        for(std::size_t i=0;i<size;++i) if(reg+i>=0x22 && reg+i<=0x27) memory[reg+i]=0;
        return true;
    }
    bool write(std::uint8_t reg,const std::uint8_t* bytes,std::size_t size) override {
        if(!advance()) return false;
        check(!(reg==0x0F && (bytes[0]&0x20)),"charge enabled");
        std::copy_n(bytes,size,memory.data()+reg);
        // Current board's documented minimum ILIM clamp; no write may create
        // an accepted 1.5 A setting while external limiting stays enabled.
        if(reg==0x06 && size==2 && (memory[0x14]&2) && ((bytes[0]<<8)|bytes[1])>10) {
            memory[0x06]=0;memory[0x07]=10;
        }
        if(reg==0x10) memory[0x10]&=~8;
        return true;
    }
    std::uint64_t now_ms() const override { check(!Gate::held,"clock inside gate");return static_cast<std::uint64_t>(time.us)/1000; }
    void wait_ms(unsigned) override { check(false,"unexpected charger wait"); }
};
struct Wire final:gc::WordTransport {
    Time& time;std::array<std::uint16_t,512> words{};
    gc::Owner owner=1;unsigned calls=0,fail_at=0;std::int64_t step=450;
    std::function<void()> during,on_clock;
    std::function<void(unsigned,std::uint16_t&)> word_hook;
    explicit Wire(Time& t):time(t) {
        const auto p=profile();words[0x021]=p.pack.dev_name;words[0x1B5]=p.pack.pack_config;
        words[0x1B9]=p.pack.nv_config1;words[0x1CF]=p.pack.sense_resistor;words[0x1CA]=p.pack.thermistor_config;
        words[0x00B]=p.config;words[0x0AB]=p.config2;words[0x1B0]=p.nv_config;
        for(std::size_t i=0;i<4;++i) words[0x1BC+i]=p.rom[i];
        words[0x0F1]=3;words[0x006]=50*256;words[0x0DA]=words[0x0DB]=35520;
        words[0x0D8]=words[0x0D7]=words[0x0D6]=47360;words[0x01C]=static_cast<std::uint16_t>(-6400);
        words[0x139]=words[0x13A]=25*256;
    }
    gc::Owner current_owner() const override { return owner; }
    std::int64_t now_us() override { check(!Gate::held,"gauge clock inside gate");if(on_clock) on_clock();return time.us; }
    bool transfer(std::uint8_t device,std::uint8_t pointer,std::array<std::uint8_t,2>& bytes,std::uint32_t timeout) override {
        check(!Gate::held && timeout==10,"gauge transfer inside gate or changed timeout");
        auto raw=words[pointer+(device==0x0B ? 0x100:0)];
        if(word_hook) word_hook(calls+1,raw);
        bytes={static_cast<std::uint8_t>(raw),static_cast<std::uint8_t>(raw>>8)};
        ++calls;time.us+=step;if(during) during();return calls!=fail_at;
    }
};
struct Fixture {
    Time time;Gate gate;gc::BusEpoch epoch;gc::JointMailbox box{gate,epoch,context()};
    Inhibit inhibit;ChargerBus bus{time};ch::Bq25798 charger{bus,inhibit,&box};Wire wire{time};
    gc::OwnedSession session;
    gc::Window window;
    explicit Fixture(gc::Profile p=profile()):session(p,context(),wire,epoch,1,box,charger) {
        check(charger.configure(ch::SourceVoltage::nine)==ch::Error::none,"fixture charger config failed");
        window=box.open_window();check(bool(window),"fixture window failed");reset_counts();
    }
    void reset_counts() { bus.calls=wire.calls=0; }
    gc::Refresh refresh() { return session.refresh(context(),window); }
    gc::JointRecord get(std::uint64_t now) {
        auto read=box.read_latest(window,now);check(bool(read),"no latest read");
        auto result=read->consume(now);check(bool(result),"latest read failed consumption");return *result;
    }
    gc::JointRecord warm() {
        check(refresh()==gc::Refresh::warming && !box.read_latest(window,time.us),"warmup bypassed");
        time.us=4300000;check(refresh()==gc::Refresh::published,"warm publication failed");
        auto result=get(time.us);
        check(result.charger.started_ms==4300 && result.charger.finished_ms==4305 &&
              result.gauge.evidence.report.observed_us==4305500 &&
              result.gauge.evidence.report.voltage_earliest_us==3905500 &&
              result.gauge.evidence.report.temperature_earliest_us==1105500,
              "commit replaced original source timestamps");
        reset_counts();return result;
    }
};
}
