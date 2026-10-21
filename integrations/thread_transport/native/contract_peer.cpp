// Loopback-only scripted APPLICATION contract. No executor or physical evidence.
#include "common.hpp"
#include "smart_blinds/motion_runtime.hpp"
#include "smart_blinds/clock_protocol.hpp"
#include "smart_blinds/radio_window.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <memory>
#include <thread>
#include <vector>

namespace sbcontract {
using Phase=blinds::MotionSession::Phase;
using Result=blinds::MotionSession::Result;
using Kind=blinds::wire::Kind;
static std::uint64_t now_us() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
struct Trace { std::uint64_t at,command,message; unsigned event; };
struct Decoded { std::uint64_t received,connection; blinds::wire::Request request; };
class Peer {
public:
    coap_context_t* context=nullptr;
    coap_session_t* owner=nullptr;
    coap_dtls_spsk_t setup{};
    std::array<std::uint8_t,32> key{};
    std::string identity;
    const std::uint64_t boot;
    const bool qualified;
    const std::int64_t low_um,high_um;
    const std::uint32_t max_speed_um_s,max_acceleration_um_s2;
    std::atomic<bool> stop{false};
    std::thread network;
    std::mutex gate;
    blinds::MotionSession::Inbox inbox;
    blinds::runtime::Ingress ingress;
    smart_blinds::ClockProbes probes;
    smart_blinds::RadioWindow window;
    blinds::wire::Projection projection;
    blinds::runtime::Snapshot snapshot{};
    blinds::runtime::Power power{};
    std::uint64_t nonce=0,lease_until=0,lease_origin=0,lease_error=0,last_sent=0,start_local=0,session_until=0;
    std::uint64_t last_published=0;
    std::int64_t target_um=0;
    bool synthetic_off=true;
    unsigned connections=0,requests=0;
    std::vector<Trace> trace;
    std::array<std::uint64_t,8> active_clock{};
    std::array<std::uint64_t,20> first_fault{};
    std::vector<Decoded> decoded; // Read-only, bounded accepted-request evidence.

