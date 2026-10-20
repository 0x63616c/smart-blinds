"""One bounded transport owner per explicitly selected node; no automatic retry."""
from collections import deque
from dataclasses import dataclass, replace
import queue
import threading
import time
from integrations.thread_transport.motion import MotionSession
from integrations.thread_transport.clock import ClockUncertain
from integrations.thread_transport.client import ProtocolError
from .mapping import micrometres, microseconds


def now_us(): return time.monotonic_ns()//1000


@dataclass(frozen=True)
class Event:
    device_id: str
    kind: str
    detail: str = ''


class Mailbox:
    """Four ordinary intents, one coalesced unsent lease, priority STOP."""
    def __init__(self):
        self.lock = threading.Lock()
        self.commands = deque()
        self.lease = None
        self.stopped = False
        self.stop_source_ms = None

    def put(self, envelope):
        with self.lock:
            if self.stopped: return False
            if envelope.kind == 'stop':
                self.stopped = True
                self.stop_source_ms = envelope.payload.get('sent_ms')
                self.commands.clear(); self.lease = None
                return True
            if envelope.kind == 'lease':
                # Newest *original source* intent replaces unsent older intent;
                # neither has been assigned a wire sequence yet.
                if self.lease is None or envelope.payload['sent_ms'] > self.lease.payload['sent_ms']:
                    self.lease = envelope
                return True
            if len(self.commands) >= 4: return False
            self.commands.append(envelope)
            return True

    def take(self):
        with self.lock:
            if self.stopped: return 'stop'
            if self.commands: return self.commands.popleft()
            value, self.lease = self.lease, None
            return value


