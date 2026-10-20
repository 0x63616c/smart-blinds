#include "c6_power_mailbox.hpp"
namespace blinds::c6 {
void PowerMailboxGate::enter() noexcept { portENTER_CRITICAL(&mux_); }
void PowerMailboxGate::leave() noexcept { portEXIT_CRITICAL(&mux_); }
} // namespace blinds::c6
