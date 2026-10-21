# Host transport timing diagnostics

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