class Worker:
    def __init__(self, selected, reservation, library, events, *, session_factory=MotionSession,
                 active_timeout_ms=40, clock=now_us):
        selected.validate()
        self.selected, self.reservation, self.library = selected, reservation, library
        self.events, self.factory, self.clock = events, session_factory, clock
        self.active_timeout_ms = active_timeout_ms
        self.mailbox = Mailbox()
        self.shutdown = threading.Event()
        self.changed = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.failure = None
        self.preflight = False
        self.commit_message = 0
        self.prepare_message = 0
        self.stop_confirmed = False
        self.calls = []  # At most bounded job calls; no keys/payloads.
        self.session = None
        self.thread = None
        self.probe = 0
        self.last_clock = 0
        self.last_poll = 0
        self.active = False
        self.stop_sent = False
        self.terminal = False
        self.pending_message = 0

    def start(self):
        if self.thread is not None: raise RuntimeError('Worker is single-use')
        self.thread = threading.Thread(target=self._run, name='blind-'+self.selected.device_id)
        self.thread.start()

    def submit(self, envelope):
        p = envelope.payload
        if (envelope.recipient != self.selected.device_id or envelope.retain or
            p.get('boot_nonce') != self.selected.boot or p.get('sequence') != self.reservation.command or
            type(p.get('sent_ms')) is not int or not 0 < p['sent_ms'] <= (2**63-1)//1000 or
            envelope.kind not in ('prepare', 'commit', 'lease', 'stop')):
            self._fail('Invalid coordinator envelope'); return False
        # Own the primitive-valued payload; callers cannot retime queued work
        # by mutating the coordinator's original dictionary after submission.
        owned=replace(envelope,payload=dict(p))
        if not self.mailbox.put(owned):
            self._fail('Command mailbox overflow or closed'); return False
        self.changed.set(); return True

    def snapshot(self):
        with self.lock: return self.latest, self.failure, self.preflight, self.commit_message, self.stop_confirmed

    def _emit(self, kind, detail=''):
        try: self.events.put_nowait(Event(self.selected.device_id, kind, detail))
        except queue.Full: self._fail('Critical event queue overflow')

    def _fail(self, reason):
        with self.lock:
            if self.failure is None: self.failure = reason
        self.changed.set()

    def _call(self, name, **kwargs):
        before = self.clock()
        try: return getattr(self.session, name)(**kwargs)
        finally:
            self.calls.append((name, self.clock()-before))
            if len(self.calls)>20000: self._fail('Call budget exhausted')

    def _poll(self):
        report = self._call('motion_status')
        self.last_poll = self.clock()
        if report.new_sample:
            with self.lock: self.latest = report
        if self.preflight and (not report.io_qualified or not report.power_ready or not report.reference_valid):
            raise ProtocolError('Qualified preflight evidence was revoked: '+report.phase+'/'+report.result)
        if self.active and report.command == self.reservation.command:
            if report.phase == 'fault' or not report.reference_valid or not report.power_ready or not report.io_qualified:
                raise ProtocolError('Worker lost qualified reference or power')
            if report.result == 'stopped' and not self.stop_sent:
                raise ProtocolError('Unrequested local stop')
            if report.result not in ('none', 'accepted', 'finished', 'stopped'):
                raise ProtocolError('Device rejected control operation: '+report.result)
            if report.result == 'finished' and report.phase in ('settling', 'idle'):
                self.terminal = True
            if report.phase == 'idle' and report.result in ('finished', 'stopped'):
                with self.lock: self.stop_confirmed = True
        return report

    def _fresh(self, phase, *, timeout_us=60000):
        until = self.clock()+timeout_us
        while self.clock()<until and not self.shutdown.is_set():
            if self.mailbox.stopped: raise ProtocolError('STOP superseded pending command')
            report = self._poll()
            if (report.phase==phase and report.new_sample and report.fresh and
                (phase!='ready' or report.ready)):
                return report
            if report.phase in ('fault','unreferenced'):
                raise ProtocolError('Device unavailable during command readiness')
            self.changed.wait(.003); self.changed.clear()
        raise ProtocolError('No fresh worker readiness before command deadline')

    def _qualify(self):
        # Qualification changes the device probe atomically. Never overtake a
        # queued request which still names the preceding probe; a queue receipt
        # is not evidence that the control worker consumed that request.
        if self.pending_message:
            report=self._poll()
            if report.last_message < self.pending_message:
                self.changed.wait(.002); self.changed.clear()
                return
        self.probe += 1
        self._call('qualify_clock', boot=self.selected.boot, sequence=self.probe)
        self.last_clock = self.clock()

    def _open(self):
        s = self.selected
        self.session = self.factory(self.library, s.host, s.port, s.identity, s.key,
            expected_boot=s.boot, calibration_revision=s.calibration,
            message_floor=self.reservation.floor, timeout_ms=1000)
        status = self._call('status')
        if not status.io_qualified: raise ProtocolError('Device has no qualified I/O')
        if not status.awake: self._call('wake', boot=s.boot, sequence=status.last_wake+1)
        readiness = self._call('readiness')
        self.probe = readiness.last_probe
        self._qualify()
        deadline = self.clock()+5000000
        while self.clock()<deadline and not self.shutdown.is_set():
            if self.clock()-self.last_clock>=200000: self._qualify()
            report = self._poll()
            if report.command >= self.reservation.command:
                raise ProtocolError('Device command exceeds trusted ledger floor')
            if (report.phase=='idle' and report.new_sample and report.fresh and report.reference_valid and
                report.power_ready and report.io_qualified):
                self.session.set_active_deadline(self.active_timeout_ms)
                with self.lock: self.preflight=True
                return
            if report.phase not in ('idle','unreferenced'):
                raise ProtocolError('Preflight requires idle referenced device')
            self.changed.wait(.01); self.changed.clear()
        raise ProtocolError('Preflight evidence deadline')

    def _dispatch(self, envelope):
        p, kind = envelope.payload, envelope.kind
        if kind=='lease' and self.terminal: return  # Definitive endpoint settling/idle, not cached optimism.
        if kind=='prepare': self._fresh('idle')
        elif kind=='commit': self._fresh('ready')
        sent = microseconds(p['sent_ms'])
        if not 0 <= self.clock()-sent <= 100000:
            raise ProtocolError('Expired original coordinator source timestamp')
        message = self.reservation.take()
        kwargs = dict(message=message, command=self.reservation.command, sent_us=sent)
        if kind=='prepare':
            kwargs.update(start_us=microseconds(p['start_ms']), origin_um=micrometres(p['start_height_mm']),
                target_um=micrometres(p['target_height_mm']), speed_um_s=micrometres(p['speed_mm_s']),
                accel_um_s2=micrometres(p['accel_mm_s2']))
            self.active = True  # Uncertain outcome still needs STOP/lease expiry.
        self._call(kind, **kwargs)
        self.pending_message=message
        if kind=='prepare':
            self.prepare_message=message
            self._emit('queued')
        elif kind=='commit':
            with self.lock: self.commit_message=message

    def _stop(self):
        if self.stop_sent or not self.active: return
        self.stop_sent=True
        number=self.reservation.take_stop()  # Burn highest ID even if I/O fails.
        source=self.mailbox.stop_source_ms
        self._call('stop', message=number, command=self.reservation.command,
                   sent_us=microseconds(source) if source is not None else self.clock())

    def _run(self):
        try:
            self._open()
            while not self.shutdown.is_set():
                with self.lock: failed=self.failure is not None
                intent=self.mailbox.take()
                if failed or intent=='stop':
                    self._stop()
                    # STOP queue receipt is not proof of a settled physical result.
                    until=self.clock()+600000
                    while self.clock()<until and not self.shutdown.is_set():
                        report=self._poll()
                        if report.phase=='idle' and report.result in ('finished','stopped'): break
                        self.changed.wait(.01); self.changed.clear()
                    break
                if intent is not None: self._dispatch(intent)
                elif self.clock()-self.last_clock>=200000: self._qualify()
                elif self.clock()-self.last_poll>=30000: self._poll()
                else:
                    self.changed.wait(.002); self.changed.clear()
        except Exception as error:
            self._fail(type(error).__name__+': '+str(error))
            try: self._stop()
            except Exception: pass  # Never reconnect or report an unconfirmed stop as confirmed.
        finally:
            if self.active and not self.terminal and not self.stop_sent:
                try: self._stop()
                except Exception: pass
            if self.session is not None: self.session.close()

    def close(self):
        self.shutdown.set(); self.changed.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
            if self.thread.is_alive(): self._fail('Worker did not stop within join deadline')
