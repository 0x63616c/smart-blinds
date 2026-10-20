#pragma once
#include <cstdint>
#include <limits>
#include <optional>

namespace blinds {
// One control owner, one boot. Independent of every external command/gesture
// sequence. Consume before attempting I/O; a failed start never returns a number.
// The optional floor supports boundary tests, not restoring motion after reboot.
class ExecutionEpoch {
public:
    explicit ExecutionEpoch(std::uint64_t floor=0) : value_(floor) {}
    std::optional<std::uint64_t> take() {
        if(value_==std::numeric_limits<std::uint64_t>::max()) return {};
        return ++value_;
    }
    std::uint64_t value() const { return value_; }
private:
    std::uint64_t value_;
};
}
