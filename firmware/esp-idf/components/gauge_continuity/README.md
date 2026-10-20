# C6 read-only gauge continuity adapter

**Integrated into the qualified branch of `MotionRuntime`; default images remain OFF.**
`CONFIG_BLINDS_GAUGE_CONTINUITY_BENCH` defaults OFF, and the portable
qualification profile defaults invalid. Enabling that build option alone
cannot attach a device. The adapter itself creates no bus, configures no GPIO,
writes no gauge register, clears no gauge flag, and grants no motor approval.
The runtime's joint session also owns a separate charger adapter; its OFF-only
operations are described in the [sensor runtime](../../../../docs/firmware/sensor-runtime.md).

The [continuity model](../../../../docs/firmware/gauge-continuity.md) remains
unchanged. This component connects it to the actual ESP-IDF synchronous I²C
API through a tested portable ownership and wire-format boundary.

## Runtime ownership

The qualified `MotionRuntime::power()` branch creates I²C0 with GPIO10/11 and
physical pullups. That one lower-priority task constructs `GaugeContinuity`,
`Bq25798Config` and the joint mailbox, then reads the charger before the gauge.
It replaces the legacy reader in this worker; they never share ownership.
The radio-only Wi-Fi evaluation app still has no I²C owner.

The runtime creates `GaugeContinuity` **on the sensor task**
and explicitly attaches its existing bus from that task. The bus must use the
synchronous SDK mode, with no asynchronous callback registration or competing
task accessing its clients. The existing `exclusive_access_verified` physical
qualification includes this ownership condition. The adapter cannot introspect
or prove the absence of an unrelated client holding the same raw SDK handle.
Never instantiate it beside the legacy gauge reader as a second owner.

Only the creating task may attach, read, park, resume or remove SDK handles.
The captured FreeRTOS task identity is checked around each word. Task-handle
reuse is not authority: task replacement retires the bus epoch and requires a
new monitoring session. Context also binds boot, bus generation, installed pack
and qualification ID.

`BusEpoch` must outlive the adapter and all publication consumers. Any task can
atomically retire it; retirement cannot wrap. A session can retire only its own
generation, so stale-object cleanup cannot cancel a deliberately issued newer
generation. A clean expired idle can explicitly retire and replace the monitoring
session on the same owner, after reader withdrawal and handle closure. This
issues a new epoch and repeats the full cold warmup; it never restores an old
epoch or repairs a failed session.

| Event | Required owner action before accepting more evidence |
|---|---|
| Initial bus/monitor construction | Stationary qualified owner, fresh context and full original warmup |
| Known MCU light sleep only | Park, withdraw readiness, then resume and perform a complete fresh capture |
| Unknown MCU reset/deep sleep/task replacement | Discard ticket; new boot/session and cold qualification |
| Bus reset/recreation, pin change, recovery, callback-mode change or ownership ambiguity | Retire epoch before the operation; owner closes handles after its read returns |
| Pack unplug/replug/service or possible cell intervention | Retire epoch; independently revalidate pack identity/profile |
| Any gauge configuration/mode/flag writer | Retire epoch before the writer acts; no writer is supplied here |
| Read timeout, NACK, clock fault, guard mismatch or owner/epoch loss | Stop on the first error, retire, reject all later reads from that object |
| Charger work sharing this bus | Same owner, sequential transactions only; charger failure/readiness remains an independent gate |
| Radio reconnect | Not a new battery timestamp; monitoring owner/session ambiguity still retires the ticket |

`close()` from a wrong task performs atomic cancellation only; it does **not**
remove handles or mutate owner-only driver state. The original task must finish
the synchronous call and close both devices before deleting/reconstructing the
bus. Device-remove failure retains the handle and reports failure, so the bus
must not be considered free. Destruction must occur on the owner after all
users stop. Concurrent destruction is unsupported; wrong-task destruction can
leak handles and is a lifetime violation.

## Read and publication boundaries

The shared `OwnedWordBus` accepts only the 31 distinct reviewed capture
registers, maps normal words to `0x36` and shadow words to `0x0B`, writes exactly
one pointer byte, reads exactly two bytes and decodes little endian. No general
register-write operation exists.

Every transfer requires the same task and epoch before and after the SDK call.
Loss during a transfer discards even successfully returned bytes and prevents
the remaining reads. A late successful word cannot restore the session.

