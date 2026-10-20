"""Strict unit and authenticated source-interval conversion at the adapter seam."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import math
from integrations.home_assistant.coordinator import Device
from integrations.home_assistant.freshness import SourceStamp, earliest_sample
from integrations.thread_transport.motion import Report
from .selection import Selection, integer


def micrometres(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite physical coordinate required')
    # Decimal(str(...)) expresses the public decimal value, not a binary float
    # epsilon. No rounding: fractional micrometres require an explicit policy.
    try: scaled = Decimal(str(value)) * 1000
    except InvalidOperation as error: raise ValueError('Invalid coordinate') from error
    if scaled != scaled.to_integral_value():
        raise ValueError('Coordinate cannot be represented exactly in micrometres')
    return integer(int(scaled), -10**9, 10**9, 'micrometre coordinate')


def microseconds(value):
    integer(value, 1, (2**63-1)//1000, 'source milliseconds')
    return value * 1000


def source_stamp(report: Report, receipt_ms: int, *, max_age_ms=100):
    if not report.new_sample:
        raise ValueError('Repeated worker snapshot is not a new report')
    integer(report.sampled_us, 1, 2**63-1, 'source sequence')
    low = integer(report.sample_host_earliest_us, 0, 2**63-1, 'source lower bound')
    error = integer(report.clock_error_us, 0, 10000, 'clock error')
    # The report supplies an earliest bound, not a centre. Build an enclosing
    # integer-ms interval once; do not subtract the clock uncertainty twice.
    lower_ms = low // 1000
    upper_ms = (low + 2*error + 999)//1000
    centre = (lower_ms+upper_ms)//2
    radius = max(centre-lower_ms, upper_ms-centre)
    stamp = SourceStamp(centre, report.sampled_us, radius)
    earliest_sample(stamp, receipt_ms, max_age_ms)
    return stamp


def device(selected: Selection, report: Report, command_floor: int, receipt_ms: int):
    if (report.boot != selected.boot or report.phase != 'idle' or not report.io_qualified or
        not report.fresh or not report.reference_valid or not report.power_ready or report.height_mm is None):
        raise ValueError('Fresh qualified idle physical reference and power are required')
    stamp = source_stamp(report, receipt_ms)
    return Device(selected.device_id, selected.boot, command_floor, selected.calibration,
        selected.low_um/1000, selected.high_um/1000, report.height_mm,
        selected.max_speed_um_s/1000, selected.max_accel_um_s2/1000,
        stamp.sample_ms, stamp.clock_error_ms, True, True, stamp.sequence)


def normalize_plan(job):
    """Round shared wire geometry once, ties to even, at most 0.5 micrometre.

    Preserve one shared origin/target for a normal job. Explicit alignment jobs
    retain their separate origins. Never clamp to one member's endpoint.
    All validation precedes mutation so a failed plan cannot partly escape.
    """
    def rounded(value):
        if type(value) not in (int,float,Decimal) or not math.isfinite(value):
            raise ValueError('Invalid wire-plan geometry')
        exact=Decimal(str(value))*1000
        encoded=exact.to_integral_value(rounding=ROUND_HALF_EVEN)
        if abs(encoded-exact)>Decimal('0.5'): raise ValueError('Wire precision exceeded')
        return integer(int(encoded),-10**9,10**9,'wire coordinate')/1000
    # Derive the shared percentage in decimal from its public inputs so a
    # binary float epsilon does not accidentally select the other half-µm tie.
    low=Decimal(str(max(m.low_mm for m in job.members.values())))
    high=Decimal(str(min(m.high_mm for m in job.members.values())))
    target=rounded(low+(high-low)*Decimal(str(job.requested_percent))/100)
    origins={name:rounded(cmd['start_height_mm']) for name,cmd in job.commands.items()}
    for name,cmd in job.commands.items():
        member=job.members[name];origin=origins[name]
        if (not member.low_mm<=target<=member.high_mm or
            not member.low_mm<=origin<=member.high_mm or abs(origin-member.height_mm)>5):
            raise ValueError('Normalized wire plan exceeds reachable range/start tolerance')
        micrometres(cmd['speed_mm_s']);micrometres(cmd['accel_mm_s2'])
    job.target_height_mm=target
    for name,cmd in job.commands.items():
        cmd['start_height_mm']=origins[name];cmd['target_height_mm']=target