    Peer(std::uint64_t b,bool q,std::int64_t low=0,std::int64_t high=100000,
         std::uint32_t speed=30000,std::uint32_t acceleration=60000):boot(b),qualified(q),
        low_um(low),high_um(high),max_speed_um_s(speed),max_acceleration_um_s2(acceleration),inbox(b),ingress(inbox),
        probes(b,{10000,1000,true}),window(b) {
        const auto now=now_us();window.attached(true,now/1000);
        auto& s=snapshot.status;s.phase=q?Phase::idle:Phase::unreferenced;
        s.reference_valid=q;s.height_mm=q?std::optional<double>(50):std::nullopt;
        s.observed_us=now;last_published=now;
    }
    ~Peer() {
        stop=true;if(network.joinable()) network.join();
        if(context) coap_free_context(context);
        OPENSSL_cleanse(key.data(),key.size());
    }
    void record(unsigned event,std::uint64_t now,std::uint64_t message=0) {
        if(trace.size()<4096) trace.push_back({now,snapshot.status.command,message,event});
        else fault(Result::deadline,now);
    }
    bool active() const {
        const auto p=snapshot.status.phase;
        return p==Phase::preparing || p==Phase::ready || p==Phase::committed || p==Phase::moving;
    }
    void fault(Result reason,std::uint64_t now,unsigned predicate=0) {
        auto& s=snapshot.status;
        if(s.phase!=Phase::fault) {
            // Capture once, using the already sampled caller time and computed
            // active-clock bounds. No clock read, network access or new predicate.
            first_fault={now,s.command,s.last_message,static_cast<std::uint64_t>(reason),predicate,
                static_cast<std::uint64_t>(s.phase),lease_until,lease_origin,lease_error,last_sent,start_local,session_until,
                active_clock[0],active_clock[1],active_clock[2],active_clock[3],active_clock[4],active_clock[5],active_clock[6],active_clock[7]};
            s.phase=Phase::fault;s.result=reason;s.reference_valid=false;s.height_mm.reset();s.ready=false;
            s.awake_required=false;s.observed_us=now;synthetic_off=false;
            if(trace.size()<4096) trace.push_back({now,s.command,s.last_message,90});
        }
    }
    bool radio(std::uint64_t now) {
        window.advance(now/1000);
        const bool awake=window.rx_on_when_idle() || snapshot.status.awake_required;
        ingress.radio(true,awake);probes.advance(now,awake);return awake;
    }
    void publish(std::uint64_t now) {
        if(now<=last_published) return;
        last_published=now;auto& s=snapshot.status;s.observed_us=now;
        const auto net=ingress.snapshot(now);snapshot.connection=net.connection;snapshot.probe=net.probe;
        // Explicitly synthetic continuously sampled fixture state, never a gauge.
        power={};
        if(qualified && s.reference_valid && s.phase!=Phase::fault) {
            power.window=1;power.gauge.state=blinds::power::State::ready;
            power.gauge.observed_us=now;power.gauge.voltage_earliest_us=now-400000;
            power.gauge.temperature_earliest_us=now-3200000;power.gauge.pack_binding=77;
            power.gauge.pack_v=11.1;power.gauge.soc_percent=65;
            power.charger.error=smart_blinds::charger::Error::none;
            power.charger.started_ms=power.charger.finished_ms=now/1000;
        }
    }
    bool source(const blinds::wire::Request& r,const blinds::runtime::Network& net,std::uint64_t now) {
        if(!net.clock || !net.probe || r.probe!=net.probe) return false;
        const auto t=projection.at(*net.clock,now);
        if(!t || t->error_us>10000) return false;
        return r.sent_us>t->host_us ? r.sent_us-t->host_us<=t->error_us :
            t->host_us-r.sent_us<=blinds::MotionSession::message_age_us-t->error_us;
    }
    bool renew(const blinds::wire::Request& r,const blinds::runtime::Network& net,std::uint64_t now) {
        if(!net.clock || r.sent_us<=last_sent) return false;
        const auto bound=projection.at(*net.clock,now+blinds::MotionSession::message_age_us+300000);
        const auto local=projection.local(r.sent_us);
        // Match the existing conservative source lease: no receipt-time refresh.
        if(!bound || (bound->error_us+999)/1000+1>10 || !local || *local<bound->error_us) return false;
        const auto until=*local-bound->error_us+300000;
        if(until<=now || until-now<=blinds::MotionExecutor::cycle_max_us+blinds::MotionExecutor::cycle_budget_us) return false;
        lease_until=until;lease_origin=*local;lease_error=bound->error_us;last_sent=r.sent_us;return true;
    }
    void consume(const blinds::wire::Envelope& e,std::uint64_t now) {
        auto& s=snapshot.status;const auto& r=e.request;
        s.last_message=r.message;record(10+static_cast<unsigned>(r.kind),now,r.message);
        const auto net=ingress.snapshot(now);
        if(!e.authenticated || !e.connection || e.connection!=net.connection) { fault(Result::connection,now);return; }
        if(e.received_us>now || now-e.received_us>blinds::MotionSession::queue_age_us) { fault(Result::invalid,now);return; }
        if(!qualified || !s.reference_valid) { fault(Result::unqualified,now);return; }
        if(s.phase==Phase::fault) return;
        // Terminal scripts stay terminal despite a late ordinary request, as in
        // the real session. The Inbox still burns the authenticated message ID.
        if(s.phase==Phase::settling || (s.phase==Phase::idle && s.command && r.kind!=Kind::prepare)) return;
        if(r.kind==Kind::prepare && s.phase==Phase::idle && net.clock) projection.bind(*net.clock,now);
        if(!net.attached || !net.awake || !source(r,net,now)) { fault(Result::stale,now);return; }
        if(r.calibration!=7) { fault(Result::invalid,now);return; }
        if(r.kind==Kind::prepare) {
            if(s.phase!=Phase::idle || r.command<=s.command || !s.height_mm ||
               r.origin_um<low_um || r.origin_um>high_um || r.target_um<low_um || r.target_um>high_um ||
               r.speed_um_s>max_speed_um_s || r.acceleration_um_s2>max_acceleration_um_s2 ||
               std::abs(r.origin_um/1000.-*s.height_mm)>5) { fault(Result::invalid,now);return; }
            const auto local=projection.local(r.start_us);
            const auto t=projection.at(*net.clock,now);
            blinds::Limits limits{};
            if(!local || !t || r.start_us<=t->host_us ||
               (r.start_us+999)/1000-t->host_us/1000<limits.min_prepare_lead_ms+30 ||
               (r.start_us+999)/1000-t->host_us/1000>limits.max_prepare_lead_ms) { fault(Result::deadline,now);return; }
            last_sent=0;if(!renew(r,net,now)) { fault(Result::stale,now);return; }
            s.command=r.command;s.phase=Phase::preparing;s.result=Result::accepted;
            s.awake_required=true;s.ready=false;synthetic_off=false;
            blinds::Trajectory trajectory;
            if(!trajectory.configure(r.origin_um/1000.,r.target_um/1000.,r.speed_um_s/1000.,r.acceleration_um_s2/1000.)) {
                fault(Result::invalid,now);return;
            }
            const auto duration=static_cast<std::uint64_t>(std::ceil(trajectory.duration_s()*1e6));
            if(*local<now || *local-now+duration+2500000>blinds::MotionSession::max_session_us) {
                fault(Result::deadline,now);return;
            }
            start_local=*local;session_until=start_local+duration+2500000;target_um=r.target_um;
            record(21,now,r.message);return;
        }
        if(r.command!=s.command) { fault(Result::invalid,now);return; }
        if(r.kind==Kind::lease) {
            if(!renew(r,net,now)) fault(Result::stale,now);
        } else if(r.kind==Kind::commit) {
            if(s.phase!=Phase::ready || lease_until<=now || start_local<=now) { fault(Result::deadline,now);return; }
            s.phase=Phase::committed;s.ready=false;record(23,now,r.message);
        }
    }
    void advance(std::uint64_t now) {
        radio(now);auto& s=snapshot.status;
        // STOP is inspected before the ordinary inbox and does not renew leases.
        if(inbox.stop_pending()) {
            inbox.discard();s.last_message=ingress.received_message();record(14,now,s.last_message);
            if(active()) {s.phase=Phase::settling;s.result=Result::stopped;s.ready=false;record(25,now);}
        }
        if(active()) {
            const auto net=ingress.snapshot(now);
            if(!net.attached || !net.awake || !net.connection) fault(Result::connection,now);
            else {
                const auto current=net.clock?projection.at(*net.clock,now):std::nullopt;
                const auto lifetime=net.clock?projection.at(*net.clock,now+blinds::MotionSession::message_age_us+300000):std::nullopt;
                active_clock={current?1u:0u,lifetime?1u:0u,current?current->error_us:0,lifetime?lifetime->error_us:0,
                    net.probe,net.clock?net.clock->device_reference_us():0,
                    net.clock?static_cast<std::uint64_t>(net.clock->lower_us()):0,net.clock?static_cast<std::uint64_t>(net.clock->upper_us()):0};
                if(!current || !lifetime || (lifetime->error_us+999)/1000+1>10 || lease_origin<lifetime->error_us)
                    fault(Result::clock,now,!current?1:!lifetime?2:(lifetime->error_us+999)/1000+1>10?3:4);
                else {
                    lease_error=std::max(lease_error,lifetime->error_us);
                    lease_until=std::min(lease_until,lease_origin-lease_error+300000);
                    if(session_until<=now || lease_until<=now ||
                       lease_until-now<=blinds::MotionExecutor::cycle_max_us+blinds::MotionExecutor::cycle_budget_us)
                        fault(Result::deadline,now);
                }
            }
        }
        if(const auto e=inbox.pop()) consume(*e,now);
        if(s.phase==Phase::committed && now>=start_local) {
            if(now-start_local>blinds::Limits{}.latest_start_ms*1000) fault(Result::deadline,now);
            else {s.phase=Phase::moving;record(24,now);}
        }
        publish(now);
    }
    // Local test harness only. An explicit synthetic observation is not a GPIO
    // read, physical measurement, runtime qualification or automatic convergence.
    bool script(std::uint64_t command,unsigned event,std::int64_t synthetic_height_um) {
        std::lock_guard<std::mutex> lock(gate);const auto now=now_us();advance(now);
        auto& s=snapshot.status;
        if(!qualified || !command || command!=s.command) return false;
        if(event==1 && s.phase==Phase::preparing) {s.phase=Phase::ready;s.ready=true;record(22,now);}
        else if(event==2 && s.phase==Phase::moving && synthetic_height_um>=low_um && synthetic_height_um<=high_um) {
            s.height_mm=synthetic_height_um/1000.;s.phase=Phase::settling;s.result=Result::finished;record(25,now);
        } else if(event==3 && s.phase==Phase::settling) {
            s.phase=Phase::idle;s.awake_required=false;s.ready=false;synthetic_off=true;record(26,now);
        } else return false;
        publish(now_us());return true;
    }
    static const coap_bin_const_t* validate(coap_bin_const_t* id,coap_session_t*,void* arg) {
        auto& p=*static_cast<Peer*>(arg);
        if(id->length!=p.identity.size() || CRYPTO_memcmp(id->s,p.identity.data(),id->length)) return nullptr;
        return &p.setup.psk_info.key;
    }
    static int event(coap_session_t* session,coap_event_t ev) {
        auto* p=static_cast<Peer*>(coap_get_app_data(coap_session_get_context(session)));if(!p) return 0;
        std::lock_guard<std::mutex> lock(p->gate);const auto now=now_us();
        if(ev==COAP_EVENT_DTLS_CONNECTED && sbthread::cipher_matches(session)) {
            if(p->active()) p->fault(Result::connection,now);
            p->owner=session;p->ingress.connected();p->nonce=0;++p->connections;p->record(1,now);
        } else if((ev==COAP_EVENT_DTLS_CLOSED || ev==COAP_EVENT_DTLS_ERROR) && p->owner==session) {
            p->owner=nullptr;p->ingress.disconnected();if(p->active()) p->fault(Result::connection,now);
        }return 0;
    }
    static void handler(coap_resource_t* resource,coap_session_t* session,const coap_pdu_t* request,
                        const coap_string_t*,coap_pdu_t* response) {
        auto& p=*static_cast<Peer*>(coap_resource_get_userdata(resource));std::lock_guard<std::mutex> lock(p.gate);
        if(p.owner!=session || !sbthread::cipher_matches(session) || coap_pdu_get_type(request)!=COAP_MESSAGE_CON) {
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_UNAUTHORIZED);return;
        }
        ++p.requests;const auto received=now_us();p.advance(received);const bool awake=p.radio(received);
        std::size_t size=0;const std::uint8_t* body=nullptr;coap_get_data(request,&size,&body);
        const auto* path=coap_resource_get_uri_path(resource);const std::string name(reinterpret_cast<const char*>(path->s),path->length);
        char reply[1024]{};const auto bad=[&]{coap_pdu_set_code(response,COAP_RESPONSE_CODE_BAD_REQUEST);};
        coap_pdu_set_code(response,COAP_RESPONSE_CODE_CONTENT);
        if(name=="v1/status") {
            if(size){bad();return;}
            std::snprintf(reply,sizeof(reply),"{\"boot\":\"%016llx\",\"last_wake\":\"%016llx\",\"awake\":%s,\"io_qualified\":%s,\"clock_qualified\":%s}",
                (unsigned long long)p.boot,(unsigned long long)p.window.last_sequence(),awake?"true":"false",p.qualified?"true":"false",p.probes.qualified(received)?"true":"false");
        } else if(name=="v1/wake") {
            if(size!=16 || !p.window.wake(sbthread::read64(body),sbthread::read64(body+8),received/1000)){bad();return;}
            p.radio(now_us());std::snprintf(reply,sizeof(reply),"{\"awake_ms\":10000,\"io_qualified\":%s}",p.qualified?"true":"false");
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else if(name=="v1/clock") {
            if(size!=16 || !p.probes.begin(sbthread::read64(body),sbthread::read64(body+8),received,awake)){bad();return;}
            const auto sent=now_us();if(!p.probes.sent(sent,awake)){bad();return;}
            std::snprintf(reply,sizeof(reply),"{\"boot\":\"%016llx\",\"probe\":\"%016llx\",\"received_us\":\"%016llx\",\"sent_us\":\"%016llx\"}",
                (unsigned long long)p.boot,(unsigned long long)p.probes.sequence(),(unsigned long long)received,(unsigned long long)sent);
        } else if(name=="v1/qualify") {
            if(size!=32 || !p.probes.assess(sbthread::read64(body),sbthread::read64(body+8),sbthread::read64(body+16),sbthread::read64(body+24),received,awake)) {
                p.ingress.clear_clock();bad();return;
            }
            if(!p.ingress.qualify(sbthread::read64(body+8),p.probes.bounds(),now_us())){bad();return;}
            smart_blinds::clock_readiness_json(reply,sizeof(reply),p.boot,p.probes,now_us(),awake);
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else if(name=="v1/readiness") {
            if(size){bad();return;}smart_blinds::clock_readiness_json(reply,sizeof(reply),p.boot,p.probes,now_us(),awake);
        } else if(name=="v1/motion") {
            using R=blinds::runtime::Ingress::Result;
            const auto result=p.ingress.submit(body,size,true,received);
            if(result!=R::queued){coap_pdu_set_code(response,result==R::malformed?COAP_RESPONSE_CODE_BAD_REQUEST:COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);return;}
            // Authentication/session ownership and the unchanged Ingress decoder
            // already accepted this exact packet. This passive copy grants no authority.
            const auto decoded=blinds::wire::decode(body,size);
            if(!decoded || p.decoded.size()>=4096) {p.fault(Result::deadline,received);coap_pdu_set_code(response,COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);return;}
            p.decoded.push_back({received,p.inbox.connection(),*decoded});
            p.record(2,received,p.ingress.received_message());
            std::snprintf(reply,sizeof(reply),"{\"queued\":true}");coap_pdu_set_code(response,COAP_RESPONSE_CODE_CHANGED);
        } else if(name=="v1/motion-status") {
            if(size){bad();return;}
            blinds::runtime::status_json(reply,sizeof(reply),p.boot,p.snapshot,p.power,p.ingress.snapshot(now_us()),p.qualified,now_us());
        } else if(name=="v1/telemetry" || name=="v1/handoff") {
            if(size!=16 || sbthread::read64(body)!=p.boot || !sbthread::read64(body+8) || sbthread::read64(body+8)<=p.nonce){bad();return;}
            p.nonce=sbthread::read64(body+8);const auto& s=p.snapshot.status;
            if(name=="v1/telemetry") {
                p.record(3,received);
                std::snprintf(reply,sizeof(reply),
                    "{\"schema\":1,\"boot\":\"%016llx\",\"nonce\":\"%016llx\",\"sent_us\":\"%016llx\","
                    "\"battery\":{\"sample_us\":null,\"bus_epoch\":0,\"serial\":0,\"pack\":null,\"soc_pct\":null,\"state\":\"absent\"},"
                    "\"charger\":{\"sample_us\":null,\"bus_epoch\":0,\"state\":\"unknown\",\"input_present\":null},"
                    "\"pd\":{\"sample_us\":null,\"bus_epoch\":0,\"epoch\":0,\"serial\":0,\"state\":\"unavailable\",\"current_ma\":0,\"attached\":null},"
                    "\"pending\":false,\"fault\":{\"kind\":\"none\",\"code\":0},\"charge_authorized\":false}",
                    (unsigned long long)p.boot,(unsigned long long)p.nonce,(unsigned long long)now_us());
            } else {
                char height[40]="null";if(s.height_mm)std::snprintf(height,sizeof(height),"%.3f",*s.height_mm);
                std::snprintf(reply,sizeof(reply),
                    "{\"version\":1,\"boot\":\"%016llx\",\"nonce\":\"%016llx\",\"sampled_us\":\"%016llx\",\"responded_us\":\"%016llx\","
                    "\"command\":\"%016llx\",\"received_message\":\"%016llx\",\"phase\":\"%s\",\"result\":\"%s\",\"reference_valid\":%s,\"height_mm\":%s,\"settled_off\":%s}",
                    (unsigned long long)p.boot,(unsigned long long)p.nonce,(unsigned long long)s.observed_us,(unsigned long long)now_us(),
                    (unsigned long long)s.command,(unsigned long long)p.ingress.received_message(),blinds::runtime::name(s.phase),blinds::runtime::name(s.result),
                    s.reference_valid?"true":"false",height,p.synthetic_off && s.command && s.phase==Phase::idle && !p.ingress.pending()?"true":"false");
            }
        } else {bad();return;}
        const std::uint8_t json=COAP_MEDIATYPE_APPLICATION_JSON;coap_add_option(response,COAP_OPTION_CONTENT_FORMAT,1,&json);
        coap_add_data(response,std::strlen(reply),reinterpret_cast<const std::uint8_t*>(reply));
    }
    bool start(std::uint16_t port,const char* id,const std::uint8_t* psk) {
        if(!port || !boot || !sbthread::identity_valid(id) || !psk)return false;
        identity=id;std::copy_n(psk,32,key.begin());context=coap_new_context(nullptr);if(!context)return false;
        coap_set_app_data(context,this);coap_register_event_handler(context,event);
        setup.version=COAP_DTLS_SPSK_SETUP_VERSION;setup.psk_info.key={key.size(),key.data()};setup.validate_id_call_back=validate;setup.id_call_back_arg=this;
        if(!coap_context_set_psk2(context,&setup))return false;
        coap_address_t local;sbthread::address(local,"::1",port);if(!coap_new_endpoint(context,&local,COAP_PROTO_DTLS))return false;
        for(const char* name:{"v1/status","v1/wake","v1/clock","v1/qualify","v1/readiness","v1/motion","v1/motion-status","v1/telemetry","v1/handoff"}) {
            auto* r=coap_resource_init(coap_make_str_const(name),0);if(!r)return false;
            coap_resource_set_userdata(r,this);
            const bool get=std::strcmp(name,"v1/status")==0 || std::strcmp(name,"v1/readiness")==0 || std::strcmp(name,"v1/motion-status")==0;
            coap_register_handler(r,get?COAP_REQUEST_GET:COAP_REQUEST_POST,handler);coap_add_resource(context,r);
        }
        network=std::thread([this]{while(!stop){
            {std::lock_guard<std::mutex> lock(gate);advance(now_us());}
            if(coap_io_process(context,1)<0)break;
        }});return true;
    }
};
}
extern "C" {
void* sb_contract_peer_new(std::uint16_t port,const char* id,const std::uint8_t* key,std::uint64_t boot,bool qualified) {
    sbthread::initialize();try{auto p=std::make_unique<sbcontract::Peer>(boot,qualified);if(!p->start(port,id,key))return nullptr;return p.release();}catch(...){return nullptr;}
}
// Explicit synthetic travel/capability limits, only in this fixture library.
void* sb_contract_peer_new_configured(std::uint16_t port,const char* id,const std::uint8_t* key,std::uint64_t boot,bool qualified,
                                      std::int64_t low,std::int64_t high,std::uint32_t speed,std::uint32_t acceleration) {
    if(low<0 || low>50000 || high<50000 || high>100000 || low>=high || !speed || speed>30000 || !acceleration || acceleration>60000) return nullptr;
    sbthread::initialize();try{auto p=std::make_unique<sbcontract::Peer>(boot,qualified,low,high,speed,acceleration);if(!p->start(port,id,key))return nullptr;return p.release();}catch(...){return nullptr;}
}
std::size_t sb_contract_peer_diagnostic(void* handle,std::uint64_t* out,std::size_t count) {
    auto& p=*static_cast<sbcontract::Peer*>(handle);std::lock_guard<std::mutex> lock(p.gate);
    if(count<p.first_fault.size())return 0;
    std::copy(p.first_fault.begin(),p.first_fault.end(),out);return p.first_fault.size();
}
std::size_t sb_contract_peer_decoded(void* handle,std::uint64_t* out,std::size_t count) {
    auto& p=*static_cast<sbcontract::Peer*>(handle);std::lock_guard<std::mutex> lock(p.gate);
    const auto rows=std::min(count/14,p.decoded.size());
    for(std::size_t i=0;i<rows;++i){const auto& d=p.decoded[i];const auto& r=d.request;
        const std::uint64_t fields[14]={d.received,d.connection,static_cast<std::uint64_t>(r.kind),r.calibration,r.boot,r.message,r.command,r.probe,
            r.sent_us,r.start_us,static_cast<std::uint64_t>(r.origin_um),static_cast<std::uint64_t>(r.target_um),r.speed_um_s,r.acceleration_um_s2};
        std::copy_n(fields,14,out+i*14);
    }return rows;
}
void sb_contract_peer_free(void* p){delete static_cast<sbcontract::Peer*>(p);}
bool sb_contract_peer_script(void* p,std::uint64_t command,unsigned event,std::int64_t synthetic_height_um){return static_cast<sbcontract::Peer*>(p)->script(command,event,synthetic_height_um);}
std::size_t sb_contract_peer_trace(void* handle,std::uint64_t* out,std::size_t count) {
    auto& p=*static_cast<sbcontract::Peer*>(handle);std::lock_guard<std::mutex> lock(p.gate);
    const auto rows=std::min(count/4,p.trace.size());for(std::size_t i=0;i<rows;++i){const auto& t=p.trace[i];out[4*i]=t.at;out[4*i+1]=t.event;out[4*i+2]=t.command;out[4*i+3]=t.message;}return rows;
}
unsigned sb_contract_peer_phase(void* handle){auto& p=*static_cast<sbcontract::Peer*>(handle);std::lock_guard<std::mutex> lock(p.gate);return static_cast<unsigned>(p.snapshot.status.phase);}
}
