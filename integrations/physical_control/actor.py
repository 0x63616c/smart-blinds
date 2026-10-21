"""One permanent DTLS thread per pairing; job facades never own another handle."""
import threading
import time
from integrations.physical_bridge.service import Reader
from integrations.telemetry_transport.client import TelemetrySession
from integrations.thread_transport.client import ProtocolError, TransportError
from integrations.thread_transport.clock import ClockUncertain
from integrations.thread_bridge.worker import Worker, now_us
from .session import ActorSession


class ActorWorker(Worker):
    def __init__(self, actor, selected, reservation, library, events, **kwargs):
        self.actor = actor
        super().__init__(selected, reservation, library, events,
                         session_factory=lambda *a, **k: actor.session, **kwargs)
        self.done = threading.Event()
        self.completed = None
        self.reusable = False

    def start(self):
        if self.thread is not None: raise RuntimeError('Job facade is single-use')
        self.thread = self.actor.thread
        self.actor.assign(self)

    def _call(self, name, **kwargs):
        # Already-running bounded exchanges cannot be interrupted. Every next
        # ordinary exchange rechecks cancellation before touching the handle.
        if self.mailbox.stopped and name in ('wake','qualify_clock','prepare','commit','lease'):
            raise ProtocolError('STOP superseded ordinary transport work')
        return super()._call(name, **kwargs)

    def completion(self):
        with self.lock: return self.completed

    def _completion(self, h):
        if not self.active or h.command != self.reservation.command: return False
        if h.phase not in ('settling','idle') or h.result not in ('finished','stopped'): return False
        self.terminal = True  # Definitive terminal outcome; never send late leases.
        if h.result == 'stopped' and not self.stop_sent and not self.mailbox.stopped:
            self._fail('Unrequested local stop')
        if h.current(self.clock()):
            if not h.reference_valid or h.height_mm is None:
                raise ProtocolError('Terminal coordinate unavailable')
            with self.lock: self.completed = h; self.stop_confirmed = True
            self.shutdown.set()
        # Settling still requires the ordinary fresh power/reference report.
        # Only terminal idle may intentionally have withdrawn active evidence.
        return h.phase == 'idle'

    def _observe(self, report):
        if self.active and report.command == self.reservation.command and report.phase in ('settling','idle') and report.result in ('finished','stopped'):
            # Intentional sensor closure can withdraw power; only the separate
            # physical OFF endpoint may prove completion, never this string.
            self.terminal = True
            if report.new_sample:
                with self.lock: self.latest = report
            self.last_poll = self.clock()
            self._completion(self._call('handoff'))
            if report.phase == 'settling': return super()._observe(report)
            return report
        return super()._observe(report)

    def _poll(self):
        if self.active and self._completion(self._call('handoff')):
            self.last_poll = self.clock()
            return self.latest
        try: return super()._poll()
        except ClockUncertain:
            # Clock qualification may be cleared at terminal idle. Independent
            # OFF proof can terminate a job, but cannot authorize another move.
            if self.active and self._completion(self._call('handoff')):
                return self.latest
            raise

    def _qualify(self):
        if self.active and self._completion(self._call('handoff')): return
        try: super()._qualify()
        except ClockUncertain:
            if self.active and self._completion(self._call('handoff')): return
            raise

    def _dispose_session(self):
        # This executes only on the persistent actor. Never close its handle
        # from a coordinator/HTTP thread or retry uncertain native delivery.
        if self.session is None or self.session._failed: return
        if not self.active:
            self.reusable = not self.session._failed
            return
        until = self.clock()+600000
        while self.clock()<until:
            try:
                h = self._call('handoff')
                self._completion(h)
                if h.current(self.clock()) and h.command==self.reservation.command:
                    self.reusable = True; return
            except Exception: return
            time.sleep(.005)

    def close(self):
        # Group.close already publishes its source-stamped STOP. This fallback
        # keeps an unfinished facade from outliving its owner without STOP.
        if self.thread is not None and not self.done.is_set():
            self.shutdown.set(); self.changed.set()
            if not self.done.wait(2): self._fail('Actor job close deadline')


class Actor(Reader):
    """Reader's presentation is reused; only this thread touches the session."""
    def __init__(self, pairing, library, selected=None, floor=None, *, clock=now_us, period_s=15):
        pairing.validate()
        if not 1 <= period_s <= 30: raise ValueError('Invalid polling period')
        self.pairing, self.library, self.selected, self.floor = pairing, library, selected, floor
        self.clock, self.period = clock, period_s
        self.lock = threading.Lock()
        self.halt = threading.Event(); self.changed = threading.Event()
        self.observation = None; self.failed = False
        self.pending = None; self.current = None; self.session = None
        self.last_position = None; self.last_report = None
        self.thread = threading.Thread(target=self._run, name='physical-'+pairing.device_id)
        self.thread.start()

    def assign(self, worker):
        with self.lock:
            if self.failed or self.halt.is_set() or self.selected is None or self.pending or self.current:
                raise RuntimeError('Physical actor is unqualified, busy or unavailable')
            if worker.selected != self.selected or worker.reservation.device_id != self.selected.device_id:
                raise RuntimeError('Job belongs to another explicitly selected owner')
            self.pending = worker
        self.changed.set()

    def _run(self):
        try:
            p = self.pairing
            kwargs = dict(expected_boot=p.boot, timeout_ms=1000)
            if self.selected:
                self.session = ActorSession(self.library,p.host,p.port,p.identity,p.key,
                    calibration_revision=self.selected.calibration,command_floor=self.floor[0],
                    message_floor=self.floor[1],**kwargs)
            else:
                self.session = TelemetrySession(self.library,p.host,p.port,p.identity,p.key,clock=self.clock,**kwargs)
            poll_at = 0
            while not self.halt.is_set():
                with self.lock:
                    worker,self.pending = self.pending,None
                    self.current = worker
                if worker:
                    try:
                        if self.session.reservation and self.session.consumed_message>self.session.reservation.floor:
                            self.session.handoff() # Fresh actual proof, never rebind from a cached idle enum.
                        self.session.reserve(worker.reservation)
                        worker._run()
                        with self.lock:
                            self.last_position=worker.completed or self.last_position
                            self.last_report=worker.latest or self.last_report
                        if not worker.reusable: raise ProtocolError('Motion owner ended without verified OFF')
                    except Exception as error:
                        worker._fail(type(error).__name__+': job ownership failed')
                        raise
                    finally:
                        with self.lock: self.current=None
                        worker.done.set()
                    poll_at = 0
                elif self.clock()>=poll_at:
                    value=self.session.poll()
                    with self.lock: self.observation=value
                    poll_at=self.clock()+int(self.period*1e6)
                self.changed.wait(.01 if self.pending else max(0,min(self.period,(poll_at-self.clock())/1e6)))
                self.changed.clear()
        except Exception:
            with self.lock:
                self.failed=True
                waiting=self.pending or self.current
            if waiting:
                waiting._fail('Persistent owner failed');waiting.done.set()
        finally:
            if self.session is not None: self.session.close()

    def close(self):
        self.halt.set();self.changed.set()
        with self.lock: worker=self.current or self.pending
        if worker: worker.shutdown.set();worker.changed.set()
        self.thread.join(3)
        if self.thread.is_alive():
            with self.lock:self.failed=True
            raise RuntimeError('Physical owner did not close')
