"""Conservative four-timestamp arithmetic, independent of network I/O.

The default evaluation model is NOT hardware-validated (1000 ppm, 2 us guard).
The separate motion client uses the worst bounds allowed by the C6 configuration
(10000 ppm, 1000 us guard). No symmetry or clock adjustment is assumed.
"""
from dataclasses import dataclass

MAX_ERROR_US = 10_000
MAX_AGE_US = 1_000_000
MAX_ROUND_TRIP_US = 500_000
MAX_SOURCE_AGE_US = 100_000
GROWTH_PPM = 1000
STAMP_GUARD_US = 2


class ClockUncertain(RuntimeError):
    """Current timing evidence cannot meet the bound; no implicit retry."""


def _growth(age: int, ppm: int = GROWTH_PPM) -> int:
    return (age * ppm + 999_999) // 1_000_000


@dataclass(frozen=True)
class ClockBounds:
    # Offset = device time - host time, both monotonic microseconds.
    lower_us: int
    upper_us: int
    radius_us: int
    host_reference_us: int
    device_reference_us: int
    growth_ppm: int = GROWTH_PPM

    @classmethod
    def estimate(cls, t1: int, t2: int, t3: int, t4: int, *,
                 growth_ppm: int = GROWTH_PPM, stamp_guard_us: int = STAMP_GUARD_US) -> "ClockBounds":
        if (type(growth_ppm) is not int or not 0 <= growth_ppm <= 10000 or
            type(stamp_guard_us) is not int or not 0 <= stamp_guard_us <= 1000):
            raise ClockUncertain("Invalid clock model bound")
        if any(type(t) is not int or not 0 <= t <= (1 << 63) - 1 for t in (t1, t2, t3, t4)):
            raise ClockUncertain("Invalid monotonic timestamp")
        if t4 < t1 or t3 < t2:
            raise ClockUncertain("Monotonic clock reversed")
        rtt, processing = t4 - t1, t3 - t2
        if rtt > MAX_ROUND_TRIP_US or processing > rtt:
            raise ClockUncertain("Clock exchange exceeded its time bound")
        pad = _growth(rtt, growth_ppm) + stamp_guard_us
        low, high = t3 - t4 - pad, t2 - t1 + pad
        if low < -(1 << 63) or high > (1 << 63) - 1:
            raise ClockUncertain("Clock offset exceeded its representation")
        return cls(low, high, (rtt - processing + 1) // 2 + pad, t4, t3, growth_ppm)

    def error_us(self, now_us: int) -> int:
        age = now_us - self.host_reference_us
        if not 0 <= age <= MAX_AGE_US:
            raise ClockUncertain("Clock evidence is stale or the host clock reversed")
        error = self.radius_us + _growth(age, self.growth_ppm)
        if error > MAX_ERROR_US:
            raise ClockUncertain("Clock error exceeds the synchronization budget")
        return error

    def source_age_us(self, sampled_us: int, now_us: int, max_age_us: int = MAX_SOURCE_AGE_US) -> int:
        self.error_us(now_us)
        if type(max_age_us) is not int or not 0 <= max_age_us <= 1_000_000:
            raise ClockUncertain("Invalid source age bound")
        upper_now = self.upper_us + _growth(now_us - self.host_reference_us, self.growth_ppm)
        # Earliest possible source time yields the largest possible age. A future
        # lower bound is inconsistent; uncertainty that overlaps 'now' is valid.
        age = now_us - sampled_us + upper_now
        if age < 0 or age > max_age_us:
            raise ClockUncertain("Readiness source timestamp is future or stale")
        return age
