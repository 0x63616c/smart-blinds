#include "smart_blinds/charger.hpp"

namespace smart_blinds::charger {
Profile profile(SourceVoltage voltage) {
    // Full known field images, reserved bits written zero. No arbitrary register
    // writes, REG_RST, ship-FET mode, battery discharge or charge enable exposed.
    return {{{0x0F,1,0x82,0xFF}, // EN_CHG/ICO/BACKUP/HIZ=0, termination/OVP discharge=1.
             {0x11,1,0x00,0xFF}, // Automatic/forced DPDM/HVDCP and ship controls off.
             {0x12,1,0x00,0xFF}, // OTG off; forward protections/PFM enabled.
             {0x09,1,0x25,0xFF}, // STOP_WD_CHG=1, ITERM=200 mA, REG_RST=0.
             {0x10,1,0x93,0xFF}, // VAC OVP=18 V, watchdog=2 s; WD_RST must return to zero.
             {0x00,1,0x1A,0xFF}, // VSYSMIN=(9 V - 2.5 V)/0.25 V.
             {0x0A,1,0xA3,0xFF}, // 3S; recharge 1024 ms/200 mV below VREG.
             {0x01,2,1245,0xFFFF}, // VREG=12.45 V / 10 mV.
             {0x03,2,100,0xFFFF}, // ICHG=1 A / 10 mA.
             {0x05,1,static_cast<std::uint16_t>(voltage == SourceVoltage::nine ? 80 : 130),0xFF},
             {0x06,2,10,0xFFFF}, // OFF-only IINDPM=100 mA; keep the board's external ILIM clamp.
             {0x08,1,0xC3,0xFF}, // 71.4% VREG precharge threshold; 120 mA.
             {0x0D,1,0x4B,0xFF}, // 2 h precharge; unused OTG limit at documented default.
             {0x0E,1,0x3C,0xFF}, // All safety timers on, fast=12 h, no 2x extension/topoff.
             {0x13,1,0x21,0xFF}, // 750 kHz; IBUS OCP on; no external ACFETs/forced detection.
             {0x14,1,0x16,0xFF}, // Internal and external input limits on; no ship FET.
             {0x15,1,0xAA,0xFF}, // MPPT off, unused timing fields at defaults.
             {0x16,1,0x30,0xFF}, // Die regulation 60 C/shutdown 85 C; pulldowns/backup off.
             {0x17,1,0x00,0xFF}, // Warm voltage/current and cool current all suspend charge.
             {0x18,1,0x44,0xFF}, // Cool 10 C/warm 40 C, TS honored; unused OTG thresholds default.
             {0x2E,1,0x40,0xFF}, // ADC stopped, one shot, 15-bit, no historical averaging.
             {0x2F,1,0x00,0xFF}, // Current/voltage/TS/die channels enabled.
             {0x30,1,0xC0,0xFF}}}; // DP/DM ADC off; VAC1/2 available.
}
bool Bq25798::fail(Error error) {
    configured_ = false;
    parked_=false;
    reconciliation_authorized_=false;
    if(transition_guard_ && transition_failure_==Error::none) transition_failure_=error;
    if(first_error_==Error::none) {
        first_error_=error;
        if(sink_) sink_->failed(error);
    }
    error_ = error;
    // Independent OFF path must not depend on a healthy I2C bus. Surface failure
    // to establish even the requested GPIO state instead of claiming it is off.
    if (!inhibit_.hold_off()) { inhibit_failed_=true;error_ = Error::inhibit; }
    return false;
}
bool Bq25798::begin() {
    error_ = Error::none;
    // A failed transition is terminal. Later calls must not erase its cause
    // or emit a replacement first-failure notice while refusing recovery.
    if(transition_failure_==Error::none) {
        first_error_=Error::none;
        inhibit_failed_=false;
    }
    const auto now = bus_.now_ms();
    if (now < last_ms_) return fail(Error::clock);
    started_ms_ = last_ms_ = now;
    if(inhibit_.hold_off()) return true;
    inhibit_failed_=true;
    return fail(Error::inhibit);
}
bool Bq25798::within_budget() {
    const auto now = bus_.now_ms();
    if (now < last_ms_) return fail(Error::clock);
    last_ms_ = now;
    if (now - started_ms_ > operation_budget_ms) return fail(Error::timeout);
    return true;
}
bool Bq25798::read(std::uint8_t reg, std::uint8_t* bytes, std::size_t size) {
    if (!within_budget() || !off_guards()) return false;
    if (!bus_.read(reg, bytes, size)) return fail(Error::bus);
    return off_guards() && within_budget();
}
bool Bq25798::write(std::uint8_t reg, const std::uint8_t* bytes, std::size_t size) {
    if (!within_budget() || !off_guards()) return false;
    if (!bus_.write(reg, bytes, size)) return fail(Error::bus);
    return off_guards() && within_budget();
}
bool Bq25798::write_register(const Register& reg) {
    const std::uint8_t bytes[] = {static_cast<std::uint8_t>(reg.value >> 8), static_cast<std::uint8_t>(reg.value)};
    return write(reg.address, bytes + (reg.size == 1 ? 1 : 0), reg.size);
}
bool Bq25798::verify_register(const Register& reg) {
    std::uint8_t bytes[2]{};
    if (!read(reg.address, bytes, reg.size)) return false;
    const auto value = reg.size == 1 ? bytes[0] : (bytes[0] << 8) | bytes[1];
    return (value & reg.mask) == (reg.value & reg.mask) || fail(Error::readback);
}
bool Bq25798::verify_profile() {
    std::uint8_t identity = 0;
    if (!read(0x48, &identity, 1)) return false;
    if (identity != 0x19) return fail(Error::identity); // PN=011, documented revision=001 only.
    for (const auto& reg : profile_) if (!verify_register(reg)) return false;
    const Register dpdm{0x47,1,0,0xFF};
    return verify_register(dpdm);
}
Error Bq25798::configure(SourceVoltage voltage) {
    configured_ = false;
    if (!begin()) return error_;
    if(transition_failure_!=Error::none || parked_) {
        if(transition_failure_==Error::none) transition_failure_=Error::unconfigured;
        fail(Error::unconfigured);return error_;
    }
    if (voltage != SourceVoltage::nine && voltage != SourceVoltage::fifteen) {
        fail(Error::unconfigured); return error_;
    }
    std::uint8_t identity = 0, cells = 0, frequency = 0;
    if (!read(0x48,&identity,1)) return error_;
    if (identity != 0x19) { fail(Error::identity); return error_; }
    if (!read(0x0A,&cells,1) || !read(0x13,&frequency,1)) return error_;
    if ((cells & 0xC0) != 0x80 || !(frequency & 0x20)) { fail(Error::strap); return error_; }
    // Initial trusted setup may consume POR watchdog state, but may never
    // clear temperature/fault evidence before the first write.
    std::array<std::uint8_t,7> initial_status{};
    std::array<std::uint8_t,6> initial_flags{};
    if(!read(0x1B,initial_status.data(),initial_status.size()) ||
       !read(0x22,initial_flags.data(),initial_flags.size())) return error_;
    if(initial_status[5] || initial_status[6] || initial_flags[4] || initial_flags[5]) {
        fail(Error::fault);return error_;
    }
    if((initial_status[4]|initial_flags[3])&0x0F) { fail(Error::temperature);return error_; }
    source_ = voltage;
    profile_ = profile(voltage);
    for (const auto& reg : profile_)
        if (!write_register(reg) || !verify_register(reg)) return error_;
    if (!write_register({0x47,1,0,0xFF}) || !verify_profile()) return error_;
    // Explicit setup consumes POR watchdog/connection history. Fault history is
    // never silently accepted; subsequent captures reject any new watchdog flag.
    std::array<std::uint8_t,7> status{};
    std::array<std::uint8_t,6> flags{};
    if (!read(0x1B,status.data(),status.size()) || !read(0x22,flags.data(),flags.size())) return error_;
    if (status[5] || status[6] || flags[4] || flags[5]) { fail(Error::fault); return error_; }
    if (status[0] & 0x20) { fail(Error::status); return error_; }
    configured_ = true;
    return Error::none;
}
bool Bq25798::off_guards() {
    if(!transition_guard_) return true;
    if(park_guard_ && (!operation_identity_.valid() ||
                      !(park_guard_->identity()==operation_identity_)))
        return fail(Error::unconfigured);
    if(!inhibit_.hold_off() || !transition_guard_->hold_off()) return fail(Error::inhibit);
    if(park_guard_ && !(park_guard_->identity()==operation_identity_))
        return fail(Error::unconfigured);
    return true;
}
bool Bq25798::inspect_off(OffCapture& result,std::array<std::uint8_t,6>* latest_flags) {
    if(!read(0x1B,result.status.data(),result.status.size())) return false;
    std::array<std::uint8_t,6> flags{};
    if(!read(0x22,flags.data(),flags.size())) return false;
    if(latest_flags) *latest_flags=flags;
    for(std::size_t i=0;i<flags.size();++i) result.flags[i]|=flags[i];
        const auto mode=(result.status[1]>>1)&0x0F;
        // PG and adapter insertion/removal may change while operating from the
        // protected battery. They do not authorize charging or an input limit.
        if((result.status[0]&0x20) || (result.flags[0]&0x20) || (result.status[1]&0xE0) ||
           mode==7 || mode==9 || mode==10 || mode>=12 ||
           !(result.status[2]&1) || (result.status[2]&0xC6) || (result.status[3]&0xCE) ||
           (result.flags[2]&0x0E)) return fail(Error::status);
        if(result.status[5] || result.status[6] || result.flags[4] || result.flags[5]) return fail(Error::fault);
        if((result.status[4]|result.flags[3])&0x0F) return fail(Error::temperature);
        return true;
}
bool Bq25798::verify_parked_source(std::uint8_t& vindpm) {
    std::uint8_t identity=0;
    if(!read(0x48,&identity,1)) return false;
    if(identity!=0x19) return fail(Error::identity);
    for(const auto& reg:profile_) {
        if(reg.address==0x05) {
            if(!read(0x05,&vindpm,1)) return false;
        } else if(!verify_register(reg)) return false;
    }
    return verify_register({0x47,1,0,0xFF});
}
OffCapture Bq25798::park_off(ParkGuard& guard) {
    park_guard_=&guard;operation_identity_=guard.identity();
    auto result=transition_off(guard,true);
    transition_guard_=&guard;
    if(result.valid()) {
        const auto prior_source=result.status[0]&0x0F;
        std::array<std::uint8_t,6> latest{};
        if(verify_profile() && inspect_off(result,&latest) && within_budget() && off_guards()) {
            if((result.flags[0]&0x10) || (latest[0]&0x0F) ||
               (result.status[0]&0x0F)!=prior_source) fail(Error::status);
            else if(last_ms_-started_ms_>250) fail(Error::timeout);
            else {
                parked_identity_=operation_identity_;
                parked_source_=result.status[0]&0x0F;
                reconciliation_authorized_=true;
            }
        }
    }
    result.finished_ms=last_ms_;result.error=error_;
    transition_guard_=nullptr;park_guard_=nullptr;
    return result;
}
ParkReconciliation Bq25798::reconcile_parked(ParkGuard& guard) {
    ParkReconciliation result;
    for(const auto& reg:profile_) if(reg.address==0x05)
        result.previous_vindpm=static_cast<std::uint8_t>(reg.value);
    const bool allowed=parked_ && !configured_ && reconciliation_authorized_ &&
        transition_failure_==Error::none && first_error_==Error::none;
    transition_guard_=&guard;park_guard_=&guard;operation_identity_=parked_identity_;
    const auto work=[&] {
        // Reject before begin(), so an earlier failure remains the first cause.
        if(!allowed) { fail(Error::unconfigured);return; }
        if(!begin()) return;
        result.observation.started_ms=started_ms_;
        if(!off_guards() || !inspect_off(result.observation)) return;
        const auto first_source=static_cast<std::uint8_t>(result.observation.status[0]&0x0F);
        const bool vbus_edge=(result.observation.flags[0]&1) ||
                             ((first_source^parked_source_)&1);
        result.source_event=(result.observation.flags[0]&0x0F) ||
                            first_source!=parked_source_;
        // Poor-source history is not a clean plug/unplug event in this slice.
        if(result.observation.flags[0]&0x10) { fail(Error::status);return; }
        std::uint8_t first_value=0,second_value=0;
        if(!verify_parked_source(first_value)) return;
        std::array<std::uint8_t,6> latest{};
        const auto stable=[&] {
            if(!inspect_off(result.observation,&latest)) return false;
            return (!((latest[0])&0x1F) &&
                    (result.observation.status[0]&0x0F)==first_source) || fail(Error::status);
        };
        if(!stable() || !verify_parked_source(second_value) || !stable()) return;
        result.observed_vindpm=second_value;
        if(first_value!=second_value || second_value<36 || second_value>220) {
            fail(Error::readback);return;
        }
        const bool changed=second_value!=result.previous_vindpm;
        if(changed && !vbus_edge) { fail(Error::readback);return; }
        if((changed || result.source_event) && !(first_source&1) &&
           (second_value!=36 || (first_source&8))) { fail(Error::status);return; }
        if(!within_budget() || !off_guards()) return;
        if(last_ms_-started_ms_>250) { fail(Error::timeout);return; }
        // Exact future readback, not a permanent REG05 mask. No source voltage
        // enum, current allowance or hardware register is changed.
        for(auto& reg:profile_) if(reg.address==0x05) reg.value=second_value;
        parked_source_=first_source;
    };
    work();
    result.observation.finished_ms=last_ms_;
    result.observation.error=error_;
    transition_guard_=nullptr;park_guard_=nullptr;
    return result;
}
OffCapture Bq25798::adopt_parked(SourceVoltage voltage,Inhibit& motor_off) {
    OffCapture result;
    const bool allowed=!configured_ && !parked_ && transition_failure_==Error::none &&
        (voltage==SourceVoltage::nine || voltage==SourceVoltage::fifteen);
    transition_guard_=&motor_off;
    if(begin()) {
        result.started_ms=started_ms_;
        if(!allowed) fail(Error::unconfigured);
        else {
            source_=voltage;profile_=profile(voltage);
            for(auto& reg:profile_) if(reg.address==0x10) reg.value=0x90;
            if(inspect_off(result) && verify_profile() && off_guards()) {
                if(last_ms_-started_ms_>250) fail(Error::timeout);
                else parked_=true;
            }
        }
    }
    result.finished_ms=last_ms_;result.error=error_;transition_guard_=nullptr;
    return result;
}
OffCapture Bq25798::park_off(Inhibit& guard) { return transition_off(guard,true); }
OffCapture Bq25798::resume_off(Inhibit& guard) { return transition_off(guard,false); }
OffCapture Bq25798::resume_off(ParkGuard& guard) {
    park_guard_=&guard;operation_identity_=parked_identity_;
    auto result=transition_off(guard,false);
    park_guard_=nullptr;
    return result;
}
OffCapture Bq25798::transition_off(Inhibit& motor_off,bool park) {
    OffCapture result;
    const bool allowed=transition_failure_==Error::none &&
        (!reconciliation_authorized_ || park_guard_) &&
        (park ? configured_ && !parked_:parked_ && !configured_);
    reconciliation_authorized_=false;
    transition_guard_=&motor_off;
    const auto same_source=[&] {
        return !park_guard_ || park ||
               (!(result.flags[0]&0x1F) && (result.status[0]&0x0F)==parked_source_) ||
               fail(Error::status);
    };
    const auto work=[&] {
        if(!begin()) return;
        result.started_ms=started_ms_;
        if(!allowed) { fail(Error::unconfigured);return; }
        // Read-to-clear history precedes any write AND any profile mismatch.
        // An expected watchdog expiry has no bypass here: it remains a fault.
        if(!inspect_off(result) || !same_source() || !verify_profile() || !off_guards()) return;
        const auto value=static_cast<std::uint16_t>(park ? 0x90:0x93);
        if(!write_register({0x10,1,value,0xFF})) return;
        for(auto& reg:profile_) if(reg.address==0x10) reg.value=value;
        if(!inspect_off(result) || !same_source() || !verify_profile() || !off_guards()) return;
        // Bound resume keeps a final read-to-clear event cut after verification.
        if(park_guard_ && !park && (!inspect_off(result) || !same_source() || !off_guards())) return;
        if(last_ms_-started_ms_>250) { fail(Error::timeout);return; }
        configured_=!park;parked_=park;
    };
    work();
    result.finished_ms=last_ms_;result.error=error_;
    transition_guard_=nullptr;
    return result;
}
OffCapture Bq25798::capture_off() {
    OffCapture result;
    const bool had_configuration=configured_;
    if(!begin()) { result.error=error_; return result; }
    result.started_ms=started_ms_;
    if(!had_configuration) { fail(Error::unconfigured); result.error=error_; return result; }
    const auto inspect=[&]() { return verify_profile() && inspect_off(result); };
    if(inspect() && write_register({0x10,1,0x9B,0xF7}) && inspect()) {
        if(bus_.now_ms()-started_ms_>250) fail(Error::timeout);
    }
    result.finished_ms=last_ms_;
    result.error=error_;
    return result;
}
Capture Bq25798::capture() {
    Capture result;
    const bool had_configuration = configured_;
    if (!begin()) { result.error = error_; return result; }
    result.started_ms = started_ms_;
    result.source_mv = static_cast<std::uint16_t>(source_);
    if (!had_configuration) { fail(Error::unconfigured); result.error = error_; return result; }
    const auto work = [&]() -> bool {
        if (!verify_profile() || !read(0x1B,result.status.data(),result.status.size()) ||
            !read(0x22,result.flags.data(),result.flags.size())) return false;
        // Read watchdog/fault history BEFORE any write that could clear default mode.
        if ((result.status[0] & 0x20) || (result.flags[0] & 0x3F) || result.flags[1] ||
            (result.flags[2] & 0x4F)) return fail(Error::status);
        if (result.flags[3] & 0x0F) return fail(Error::temperature);
        if (result.status[5] || result.status[6] || result.flags[4] || result.flags[5]) return fail(Error::fault);
        if (!write_register({0x10,1,0x9B,0xF7})) return false; // Explicit watchdog reset, profile unchanged.
        result.conversion_started_ms = bus_.now_ms();
        if (!write_register({0x2E,1,0xC0,0xFF})) return false; // Start a fresh one-shot.
        std::uint8_t control = 0;
        bool saw_busy = false;
        bool complete = false;
        for (unsigned polls = 0; polls < 100; ++polls) {
            if (!read(0x2E,&control,1)) return false;
            if ((control & 0x7F) != 0x40) return fail(Error::readback);
            if (!(control & 0x80)) { complete = true; break; }
            saw_busy = true;
            bus_.wait_ms(5);
            if (!within_budget()) return false;
        }
        if (error_ != Error::none) return false;
        if (!complete) return fail(Error::timeout);
        std::array<std::uint8_t,18> bytes{};
        if (!read(0x31,bytes.data(),bytes.size()) ||
            !read(0x1B,result.status.data(),result.status.size()) ||
            !read(0x22,result.flags.data(),result.flags.size()) || !verify_profile()) return false;
        for (std::size_t i=0;i<result.adc.size();++i) result.adc[i] = static_cast<std::uint16_t>((bytes[2*i]<<8)|bytes[2*i+1]);
        // ADC_DONE_STAT is REG1E bit 5; ADC_DONE_FLAG is REG24 bit 5.
        if (!saw_busy || !(result.status[3] & 0x20) || !(result.flags[2] & 0x20)) return fail(Error::adc);
        if ((result.status[0] & 0x29) != 0x09 || !(result.status[2] & 0x01) ||
            (result.status[2] & 0xC6) || (result.status[3] & 0xCE) ||
            (result.status[1] & 0xE0) || (result.flags[0] & 0x3F) || result.flags[1] ||
            (result.flags[2] & 0x4F)) return fail(Error::status);
        const auto bus_mode = (result.status[1] >> 1) & 0x0F;
        if (bus_mode == 7 || bus_mode == 12) return fail(Error::status); // OTG/backup forbidden.
        if (result.status[5] || result.status[6] || result.flags[4] || result.flags[5]) return fail(Error::fault);
        if ((result.status[4] | result.flags[3]) & 0x0F) return fail(Error::temperature);
        return true;
    };
    work();
    if (error_ == Error::none) within_budget();
    result.finished_ms = last_ms_;
    result.error = error_;
    return result;
}
Readiness assess(const Capture& c, const PackEvidence& p, const SourceEvidence& s,
                 bool motor_stopped, std::uint64_t now) {
    if (!c.valid()) return Readiness::charger;
    if (!p.pack_identity || !s.contract_epoch || !p.commissioned_protection || !p.healthy_protection ||
        !p.cells_present || !p.sensor_placement_verified || !p.conversions_fresh ||
        !s.fixed_contract || !s.factory_image_verified || !s.hardware_path_qualified) return Readiness::evidence_missing;
    const auto fresh = [now](std::uint64_t stamp) { return stamp <= now && now-stamp <= 250; };
    if (!fresh(p.sampled_ms) || !fresh(s.sampled_ms) || !fresh(c.conversion_started_ms) ||
        c.started_ms > c.conversion_started_ms || c.conversion_started_ms > c.finished_ms || c.finished_ms > now)
        return Readiness::stale;
    if ((s.voltage_mv != 9000 && s.voltage_mv != 15000) || c.source_mv != s.voltage_mv || s.current_ma < 2500 ||
        c.vbus_mv() < s.voltage_mv*90/100 || c.vbus_mv() > s.voltage_mv*110/100) return Readiness::source;
    std::uint32_t sum = 0;
    for (auto cell : p.cell_mv) { if (cell < 3000 || cell > 4150) return Readiness::pack; sum += cell; }
    const std::uint32_t battery_mv = c.battery_mv();
    if (battery_mv+150U < sum || battery_mv > sum+150U) return Readiness::pack;
    for (auto temperature : p.temperature_deci_c)
        if (temperature < 100 || temperature >= 400) return Readiness::temperature;
    if (!motor_stopped) return Readiness::motion;
    return Readiness::ready_for_review; // Never an EN_CHG/CE permission.
}
} // namespace smart_blinds::charger
