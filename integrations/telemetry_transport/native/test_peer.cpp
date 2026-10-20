// Localhost-only fixture for the exact portable Wi-Fi parser/policy. OpenSSL,
// not the C6 Mbed TLS backend: no over-the-air or hardware evidence implied.
#include "common.hpp"
#include "smart_blinds/wifi_motion.hpp"
#include "smart_blinds/telemetry.hpp"
#include <algorithm>
#include <atomic>
#include <memory>
#include <thread>
namespace {
class InfoPort final : public smart_blinds::wifi::MotionPort {
public:
    blinds::MotionSession::Inbox inbox;
    blinds::runtime::Ingress input;
    blinds::telemetry::Samples info{};
    std::uint64_t boot;
    unsigned commands=0;
    std::atomic<unsigned> mode{0};
    explicit InfoPort(std::uint64_t b):inbox(b),input(inbox),boot(b) {}
    blinds::runtime::Ingress& ingress() override { return input; }
    void publish(std::uint64_t) override {}
    void notify() override { ++commands; }
    void revoke() override {}
    bool qualified() const override { return false; }
    bool parked(std::uint64_t) const override { return false; }
    bool status(char*,std::size_t,std::uint64_t) override { return false; }
    bool telemetry(char* out,std::size_t size,std::uint64_t nonce,std::uint64_t now) override {
        auto copied=info;
        if(mode==2) {copied.fault=blinds::telemetry::Fault::charger;copied.fault_code=4;}
        if(mode==3) copied.battery.sample_us=now+1;
        if(mode==4) copied.charger.input_present=false;
        return blinds::telemetry::json(out,size,boot,nonce,now,copied,mode==2,mode==1,1);
    }
};
class Peer {
public:
    coap_context_t* context=nullptr;
    coap_session_t* session=nullptr;
    coap_dtls_spsk_t setup{};
    smart_blinds::wifi::Credentials credentials;
    InfoPort port;
    smart_blinds::wifi::MotionBinding app;
    std::uint64_t owner=0;
    std::atomic<bool> stop{false},loss{false};
    std::atomic<unsigned> requests{0};
    std::thread worker;
    explicit Peer(std::uint64_t boot) : port(boot),app(boot,port) {}
    ~Peer() {
        stop=true;if(worker.joinable()) worker.join();
        if(context) coap_free_context(context);
        OPENSSL_cleanse(&credentials,sizeof(credentials));
    }
    static std::uint64_t now() {
        return std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    }
    static const coap_bin_const_t* identity(coap_bin_const_t* id,coap_session_t*,void* arg) {
        auto& self=*static_cast<Peer*>(arg);const auto n=std::strlen(self.credentials.identity.data());
        if(id->length!=n || CRYPTO_memcmp(id->s,self.credentials.identity.data(),n)) return nullptr;
        return &self.setup.psk_info.key;
    }
    static int event(coap_session_t* s,coap_event_t e) {
        auto& self=*static_cast<Peer*>(coap_get_app_data(coap_session_get_context(s)));
        if(e==COAP_EVENT_DTLS_CONNECTED) {
            if(self.session || self.loss || !sbthread::cipher_matches(s) || !(self.owner=self.app.connected(now()))) {
                coap_session_disconnected(s,COAP_NACK_NOT_DELIVERABLE);return 0;
            }
            self.session=s;self.app.invalidate(now());
        } else if((e==COAP_EVENT_DTLS_CLOSED || e==COAP_EVENT_DTLS_ERROR ||
                   e==COAP_EVENT_DTLS_RENEGOTIATE) && s==self.session) {
            self.app.disconnected(self.owner,now());self.session=nullptr;self.owner=0;self.app.invalidate(now());
        }
        if(e==COAP_EVENT_DTLS_RENEGOTIATE) coap_session_disconnected(s,COAP_NACK_NOT_DELIVERABLE);
        return 0;
    }
    static void handler(coap_resource_t* resource,coap_session_t* s,const coap_pdu_t* p,
                        const coap_string_t*,coap_pdu_t* response) {
        auto& self=*static_cast<Peer*>(coap_resource_get_userdata(resource));
        if(self.loss || s!=self.session || !sbthread::cipher_matches(s) || coap_pdu_get_type(p)!=COAP_MESSAGE_CON) {
            coap_pdu_set_code(response,COAP_RESPONSE_CODE_UNAUTHORIZED);return;
        }
        ++self.requests;
        std::size_t size=0;const std::uint8_t* body=nullptr;coap_get_data(p,&size,&body);
        const auto* uri=coap_resource_get_uri_path(resource);const auto received=now();
        const auto reply=self.app.request(self.owner,
            std::string_view(reinterpret_cast<const char*>(uri->s),uri->length),
            static_cast<std::uint8_t>(coap_pdu_get_code(p)),body,size,received,now());
        coap_pdu_set_code(response,static_cast<coap_pdu_code_t>(reply.code));
        if(reply.body[0]) {
            const std::uint8_t json=COAP_MEDIATYPE_APPLICATION_JSON;
            coap_add_option(response,COAP_OPTION_CONTENT_FORMAT,1,&json);
            coap_add_data(response,std::strlen(reply.body.data()),reinterpret_cast<const std::uint8_t*>(reply.body.data()));
        }
    }
    bool start(std::uint16_t port,const char* id,const std::uint8_t* key) {
        if(!port || !sbthread::identity_valid(id) || !key) return false;
        credentials.approved=true;credentials.board_profile=1;
        std::strcpy(credentials.ssid.data(),"local-fixture");std::strcpy(credentials.password.data(),"unused-test");
        std::strcpy(credentials.identity.data(),id);std::copy_n(key,32,credentials.key.begin());
        if(!app.policy.configure(credentials,now()/1000) || !app.policy.begin_association(now()/1000) ||
           !app.policy.network_ready(1,now()/1000)) return false;
        context=coap_new_context(nullptr);if(!context) return false;
        coap_set_app_data(context,this);coap_register_event_handler(context,event);
        setup.version=COAP_DTLS_SPSK_SETUP_VERSION;
        setup.psk_info.key={32,credentials.key.data()};setup.validate_id_call_back=identity;setup.id_call_back_arg=this;
        if(!coap_context_set_psk2(context,&setup)) return false;
        coap_address_t address;sbthread::address(address,"::1",port);
        if(!coap_new_endpoint(context,&address,COAP_PROTO_DTLS)) return false;
        for(const char* name: {"v1/status","v1/wake","v1/clock","v1/qualify","v1/readiness","v1/motion","v1/motion-status","v1/telemetry"}) {
            auto* r=coap_resource_init(coap_make_str_const(name),0);if(!r) return false;
            coap_resource_set_userdata(r,this);
            const auto path=std::string_view(name);
            const bool get=path=="v1/status" || path=="v1/readiness" || path=="v1/motion-status";
            coap_register_handler(r,get ? COAP_REQUEST_GET:COAP_REQUEST_POST,handler);coap_add_resource(context,r);
        }
        const auto stamp=now();
        // Explicit synthetic loopback observations, never physical pack data.
        this->port.info.battery={stamp,77,1,1,42.1875,true,true};
        this->port.info.charger={stamp,1,true,true};
        this->port.info.pd={stamp,1,1,1,2500,blinds::telemetry::Source::policy_observed,true,true};
        worker=std::thread([this] {
            while(!stop) {
                if(loss.exchange(false)) {app.policy.lost_network(now()/1000);app.invalidate(now());}
                if(coap_io_process(context,5)<0) break;
            }
        });return true;
    }
};
}
extern "C" {
void* sb_telemetry_peer_new(std::uint16_t port,const char* identity,const std::uint8_t* key,std::uint64_t boot) {
    sbthread::initialize();
    try { auto p=std::make_unique<Peer>(boot);return p->start(port,identity,key) ? p.release():nullptr; }
    catch(...) {return nullptr;}
}
void sb_telemetry_peer_free(void* p) {delete static_cast<Peer*>(p);}
void sb_telemetry_peer_loss(void* p) {static_cast<Peer*>(p)->loss=true;}
void sb_telemetry_peer_mode(void* p,unsigned mode) {static_cast<Peer*>(p)->port.mode=mode;}
unsigned sb_telemetry_peer_requests(void* p) {return static_cast<Peer*>(p)->requests;}
}
