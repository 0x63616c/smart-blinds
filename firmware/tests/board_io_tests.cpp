#include "smart_blinds/board_io.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <vector>
using namespace blinds::io;
void check(bool ok,const char* text) { if (!ok) { std::cerr<<text<<'\n'; std::exit(1); } }
struct Backend : DisabledBackend {
    std::array<bool,24> levels{};
    std::vector<int> pins;
    unsigned calls=0, fail_at=0;
    bool step() { return ++calls!=fail_at; }
    bool output(int pin,bool high) override {
        pins.push_back(pin);
        check((pin==Pins::in1 || pin==Pins::in2) ? !high : high,"unsafe level requested");
        if (!step()) return false;
        levels[pin]=high; return true;
    }
    bool configure_inputs() override { check(levels[Pins::request_n],"inputs before inhibit"); return step(); }
    bool configure_counter_stopped() override { check(levels[Pins::encoder_n],"encoder rail energized"); return step(); }
    bool configure_pwm_stopped_low() override { check(levels[Pins::request_n],"PWM before inhibit"); return step(); }
    bool force_pwm_low() override { return step(); }
    bool outputs_are_off() override {
        return step() && levels[Pins::request_n] && levels[Pins::charge_n] && levels[Pins::encoder_n] &&
               levels[Pins::wdi] && !levels[Pins::in1] && !levels[Pins::in2];
    }
};
void initialization() {
    Backend success; DisabledSetup setup(success);
    check(setup.initialize(),"disabled setup failed");
    check(!setup.motion_allowed(),"setup permits motion");
    const auto calls=success.calls;
    check(!setup.initialize(),"reinitialized live handles");
    for (unsigned i=1;i<=calls;++i) {
        Backend bus; bus.fail_at=i; DisabledSetup f(bus);
        check(!f.initialize() && f.state()==DisabledSetup::State::fault,"injected init fault ignored");
        check(bus.pins.front()==Pins::request_n,"request not first output");
        check(bus.levels[Pins::request_n] && bus.levels[Pins::charge_n] && bus.levels[Pins::encoder_n],"failure cleanup did not try all disables");
        check(!f.initialize(),"fault implicitly retried");
    }
    for (unsigned i=1;i<=8;++i) {
        Backend bus; DisabledSetup f(bus); check(f.initialize(),"setup failed");
        bus.calls=0; bus.fail_at=i;
        check(!f.hold_off(),"stop fault hidden");
        check(bus.calls==8,"stop skipped later disables after failure");
    }
    Backend discrepant; DisabledSetup f(discrepant);
    check(f.initialize(),"setup failed");
    discrepant.levels[Pins::request_n]=false;
    check(!f.verify_off(),"unexpected ON readback accepted");
    check(discrepant.levels[Pins::request_n],"readback discrepancy did not request OFF");
    check(f.state()==DisabledSetup::State::fault && !f.verify_off(),"successful OFF recovery silently restored validity");
    check(!f.initialize(),"readback fault reinitialized without teardown");
}
struct ButtonFixture {
    Buttons buttons; std::uint64_t now=0;
    ButtonAction at(bool up,bool down,bool active=false,unsigned dt=10) {
        now+=dt; return buttons.sample(up,down,active,now);
    }
    void release() { at(false,false); at(false,false); at(false,false); }
};
void gestures() {
    ButtonFixture f; f.release();
    check(f.at(true,false)==ButtonAction::none,"press starts before release");
    f.at(true,false); f.at(true,false); f.at(false,false); f.at(false,false);
    check(f.at(false,false)==ButtonAction::up_tap,"valid tap missing");
    check(f.at(false,false)==ButtonAction::none,"tap replayed");
    // A bouncing press shorter than debounce must not become a tap.
    check(f.at(false,true)==ButtonAction::none,"bouncing press acted");
    for(int i=0;i<5;++i) check(f.at(false,false)==ButtonAction::none,"bouncing release became motion");
    check(f.at(false,false)==ButtonAction::none,"bounce became motion");
    check(f.at(true,false,true)==ButtonAction::stop,"moving STOP was debounced");
    f.at(true,false,false); f.at(true,false,false); f.release();
    check(f.at(false,false)==ButtonAction::none,"stop release became endpoint");
    check(f.at(true,true)==ButtonAction::stop,"both buttons did not stop immediately");
    f.at(true,false); f.release();
    check(f.at(false,false)==ButtonAction::none,"both-button release became endpoint");
    f.at(true,false); f.at(true,false); f.at(true,false);
    check(f.at(false,true)==ButtonAction::stop,"ambiguous direct button swap did not stop");
    f.release();
    ButtonFixture held;
    for (int i=0;i<200;++i) check(held.at(true,false)==ButtonAction::none,"boot-held button acted");
    held.release();
    ButtonAction action=ButtonAction::none; unsigned holds=0;
    for (int i=0;i<170;++i) { action=held.at(false,true); if(action==ButtonAction::service_hold) ++holds; else check(action==ButtonAction::none,"long hold became motion"); }
    check(holds==1,"service hold missing/repeated");
    held.release(); check(held.at(false,false)==ButtonAction::none,"long hold release became motion");
    check(held.at(false,false,false,51)==ButtonAction::stop,"sampling gap not rejected");
    check(held.buttons.sample(false,false,false,0)==ButtonAction::stop,"reverse clock not rejected");
}
int main() { initialization(); gestures(); std::cout<<"disabled I/O failure ordering and button gestures passed\n"; }
