// Synthetic plant and qualifications ONLY for local protocol tests. Never built
// into the production transport library. The queue/session/executor are shared
// production code; DTLS is libcoap/OpenSSL, not an ESP32/OpenThread radio peer.
#include "common.hpp"
#include "smart_blinds/motion_runtime.hpp"
#include "smart_blinds/clock_protocol.hpp"
#include "smart_blinds/radio_window.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <memory>
#include <thread>
#include <ctime>
#include <limits>

namespace sbthread {
namespace {
std::uint64_t mono_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
blinds::Calibration calibration(double low,double high,double counts) {
    blinds::Calibration c;
    const blinds::Knot knots[]={{0,low},{counts,high}};
    c.assign(knots,2,7); return c;
}
blinds::BenchMotionProfile profile() {
    blinds::BenchMotionProfile p;
    p.bench_qualified=p.holding_qualified=true; p.qualification_id=123;
    p.feedforward=.00025; return p;
}
// Fixture-only operation attribution. These stamps observe the exact existing
// executor before/call/after envelope; they never replace or advance its clock.
enum class IoOperation : unsigned { none,parked,request,charge,coast,wdi,encoder,
    counter_start,counter_stop,awake,pwm,heartbeat };
constexpr std::uint64_t no_cpu=std::numeric_limits<std::uint64_t>::max();
std::uint64_t thread_cpu_ns() {
    timespec t{};
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)!=0) return no_cpu;
    return static_cast<std::uint64_t>(t.tv_sec)*1000000000ULL+static_cast<std::uint64_t>(t.tv_nsec);
}
struct IoTrace {
    unsigned operation=0;
    std::uint64_t before=0,entered=0,returned=0,after=0,cpu_before=no_cpu,cpu_after=no_cpu;
    bool ok=false;
    unsigned injected=0;
    bool ordered() const { return before<=entered && entered<=returned && returned<=after; }
    std::uint64_t wall() const { return after>=before ? after-before : 0; }
    bool cpu_valid() const { return cpu_before!=no_cpu && cpu_after!=no_cpu && cpu_after>=cpu_before; }
};
struct Plant : blinds::MotionIo,blinds::CounterOrigin {
    bool off=true,counter=false,rail=false,awake=false;
    double count=500,duty=0;
    int direction=0;
    std::uint64_t epoch=0,last=mono_us();
    mutable std::uint64_t previous_read_us=0,previous_cpu_ns=no_cpu,max_read_gap_us=0;
    mutable bool reversed_read=false,inside_io=false;
    mutable IoTrace pending{},first_bad{};
    mutable unsigned after_return_wait_us=0;
    // High16 target operation, next16 probe kind, low32 duration. Only the
    // control owner consumes this atomic test request; no plant state races.
    std::atomic<std::uint64_t> io_probe{0};
    void begin_cycle() { max_read_gap_us=0; reversed_read=false; }
    std::uint64_t now_us() const override {
        if(pending.operation && !inside_io && after_return_wait_us) {
            const auto wait=after_return_wait_us; after_return_wait_us=0;
            std::this_thread::sleep_for(std::chrono::microseconds(wait));
        }
        const auto now=mono_us();
        const auto cpu=thread_cpu_ns();
        if(pending.operation && !inside_io) {
            pending.after=now; pending.cpu_after=cpu;
            if(!first_bad.operation && (!pending.ok || !pending.ordered() ||
                pending.wall()>blinds::MotionExecutor::io_budget_us)) first_bad=pending;
            pending={};
        }
        if(previous_read_us) {
            if(now<previous_read_us) reversed_read=true;
            else max_read_gap_us=std::max(max_read_gap_us,now-previous_read_us);
        }
        previous_read_us=now; previous_cpu_ns=cpu;
        return now;
    }
    template<class F> bool operation(IoOperation id,F call) {
        IoTrace trace;
        trace.operation=static_cast<unsigned>(id);
        trace.before=previous_read_us; trace.cpu_before=previous_cpu_ns;
        trace.entered=mono_us();
        inside_io=true;
        auto probe=io_probe.load();
        if((probe>>48)==trace.operation && io_probe.compare_exchange_strong(probe,0)) {
            trace.injected=static_cast<unsigned>((probe>>32)&0xffff);
            const auto delay=static_cast<unsigned>(probe&0xffffffff);
            if(trace.injected==1) std::this_thread::sleep_for(std::chrono::microseconds(delay));
            if(trace.injected==2) after_return_wait_us=delay;
        }
        trace.ok=call();
        if(trace.injected==3) trace.ok=false;
        trace.returned=mono_us();
        inside_io=false; pending=trace;
        return trace.ok;
    }
    void advance() {
        const auto now=now_us();
        if(!off && counter) count+=direction*duty*4000*(now-last)/1000000.0;
        last=now;
    }
    bool parked_off() override { return operation(IoOperation::parked,[&]{return off && !counter && !rail && !awake && duty==0;}); }
    bool request_n(bool high) override { return operation(IoOperation::request,[&]{advance();off=high;return true;}); }
    bool charge_off() override { return operation(IoOperation::charge,[]{return true;}); }
    bool coast() override { return operation(IoOperation::coast,[&]{advance();duty=0;direction=0;return true;}); }
    bool wdi_high() override { return operation(IoOperation::wdi,[]{return true;}); }
    bool encoder_power(bool value) override { return operation(IoOperation::encoder,[&]{rail=value;return true;}); }
    bool counter_start(std::uint64_t value) override { return operation(IoOperation::counter_start,[&]{counter=rail && epoch==value;return counter;}); }
    bool counter_stop() override { return operation(IoOperation::counter_stop,[&]{counter=false;return true;}); }
    bool awake_lock(bool held) override { return operation(IoOperation::awake,[&]{awake=held;return true;}); }
    bool pwm(int dir,double value) override { return operation(IoOperation::pwm,[&]{
        advance();
        if(off || !counter || (dir!=1 && dir!=-1) || value<0 || value>.5) return false;
        direction=dir; duty=value; return true;
    }); }
    bool heartbeat_pulse() override { return operation(IoOperation::heartbeat,[&]{return !off;}); }
    bool set_counter_origin(std::uint64_t value,double origin) override {
        if(!off || counter) return false;
        epoch=value; count=origin; return true;
    }
};
blinds::runtime::Power power(std::uint64_t now,bool good) {
    blinds::runtime::Power p;
    if(!good) return p;
    p.window=1; p.gauge.state=blinds::power::State::ready; p.gauge.observed_us=now;
    p.gauge.voltage_earliest_us=now-400000; p.gauge.temperature_earliest_us=now-3200000;
    p.gauge.pack_binding=77; p.gauge.pack_v=11.1; p.gauge.soc_percent=65;
    p.charger.error=smart_blinds::charger::Error::none;
    p.charger.started_ms=p.charger.finished_ms=now/1000;
    return p;
}
}
class MotionPeer {
public:
    coap_context_t* context=nullptr;
    coap_session_t* peer=nullptr; // Network owner only, borrowed from context.
    coap_dtls_spsk_t setup{};
    std::array<std::uint8_t,32> key{};
    std::string identity;
    std::uint64_t boot;
    std::atomic<bool> stop{false};
    std::atomic<std::uint64_t> body_bytes{0};
    std::atomic<unsigned> mode{0},requests{0}; // bit0 pause control, bit1 failed power, bit2 freeze report.
    std::atomic<bool> off{true},paused{false};
    std::atomic<unsigned> executor_fault{0};
    std::uint64_t previous_cycle_start=0,previous_cycle_end=0;
    std::atomic<std::uint64_t> fault_start_gap_us{0},fault_end_gap_us{0},fault_duration_us{0};
    std::atomic<unsigned> stall_next_us{0},first_executor_fault{0};
    std::atomic<std::uint64_t> fault_read_gap_us{0};
    std::atomic<bool> fault_read_reversed{false};
    std::array<std::atomic<std::uint64_t>,11> fault_io{};
    std::thread network_worker,control_worker;
    std::mutex publication;
    blinds::MotionSession::Inbox inbox;
    blinds::runtime::Ingress ingress;
    smart_blinds::RadioWindow window;
    smart_blinds::ClockProbes probes;
    Plant plant;
    blinds::MotionSession motion;
    blinds::runtime::Snapshot snapshot{};
    blinds::runtime::Power observed{};
    char frozen[768]{};
    explicit MotionPeer(std::uint64_t nonce,double low=0,double high=100,double counts=1000) : boot(nonce),inbox(nonce),ingress(inbox),window(nonce),
        probes(nonce,{1000,2,true}),motion(plant,plant,calibration(low,high,counts),{},profile(),nonce) {
        plant.count=(50-low)*counts/(high-low);
        window.attached(true,mono_us()/1000);
        // Test-only evidence: there is no corresponding production network API.
        motion.establish_reference({true,boot,1,mono_us(),77,7,plant.count});
    }
    ~MotionPeer() {
        stop=true;
        if(network_worker.joinable()) network_worker.join();
        if(control_worker.joinable()) control_worker.join();
        if(context) coap_free_context(context);
        OPENSSL_cleanse(key.data(),key.size());
    }
    bool radio() {
        window.advance(mono_us()/1000);
        const bool awake=window.rx_on_when_idle() || snapshot.status.awake_required;
        ingress.radio(true,awake); return awake;
    }
    static const coap_bin_const_t* validate(coap_bin_const_t* id,coap_session_t*,void* arg) {
        auto& self=*static_cast<MotionPeer*>(arg);
        if(id->length!=self.identity.size() || CRYPTO_memcmp(id->s,self.identity.data(),id->length)) return nullptr;
        return &self.setup.psk_info.key;
    }
    static int event(coap_session_t* session,coap_event_t event) {
        auto* self=static_cast<MotionPeer*>(coap_get_app_data(coap_session_get_context(session)));
        if(!self) return 0;
        std::lock_guard<std::mutex> lock(self->publication);
        if(event==COAP_EVENT_DTLS_CONNECTED && cipher_matches(session)) {
            // Match C6 single-peer semantics: a new connection invalidates the
            // old generation; requests from the superseded session are rejected.
            self->peer=session; self->ingress.connected();
        } else if((event==COAP_EVENT_DTLS_CLOSED || event==COAP_EVENT_DTLS_ERROR) && self->peer==session) {
            self->peer=nullptr; self->ingress.disconnected();
        }
        return 0;
    }
    static void handler(coap_resource_t* resource,coap_session_t* session,const coap_pdu_t* request,
                        const coap_string_t*,coap_pdu_t* response) {
        auto& self=*static_cast<MotionPeer*>(coap_resource_get_userdata(resource));
        std::lock_guard<std::mutex> lock(self.publication);
        if(self.peer!=session || !cipher_matches(session) || coap_pdu_get_type(request)!=COAP_MESSAGE_CON) {
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_UNAUTHORIZED); return;
        }
        ++self.requests;
        const auto received=mono_us();
        const bool awake=self.radio();
        self.probes.advance(received,awake);
        std::size_t size=0; const std::uint8_t* body=nullptr;
        coap_get_data(request,&size,&body);
        self.body_bytes+=size;
        const auto* path=coap_resource_get_uri_path(resource);
        const std::string name(reinterpret_cast<const char*>(path->s),path->length);
        char reply[768]{};
        const auto bad=[&] { coap_pdu_set_code(response,COAP_RESPONSE_CODE_BAD_REQUEST); };
        coap_pdu_set_code(response,COAP_RESPONSE_CODE_CONTENT);
        if(name=="v1/status") {
            if(size) { bad(); return; }
            std::snprintf(reply,sizeof(reply),"{\"boot\":\"%016llx\",\"last_wake\":\"%016llx\",\"awake\":%s,\"io_qualified\":true,\"clock_qualified\":%s}",
                static_cast<unsigned long long>(self.boot),static_cast<unsigned long long>(self.window.last_sequence()),
                awake?"true":"false",self.ingress.snapshot(received).clock?"true":"false");
        } else if(name=="v1/wake") {
            if(size!=16 || !self.window.wake(read64(body),read64(body+8),received/1000)) { bad(); return; }
            self.radio();
            std::snprintf(reply,sizeof(reply),"{\"awake_ms\":10000,\"io_qualified\":true}");
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else if(name=="v1/clock") {
            if(size!=16 || !self.probes.begin(read64(body),read64(body+8),received,awake)) { bad(); return; }
            const auto sent=mono_us();
            if(!self.probes.sent(sent,awake)) { bad(); return; }
            std::snprintf(reply,sizeof(reply),"{\"boot\":\"%016llx\",\"probe\":\"%016llx\",\"received_us\":\"%016llx\",\"sent_us\":\"%016llx\"}",
                static_cast<unsigned long long>(self.boot),static_cast<unsigned long long>(self.probes.sequence()),
                static_cast<unsigned long long>(received),static_cast<unsigned long long>(sent));
        } else if(name=="v1/qualify") {
            if(size!=32 || !self.probes.assess(read64(body),read64(body+8),read64(body+16),read64(body+24),received,awake)) {
                self.ingress.clear_clock(); bad(); return;
            }
            self.ingress.qualify(read64(body+8),self.probes.bounds(),mono_us());
            smart_blinds::clock_readiness_json(reply,sizeof(reply),self.boot,self.probes,mono_us(),awake);
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else if(name=="v1/readiness") {
            if(size) { bad(); return; }
            smart_blinds::clock_readiness_json(reply,sizeof(reply),self.boot,self.probes,mono_us(),awake);
        } else if(name=="v1/motion") {
            using R=blinds::runtime::Ingress::Result;
            const auto result=self.ingress.submit(body,size,true,received);
            if(result!=R::queued) {
                coap_pdu_set_code(response,result==R::malformed ? COAP_RESPONSE_CODE_BAD_REQUEST : COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);
                return;
            }
            std::snprintf(reply,sizeof(reply),"{\"queued\":true}");
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else {
            if(size) { bad(); return; }
            if((self.mode.load()&4U) && self.frozen[0]) std::strcpy(reply,self.frozen);
            else {
                blinds::runtime::status_json(reply,sizeof(reply),self.boot,self.snapshot,self.observed,
                    self.ingress.snapshot(mono_us()),true,mono_us());
                if(self.mode.load()&4U) std::strcpy(self.frozen,reply);
                else self.frozen[0]=0;
            }
        }
        const std::uint8_t json=COAP_MEDIATYPE_APPLICATION_JSON;
        coap_add_option(response,COAP_OPTION_CONTENT_FORMAT,1,&json);
        self.body_bytes+=std::strlen(reply);
        coap_add_data(response,std::strlen(reply),reinterpret_cast<const std::uint8_t*>(reply));
    }
    bool start(std::uint16_t port,const char* id,const std::uint8_t* psk) {
        if(!port || !boot || !identity_valid(id) || !psk) return false;
        identity=id; std::copy_n(psk,32,key.begin());
        context=coap_new_context(nullptr);
        if(!context) return false;
        coap_set_app_data(context,this); coap_register_event_handler(context,event);
        setup.version=COAP_DTLS_SPSK_SETUP_VERSION; setup.psk_info.key={key.size(),key.data()};
        setup.validate_id_call_back=validate; setup.id_call_back_arg=this;
        if(!coap_context_set_psk2(context,&setup)) return false;
        coap_address_t local; address(local,"::1",port);
        if(!coap_new_endpoint(context,&local,COAP_PROTO_DTLS)) return false;
        for(const char* name:{"v1/status","v1/wake","v1/clock","v1/qualify","v1/readiness","v1/motion","v1/motion-status"}) {
            auto* resource=coap_resource_init(coap_make_str_const(name),0);
            if(!resource) return false;
            coap_resource_set_userdata(resource,this);
            const bool get=std::strcmp(name,"v1/status")==0 || std::strcmp(name,"v1/readiness")==0 || std::strcmp(name,"v1/motion-status")==0;
            coap_register_handler(resource,get?COAP_REQUEST_GET:COAP_REQUEST_POST,handler);
            coap_add_resource(context,resource);
        }
        control_worker=std::thread([this] {
            std::uint64_t sequence=0;
            auto deadline=std::chrono::steady_clock::now();
            while(!stop) {
                deadline+=std::chrono::milliseconds(10);
                const bool pause=(mode.load()&1U)!=0;
                paused=pause;
                if(!pause) {
                    // Test-only wall-clock stall; no virtual time or catch-up samples.
                    if(const auto stall=stall_next_us.exchange(0))
                        std::this_thread::sleep_for(std::chrono::microseconds(stall));
                    blinds::runtime::Network net;
                    { std::lock_guard<std::mutex> lock(publication); radio(); net=ingress.snapshot(mono_us()); }
                    plant.begin_cycle();
                    plant.advance();
                    const auto now=mono_us();
                    const auto p=power(now,!(mode.load()&2U));
                    const blinds::FastObservation fast{true,plant.counter,false,false,++sequence,now,plant.epoch,plant.count,.1};
                    const auto before=mono_us();
                    const auto status=motion.cycle(inbox,blinds::runtime::input(fast,p,net,now));
                    const auto after=mono_us();
                    if(!first_executor_fault && motion.executor_fault()!=blinds::MotionExecutor::Fault::none) {
                        fault_start_gap_us=before-previous_cycle_start;
                        fault_end_gap_us=before-previous_cycle_end;
                        fault_duration_us=after-before;
                        fault_read_gap_us=plant.max_read_gap_us;
                        fault_read_reversed=plant.reversed_read;
                        const auto& io=plant.first_bad;
                        const std::uint64_t metrics[]={io.operation,io.before,io.entered,io.returned,io.after,
                            io.wall(),io.cpu_valid()?io.cpu_after-io.cpu_before:0,
                            io.cpu_valid(),io.ok,io.ordered(),io.injected};
                        for(std::size_t i=0;i<fault_io.size();++i) fault_io[i]=metrics[i];
                        first_executor_fault=static_cast<unsigned>(motion.executor_fault());
                    }
                    previous_cycle_start=before;previous_cycle_end=after;
                    off=plant.off;
                    executor_fault=static_cast<unsigned>(motion.executor_fault());
                    { std::lock_guard<std::mutex> lock(publication); snapshot={status,net.connection,net.probe}; observed=p; }
                }
                std::this_thread::sleep_until(deadline);
                // Do not replay missed periods as fresh samples.
                if(deadline<std::chrono::steady_clock::now()-std::chrono::milliseconds(10)) deadline=std::chrono::steady_clock::now();
            }
        });
        network_worker=std::thread([this] { while(!stop) if(coap_io_process(context,5)<0) break; });
        return true;
    }
};
}
extern "C" {
void* sb_motion_peer_new(std::uint16_t port,const char* id,const std::uint8_t* key,std::uint64_t boot) {
    sbthread::initialize();
    try { auto peer=std::make_unique<sbthread::MotionPeer>(boot); if(!peer->start(port,id,key)) return nullptr; return peer.release(); }
    catch(...) { return nullptr; }
}
void* sb_motion_peer_new_geometry(std::uint16_t port,const char* id,const std::uint8_t* key,
                                  std::uint64_t boot,double low,double high,double counts) {
    sbthread::initialize();
    if(!std::isfinite(low) || !std::isfinite(high) || !std::isfinite(counts) ||
       low>=50 || high<=50 || counts<100 || counts>10000) return nullptr;
    try { auto peer=std::make_unique<sbthread::MotionPeer>(boot,low,high,counts);
        if(!peer->start(port,id,key)) return nullptr;
        return peer.release(); }
    catch(...) { return nullptr; }
}
std::uint64_t sb_motion_peer_body_bytes(void* p) { return static_cast<sbthread::MotionPeer*>(p)->body_bytes; }
void sb_motion_peer_free(void* p) { delete static_cast<sbthread::MotionPeer*>(p); }
bool sb_motion_peer_mode(void* p,unsigned value) {
    auto& peer=*static_cast<sbthread::MotionPeer*>(p);
    peer.mode=value;
    if(value&1U) {
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(50);
        while(!peer.paused && std::chrono::steady_clock::now()<deadline)
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        return peer.paused;
    }
    return true;
}
unsigned sb_motion_peer_requests(void* p) { return static_cast<sbthread::MotionPeer*>(p)->requests; }
unsigned sb_motion_peer_executor_fault(void* p) { return static_cast<sbthread::MotionPeer*>(p)->executor_fault; }
std::uint64_t sb_motion_peer_timing(void* p,unsigned metric) {
    auto& peer=*static_cast<sbthread::MotionPeer*>(p);
    switch(metric) {
    case 0:return peer.fault_start_gap_us;
    case 1:return peer.fault_end_gap_us;
    case 2:return peer.fault_duration_us;
    case 3:return peer.fault_read_gap_us;
    case 4:return peer.fault_read_reversed;
    case 5:return peer.first_executor_fault;
    default:return 0;
    }
}
bool sb_motion_peer_stall_next(void* p,unsigned us) {
    if(us<20001 || us>100000) return false;
    auto& peer=*static_cast<sbthread::MotionPeer*>(p);
    unsigned expected=0;
    return peer.stall_next_us.compare_exchange_strong(expected,us);
}
std::uint64_t sb_motion_peer_io_timing(void* p,unsigned metric) {
    auto& peer=*static_cast<sbthread::MotionPeer*>(p);
    return metric<peer.fault_io.size()?peer.fault_io[metric].load():0;
}
bool sb_motion_peer_io_probe_next(void* p,unsigned operation,unsigned kind,unsigned us) {
    if(!operation || operation>static_cast<unsigned>(sbthread::IoOperation::heartbeat) ||
       kind<1 || kind>3 || (kind==3 ? us!=0 : us<101 || us>10000)) return false;
    auto& peer=*static_cast<sbthread::MotionPeer*>(p);
    std::uint64_t expected=0;
    const auto probe=(static_cast<std::uint64_t>(operation)<<48)|(static_cast<std::uint64_t>(kind)<<32)|us;
    return peer.plant.io_probe.compare_exchange_strong(expected,probe);
}
bool sb_motion_peer_off(void* p) { return static_cast<sbthread::MotionPeer*>(p)->off; }
}
