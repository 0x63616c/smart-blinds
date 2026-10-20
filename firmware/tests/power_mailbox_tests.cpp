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
namespace {
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
    explicit ChargerBus(Time& t):time(t) { memory[0x48]=0x19;memory[0x0A]=0xA3;memory[0x13]=0x21;memory[0x1D]=1; }
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
        std::copy_n(bytes,size,memory.data()+reg);if(reg==0x10) memory[0x10]&=~8;return true;
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
void ordering_retention_and_single_use() {
    Fixture f;const auto old=f.warm();auto held=f.box.read_latest(f.window,f.time.us);
    const auto sampled=static_cast<std::uint64_t>(f.time.us);f.time.us+=1000;
    unsigned charger_checks=0,gauge_checks=0;
    f.bus.during=[&]{check(f.wire.calls==0,"gauge ran before charger completed");
        const auto r=f.get(f.time.us);check(r.gauge.serial==old.gauge.serial && r.charger.started_ms==old.charger.started_ms,
            "healthy charger refresh changed old record");++charger_checks;};
    f.wire.during=[&]{const auto r=f.get(f.time.us);check(r.gauge.serial==old.gauge.serial &&
        r.gauge.evidence.report.observed_us==old.gauge.evidence.report.observed_us,"healthy gauge refresh withdrew old");++gauge_checks;};
    check(f.refresh()==gc::Refresh::published && charger_checks==55 && gauge_checks==52,"incomplete joint capture");
    const auto next=f.get(f.time.us);check(next.gauge.serial==old.gauge.serial+1,"sole serial not replaced once");
    // Read was linearized before healthy replacement. Use independent read time
    // with a zero-duration capture to exercise the immediate 20ms right.
    check(!held->consume(f.time.us),"read older than one control iteration accepted");
    f.bus.during={};f.wire.during={};f.bus.step=f.wire.step=0;
    auto immediate=f.box.read_latest(f.window,f.time.us);f.time.us+=1;
    check(f.refresh()==gc::Refresh::published,"zero-duration synthetic refresh failed");
    auto previous=immediate->consume(f.time.us);
    check(previous && previous->gauge.serial==next.gauge.serial,"healthy replacement invalidated immediate read");
    check(!immediate->consume(f.time.us),"read consumed twice");
    auto move_from=f.box.read_latest(f.window,f.time.us);auto moved=std::move(*move_from);
    check(!move_from->consume(f.time.us) && moved.consume(f.time.us),"move duplicated consumption");
    check(sampled<static_cast<std::uint64_t>(f.time.us),"fixture chronology");
    for(unsigned extra:{20000,20001}) {
        auto read=f.box.read_latest(f.window,f.time.us);
        check(bool(read->consume(f.time.us+extra))==(extra==20000),"immediate lifetime boundary changed");
    }
    auto backwards=f.box.read_latest(f.window,f.time.us);
    check(!backwards->consume(f.time.us-1) && !backwards->consume(f.time.us),"clock failure retained right");
}
void expiry_and_slow_pair() {
    Fixture f;const auto first=f.warm();
    const auto charger_start=first.charger.started_ms*1000;
    check(f.box.read_latest(f.window,charger_start+250999).has_value(),"actual millisecond age boundary tightened");
    check(!f.box.read_latest(f.window,charger_start+251000),"old charger age renewed");
    // During refresh original age crosses exactly that unchanged boundary.
    f.time.us=static_cast<std::int64_t>(charger_start+250900);f.bus.step=100;
    bool expired=false;f.bus.during=[&]{expired=true;check(!f.box.read_latest(f.window,f.time.us),"old charger hidden by refresh");};
    check(f.refresh()==gc::Refresh::published && expired,"healthy fresh pair failed after prior expiry");
    Fixture slow;slow.warm();slow.time.us+=1000;slow.bus.step=4000;slow.wire.step=1000;
    check(slow.refresh()==gc::Refresh::failed && !slow.box.read_latest(slow.window,slow.time.us),
          "individually valid but jointly stale pair published");
    check(slow.box.failure().kind==gc::FailureKind::lifecycle,"joint age fault lost");
    auto longest=profile();longest.pack.voltage_period_bound_us=500000;
    longest.pack.temperature_period_bound_us=4000000;
    Fixture bounds(longest);bounds.bus.step=bounds.wire.step=0;
    check(bounds.refresh()==gc::Refresh::warming,"cold history bypassed");
    bounds.time.us=6000000;check(bounds.refresh()==gc::Refresh::published,"qualified longest cadence refused");
    const auto r=bounds.get(bounds.time.us);
    check(r.gauge.evidence.report.voltage_earliest_us==5500000 &&
          r.gauge.evidence.report.temperature_earliest_us==2000000,"original ADC bounds restamped");
    check(bounds.box.read_latest(bounds.window,6250000).has_value() &&
          !bounds.box.read_latest(bounds.window,6250001),"250ms/750ms/4.25s boundary changed");
}
void acquisition_failures() {
    for(unsigned position=1;position<=55;++position) {
        Fixture f;f.warm();auto snapshot=f.box.read_latest(f.window,f.time.us);f.bus.fail_at=position;
        bool noticed=false;f.inhibit.callback=[&]{if(f.bus.calls==position) {
            noticed=true;check(!f.box.read_latest(f.window,f.time.us),"charger revocation delayed until return");
            check(f.box.failure().kind==gc::FailureKind::charger && f.box.failure().code==static_cast<unsigned>(ch::Error::bus),
                  "charger primary fault not latched before inhibit");
            f.box.retire(); // Secondary lifecycle cause cannot replace bus failure.
        }};
        check(f.refresh()==gc::Refresh::failed && noticed && f.wire.calls==0 && !snapshot->consume(f.time.us),
              "charger failure allowed gauge or old snapshot");
        f.inhibit.callback={};f.bus.fail_at=0;const auto count=f.bus.calls;
        check(f.refresh()==gc::Refresh::failed && f.bus.calls==count,"later success repaired joint epoch");
    }
    for(unsigned position=1;position<=52;++position) {
        Fixture f;f.warm();f.wire.fail_at=position;bool noticed=false;
        f.wire.on_clock=[&]{if(f.wire.calls==position) {
            noticed=true;check(!f.box.read_latest(f.window,f.time.us),"gauge first failure retained joint pair");
            check(f.box.failure().kind==gc::FailureKind::gauge && f.box.failure().code==static_cast<unsigned>(gc::Fault::bus),
                  "gauge first fault relabelled");
            f.time.us=-1; // Subsequent clock must not replace the first fault.
        }};
        check(f.refresh()==gc::Refresh::failed && noticed && f.wire.calls==position,"gauge failure continued");
    }
    for(unsigned kind=0;kind<4;++kind) {
        Fixture f;f.warm();
        if(kind==0) f.bus.memory[0x48]=0;
        if(kind==1) f.bus.memory[0x1F]=1;
        if(kind==2) f.bus.memory[0x20]=1;
        if(kind==3) f.bus.memory[0x12]=0x40;
        check(f.refresh()==gc::Refresh::failed && f.box.failure().kind==gc::FailureKind::charger,
              "unsafe charger state kept joint evidence");
    }
    Fixture gauge_bad;gauge_bad.warm();gauge_bad.wire.words[0x0F1]=0;
    check(gauge_bad.refresh()==gc::Refresh::failed && gauge_bad.box.failure().kind==gc::FailureKind::gauge,
          "bad gauge guard kept joint evidence");
    const std::array<std::uint16_t,21> bad={2,8,8,2,1,1,0x100,0,0,0,0x8000,0,0,0,0,0,0,1,0,0,0};
    for(bool tail:{false,true}) for(unsigned i=0;i<bad.size();++i) {
        Fixture f;f.warm();const auto position=1+i+(tail ? 31:0);bool noticed=false;
        f.wire.word_hook=[&](unsigned at,std::uint16_t& raw){if(at==position) raw=bad[i];};
        f.wire.on_clock=[&]{if(f.wire.calls==position && !f.box.healthy()) {
            noticed=true;check(!f.box.read_latest(f.window,f.time.us),"late bad guard retained joint pair");
            f.time.us=-1;
        }};
        check(f.refresh()==gc::Refresh::failed && noticed && f.wire.calls==position &&
              f.box.failure().kind==gc::FailureKind::gauge &&
              f.box.failure().code==static_cast<unsigned>(i<7 ? gc::Fault::protection:gc::Fault::profile),
              "joint guard rejection delayed or diagnostic lost");
    }
}
void closure_and_park() {
    for(bool in_gauge:{false,true}) {
        Fixture f;f.warm();auto pending=f.box.read_latest(f.window,f.time.us);bool closed=false;
        auto close=[&]{if(closed) return;closed=true;f.box.close_window(f.window);
            check(!f.box.closure_acknowledged(f.window) && !f.box.open_window(),"reopened before sensor acknowledged");
            check(!pending->consume(f.time.us) && !f.box.read_latest(f.window,f.time.us),"closed window accepted snapshot");};
        if(in_gauge) f.wire.during=close;else f.bus.during=close;
        check(f.refresh()==gc::Refresh::closed && f.box.closure_acknowledged(f.window) && f.box.healthy(),
              "clean close destroyed continuity or republished");
        f.wire.during={};f.bus.during={};
        check(f.session.park_light_sleep(context()),"clean acknowledged closure could not park");
        f.time.us=10000000;check(f.session.resume_light_sleep(context()),"qualified fixture resume failed");
        const auto old=f.window;f.window=f.box.open_window();check(bool(f.window),"reopen failed");
        f.box.close_window(old);check(!f.box.closure_acknowledged(old),"stale close shut newer window");
        check(!f.box.read_latest(f.window,f.time.us),"resume revived presleep record");
        check(f.refresh()==gc::Refresh::published,"fresh post-wake pair lost continuity");
    }
    Fixture fault;fault.warm();fault.wire.fail_at=1;
    fault.wire.during=[&]{fault.box.close_window(fault.window);};
    check(fault.refresh()==gc::Refresh::failed && !fault.box.closure_acknowledged(fault.window) &&
          !fault.session.park_light_sleep(context()),"fault after clean close preserved ticket");
    Fixture bad_park;bad_park.warm();
    check(!bad_park.session.park_light_sleep(context()) && !bad_park.box.healthy(),"park without closure accepted");
}
void binding_and_retirement() {
    Fixture f;f.warm();auto read=f.box.read_latest(f.window,f.time.us);f.box.retire();
    check(!read->consume(f.time.us) && !f.box.open_window(),"retirement retained read/window");
    const auto newer=f.epoch.value();f.box.retire();check(f.epoch.value()==newer,"old retirement cancelled next epoch");
    Fixture external;external.warm();external.epoch.retire();
    check(!external.box.read_latest(external.window,external.time.us),"external epoch change escaped");
    Fixture wrong;wrong.warm();wrong.wire.owner=2;
    check(wrong.refresh()==gc::Refresh::failed && wrong.bus.calls==0,"wrong owner touched charger");
    Fixture context_bad;context_bad.warm();auto changed=context();++changed.monitoring_session;
    check(context_bad.session.refresh(changed,context_bad.window)==gc::Refresh::failed && context_bad.bus.calls==0,
          "changed session accessed bus");
    Fixture legacy;legacy.warm();const auto raw=legacy.session.read(context());
    check(!raw.evidence.report.ready() && !legacy.box.healthy(),"joint session created standalone publication");
    Fixture unqualified({});check(unqualified.refresh()==gc::Refresh::failed && unqualified.bus.calls==0 &&
        unqualified.wire.calls==0,"default profile accessed acquisition hardware");
    Fixture twice;twice.warm();
    gc::OwnedSession second(profile(),context(),twice.wire,twice.epoch,1,twice.box,twice.charger);
    check(!twice.box.healthy() && !second.can_attach(context()),"second producer rebound joint authority");
    static_assert(gc::JointMailbox::successor(UINT32_MAX)==UINT32_MAX);
    static_assert(gc::JointMailbox::successor(UINT32_MAX-1)==UINT32_MAX);
    static_assert(!std::is_copy_constructible_v<gc::JointRead>);
}
// Deterministic backend pauses let retirement run while commit/copy is locked.
void retire_at_gate_boundary() {
    for(unsigned kind=0;kind<2;++kind) {
        Fixture f;f.warm();f.bus.step=f.wire.step=0;f.time.us+=1;
        unsigned exits=0;bool fired=false;
        f.gate.before_unlock=[&] {
            ++exits;
            // refresh: begin exit, commit exit, finish exit. read: one exit.
            if(exits==(kind==0 ? 2U:1U)) { fired=true;f.box.retire(); }
        };
        if(kind==0) check(f.refresh()==gc::Refresh::failed,"retirement at commit republished epoch");
        else check(!f.box.read_latest(f.window,f.time.us),"retirement during copy yielded snapshot");
        f.gate.before_unlock={};check(fired && !f.box.healthy(),"boundary was not exercised");
    }
}
void serial_and_body_commit_together() {
    Fixture f;const auto previous=f.warm();f.bus.step=f.wire.step=0;f.time.us+=1;
    unsigned entries=0;bool checked=false;
    f.gate.before_lock=[&] {
        if(++entries!=2) return; // begin, then final joint commit, before lock.
        const auto r=f.get(f.time.us); // Nested read enters at #3, not #2.
        checked=true;
        check(r.gauge.serial==previous.gauge.serial &&
              r.gauge.evidence.report.observed_us==previous.gauge.evidence.report.observed_us,
              "accepted serial escaped body commit gate");
    };
    check(f.refresh()==gc::Refresh::published && checked,"joint commit boundary not exercised");
    f.gate.before_lock={};
}
void concurrent_readers() {
    Fixture f;f.wire.words[0x006]=0;f.warm();f.bus.step=f.wire.step=0;
    std::atomic<bool> done{false};std::atomic<unsigned> reads{0};
    std::mutex start_mutex;std::condition_variable start_cv;unsigned started=0;
    const auto now=static_cast<std::uint64_t>(f.time.us); // Stable fake time, no racing clock access.
    const auto reader=[&]{
      { std::lock_guard<std::mutex> lock(start_mutex);++started;start_cv.notify_all(); }
      while(!done.load(std::memory_order_acquire)) {
        auto r=f.box.read_latest(f.window,now+1000);
        if(r) { auto value=r->consume(now+1000);if(value) {
            check(value->gauge.serial && value->gauge.epoch==1 && value->window.value==f.window.value,
                  "torn joint metadata");
            check(value->charger.finished_ms*1000<=value->gauge.evidence.report.observed_us,
                  "torn charger/gauge order");++reads;
            check(value->gauge.evidence.report.soc_percent.value()==(value->charger.source_present() ? 1:0),
                  "mixed collection cycles");
            check(value->gauge.evidence.report.soc_percent.value()==(value->gauge.serial-1)%2,
                  "mixed accepted serial and body");
        }}
    }};
    std::thread a(reader),b(reader);
    { std::unique_lock<std::mutex> lock(start_mutex);start_cv.wait(lock,[&]{return started==2;}); }
    for(unsigned i=0;i<500;++i) {
        f.time.us=static_cast<std::int64_t>(now+i+1);
        f.bus.memory[0x1B]=(i+1)%2;f.wire.words[0x006]=((i+1)%2)*256;
        check(f.refresh()==gc::Refresh::published,"producer failed");
    }
    done.store(true,std::memory_order_release);a.join();b.join();check(reads>0,"no concurrent reads exercised");
}
void blocked_owner_close() {
    for(bool fault:{false,true}) {
        Fixture f;f.warm();std::mutex mutex;std::condition_variable cv;
        bool blocked=false,resume=false;
        f.wire.during=[&] {
            if(f.wire.calls!=1) return;
            std::unique_lock<std::mutex> lock(mutex);blocked=true;cv.notify_all();
            cv.wait(lock,[&]{return resume;});
        };
        gc::Refresh result=gc::Refresh::warming;
        std::thread owner([&]{result=f.refresh();});
        { std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return blocked;}); }
        // Producer is inside a synchronous transport call, holding no gate.
        if(fault) f.box.retire();else f.box.close_window(f.window);
        check(!f.box.read_latest(f.window,f.time.us) && !f.box.open_window() &&
              !f.box.closure_acknowledged(f.window),"blocked owner left publication or reopened");
        { std::lock_guard<std::mutex> lock(mutex);resume=true;cv.notify_all(); }
        owner.join();
        check(result==(fault ? gc::Refresh::failed:gc::Refresh::closed),"blocked owner result wrong");
        check(f.box.closure_acknowledged(f.window)==!fault,"closure acknowledgment lost fault distinction");
    }
}
}
int main() {
    ordering_retention_and_single_use();expiry_and_slow_pair();acquisition_failures();closure_and_park();
    binding_and_retirement();retire_at_gate_boundary();serial_and_body_commit_together();
    concurrent_readers();blocked_owner_close();
    std::cout<<"joint publication, charger-first faults, closure, snapshot lifetime and concurrent readers passed\n";
}
