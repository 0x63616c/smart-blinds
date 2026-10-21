# Host transport timing diagnostics

## Ordered request observations in the host fixture

The next CI run, [39542952966](https://github.com/0x63616c/smart-blinds/actions/runs/39542952966),
failed separately at `actual handoff request failed`. The fixture passed
`now(), now()` as receive/send arguments in ten places. C++ does not specify
their evaluation order, while the binding correctly rejects a send observation
older than receipt. The actual radio handler already captures receipt first.

The fixture now captures those observations in two sequenced statements. An
increasing-clock control detects inverted, reused or omitted captures; the real
binding still rejects explicitly reversed timestamps without consuming the
handoff nonce. A handoff assertion now prints the returned code and nonce.
No production source, deadline, wire schema or timing guard changed.

The candidate and an independent fresh build from the owning checkout both
passed `c6_runtime_owner_tests` on their first run (43.232 s and 43.37 s).
A deliberately reversed capture order fails the focused control. These are
host-software results, not physical-device timing evidence. The original CI log
did not include its return code, so it cannot prove retrospectively that this
specific guard caused that historical failure.

That run's separate transport result was 61/62, with a peer returning `invalid`
and zero executor/I/O diagnostic fields. Its exact rejecting guard remains
unidentified; the fixture correction does not claim to resolve that failure.

All thirteen jobs passed for the fixture correction in
[CI run 39546114350](https://github.com/0x63616c/smart-blinds/actions/runs/39546114350).
That successful run includes the real transport tests and all four embedded
builds; it does not retrospectively identify the historical rejection.

## Inbox publication and cycle time

A separate deterministic regression reproduces a production ordering defect:
the motion session captured cycle time at 2,000,000 microseconds, then consumed
a command published at 2,000,010. Its future-receipt guard correctly refused
the command relative to the older observation, even though the producer had
published a fresh command before the dequeue.

The session now copies at most one eligible ordinary command before observing
cycle time. A command arriving during the clock read stays queued for the next
cycle. The copy grants no authority: STOP, faults and the existing freshness,
lease, connection and calibration checks still precede execution. Remote STOP
is sampled after the clock, so a STOP arriving during that read still outranks
an already copied command. No timestamp is rewritten and no deadline is relaxed.

The focused controls retain the four-slot queue, one command per cycle, exact
40 ms queue-age boundary, replay rejection, reversed/future/stale clock checks,
OFF holds, STOP priority, source-based lease expiry and control-cadence faults.
Both the original dequeue order and an incorrectly moved STOP sample are
rejected by deliberate regression mutations. The candidate passed all 24 host
targets and four focused sanitizer targets. The owning checkout independently
passed all 24 host targets on its first run in 49.09 seconds.

These are software scheduling results. The earlier CI peer rejection did not
record its exact invalid guard, so this independently reproduced defect is not
claimed as its established cause. [CI for this production correction](https://github.com/0x63616c/smart-blinds/actions/runs/39547483287)
passed all thirteen jobs at `33cc04a`, including transport and all four embedded
builds. Physical-device qualification remains a separate validation step.

## First-failing I/O observations

The localhost peer is a synthetic plant around the real motion session and
executor. It is not a real-time host, MCU timing qualification, or a physical
motor. The executor still enforces a 100 µs I/O envelope, 20 ms control cadence,
and 500 µs cycle budget. This checkpoint changes no production clocks, limits,
protocol fields, or firmware sources.

The fixture records the first bad I/O envelope: operation, executor-before,
method-entry, method-return and executor-after times, return value, ordering,
injected-probe kind, and the thread CPU interval when the OS supports it. Those
values use the existing real monotonic clock. Cleanup cannot overwrite the first
bad operation. They are diagnostic data, never motion authority. CPU measurement
adds observable overhead; its cost is not subtracted from any deadline.

`MotionPeer.io_probe_next()` supplies three explicit test-only fault probes:

* `during_call`: actually sleep inside one selected synthetic method.
* `after_return`: actually sleep before the executor's next clock sample.
* `false_result`: execute the synthetic method, then return false.

The slow probes and existing whole-worker stall test assert fault, invalidated
reference, inhibited output, and no later recovery. The probes do not run on
production hardware or enter production library builds. Fault metrics publish
before `first_executor_fault`; inspect a nonzero first fault before treating
them as a completed record.

## Evidence and remaining question

Original CI run 39502050091 at 313c35d had one failed seven-peer test out of 59.
Peer 5 reported executor `io` (enum 5), a 594 µs cycle, and a 10,094 µs start gap.
It did not record the operation or thread CPU time. That record cannot establish
which I/O call failed or distinguish a bad return from a timing overrun.

The first diagnostic Mac run executed 62 tests: 59 passed and three group tests
failed. Two failure records identify `coast`, returning true with ordered stamps
and no injected fault:

| Scenario | I/O wall interval | Thread CPU interval | Interval inside method |
| --- | ---: | ---: | ---: |
| First job in two-job test | 107 µs | 6.209 µs | 106 µs |
| Seven-peer equal-height test | 193 µs | 13.208 µs | 192 µs |

These reproductions spent most of the interval off CPU within synthetic
`coast`/`advance`, whose normal implementation performs arithmetic and clock
reads, with no mutex, blocking I/O, or deliberate wait. Host descheduling or
clock-system-call waiting can explain that wall/CPU split; it is not evidence
of a real C6 I/O delay. The third failure had the same `fault/io` outcome but its
assertion omitted metrics. That assertion and the equivalent worker-loss
assertion now include them. The original CI cause is still unconfirmed.

All three injected-I/O probes and the existing 30 ms control-stall probe passed
in the focused first run and in the full run. No test was retried to obtain a
pass. The failing full run is retained. Linux comparison was not completed:
the existing pinned IDF image lacked OpenSSL development headers, and an optional
derived-image build was cancelled to conserve disk and avoid interfering with
the active CAD runner. Its diagnostics and cancellation log are retained.

This is an observability checkpoint, not a claimed timing fix. A future host
fixture clock-model change needs separate review: real control cadence, command
ages, leases, delayed I/O fault tests and production limits must remain intact.
Fresh Linux/CI operation-level evidence is still required.

An independent fresh build from the owning checkout also passed all four focused
fault probes. That verification does not replace the retained full-run failures.

## Separate I/O failures from heartbeat acknowledgment expiry

A bounded, instrumented replay of the six retained strict-host failures executed
each case once: four passed and two failed. One failure began with a 140 µs
ordinary coast operation; the other began with a 486 µs heartbeat-pulse operation.
Both exceeded the unchanged 100 µs I/O limit. In the latter case, the executor
reported a heartbeat fault even though its combined condition had short-circuited
before checking the heartbeat acknowledgment. A later heartbeat expiry occurred
during cleanup and was not the initiating cause. The wall/CPU split is compatible
with host scheduling delay; it does not prove that cause or characterize C6 timing.

The executor now reports a failed or over-budget request/pulse operation as I/O,
and an expired request/edge acknowledgment as heartbeat. The split preserves the
same calls, clock reads, short-circuit behavior, deadlines and shutdown sequence.
Cleanup I/O failure can still override the final fault label. No transport schema
or motion permission changes, and this correction does not resolve the underlying
host timing overruns.

Eight cases in the existing executor test cover false and slow request/pulse I/O,
acknowledgment at 100 µs, and expiry at 101 µs. They check exact clock/I/O counts,
cleanup order and inactive outputs. The target and sanitizer build pass; restoring
either combined condition independently fails with its classification diagnostic.
A fresh owning-checkout build also passed all six relevant executor, session and
runtime targets. The optional work-only first-fault instrumentation remains outside
production; its old source pins intentionally reject the modified executor.
