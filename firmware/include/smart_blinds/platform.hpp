#pragma once
#include "smart_blinds/control.hpp"
#include <cmath>

namespace blinds {
// Board-specific implementation is intentionally absent until pin map and measured
// electrical limits are reviewed. The driver owns the closed encoder-speed loop.
class BoardPort {
public:
    virtual ~BoardPort() = default;
    virtual bool configured() const = 0;
    virtual Measurement read() = 0;
    virtual void disable_motor() = 0;
    virtual bool set_fabric_velocity(double velocity_mm_s) = 0;
};

class ActuatorGate {
public:
    explicit ActuatorGate(BoardPort& board) : board_(board) { board_.disable_motor(); }
    bool apply(const Output& output) {
        if (!board_.configured() || !output.motor_enable || output.state != State::moving ||
            output.reason != Reason::ok ||
            !std::isfinite(output.velocity_mm_s) || output.velocity_mm_s == 0) {
            board_.disable_motor();
            return false;
        }
        if (!board_.set_fabric_velocity(output.velocity_mm_s)) {
            board_.disable_motor();
            return false;
        }
        return true;
    }
    void stop() { board_.disable_motor(); }
private:
    BoardPort& board_;
};
} // namespace blinds
