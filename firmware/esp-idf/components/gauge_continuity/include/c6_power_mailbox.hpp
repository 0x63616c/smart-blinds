#pragma once
#include "freertos/FreeRTOS.h"
#include "smart_blinds/power_mailbox.hpp"

namespace blinds::c6 {
// Compile-only adapter; neither application instantiates a joint mailbox.
// C6 UNICORE enters interrupt masking. It has no useful try-lock timeout:
// fixed-size copy duration must be measured before physical qualification.
class PowerMailboxGate final:public power::continuity::MailboxGate {
public:
    void enter() noexcept override;
    void leave() noexcept override;
private:
    portMUX_TYPE mux_=portMUX_INITIALIZER_UNLOCKED;
};
} // namespace blinds::c6
