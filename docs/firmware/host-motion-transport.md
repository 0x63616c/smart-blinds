# Explicit host motion transport

`integrations.thread_transport.motion.MotionSession` sends the existing exact
80-byte [binary request](motion-session.md#binary-request) over the native
libcoap DTLS session and parses the [worker status](c6-motion-runtime.md#resources).
This is a host implementation milestone. The C6 default still has empty
qualification, no established reference and no configured motor pins. The new
client cannot write commissioning records, create a physical reference or make
an unqualified target ready. It is not installed in Home Assistant.

## Explicit operations and ownership

Construct with the native library path, literal address, port, identity and
per-device PSK, plus **expected boot**, calibration revision and a durably
consumed message floor for that boot. The client never adopts a new boot. A
wrong boot fails the session. An explicit new client is required after transport
failure or reboot, with recovery and fresh source evidence. No queued operation,
prepare, commit or lease is restored automatically.

The caller explicitly requests status, wake, clock assessment and worker status
before preparing. `prepare`, `commit`, `lease` and `stop` each take a new message
number, command number and **original source timestamp** in host monotonic
microseconds. Source stamps are never replaced by transmission/receipt time.
Prepare additionally takes the scheduled start and integer micrometre geometry,
velocity and acceleration. Out-of-range values, booleans, floats where an integer
is required, reserved bytes and trailing fields are rejected; there is no clamp
or implicit unit rounding.

Each attempted wire request consumes its message number before transmission,
even when the response is rejected, lost or times out. The caller must reserve
that number durably before the call and preserve `consumed_message` for recovery.
`last_message` in a device report **is not the ingress replay floor**: STOP and
discarded queued messages may advance the floor without appearing there. Keep
command identity, motion-message sequence, wake sequence and clock-probe sequence
separate. This client implements no persistence or key vault.

`Queued(message, command, kind)` means the device copied a record into its
inbox. It has no ready property. `commit()` requires a subsequent fresh worker
report with the matching command, processed prepare message and `ready=true`.
It sends no commit automatically. A new clock assessment invalidates cached
readiness until a new worker report. Explicit lease calls are needed **while
preparing/ready**, as well as committed/moving; the first prepare starts the
same 300 ms source-based lease. STOP remains clock-independent after a current
boot has been observed and is authenticated like every other operation.

Calls remain synchronous and serialized per device. They must run in dedicated
coordinator workers, not the HA event loop. A blocked network call cannot be
interrupted by another call on the same handle; the device's local lease and
physical STOP remain the independent stop mechanisms. The existing 1–5000 ms
request limit is a transport deadline, not permission to extend a 300 ms motion
lease. The future coordinator must choose practical active-session deadlines,
refresh at 100 ms and treat missed deadlines as a failed group operation.

## Source-stamped status

Motion status has an exact schema, finite bounded values and exact-width
hexadecimal identities. It retains both the control sample and power observation
time. A successful receive never makes old data fresh. The client requires an
explicit authenticated clock assessment and accepts only a device assertion that
its locally selected clock model is validated; that assertion is not physical
validation performed by the host.

The host conservatively uses the largest clock uncertainty model the C6
configuration permits: 10,000 ppm relative growth and a 1,000 us stamp guard.
The default evaluation client retains its existing 1,000 ppm / 2 us model and
never gains motion authority. Excessive uncertainty, source times wholly in the
future and control samples older than 100 ms are rejected. Worker freshness and
ready additionally require an age bound of 30 ms; valid power observations are
bounded to 250 ms. Clock evidence has its existing 1 s ceiling and 10 ms error
ceiling; conservative growth can make it expire sooner.

`Report` includes original device `sampled_us`, conservative host earliest sample,
clock error, age, phase/result, identities, measured height and nullable battery
percentage. Missing power produces no fake charge level. Duplicate worker
snapshots return `new_sample=false` and cannot supply readiness. Decreasing
sample times or conflicting worker-owned fields at the same timestamp fail the
session. Fields that can change between worker publications, such as immediate
network readiness revocation or power freshness, are checked separately.

## Coordinator and Home Assistant boundary

The existing coordinator and HA bridge were inspected but are **not wired to
this client**. The current bridge remains explicitly simulation-only. The next
adapter must do all of the following before exposing real motion:

- Bind one explicit device/boot/calibration/qualification selection to each
  worker and maintain separate persistent command/message sequence ledgers.
- Convert the coordinator's millimetres and milliseconds to exact bounded
  micrometres and microseconds, rejecting unrepresentable values. Preserve the
  coordinator's original `sent_ms` when producing `sent_us`.
- Translate only new authenticated worker samples into `SourceStamp`; use the
  original increasing device sample timestamp as the sequence, never a receipt
  counter. `sample_host_earliest_us` is already conservative; any extra clock
  margin must not accidentally be subtracted twice and reported as an exact
  source timestamp. The adapter needs an explicit centre/error conversion.
- Acknowledge `prepared` only on matching fresh `ready` and `committed` only on a
  new matching worker phase, never on a queue receipt. Publish power/fault and
  nullable battery values with their source ages.
- Start explicit 100 ms lease refresh after prepare is queued and continue while
  waiting for all peers. **Current `Job.tick` only leases in ARMED/MOVING** and
  cannot yet maintain the device's prepare/ready lease. Fix that lifecycle with
  tests before using it with this adapter.
- Refresh each clock deliberately within its measured budget, poll current
  readiness after refresh, and abort all peers on offline/clock/boot/reference
  changes. Keep the existing shared physical-height target, common reachable
  range, aligned-start requirement and explicit rejoin semantics.

No HomePod model, Thread credentials, routable device addresses or owner's HA
installation was inferred or modified. Network commissioning, persistent record
verification, owner reference/recovery flow and physical qualification remain
separate work.

## Evidence

The combined transport suites pass **37 tests** locally: the existing 19
DTLS/clock/schema cases, 17 motion cases and one conservative-clock arithmetic
case. Tests use fresh disposable keys and IPv6 loopback. The separate motion
fixture runs real libcoap/OpenSSL DTLS, the production decoder/inbox/session/
executor/controller and one synthetic control worker. It checks delayed/full
queues, priority STOP, source freshness/replay, wrong boot/key/identity, clock
failure, failed power, lease expiry, reconnect, lost acknowledgement and explicit
prepare/ready/commit/motion/STOP behavior. It creates test-only synthetic
qualification and reference evidence in memory; there is no equivalent network
operation or production record.

`SB_BUILD_TEST_PEER=OFF` excludes both fixture implementations and all synthetic
plant code. Tests do not prove C6/OpenThread DTLS interoperability, actual radio
latency, physical settling, pack health or production clock bounds. The scoped
CCM8 policy exception remains explicit and defaults off; see the
[build/security notes](../../integrations/thread_transport/README.md).


The separate [group bridge checkpoint](thread-group-bridge.md) now binds this explicit
client to the group coordinator using bounded workers and durable sequence reservations.
It remains opt-in localhost correctness evidence; its present polling traffic exceeds
Thread's radio capacity and the default HA application remains simulation-only.
