"""Explicit single-job library adapter; no discovery, HA service, or retries."""
import queue
import time
from integrations.home_assistant.coordinator import Phase, begin_group
from .mapping import device, source_stamp, normalize_plan
from .worker import Worker, now_us
from integrations.home_assistant.freshness import SourceStamp, earliest_sample


class Group:
    """The calling thread owns Job. Each peer has one bounded transport worker.

    A reserved job is single-use, including failure before any packet. Call close
    in a finally block; closing an active group requests STOP, never resume.
    """
    def __init__(self, selections, ledger, library, *, worker_factory=Worker, clock=now_us):
        self.clock = clock
        self.events = queue.Queue(maxsize=32)
        self.reservations = ledger.reserve(selections)
        self.workers = {s.device_id: worker_factory(s, self.reservations[s.device_id], library,
                        self.events, clock=clock) for s in selections}
        self.job = None
        self.closed = False
        self.started = False
        self.last_sample = {}

    def start(self, percent, *, align=False, speed_mm_s=20, accel_mm_s2=40, timeout_s=6):
        if self.started or self.closed: raise RuntimeError('Group is single-use')
        self.started = True
        try:
            for w in self.workers.values(): w.start()
            until = self.clock()+int(timeout_s*1000000)
            while self.clock()<until:
                snapshots = {name:w.snapshot() for name,w in self.workers.items()}
                observed_us = self.clock()  # after every consumed owner copy
                if observed_us >= until: break
                now = observed_us//1000
                values = []
                for name, w in self.workers.items():
                    report, failure, ready, _, _ = snapshots[name]
                    if failure: raise RuntimeError(name+': '+failure)
                    if w.thread is not None and not w.thread.is_alive():
                        raise RuntimeError(name+': worker exited during preflight')
                    if ready and report is not None:
                        try: values.append(device(w.selected, report, self.reservations[name].command-1, now))
                        except ValueError: pass  # Await fresh simultaneous evidence, bounded below.
                if len(values)==len(self.workers):
                    self.job, commands = begin_group(values, percent, now, align=align,
                        speed_mm_s=speed_mm_s, accel_mm_s2=accel_mm_s2)
                    normalize_plan(self.job)
                    self.last_sample={d.device_id:d.report_sequence for d in values}
                    self._send(commands)
                    return self.job
                time.sleep(.002)
            raise RuntimeError('All-peer qualified preflight deadline')
        except Exception:
            self.close()
            raise

    def _send(self, envelopes):
        failed=[]
        for envelope in envelopes:
            if not self.workers[envelope.recipient].submit(envelope): failed.append(envelope.recipient)
        if failed and self.job and self.job.phase not in (Phase.COMPLETE,Phase.ABORTED):
            self._send(self.job.abort('Worker rejected delivery: '+','.join(failed)))

    def abort(self, reason='Explicit group STOP'):
        if self.job: self._send(self.job.abort(reason))

    def step(self):
        if self.job is None or self.closed: raise RuntimeError('No open group job')
        if self.job.phase in (Phase.COMPLETE,Phase.ABORTED): return self.job.phase
        # Copy all consumed publications before sampling their validation time.
        # In particular, terminal OFF may be published after the ordinary report.
        snapshots={name:w.snapshot() for name,w in self.workers.items()}
        completions={name:getattr(w, 'completion', lambda: None)() for name,w in self.workers.items()}
        receipts=[]
        for _ in range(self.events.maxsize):
            try: receipts.append(self.events.get_nowait())
            except queue.Empty: break
        observed_us=self.clock()
        now=observed_us//1000
        # A failure is checked before dispatching any further ordinary work.
        for name,w in self.workers.items():
            failure=snapshots[name][1]
            if failure or (w.thread is not None and not w.thread.is_alive()):
                self.abort(name+': '+(failure or 'worker exited'))
                return self.job.phase
        for event in receipts:
            if event.kind!='queued' or event.device_id not in self.workers:
                self.abort('Invalid worker receipt'); return self.job.phase
            r=self.reservations[event.device_id]
            self._send(self.job.prepare_queued(event.device_id,r.boot,r.command,now))
        for name,(report,_,_,commit_message,_) in snapshots.items():
            if name in self.job.completed: continue
            completion=completions[name]
            if completion is not None:
                r=self.reservations[name]
                try:
                    if (completion.boot!=r.boot or completion.command!=r.command or
                        completion.result!='finished' or not completion.reference_valid or
                        completion.height_mm is None or not completion.current(observed_us)):
                        raise ValueError('Invalid terminal OFF observation')
                    # Outward-rounded one-exchange source interval. This is only
                    # completion evidence; it creates no qualified motion clock.
                    lo=completion.earliest_host_us//1000
                    hi=(completion.latest_host_us+999)//1000
                    centre=(lo+hi)//2
                    stamp=SourceStamp(centre,completion.sampled_us,max(centre-lo,hi-centre))
                    earliest_sample(stamp,now,30)
                    self._send(self.job.report(name,r.boot,r.command,now,stamp=stamp,
                        height_mm=completion.height_mm,state='idle'))
                except ValueError:
                    self.abort(name+': invalid terminal OFF source')
                continue
            if report is None or name not in self.job.queued or report.sampled_us<=self.last_sample.get(name,0): continue
            r=self.reservations[name]
            if report.boot!=r.boot:
                self.abort(name+': boot changed'); break
            # A queued intent may precede its first control iteration. It is not
            # readiness and cannot refresh Job telemetry with the old command.
            if report.command!=r.command: continue
            try: stamp=source_stamp(report,now,max_age_ms=30 if report.ready else 100)
            except ValueError:
                self.abort(name+': stale/uncertain worker source'); break
            self.last_sample[name]=report.sampled_us
            if (not report.io_qualified or not report.reference_valid or not report.power_ready or
                report.height_mm is None or report.phase=='fault' or
                report.result not in ('accepted','finished')):
                self.abort(name+': worker revoked motion evidence'); break
            if report.phase=='ready' and report.ready and self.job.phase==Phase.PREPARING and name not in self.job.prepared:
                self._send(self.job.acknowledge(name,r.boot,r.command,'prepared',now,stamp=stamp))
            elif (commit_message and report.last_message>=commit_message and report.phase=='committed' and
                  self.job.phase==Phase.COMMITTING and name not in self.job.committed):
                self._send(self.job.acknowledge(name,r.boot,r.command,'committed',now,stamp=stamp))
            else:
                states={'preparing':'preparing','ready':'prepared','committed':'armed',
                        'moving':'moving','settling':'settling','idle':'idle'}
                # A terminal outcome, not merely idle/at target, proves completion.
                if report.phase in ('settling','idle') and report.result!='finished':
                    self.abort(name+': no definitive completed outcome'); break
                self._send(self.job.report(name,r.boot,r.command,now,stamp=stamp,
                    height_mm=report.height_mm,state=states.get(report.phase,'invalid')))
        self._send(self.job.tick(now))
        return self.job.phase

    def close(self):
        if self.closed: return
        if self.job and self.job.phase not in (Phase.COMPLETE,Phase.ABORTED): self.abort('Group owner closed')
        # Allow ordered STOP handling, but never call a queue receipt proof of OFF.
        until=time.monotonic()+.8
        while self.job and self.job.phase==Phase.ABORTED and time.monotonic()<until:
            if all((not w.active or w.snapshot()[4] or not w.thread or not w.thread.is_alive())
                   for w in self.workers.values()): break
            time.sleep(.005)
        for w in self.workers.values(): w.close()
        self.closed=True

    def __enter__(self): return self
    def __exit__(self,*_): self.close()
