# Isolated joint power mailbox

This is portable implementation and compile evidence. **No application creates
the mailbox, no physical qualification is supplied, and no motor or charge
permission changes.** The current C6 runtime still uses its previous sensor
worker. The earlier Thread group timing failure is unrelated and remains an
open investigation.

The mailbox solves the interval between accepting a new gauge serial and
delivering its report to a consumer. A joint-mode `OwnedSession` owns one
charger-first refresh: `BQ25798::capture_off()`, the existing 52-word gauge
capture/validation, then one joint commit. The complete gauge report, charger
report, window and **sole accepted gauge serial** enter a fixed-size slot under
one gate. Callers cannot submit raw records to the slot.

The joint session binds once to a mailbox and to a charger whose immutable
failure sink is that mailbox. Its standalone `read()` operation rejects and
retires the session; `current()` cannot authorize standalone publications.
Existing standalone sessions retain their previous API and tests. Neither
mode can be changed after construction. All charger operations and the gauge
session remain owned by the same sensor task; this does not prove that an
unrelated caller with a raw bus handle cannot interfere.

## Report lifetime

During a healthy charger or gauge refresh, readers can acquire the previous
complete pair until its original age expires. Completion replaces it once.
The first detected charger or gauge failure atomically retires the authority
before further cleanup or return work; a late success cannot restore it.

`read_latest(window, now)` returns an opaque, noncopyable `JointRead`.
Moving it transfers the single consumption right. `consume(now)` succeeds only
once, during the same immediate control iteration (at most 20 ms), with the
original source bounds and live epoch/window. A failed attempt also consumes
the right. Do not queue it, retain its resulting data across control iterations,
or treat a returned informational record as a new hardware approval.

A successful healthy replacement after the read linearizes does not invalidate
that immediate snapshot. Retirement and window closure do. This deliberately
differs from submitting an arbitrary earlier `Publication` to `current()`;
there is no such input API. Requiring the snapshot to remain newest after the
gate unlocks would recreate the handoff race.

All freshness checks call the existing `motion_power()` predicate:

| Evidence | Existing bound |
|---|---|
| Gauge observation | 250,000 µs |
| Conservative voltage conversion age | 750,000 µs |
| Conservative temperature conversion age | 4,250,000 µs |
| Charger acquisition duration and age | 250 ms, using its original millisecond clock |

No timestamp is replaced by queue/commit/wake time. The existing charger
millisecond comparison permits its exact 250 ms bucket, including a fractional
millisecond; it is preserved, not silently changed to a different bound.
Combined stale evidence fails even if each acquisition individually met its
own duration limit. This code cannot interrupt a synchronous SDK call which
never returns. Consumer age expiry and existing motion supervision remain
independent.

## Window and fault ownership

`open_window()` returns a nonwrapping token only after the prior window has
closed and its sensor acquisition has returned. `close_window(token)` withdraws
both old and in-progress evidence immediately. Closing an old token cannot
close a later window. An acquisition finishing after closure discards its
candidate; `closure_acknowledged(token)` becomes true when that owner returns.
An ordinary clean close does not destroy gauge continuity.

Park/resume in joint mode requires this acknowledged closure. No pre-sleep
record becomes available after resume; a new window and a complete fresh pair
are required. A failure detected after clean closure still retires the epoch
and destroys the ticket. Unknown reset, task/bus replacement, pack/config
ambiguity, explicit retirement and owner/context loss remain terminal.

The mailbox has one atomic typed first-cause latch (gauge, charger, lifecycle)
plus the existing bus epoch. Retirement does not take the gate or tear down
SDK handles. A stale object's retirement cannot cancel a deliberately issued
new bus epoch.

The charger now has an optional bounded `FailureSink`. It is called once for
the first error in an operation, before independent OFF cleanup. The charger
keeps `first_error()` separately from `inhibit_failed()`; its existing returned
error still prioritizes failure to establish OFF. The mailbox preserves the
first cause across later operations/cleanup. The sink must not reenter the
charger or perform I/O. `capture_off()` still services the configured watchdog
and consumes read-to-clear flags: it is not a read-only charger operation.
No additional charger write or charge-enable operation is introduced.

## Gate and runtime integration

Only fixed-size copy and metadata/atomic checks occur under `MailboxGate`.
Readiness arithmetic, bus access, GPIO, clock calls, notifications, logging,
allocation and waits stay outside. `JointRecord` is trivially copyable with a
compile-time maximum size of 384 bytes. The test gate uses a host mutex; the C6
backend uses a FreeRTOS critical section and is compiled without an instance.

In the pinned ESP-IDF C6 single-core configuration this masks interrupts; the
single-core try-enter timeout is not a duration bound. Actual copy duration
must be physically measured before admission. The backend does not spin or
wait for the lower-priority sensor worker. The mailbox, epoch and gate must
outlive the session and all snapshots; concurrent destruction is unsupported.

The next runtime integration must provide qualified continuity records, a
single sensor owner, monotonic clock values, clean closure/park acknowledgment
before PM locks are released, independent control/status snapshots, and
retirement if required notification/handoff fails. Take the snapshot near the
control input boundary and recheck asynchronous STOP/faults as usual.
Retirement after a final sampled check can only be acted on at the next control
boundary; this API does not promise instantaneous hardware shutdown.

## Verification

`power_mailbox_tests` uses the real portable BQ driver and owned gauge session
over synthetic buses. It checks charger-first ordering, retention and
replacement, original age boundaries, joint timeout, all 55 charger transfer
failures and 52 gauge transfer failures, all 42 head/tail guard positions,
typed cause precedence, immediate
single-use snapshots, both acquisition closure points, resume, wrong
owner/context, default qualification rejection, competing readers and
blocked-owner cancellation. Backend injection covers retirement at the commit
and reader-copy boundary. No I/O or clock callback may run while the test gate
is held. Counter saturation arithmetic is checked explicitly; billions of
actual window/serial increments are not executed.

The charger tests independently check first-failure notification before inhibit
cleanup, including a secondary inhibit failure and preserved legacy error
precedence. Existing standalone gauge tests continue to cover every guard
position and incremental/full predicate parity. Sanitizers, restored-bug
controls and pinned default/bench C6 compile results are recorded in the
source-bound checkpoint manifest under `work/gauge-mailbox-checkpoint`.
