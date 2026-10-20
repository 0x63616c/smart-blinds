#include "smart_blinds/sensor_access.hpp"
#include "fakes/sensor_fixture.hpp"
using namespace sensor_fixture;
void independent_reads_and_cancel() {
    Fixture f;f.warm();Gate selector;gc::SensorAccess access(selector,f.epoch);
    check(access.install(f.box,f.window,8),"install failed");
    const auto clock=[&]{return f.time.us;};
    auto control=access.snapshot(8,clock),status=access.snapshot(8,clock);
    check(control && status && access.current(*control,8),"independent reader consumed other reader authority");
    check(!access.snapshot(7,clock),"wrong request selected power");
    unsigned clocks=0;
    const auto delayed=[&] { if(++clocks==2) f.time.us+=20001;return f.time.us; };
    check(!access.snapshot(8,delayed),"single clock stamp bypassed immediate read bound");
    access.withdraw();
    check(access.quiescent() && !access.current(*control,8) && !access.snapshot(8,clock),"withdrawal retained authority");
}
void pinned_lifetime() {
    Fixture f;f.warm();Gate selector;gc::SensorAccess access(selector,f.epoch);
    check(access.install(f.box,f.window,9),"install failed");
    std::mutex mutex;std::condition_variable cv;bool pinned=false,released=false;
    std::optional<gc::JointRecord> result;
    std::thread reader([&] {
        unsigned calls=0;
        result=access.snapshot(9,[&] {
            if(++calls==1) {
                std::unique_lock<std::mutex> lock(mutex);pinned=true;cv.notify_all();
                cv.wait(lock,[&]{return released;});
            }
            return f.time.us;
        });
    });
    { std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return pinned;}); }
    access.withdraw();f.box.retire();
    check(!access.quiescent(),"retirement allowed object destruction with pinned reader");
    check(!access.install(f.box,f.window,10),"installed over live retired reader");
    { std::lock_guard<std::mutex> lock(mutex);released=true;cv.notify_all(); }
    reader.join();check(!result && access.quiescent(),"retired reader recovered or leaked pin");
}
void blocked_refresh_retains_control_and_closes() {
    Fixture f;f.warm();Gate selector;gc::SensorAccess access(selector,f.epoch);
    check(access.install(f.box,f.window,10),"install failed");
    for(bool charger:{true,false}) {
        std::mutex mutex;std::condition_variable cv;bool blocked=false,released=false;
        std::atomic<bool> stop{false};
        const auto block=[&] {
            std::unique_lock<std::mutex> lock(mutex);
            if(blocked) return;
            blocked=true;cv.notify_all();cv.wait(lock,[&]{return released;});
        };
        f.bus.during=charger ? std::function<void()>(block):std::function<void()>{};
        f.wire.during=charger ? std::function<void()>{}:std::function<void()>(block);
        gc::Refresh result{};
        std::thread owner([&]{result=f.refresh();});
        { std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return blocked;}); }
        const auto stamp=f.time.us;
        check(access.snapshot(10,[&]{return stamp;}).has_value(),"blocked healthy read withdrew old record");
        stop.store(true);access.withdraw();f.box.close_window(f.window);
        check(stop.load() && !f.box.closure_acknowledged(f.window),"blocked owner acknowledged closure");
        check(!access.snapshot(10,[&]{return stamp;}),"close still published old power");
        { std::lock_guard<std::mutex> lock(mutex);released=true;cv.notify_all(); }
        owner.join();check(result==gc::Refresh::closed && f.box.closure_acknowledged(f.window),"closed acquisition published/never acknowledged");
        f.bus.during={};f.wire.during={};
        f.window=f.box.open_window();check(bool(f.window),"next window refused");
        check(f.refresh()==gc::Refresh::published && access.install(f.box,f.window,10),"new window failed");
    }
}
void cold_session_restart() {
    Time time;Gate gate,selector;gc::BusEpoch epoch;Inhibit inhibit,motor;ChargerBus bus(time);Wire wire(time);
    gc::SensorAccess access(selector,epoch);
    struct Session {
        gc::Context context;
        gc::JointMailbox box;
        ch::Bq25798 charger;
        gc::OwnedSession owner;
        gc::Window window;
        Session(Gate& gate,gc::BusEpoch& epoch,ChargerBus& bus,Inhibit& inhibit,Wire& wire)
            :context{99,epoch.value(),epoch.value(),7,10},box(gate,epoch,context),charger(bus,inhibit,&box),
             owner(profile(),context,wire,epoch,1,box,charger) {}
    };
    std::optional<Session> slot;slot.emplace(gate,epoch,bus,inhibit,wire);
    check(slot->charger.configure(ch::SourceVoltage::nine)==ch::Error::none,"cold config failed");
    slot->window=slot->box.open_window();
    check(slot->owner.refresh(slot->context,slot->window)==gc::Refresh::warming,"cold guard bypassed");
    time.us+=3200000;check(slot->owner.refresh(slot->context,slot->window)==gc::Refresh::published,"cold warmup failed");
    check(access.install(slot->box,slot->window,1),"first install failed");
    const auto old=access.snapshot(1,[&]{return time.us;});check(bool(old),"first report absent");
    access.withdraw();slot->box.close_window(slot->window);
    check(slot->charger.park_off(motor).valid() && slot->owner.park_light_sleep(slot->context),"clean park failed");
    const auto parked=time.us;
    for(unsigned i=0;i<20;++i) {
        time.us+=1000000;
        check(!access.snapshot(1,[&]{return time.us;}),"DTIM/status wake revived evidence");
    }
    time.us=parked+8LL*60*60*1000000;
    // Explicit owner retirement, not an implicit successful resume or MCU reboot.
    slot->box.retire({gc::FailureKind::lifecycle,10});
    check(access.quiescent() && !access.current(*old,1),"old reader survived cold boundary");
    const auto prior_epoch=old->gauge.epoch;slot.reset();slot.emplace(gate,epoch,bus,inhibit,wire);
    check(slot->context.monitoring_session!=prior_epoch && slot->context.boot==99,"cold restart reused identity/rebooted");
    const auto prior_writes=bus.calls;
    check(slot->charger.adopt_parked(ch::SourceVoltage::nine,motor).valid() && bus.calls>prior_writes,
          "new session did not independently inspect hardware park");
    check(slot->charger.resume_off(motor).valid() && bus.memory[0x10]==0x93,"active watchdog not restored");
    slot->window=slot->box.open_window();check(access.install(slot->box,slot->window,2),"cold install failed");
    check(slot->owner.refresh(slot->context,slot->window)==gc::Refresh::warming &&
          !access.snapshot(2,[&]{return time.us;}),"expired continuity skipped cold warmup");
    time.us+=3200000;check(slot->owner.refresh(slot->context,slot->window)==gc::Refresh::published,"second warmup failed");
    const auto fresh=access.snapshot(2,[&]{return time.us;});
    check(fresh && fresh->gauge.epoch!=prior_epoch && fresh->gauge.evidence.report.observed_us>old->gauge.evidence.report.observed_us,
          "cold session revived old timestamp");
    // A watchdog-reset image is not a clean parked image, even with CE OFF.
    access.withdraw();slot->box.close_window(slot->window);check(slot->charger.park_off(motor).valid(),"second park failed");
    slot->box.retire({gc::FailureKind::lifecycle,10});slot.reset();
    bus.memory[0x22]=0x20;bus.memory[0x11]=0x40;
    slot.emplace(gate,epoch,bus,inhibit,wire);
    check(!slot->charger.adopt_parked(ch::SourceVoltage::nine,motor).valid() &&
          slot->box.failure().kind==gc::FailureKind::charger && bus.memory[0x11]==0x40,
          "unexpected watchdog/default image was repaired or hidden");
}
int main() {
    independent_reads_and_cancel();pinned_lifetime();blocked_refresh_retains_control_and_closes();cold_session_restart();
    std::cout<<"independent snapshots, pinned retirement, blocked I/O closure and explicit cold restart passed\n";
}
