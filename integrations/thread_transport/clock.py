"""Conservative four-timestamp arithmetic, independent of network I/O.

The v1 experimental model is deliberately NOT hardware-validated. Bounds assume
relative offset growth <=1000 ppm and a 2 us timestamp guard. No symmetry is
assumed and no host or device clock is adjusted.
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


def _growth(age: int) -> int:
    return (age * GROWTH_PPM + 999_999) // 1_000_000


@dataclass(frozen=True)
class ClockBounds:
    # Offset = device time - host time, both monotonic microseconds.
    lower_us: int
    upper_us: int
    radius_us: int
    host_reference_us: int
    device_reference_us: int

    @classmethod
    def estimate(cls, t1: int, t2: int, t3: int, t4: int) -> "ClockBounds":
        if any(type(t) is not int or not 0 <= t <= (1 << 63) - 1 for t in (t1, t2, t3, t4)):
            raise ClockUncertain("Invalid monotonic timestamp")
        if t4 < t1 or t3 < t2:
            raise ClockUncertain("Monotonic clock reversed")
        rtt, processing = t4 - t1, t3 - t2
        if rtt > MAX_ROUND_TRIP_US or processing > rtt:
            raise ClockUncertain("Clock exchange exceeded its time bound")
        pad = _growth(rtt) + STAMP_GUARD_US
        low, high = t3 - t4 - pad, t2 - t1 + pad
        if low < -(1 << 63) or high > (1 << 63) - 1:
            raise ClockUncertain("Clock offset exceeded its representation")
        return cls(low, high, (rtt - processing + 1) // 2 + pad, t4, t3)

    def error_us(self, now_us: int) -> int:
        age = now_us - self.host_reference_us
        if not 0 <= age <= MAX_AGE_US:
            raise ClockUncertain("Clock evidence is stale or the host clock reversed")
        error = self.radius_us + _growth(age)
        if error > MAX_ERROR_US:
            raise ClockUncertain("Clock error exceeds the synchronization budget")
        return error

    def source_age_us(self, sampled_us: int, now_us: int) -> int:
        self.error_us(now_us)
        upper_now = self.upper_us + _growth(now_us - self.host_reference_us)
        # Earliest possible source time yields the largest possible age. A future
        # lower bound is inconsistent; uncertainty that overlaps 'now' is valid.
        age = now_us - sampled_us + upper_now
        if age < 0 or age > MAX_SOURCE_AGE_US:
            raise ClockUncertain("Readiness source timestamp is future or stale")
        return age
