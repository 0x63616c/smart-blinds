#pragma once
#include <cstdint>
#include <limits>
#include <optional>

namespace smart_blinds {
// Offset is device_time - coordinator_time. No clock is adjusted and no network
// symmetry is assumed. A configured drift budget is an assumption until measured.
struct ClockModel {
    std::uint32_t growth_ppm = 1000;
    std::uint32_t stamp_guard_us = 2;
    bool validated = false;
};
struct ClockExchange {
    std::uint64_t host_send_us, device_receive_us, device_send_us, host_receive_us;
};
class ClockBounds {
public:
    static constexpr std::uint64_t max_round_trip_us = 500000;
    static constexpr std::uint64_t max_age_us = 1000000;
    static constexpr std::uint64_t max_error_us = 10000;
    static std::optional<ClockBounds> estimate(const ClockExchange& x, ClockModel model = {}) {
        constexpr auto limit = static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
        if (x.host_send_us > limit || x.host_receive_us > limit || x.device_receive_us > limit ||
            x.device_send_us > limit || x.host_receive_us < x.host_send_us ||
            x.device_send_us < x.device_receive_us || model.growth_ppm > 10000 ||
            model.stamp_guard_us > 1000) return std::nullopt;
        const auto rtt = x.host_receive_us - x.host_send_us;
        const auto processing = x.device_send_us - x.device_receive_us;
        if (rtt > max_round_trip_us || processing > rtt) return std::nullopt;
        const auto width = rtt - processing;
        const auto pad = growth(rtt, model.growth_ppm) + model.stamp_guard_us;
        const auto low = static_cast<std::int64_t>(x.device_send_us) - static_cast<std::int64_t>(x.host_receive_us);
        const auto high = static_cast<std::int64_t>(x.device_receive_us) - static_cast<std::int64_t>(x.host_send_us);
        if (low < std::numeric_limits<std::int64_t>::min() + static_cast<std::int64_t>(pad) ||
            high > std::numeric_limits<std::int64_t>::max() - static_cast<std::int64_t>(pad)) return std::nullopt;
        return ClockBounds(low - static_cast<std::int64_t>(pad), high + static_cast<std::int64_t>(pad),
            (width + 1) / 2 + pad, x.host_receive_us, x.device_send_us, model);
    }
    std::optional<std::uint64_t> host_error(std::uint64_t now) const { return error(now, host_reference_us_); }
    std::optional<std::uint64_t> device_error(std::uint64_t now) const { return error(now, device_reference_us_); }
    bool host_qualified(std::uint64_t now) const {
        const auto bound = host_error(now);
        return model_.validated && bound && *bound <= max_error_us;
    }
    bool device_qualified(std::uint64_t now) const {
        const auto bound = device_error(now);
        return model_.validated && bound && *bound <= max_error_us;
    }
    std::int64_t lower_us() const { return lower_us_; }
    std::int64_t upper_us() const { return upper_us_; }
    std::uint64_t host_reference_us() const { return host_reference_us_; }
    std::uint64_t device_reference_us() const { return device_reference_us_; }
private:
    ClockBounds(std::int64_t low, std::int64_t high, std::uint64_t radius,
                std::uint64_t host_ref, std::uint64_t device_ref, ClockModel model)
        : lower_us_(low), upper_us_(high), radius_us_(radius), host_reference_us_(host_ref),
          device_reference_us_(device_ref), model_(model) {}
    static std::uint64_t growth(std::uint64_t age, std::uint32_t ppm) {
        return (age * ppm + 999999) / 1000000; // Inputs are capped before multiplication.
    }
    std::optional<std::uint64_t> error(std::uint64_t now, std::uint64_t reference) const {
        if (now < reference || now - reference > max_age_us) return std::nullopt;
        return radius_us_ + growth(now - reference, model_.growth_ppm);
    }
    std::int64_t lower_us_, upper_us_;
    std::uint64_t radius_us_, host_reference_us_, device_reference_us_;
    ClockModel model_;
};

// Device-side challenge binding; no clock assessment is a motion permission.
class ClockProbes {
public:
    explicit ClockProbes(std::uint64_t boot, ClockModel model = {}) : boot_(boot), model_(model) {}
    bool begin(std::uint64_t boot, std::uint64_t sequence, std::uint64_t receive_us, bool awake) {
        if (!advance(receive_us, awake) || !awake || boot_ == 0 || boot != boot_ || sequence <= sequence_) return false;
        sequence_ = sequence;
        bounds_.reset(); // The reported probe always describes the current evidence.
        receive_us_ = receive_us;
        pending_ = true;
        sent_ = false;
        return true;
    }
    bool sent(std::uint64_t send_us, bool awake) {
        if (!advance(send_us, awake) || !pending_ || sent_) return false;
        send_us_ = send_us;
        sent_ = true;
        return true;
    }
    bool assess(std::uint64_t boot, std::uint64_t sequence, std::uint64_t host_send,
                std::uint64_t host_receive, std::uint64_t now_us, bool awake) {
        if (!advance(now_us, awake) || !pending_ || !sent_ || boot != boot_ || sequence != sequence_) return false;
        pending_ = false; // Every submitted assessment consumes its probe.
        bounds_.reset();
        if (now_us - receive_us_ > ClockBounds::max_round_trip_us) return false;
        auto candidate = ClockBounds::estimate({host_send, receive_us_, send_us_, host_receive}, model_);
        if (!candidate) return false;
        const auto error = candidate->device_error(now_us);
        if (!error || *error > ClockBounds::max_error_us) return false;
        bounds_ = candidate;
        return true; // Accepted arithmetic under the model, not a validated model.
    }
    bool advance(std::uint64_t now, bool awake) {
        if (clock_fault_ || now < last_now_us_) {
            clock_fault_ = true;
            invalidate();
            return false;
        }
        last_now_us_ = now;
        if (!awake) invalidate();
        if (pending_ && now - receive_us_ > ClockBounds::max_round_trip_us) pending_ = false;
        if (bounds_) {
            const auto error = bounds_->device_error(now);
            if (!error || *error > ClockBounds::max_error_us) bounds_.reset();
        }
        return awake;
    }
    void invalidate() { pending_ = sent_ = false; bounds_.reset(); }
    const std::optional<ClockBounds>& bounds() const { return bounds_; }
    bool qualified(std::uint64_t now) const { return bounds_ && bounds_->device_qualified(now); }
    std::uint64_t sequence() const { return sequence_; }
    bool model_validated() const { return model_.validated; }
private:
    std::uint64_t boot_, sequence_ = 0, last_now_us_ = 0, receive_us_ = 0, send_us_ = 0;
    ClockModel model_;
    std::optional<ClockBounds> bounds_;
    bool pending_ = false, sent_ = false, clock_fault_ = false;
};
}
