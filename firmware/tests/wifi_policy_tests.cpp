#include "smart_blinds/wifi_evaluation.hpp"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace smart_blinds::wifi;
Credentials credentials() {
    Credentials c; c.approved=true;c.board_profile=1;c.key[0]=19;
    std::strcpy(c.ssid.data(),"disposable-test");std::strcpy(c.password.data(),"fixture-only");
    std::strcpy(c.identity.data(),"fixture"); return c;
}
int main() {
    auto c=credentials(); assert(c.valid());
    auto bad=c;bad.approved=false;assert(!bad.valid());
    bad=c;bad.board_profile=2;assert(!bad.valid());
    bad=c;bad.key.fill(0);assert(!bad.valid());
    bad=c;bad.password.fill('x');assert(!bad.valid());
    bad=c;bad.identity[0]='/';assert(!bad.valid());
    Policy p(7);assert(!p.begin_association(0));assert(!p.connected(0));assert(!p.awake());
    assert(p.configure(c,1));assert(p.begin_association(1));assert(!p.network_ready(9,8001));
    assert(p.state()==Policy::State::offline && !p.begin_association(38000));
    assert(p.begin_association(38001));p.lost_network(38002);
    assert(!p.begin_association(158001));assert(p.begin_association(158002));
    p.lost_network(158003);assert(!p.begin_association(300000));assert(p.attempts()==3);
    // Backoff is bounded, and a successful connection cannot erase attempt history.
    Policy q(7);assert(q.configure(c,0));assert(q.begin_association(0));assert(q.network_ready(11,1));
    auto owner=q.connected(2);assert(owner);assert(!q.connected(3));
    assert(!q.wake(owner+1,7,1,4));assert(!q.wake(owner,6,1,4));assert(q.wake(owner,7,1,4));
    assert(!q.wake(owner,7,1,5));assert(q.awake());
    assert(q.begin_operation(owner,6));assert(!q.settled_off(owner,false,7));
    q.disconnected(owner,8);assert(q.state()==Policy::State::fault);
    assert(!q.begin_association(200000));assert(!q.connected(200000));
    Policy r(8);assert(r.configure(c,0));assert(r.begin_association(0));assert(r.network_ready(1,1));
    auto a=r.connected(2);assert(r.wake(a,8,1,3));
    r.advance(10003);assert(!r.awake());r.disconnected(a,10004);
    auto b=r.connected(10005);assert(b>a);assert(!r.wake(a,8,2,15003));
    assert(r.wake(b,8,2,15004));assert(r.begin_operation(b,15005));
    assert(r.settled_off(b,true,15006));assert(!r.awake());
    // An IP change or queue/PM failure cannot migrate an owned operation.
    Policy ip(9);assert(ip.configure(c,0));assert(ip.begin_association(0));assert(ip.network_ready(1,1));
    auto id=ip.connected(2);assert(ip.wake(id,9,1,3));assert(!ip.network_ready(2,4));
    assert(ip.state()==Policy::State::fault);
    Policy clock(1);assert(clock.configure(c,5));assert(!clock.advance(4));assert(!clock.begin_association(6));
    Policy limit(10);assert(limit.configure(c,0));assert(limit.begin_association(0));assert(limit.network_ready(1,1));
    const auto limited=limit.connected(2);assert(limit.wake(limited,10,1,3));
    assert(limit.begin_operation(limited,4));assert(limit.advance(240003));
    assert(!limit.advance(240004));assert(limit.state()==Policy::State::fault);
    // A local button can hold the radio awake, but never authorizes a remote
    // operation without a separate authenticated wake window.
    Policy local(11);assert(local.configure(c,0));assert(local.begin_association(0));assert(local.network_ready(1,1));
    const auto local_owner=local.connected(2);local.buttons(true,3);assert(local.awake());
    assert(!local.begin_operation(local_owner,4));local.buttons(false,5);assert(!local.awake());
    local.lost_network(6);assert(local.state()==Policy::State::offline);
    assert(!local.begin_association(30005));assert(local.begin_association(30006));
    assert(local.network_ready(2,30007));assert(local.attempts()==2);
    assert(local.connected(30008)>local_owner);assert(!local.wake(local_owner,11,1,30009));
    Evaluation e(22);assert(e.policy.configure(c,0));assert(e.policy.begin_association(0));assert(e.policy.network_ready(1,1));
    auto session=e.policy.connected(2);
    assert(e.request(session,"v1/status",1,nullptr,0,3000,3000).code==69);
    assert(e.request(session+1,"v1/status",1,nullptr,0,3001,3001).code==129);
    assert(e.request(session,"v1/status",2,nullptr,0,3002,3002).code==133);
    std::uint8_t wake[16]{};wake[7]=22;wake[15]=1;
    assert(e.request(session,"v1/wake",2,wake,15,4000,4000).code==128);
    assert(e.request(session,"v1/wake",2,wake,16,4001,4001).code==68);
    assert(e.request(session,"v1/wake",2,wake,16,4002,4002).code==128);
    assert(e.request(session,"v1/motion",2,wake,16,4003,4003).code==163);
    const auto readiness=e.request(session,"v1/readiness",1,nullptr,0,4004,4004);
    assert(std::strstr(readiness.body.data(),"\"motor_ready\":false"));
    assert(std::strstr(readiness.body.data(),"\"clock_model_validated\":false"));
    e.policy.lost_network(5);e.invalidate();
    assert(e.request(session,"v1/status",1,nullptr,0,6000,6000).code==129);
    std::cout<<"Wi-Fi configuration, ownership, timeout, parser and fail-off policy checks passed\n";
}
