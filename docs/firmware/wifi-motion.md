# Wi-Fi motion binding: unqualified implementation checkpoint

The separate `firmware/esp-idf-wifi-motion` target now binds the existing
authenticated 80-byte protocol to `MotionRuntime`, `MotionSession` and the real
C6 port. Empty qualification records and the default-OFF bench option prevent
hardware initialization. The existing radio-only evaluation remains intact.
This is compiled software and injected-I/O evidence, not commissioned hardware.

## Admission and ownership

Existing encrypted NVS credentials, board selection and approval retain exactly
the [evaluation contract](wifi-evaluation.md). No credentials are committed,
logged, generated or written; no owner network or device is contacted.
Radio approval only permits networking and the selected held-OFF pin setup.
It never fills `runtime::Configuration`.

Boot selects one hardware owner. Empty/unqualified records select permanent
GPIO holds at motor-request OFF, charging OFF, encoder OFF, WDI HIGH and both
motor inputs LOW. A future qualified build selects the control owner instead;
it must initialize its own pads/peripherals and never coexist with those holds.
Its GPIO/peripheral retention and disabled automatic sleep pin switching preserve
the verified parked state. It installs button wake/interrupts after port input
configuration, which otherwise disables interrupts.

One libcoap task owns the PSK-authenticated DTLS session, Wi-Fi policy, clock
probes and inbox producer. One priority-8 worker owns motor I/O and consumes at
most one ordinary request each cycle. The lower-priority power worker owns
I2C. `MotionBinding` maps a local Wi-Fi owner to a separately allocated ingress
generation. Neither generation comes from a packet; reconnect does not reset
the per-boot message floor. No automatic commit, reconnect during work, address
migration, radio migration or command replay is introduced.

The new target initially uses the same explicit IPv4/libcoap
DTLS 1.2 PSK AES-128-CCM-8 transport as the evaluation. Its tag-length and
commissioning limitations remain unchanged. Host protocol clients still require
explicit commissioned selection; this checkpoint adds no HA service or discovery.

## Cancellation before stale publication

SDK callbacks only advance a lock-free, nonwrapping revocation generation and
wake the control worker. They do not mutate the SPSC inbox or touch GPIO.
The callback marks its network event pending **before** revocation. The network
owner captures the acknowledged revocation generation **before** checking for
pending SDK events and publishing a copied network record. An event racing that
copy leaves an old generation, which the worker rejects; it cannot silently
relabel old attached/clock evidence with a new epoch.

The worker rechecks revocation after current sampling and before the session
cycle. Cached ready status also checks current revocation immediately. Generation
exhaustion or a delivery failure is permanent failure for this runtime.
This is bounded software cancellation, not an instantaneous hardware interlock;
the independently reviewed watchdog remains necessary for a stalled task.

Button edges latch raw STOP and notify the worker and radio wake relay. GPIOs
are also inspected before ADC. The first raw STOP enters the session without
waiting for an ADC conversion; a STOP arriving during sampling is checked again
in that cycle. While already settling, inhibited outputs may continue to collect
the observations needed for a final coordinate. A held button drains commands
and cannot restart motion. No endpoint gesture, calibration gesture or long-press
motion path is implemented here.

## Parking and sleep are evidence, not requested state

An activity counter brackets request publication with an odd/in-progress and
even/completed generation. It covers accepted/rejected enqueue attempts,
including authenticated priority STOP. A parked report carries that generation,
the revocation generation and its original observation timestamp. It is accepted
only within **30 ms**, with matching generations and no pending local STOP.
Consequently, an old idle report cannot finish a newly queued prepare, an
in-flight publication cannot authorize parking, and a stopped worker cannot
keep refreshing an OFF claim.

The physical check verifies motor request/charge/encoder OFF, WDI HIGH, both
motor pads LOW, stopped/disabled PCNT, stopped/disabled PWM timer and the
reviewed route/action readbacks. `awake_required=false` is only one condition.
Readback failure, missing evidence or failed teardown retains the control power
ownership and removes readiness. Fault/unknown stop never invents a settled
coordinate. Existing terminal finished/stopped results survive legitimate
settling and late ordinary messages.

The control worker independently owns `NO_LIGHT_SLEEP` and `CPU_FREQ_MAX`
through preflight, preparation, movement and settling. Radio callbacks cannot
release these locks. Radio locks alone are insufficient. The executor's narrower
sensing/timer/APB ownership remains in place.

