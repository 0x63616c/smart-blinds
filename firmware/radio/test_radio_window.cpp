#include "smart_blinds/radio_window.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
using smart_blinds::RadioWindow;
void check(bool value, const char* text) {
    if (!value) { std::cerr << text << '\n'; std::exit(1); }
}
int main() {
    RadioWindow window(42);
    check(!window.wake(42, 1, 100), "offline wake accepted");
    window.attached(true, 100);
    check(!window.wake(41, 1, 100), "wrong boot accepted");
    check(!window.wake(42, 0, 100), "zero sequence accepted");
    check(window.wake(42, 1, 100), "first authenticated wake rejected");
    check(window.rx_on_when_idle(), "not awake");
    check(!window.wake(42, 2, 101), "wake extended active budget");
    check(window.deadline() == 10100, "deadline extended");
    window.advance(10100);
    check(!window.rx_on_when_idle(), "deadline failed to sleep");
    check(!window.wake(42, 2, 15099), "cooldown bypassed");
    check(window.wake(42, 2, 15100), "new window rejected after cooldown");
    window.attached(false, 16000);
    check(!window.rx_on_when_idle(), "detach did not sleep");
    window.attached(true, 16001);
    check(!window.wake(42, 3, 16001), "reattach bypassed cooldown");
    window.advance(30100);
    check(!window.wake(42, 2, 30100), "reconnect replay accepted");
    check(window.wake(42, 3, 30100), "new sequence rejected");
    window.cancel(30101);
    check(!window.rx_on_when_idle(), "cancel failed");
    check(!window.advance(30000), "backwards clock accepted");
    window.attached(true, 50000);
    check(!window.wake(42, 4, 50000), "clock fault was cleared implicitly");
    RadioWindow invalid(0);
    invalid.attached(true, 0);
    check(!invalid.wake(0, 1, 0), "zero boot accepted");
    RadioWindow overflow(1);
    overflow.attached(true, 1);
    check(!overflow.wake(1, 1, std::numeric_limits<std::uint64_t>::max() - 100), "overflow accepted");
    std::cout << "radio window boundaries passed\n";
}
