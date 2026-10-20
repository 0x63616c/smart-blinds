#pragma once
#include "smart_blinds/motion_session.hpp"
#include "smart_blinds/port_checks.hpp"
#include "smart_blinds/board_io.hpp"
#include "driver/i2c_master.h"
#include "esp_timer.h"
#include <atomic>
namespace runtime_fake { extern std::atomic<unsigned> fast_reads,stop_reads,actuations;extern std::atomic<bool> stop,fault,physical_off;void before_sample(); }
namespace blinds::c6 {
struct FastInputs { bool valid=false;std::uint64_t sequence=0,sampled_us=0; };
inline FastObservation motion_observation(const FastInputs& f) { return {f.valid,false,false,false,f.sequence,f.sampled_us,0,0,0}; }
class BenchC6Io final:public MotionIo,public CounterOrigin {
public:
 explicit BenchC6Io(port::Profile p):profile_(p) {}
 bool initialize() { return profile_.valid(); }
 bool shutdown() { return true; }
 bool set_counter_origin(std::uint64_t,double) override { return true; }
 FastInputs sample_fast() { runtime_fake::before_sample(); ++runtime_fake::fast_reads;return {true,++sequence_,now_us()}; }
 bool stop_pressed() const { ++runtime_fake::stop_reads;return runtime_fake::stop.load(); }
 bool parked_off() override { return runtime_fake::physical_off.load(); }
 bool faulted() const { return runtime_fake::fault.load(); }
 std::uint64_t now_us() const override { return esp_timer_get_time(); }
 bool request_n(bool high) override { if(!high) ++runtime_fake::actuations;return true; }
 bool charge_off() override { return true; }
 bool coast() override { return true; }
 bool wdi_high() override { return true; }
 bool encoder_power(bool on) override { if(on) ++runtime_fake::actuations;return true; }
 bool counter_start(std::uint64_t) override { ++runtime_fake::actuations;return true; }
 bool counter_stop() override { return true; }
 bool awake_lock(bool) override { return true; }
 bool pwm(int,double duty) override { if(duty) ++runtime_fake::actuations;return true; }
 bool heartbeat_pulse() override { ++runtime_fake::actuations;return true; }
private:port::Profile profile_;std::uint64_t sequence_=0;
};
}
