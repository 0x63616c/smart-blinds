#include "smart_blinds/motion_protocol.hpp"
#include <cstdlib>
#include <iostream>
using namespace blinds::wire;
namespace {
void check(bool value,const char* text) { if(!value) { std::cerr<<text<<'\n'; std::exit(1); } }
Request request() { return {Kind::prepare,3,99,1,1,9,1000000,1300000,-500000,3000000,20000,40000}; }
void framing() {
    auto bytes=encode(request()); auto value=decode(bytes.data(),bytes.size());
    check(value && value->origin_um==-500000 && value->target_um==3000000 && value->boot==99,"signed/network field roundtrip");
    for(std::size_t n=0;n<bytes.size();++n) check(!decode(bytes.data(),n),"short payload accepted");
    check(!decode(nullptr,bytes.size()) && !decode(bytes.data(),81),"invalid pointer/length accepted");
    for(int i:{0,2,3}) { auto bad=bytes; bad[i]^=2; check(!decode(bad.data(),bad.size()),"unknown version/reserved byte accepted"); }
    for(auto kind:{Kind::commit,Kind::lease,Kind::stop}) {
        auto r=request(); r.kind=kind;
        auto bad=encode(r); check(!decode(bad.data(),bad.size()),"unexpected command extension accepted");
        r.start_us=0; r.origin_um=r.target_um=0; r.speed_um_s=r.acceleration_um_s2=0;
        auto good=encode(r); check(decode(good.data(),good.size()).has_value(),"valid non-prepare rejected");
    }
    for(int i=0;i<10;++i) {
        auto r=request();
        switch(i) {
        case 0:r.boot=0;break; case 1:r.message=0;break; case 2:r.command=0;break;
        case 3:r.probe=0;break; case 4:r.calibration=0;break; case 5:r.sent_us=UINT64_MAX;break;
        case 6:r.origin_um=INT64_MIN;break; case 7:r.target_um=1000000001;break;
        case 8:r.speed_um_s=30001;break; case 9:r.acceleration_um_s2=0;break;
        }
        auto bad=encode(r); check(!decode(bad.data(),bad.size()),"invalid command bound accepted");
    }
}
void inbox() {
    Inbox<2> queue(99); check(queue.connected(1),"connection rejected");
    Envelope a{request(),1,1000,true}, b=a; b.request.message=2;
    check(queue.push(a) && queue.push(b),"queue insertion failed");
    a.request.message=3; check(!queue.push(a),"queue overflow did not reject");
    auto stop=a; stop.request.kind=Kind::stop; stop.request.boot=98;
    stop.request.start_us=0; stop.request.origin_um=stop.request.target_um=0;
    stop.request.speed_um_s=stop.request.acceleration_um_s2=0;
    check(!queue.push(stop) && !queue.stop_pending(),"old boot STOP accepted");
    stop.request.boot=99; stop.connection=2;
    check(!queue.push(stop),"foreign session STOP accepted"); stop.connection=1;
    check(queue.push(stop) && queue.stop_pending() && !queue.stop_pending(),"STOP did not bypass full queue exactly once");
    check(!queue.push(stop),"STOP replay accepted");
    queue.discard(); check(!queue.pop(),"STOP discard left old work queued");
    b.request.message=4; check(queue.push(b),"queue could not accept fresh post-discard message");
    auto next=queue.pop(); check(next && next->request.message==4 && !queue.pop(),"FIFO/drop behavior incorrect");
    a.request.message=5; a.authenticated=false; check(!queue.push(a),"unauthenticated frame queued");
    a.authenticated=true; a.connection=0; check(!queue.push(a),"unbound connection queued");
    queue.disconnected(); a.connection=1; check(!queue.push(a),"detached frame accepted");
    check(!queue.connected(1) && queue.connected(2),"connection generation reused");
    check(!queue.push(a),"old connection frame accepted after reconnect");
    a.connection=2; check(queue.push(a),"new connection rejected");
}
auto bounds(std::uint64_t offset,smart_blinds::ClockModel model={1000,2,true}) {
    return smart_blinds::ClockBounds::estimate({1000000,1001000+offset,1001100+offset,1002100},model);
}
void projection() {
    auto b=bounds(500000); check(b.has_value(),"clock fixture invalid");
    Projection p; check(p.bind(*b,1502000),"clock bind rejected");
    auto t=p.at(*b,1503000);
    check(t && t->host_us==1003000 && t->error_us<1100,"coordinator translation incorrect");
    check(p.local(1003000)==1503000,"reverse projection incorrect");
    auto shifted=bounds(500500);
    auto moved=p.at(*shifted,1503000);
    check(moved && moved->host_us==1003000 && moved->error_us>t->error_us,"requalification stepped trajectory time");
    auto drift=bounds(520000); check(!p.at(*drift,1530000),"excess clock drift accepted");
    check(!p.at(*b,2600000),"stale clock accepted");
    auto unqualified=bounds(500000,{1000,2,false});
    Projection q; check(!q.bind(*unqualified,1502000),"unvalidated clock model authorized projection");
    p.invalidate(); check(!p.at(*b,1503000) && !p.local(1003000),"invalid projection retained");
    auto negative=smart_blinds::ClockBounds::estimate({2000000,1001000,1001100,2002100},{1000,2,true});
    check(negative && q.bind(*negative,1002000),"negative offset bind rejected");
    check(q.at(*negative,1003000)->host_us==2003000,"negative offset projection");
    check(!q.local(10),"negative device timestamp wrapped");
    check(!q.local(UINT64_MAX),"oversized host timestamp accepted");
}
}
int main() { framing(); inbox(); projection(); std::cout<<"bounded motion framing, STOP queue priority and clock projection passed\n"; }
