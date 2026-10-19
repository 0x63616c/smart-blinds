"""Source-age validation after peer authentication and clock-domain translation.

This module does not authenticate messages or estimate clocks. The transport must
bind all stamp fields to the authenticated device and current coordinator epoch.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceStamp:
    sample_ms: int       # Source sample time translated to coordinator monotonic time
    sequence: int        # Increasing for every status/ACK in one device boot
    clock_error_ms: int  # Conservative absolute translation error bound


def earliest_sample(stamp: SourceStamp, receipt_ms: int, max_age_ms: int) -> int:
    values = (stamp.sample_ms, stamp.sequence, stamp.clock_error_ms, receipt_ms, max_age_ms)
    if any(type(value) is not int or not 0 <= value < 2**64 for value in values):
        raise ValueError("invalid timestamp or sequence")
    if stamp.sequence == 0 or stamp.clock_error_ms > 10:
        raise ValueError("invalid sequence or uncertain clock")
    if stamp.sample_ms > receipt_ms and stamp.sample_ms - receipt_ms > stamp.clock_error_ms:
        raise ValueError("source timestamp in the future")
    earliest = max(0, stamp.sample_ms - stamp.clock_error_ms)
    if receipt_ms - earliest > max_age_ms:
        raise ValueError("stale source sample")
    return earliest


class FreshnessTracker:
    """Per-job replay high-water marks; boot/command checks belong to the caller."""
    def __init__(self):
        self._last: dict[str, SourceStamp] = {}

    def accept(self, device_id: str, stamp: SourceStamp, receipt_ms: int,
               max_age_ms: int) -> int:
        earliest = earliest_sample(stamp, receipt_ms, max_age_ms)
        previous = self._last.get(device_id)
        if previous and (stamp.sequence <= previous.sequence or stamp.sample_ms < previous.sample_ms):
            raise ValueError("replayed or out-of-order source sample")
        self._last[device_id] = stamp
        return earliest