A publication carries both epoch and monotonically issued sample serial.
An ordinary active refresh retains only the last completed serial until the
new complete ready capture replaces it. All fields of the old report,
including its observation and conservative conversion timestamps, stay
unchanged. It can expire during the refresh; there is no grace period.
Parking, resuming, any detected failure or retirement still withdraws it.
A warming capture has no ready serial.

The owner synchronously revokes on the first returned bus error, detected
clock/timeout error, or received word that proves an existing guard/value
violation. Incremental checks share the complete monitor's predicates;
partial data can only reject, never publish readiness. The first fault is
latched before retiring the epoch, so later clock/context failures cannot
replace its diagnostic. A successful later word cannot repair that object.

Queues/consumers must call `current(publication, now)` before using a report,
then apply the existing joint `motion_power()` freshness/charger checks.
The publication fence reads atomics and immutable copies across tasks without
touching the single-owner monitor. It never grants actuation.

The runtime uses the [joint power mailbox](../../../../docs/firmware/power-mailbox.md)
mode instead of queueing standalone publications. That mode atomically publishes
the completed pair and its sole serial. A stable `SensorAccess` selector pins
the immutable session while control and status take independent immediate
snapshots. The owner withdraws it and waits for pins before destroying old
storage. No arbitrary older serial is accepted, and standalone `current()` is
not the runtime admission path.

Control retains its PM locks until a matching sensor closure acknowledgment and
fresh actual OFF evidence agree. A blocked synchronous bus call cannot authorize
sleep or prevent raw STOP handling on the independent control worker. Qualified
idle preserves the original park time; expired continuity starts a new cold
session. Physical gate duration, SDK fault timing and continuity remain unmeasured.

## Requested timeouts versus physical timing

The portable reader requests 10 ms per transfer and rejects any call whose
measured duration exceeds that value; total capture budget remains 250 ms.
These are software acceptance limits, not a guarantee that ESP-IDF returns
within 10 ms under all faults.

The pinned [ESP-IDF v5.5.4 I²C implementation](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_driver_i2c/i2c_master.c)
uses the supplied timeout separately for the bus semaphore and transaction
path. It may reset the hardware state machine internally on an error/busy bus.
The adapter adds no retry or recovery transaction; any reported error or
measured overrun retires evidence. Device add/remove uses `portMAX_DELAY` for
driver administration and is therefore permitted only during stationary owner
setup/teardown, with no concurrent clients. This API cannot enforce a hard
deadline on a driver that never returns.

The real motor owner must remain independent of this lower-priority I²C worker
and rely on its existing sample-age expiry and hardware supervision. Actual
stuck-bus timing, bus contention, pad behavior, continuity and button latency
remain unmeasured.

## Verification scope

- `gauge_bus_session_tests` exercises the actual shared word/session logic:
  address mapping, little endian, timeouts, first error, task/epoch loss at all
  52 transfer positions, immediate head/tail rejection, healthy-refresh
  retention, original age expiry, park withdrawal, cold requalification,
  cross-thread refresh/cancellation barriers and nonwrapping retirement.
- `gauge_continuity_tests` compares guard bit mutations and every raw value of
  every payload word against independently specified original masks and a
  frozen pre-change numeric predicate oracle, as well as the complete monitor.
- Two host targets compile the **actual C6 adapter source** against a minimal
  fake SDK, with the bench gate both OFF and ON. They test no default SDK access,
  qualification rejection, actual attachment address selection, transaction
  shape, partial-attach cleanup, first error and wrong-task teardown.
- Earlier pinned C6 cross-builds covered the isolated component in Thread and
  Wi-Fi targets. The runtime-integration checkpoint adds fresh real Wi-Fi motion
  default and bench builds; the latter enables both motion and continuity
  branches, while its application records stay empty.
- `sensor_access_tests` checks pinned-reader lifetime and independent snapshots.
  `c6_runtime_owner_tests` compiles the actual runtime and both C6 bus adapters
  against a fake SDK, including blocked transfers, PM ownership, clean long-idle
  replacement and terminal-fault refusal. No image has been flashed.

The host SDK seam does not model ESP-IDF interrupt, electrical or scheduling
behavior. It supplements the real cross-build; it does not establish hardware
readiness.
