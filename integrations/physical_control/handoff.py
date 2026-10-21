"""Bounded physical OFF completion observation, never motion readiness."""
from dataclasses import dataclass
import math
from integrations.thread_transport.client import ProtocolError, _hex64, _json
from integrations.thread_transport.motion import PHASES, RESULTS, MAX_TIME

# Existing C6 qualified configuration's largest permitted rate/stamp bounds.
RATE_PPM = 10000
STAMP_GUARD_US = 1000
MAX_AGE_US = 30000

@dataclass(frozen=True)
class Handoff:
    boot: int
    nonce: int
    sampled_us: int
    responded_us: int
    command: int
    received_message: int
    phase: str
    result: str
    reference_valid: bool
    height_mm: float | None
    settled_off: bool
    receipt_us: int
    earliest_host_us: int
    latest_host_us: int

    def current(self, now_us):
        return (self.settled_off and self.sampled_us > 0 and
                self.receipt_us <= now_us and 0 <= now_us-self.earliest_host_us <= MAX_AGE_US)


def decode(payload, *, boot, nonce, sent_host_us, received_us):
    v = _json(payload)
    required = {'version','boot','nonce','sampled_us','responded_us','command','received_message',
                'phase','result','reference_valid','height_mm','settled_off'}
    if (set(v) != required or type(v['version']) is not int or v['version'] != 1 or
        _hex64(v['boot'],nonzero=True) != boot or _hex64(v['nonce'],nonzero=True) != nonce or
        type(v['reference_valid']) is not bool or type(v['settled_off']) is not bool or
        type(v['phase']) is not str or v['phase'] not in PHASES or
        type(v['result']) is not str or v['result'] not in RESULTS):
        raise ProtocolError('Unsupported handoff or changed boot/nonce')
    sample, response = _hex64(v['sampled_us']), _hex64(v['responded_us'])
    command, message = _hex64(v['command']), _hex64(v['received_message'])
    if (any(type(n) is not int or not 0 <= n <= MAX_TIME for n in (sent_host_us,received_us)) or
        received_us < sent_host_us or not sample <= response <= MAX_TIME):
        raise ProtocolError('Invalid handoff clock/source order')
    height=v['height_mm']
    if height is not None and (type(height) not in (float,int) or not math.isfinite(height) or not -1e6 <= height <= 1e6):
        raise ProtocolError('Invalid actual handoff coordinate')
    if v['reference_valid'] != (height is not None):
        raise ProtocolError('Handoff reference/coordinate mismatch')
    if v['settled_off'] and (not sample or v['phase']!='idle' or v['result'] not in ('finished','stopped')):
        raise ProtocolError('Handoff fabricated terminal OFF')
    # This interval is not a synchronized clock estimate. It bounds the age of
    # this one authenticated observation using original source elapsed time and
    # the whole measured exchange. Both stamp guards are included, rounding out.
    delta=response-sample
    oldest=((delta+2*STAMP_GUARD_US)*1_000_000+999999-RATE_PPM)//(1_000_000-RATE_PPM)
    youngest=max(0,delta-2*STAMP_GUARD_US)*1_000_000//(1_000_000+RATE_PPM)
    earliest=received_us-(received_us-sent_host_us)-oldest
    latest=received_us-youngest
    if sample and (earliest<0 or latest<earliest):
        raise ProtocolError('Unrepresentable handoff source interval')
    return Handoff(boot,nonce,sample,response,command,message,v['phase'],v['result'],v['reference_valid'],
                   height,v['settled_off'],received_us,max(0,earliest),max(0,latest))

class History:
    def __init__(self): self.previous=None
    def accept(self, result):
        old=self.previous
        if old:
            if (result.boot!=old.boot or result.nonce<=old.nonce or result.responded_us<old.responded_us or
                result.sampled_us<old.sampled_us or result.received_message<old.received_message or
                result.command<old.command):
                raise ProtocolError('Handoff source, nonce or consumed identity regressed')
            if result.sampled_us==old.sampled_us and any(getattr(old,k)!=getattr(result,k) for k in
                ('command','phase','result','reference_valid','height_mm')):
                raise ProtocolError('Conflicting terminal source snapshot')
        self.previous=result
        return result
