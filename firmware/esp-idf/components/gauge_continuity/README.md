# C6 read-only gauge continuity adapter

**Compiled only; no application instantiates this component.**
`CONFIG_BLINDS_GAUGE_CONTINUITY_BENCH` defaults OFF, and the portable
qualification profile defaults invalid. Enabling that build option alone
cannot attach a device. There is no bus creation, GPIO configuration, gauge
register write, flag clear, NVM command, charger control or motor approval.

The [continuity model](../../../../docs/firmware/gauge-continuity.md) remains
unchanged. This component connects it to the actual ESP-IDF synchronous I²C
API through a tested portable ownership and wire-format boundary.

## Existing and future ownership

Currently `MotionRuntime::power()` creates I²C0 with GPIO10/11 and physical
pullups, then uses `Max17320Reader` and `Bq25798Config` sequentially on that one
lower-priority task. Its monitor still restarts on each sensing window; this
checkpoint does not replace it. The Wi-Fi evaluation app has no I²C owner.

A future qualified owner must create `GaugeContinuity` **on the sensor task**
and explicitly attach an existing bus from that task. The bus must use the
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
generation. There is no automatic reattachment or epoch restoration.

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

**Runtime handoff remains unresolved and this adapter remains uninstantiated.**
Replacing a serial before delivering its new report to a consumer queue leaves
a fail-closed interval in which the consumer's older copy rejects. Connecting
the adapter needs a reviewed coherent report/serial handoff; accepting arbitrary
older serials or bypassing `current` is not a solution.

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
- Real pinned C6 cross-builds compile the component in Thread and Wi-Fi targets.
  A separate bench-option compile checks the normally excluded attachment
  branch against the real SDK. No image is flashed, and the applications still
  contain no adapter instance.

The host SDK seam does not model ESP-IDF interrupt, electrical or scheduling
behavior. It supplements the real cross-build; it does not establish hardware
readiness.
