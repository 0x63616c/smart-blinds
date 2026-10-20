#include "c6_gauge_continuity.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
namespace gc=blinds::power::continuity;
using blinds::c6::GaugeContinuity;
struct MockBus {};
struct MockDevice { std::uint8_t address=0; };
struct MockTask {};
namespace {
MockTask task1,task2;
TaskHandle_t current_task=&task1;
MockBus bus;
std::int64_t clock_us=1000000;
std::size_t adds=0,removes=0,transfers=0,add_failure=0,transfer_failure=0;
std::vector<std::uint8_t> addresses;
std::array<std::uint16_t,512> words{};
void check(bool condition,const char* message) {
    if(!condition) { std::cerr<<message<<'\n';std::exit(1); }
}
gc::Context context() { return {99,17,2,7,10}; }
gc::Profile profile() {
    gc::Profile p;auto& pack=p.pack;
    pack.full_profile_verified=pack.timing_verified=pack.sensor_placement_verified=true;
    pack.verified_for_boot=99;pack.qualification_id=10;pack.pack_binding=7;
    pack.dev_name=0x420A;pack.pack_config=0x2009;pack.nv_config1=0x0140;
    pack.sense_resistor=1000;pack.thermistor_config=0x91C3;
    p.rom={0x1234,0x5678,0x9ABC,0xDEF0};p.nv_config=0x2290;p.config=0x2210;p.config2=0x2010;
    p.mode_continuity_verified=p.exclusive_access_verified=true;p.max_light_sleep_us=60000000;
    return p; // Synthetic host fixture only.
}
void reset() {
    current_task=&task1;adds=removes=transfers=add_failure=transfer_failure=0;addresses.clear();
    clock_us=1000000;words.fill(0);const auto p=profile();
    words[0x021]=p.pack.dev_name;words[0x1B5]=p.pack.pack_config;words[0x1B9]=p.pack.nv_config1;
    words[0x1CF]=p.pack.sense_resistor;words[0x1CA]=p.pack.thermistor_config;
    words[0x00B]=p.config;words[0x0AB]=p.config2;words[0x1B0]=p.nv_config;
    for(std::size_t i=0;i<4;++i) words[0x1BC+i]=p.rom[i];
    words[0x0F1]=3;words[0x006]=50*256;
    words[0x0DA]=words[0x0DB]=35520;words[0x0D8]=words[0x0D7]=words[0x0D6]=47360;
    words[0x139]=words[0x13A]=25*256;
}
}
TaskHandle_t xTaskGetCurrentTaskHandle() { return current_task; }
std::int64_t esp_timer_get_time() { return clock_us; }
esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t b,const i2c_device_config_t* cfg,i2c_master_dev_handle_t* out) {
    check(b==&bus && current_task==&task1,"SDK add on wrong bus/task");
    check(cfg->dev_addr_length==I2C_ADDR_BIT_LEN_7 && cfg->scl_speed_hz==100000,"SDK bus configuration changed");
    ++adds;addresses.push_back(static_cast<std::uint8_t>(cfg->device_address));
    if(adds==add_failure) return ESP_ERR_TIMEOUT;
    *out=new MockDevice{static_cast<std::uint8_t>(cfg->device_address)};return ESP_OK;
}
esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t d) {
    check(current_task==&task1,"unsafe cross-task SDK teardown");
    ++removes;delete d;return ESP_OK;
}
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t d,const std::uint8_t* pointer,std::size_t send,
                                    std::uint8_t* output,std::size_t receive,int timeout) {
    check(current_task==&task1 && send==1 && receive==2 && timeout==10,"SDK transaction shape or owner changed");
    check(d->address==0x36 || d->address==0x0B,"SDK device address changed");
    ++transfers;clock_us+=100;
    const auto reg=static_cast<std::uint16_t>(*pointer+(d->address==0x0B ? 0x100:0));
    output[0]=static_cast<std::uint8_t>(words[reg]);output[1]=static_cast<std::uint8_t>(words[reg]>>8);
    return transfers==transfer_failure ? ESP_ERR_TIMEOUT:ESP_OK;
}
int main() {
    reset();
    {
        gc::BusEpoch epoch;GaugeContinuity adapter(profile(),context(),epoch);
#if !CONFIG_BLINDS_GAUGE_CONTINUITY_BENCH
        check(adapter.attach(&bus,context())==ESP_ERR_NOT_SUPPORTED,"default-off gate missing");
        check(!adapter.read(context()).evidence.report.ready() && !adds && !transfers,
              "default-off adapter touched hardware");
        current_task=&task2;
        check(adapter.close()==ESP_ERR_INVALID_STATE && !removes,"wrong-task disabled cleanup used SDK");
        current_task=&task1;
#else
        check(adapter.attach(&bus,context())==ESP_OK && addresses==std::vector<std::uint8_t>{0x36,0x0B},
              "actual SDK attachment mapping failed");
        check(adapter.read(context()).evidence.report.state==blinds::power::State::warming,"SDK read skipped warmup");
        clock_us=4200000;const auto ready=adapter.read(context());
        check(adapter.current(ready,clock_us) && std::abs(ready.evidence.report.pack_v-11.1)<1e-9,
              "SDK wire path did not produce bounded evidence");
        current_task=&task2;
        check(adapter.close()==ESP_ERR_INVALID_STATE && !removes && !adapter.current(ready,clock_us),
              "wrong-task close removed handles or retained approval");
        current_task=&task1;
        const auto prior=transfers;
        check(!adapter.read(context()).evidence.report.ready() && transfers==prior,"wrong-task loss auto-repaired");
        check(adapter.close()==ESP_OK && removes==2,"owner failed to reclaim handles");
#endif
    }
#if CONFIG_BLINDS_GAUGE_CONTINUITY_BENCH
    reset();
    {
        gc::BusEpoch epoch;GaugeContinuity adapter({},context(),epoch);
        check(adapter.attach(&bus,context())==ESP_ERR_INVALID_STATE && !adds,"unqualified profile attached");
    }
    reset();add_failure=2;
    {
        gc::BusEpoch epoch;GaugeContinuity adapter(profile(),context(),epoch);
        check(adapter.attach(&bus,context())==ESP_ERR_TIMEOUT && adds==2 && removes==1 &&
              adapter.last_error()==ESP_ERR_TIMEOUT,"partial attachment lost error/handle");
        check(adapter.attach(&bus,context())==ESP_ERR_INVALID_STATE && adds==2,"attachment silently retried");
    }
    reset();
    {
        gc::BusEpoch epoch;GaugeContinuity adapter(profile(),context(),epoch);
        check(adapter.attach(&bus,context())==ESP_OK,"setup failed");
        transfer_failure=1;
        check(!adapter.read(context()).evidence.report.ready() && transfers==1 &&
              adapter.last_error()==ESP_ERR_TIMEOUT,"SDK error did not stop on first transfer");
        transfer_failure=0;
        check(!adapter.read(context()).evidence.report.ready() && transfers==1,"SDK error auto-recovered");
    }
#endif
    std::cout<<"actual C6 adapter compiled against host SDK seam: default/qualification, mapping, ownership and cleanup passed\n";
}