Worker snapshots are copied before wake notification. The Wi-Fi sink uses a
nonblocking task notification to an application-lifetime priority-4 relay, which
writes the eventfd. The pinned SDK's task-context `event_write()` acquires a
recursive VFS lock; that possible wait belongs outside both the motor worker and
button ISR. An eventfd write failure latches transport failure and wakes the
control worker. The relay does not generate control cycles, leases or heartbeat
pulses. See the [pinned SDK implementation](https://github.com/espressif/esp-idf/blob/v5.5.4/components/vfs/vfs_eventfd.c).

## Protocol and limits

`v1/motion` returns `queued:true` only after an authenticated copied enqueue.
This is not ready or executed. `v1/motion-status` retains the existing strict
schema and source timestamps from actual worker/power observations; qualification
is not reported as live motor enable. Wake/clock/readiness retain the explicit
physical clock-model gate. The default model is unvalidated.

No safety limit changes: **300 ms source lease, 100 ms source age, 40 ms queue
age, 30 ms ready/parking snapshot, 20 ms executor gap, 240 s session ceiling**.
Clock error, uncertainty and source-time checks remain in the shared session.
The associated-light-sleep radio choice remains the
[Wi-Fi evaluation direction](wifi-evaluation.md), without an external 32 kHz
crystal assumption. AP behavior, coexistence, scheduling and whole-pack current
remain physical measurement gates. Three association attempts and five
authentication errors per boot can still require a restart after ordinary
network outages; that bounded bench behavior is not final unattended recovery.

The sensor owner now connects [gauge continuity](gauge-continuity.md) through a
joint charger/gauge mailbox. A proven bounded idle retains measurement history
but requires a complete fresh capture. An expired interval or incomplete prior
warmup starts a new monitoring session with the original **2.8–4 s** cold history
requirement. DTIM/status wakes cannot renew the parked interval. Raw STOP is
independent of this warmup; local endpoint gestures are still unwired.

Control publishes actual OFF before requesting sensor closure and holds its PM
locks until the matching sensor acknowledgment arrives. A blocked I²C call
cannot authorize sleep. The charger is parked with charging physically inhibited
and its watchdog disabled; wake restores and verifies the unchanged 2 s watchdog
before joint evidence can publish. Failed transitions remain terminal.
See the [sensor runtime](sensor-runtime.md), including the unresolved stationary
USB connection-change policy.

## Evidence and remaining work

The deterministic `wifi_motion_tests` uses the real ingress/session/executor
with explicitly synthetic I/O, time, power, calibration and clock records. It
covers default refusal, owner replacement, queue acceptance versus ready,
queued-prepare/old-idle and in-progress-publication races, stale worker parking,
revocation during queued commit, raw STOP before/during ADC, valid settling,
failed OFF readback, STOP sequence floors and active-disconnect refusal.
No fixture record is installed or made loadable by the application.

The original motion-binding checkpoint passed all 17 host CTest targets. Its motion binding and runtime tests
also passed AddressSanitizer/UndefinedBehaviorSanitizer with AppleClang and Linux
GCC. Pinned C6 builds cover
the default target, the explicit bench compile branch and the existing Thread
target after that checkpoint's shared runtime changes. Its historical build sizes on 2026-10-20 were:

| Image | Application bytes | Free in each 0x1d0000 slot |
|---|---:|---:|
| Default Wi-Fi motion | 1,113,904 (`0x10ff30`) | 786,640 (41%) |
| Bench compile coverage, still empty records | 1,133,808 (`0x114cf0`) | 766,736 (40%) |
| Existing Thread target | 844,304 (`0xce210`) | 1,056,240 (56%) |

These local artifacts do not establish timing, heap margin or hardware behavior;
fresh CI artifacts bind build evidence to a published revision.
No real-radio group, PM timing, current accuracy, watchdog waveform, motor,
pack or physical button latency has been tested.

The integrated sensor-runtime checkpoint passes all **21 host targets** under
Clang and pinned Linux GCC, including the actual C6 control/sensor workers against
a fake SDK. Focused sanitizer runs pass 3/3 ASan/UBSan and 2/2 TSan targets;
five restored-bug controls fail as expected. Fresh pinned Wi-Fi motion builds
produce `0x114d90` bytes (40% slot free) by default and `0x119cd0` (39%) with
both motion and gauge-continuity compile branches enabled. Application
qualification records remain empty in both. These supersede the two Wi-Fi image
sizes above; the earlier Thread image is historical evidence only.

Still absent: accepted board/port and motor measurements, full verified pack
profile/timing, calibration and room datum, physical reference workflow,
current-boot admission/record loader, credential commissioning, C6 local endpoint
gestures/admission, physical continuity/handoff qualification, charging permission, OTA and live HA
binding. The default remains OFF until a separately reviewed admission path has
real evidence. The earlier
[Thread-labelled host group timing investigation](thread-group-bridge.md)
remains unresolved; these deterministic tests and cross-builds do not establish
its first-fault cause or fix.

## Sensor OFF transaction and late ingress

Ordinary messages may arrive while the sensor owner parks or resumes the charger.
They retain their original receipt time, bounded queue slot and replay floor. A
control-granted OFF transaction temporarily defers their execution; it does not
accept an old command as fresh when the transaction ends. The original **40 ms
queue age** and all motion/lease limits above remain unchanged.

The sensor requests one nonwrapping token. Control grants it only after actual
peripheral OFF readback, continues STOP/fault checks and fresh physical readback,
and defers ordinary remote dequeue until that same sensor owner returns from its
synchronous work and releases the token. The grant is pinned to its original
revocation generation. A newer physical observation cannot repair a revoked grant.
Every charger guard still checks actual permission/PWM pins, qualification,
revocation, and the original **30 ms** OFF observation limit. A pending/granted
transaction excludes sleep/handoff. Requests have a **100 ms** grant wait ceiling;
a granted transaction has an independent **1 s** fault ceiling. These additional
fault caps do not extend any bus/report deadline or command age.

Remote STOP bypasses queued ordinary work. Local raw STOP, transport loss and
physical/global faults remain immediate invalidations; failed epochs are never
retried or revived. Source IRQs remain pending until the corresponding owner
service completes. No network status/handoff read can grant this token or release
power locks. The session's `defer_ordinary` parameter gates only the remote inbox:
a future local endpoint binding must respect the hold before passing a local
intent. The current C6 application supplies no local endpoint intents.

Actual-worker tests force both ingress orderings: after control captures receipt
activity but before its OFF publication, and during a successful blocked charger
read after a valid park request. A separate event matrix runs the real worker
loops for queued ingress, remote STOP, source IRQ, disconnect, raw STOP, global
fault and an expired hold. Synthetic electrical/SDK I/O is explicit; these tests
do not establish physical timing or permit actuation.
