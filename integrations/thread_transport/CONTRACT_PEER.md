# Scripted application-contract peer

This optional fixture tests the real HA → authenticated HTTP → one persistent
actor → real DTLS application path. It is a separately named library, not the C6
firmware or a replacement MotionExecutor. A passing result is
`synthetic_application_contract`, with `hardware_qualified: false`.

Build with the same pinned libcoap/OpenSSL configuration as the existing client:

```sh
cmake -S integrations/thread_transport -B work/contract-build \
  -DLIBCOAP_SOURCE_DIR="$PWD/work/libcoap-src" \
  -DSB_ALLOW_CCM8_POLICY=ON -DSB_BUILD_TEST_PEER=OFF \
  -DSB_BUILD_CONTRACT_PEER=ON -DCMAKE_BUILD_TYPE=Release
cmake --build work/contract-build -j 4
```

`SB_BUILD_CONTRACT_PEER` defaults OFF. When enabled, `libsb_contract_peer` contains
all new fixture controls; `libsb_thread` still contains only the production
client when `SB_BUILD_TEST_PEER=OFF`. The existing strict motion test names and execution timing limits remain intact.
The complete physical-control proposal adds telemetry/OFF-handoff support and
fault controls to that strict fixture, while retaining the real MotionSession/
MotionExecutor implementation and wall-clock campaign. No required test is
replaced by the scripted fixture and no timing policy changes.
The fixture binds IPv6 loopback only and accepts a disposable test PSK/identity.

## Local fixture API

Python `ContractPeer(qualified=False, boot=99)` loads only the explicitly named
`SB_CONTRACT_LIBRARY`. There is no automatic build, discovery, fallback library,
commissioning or key installation. `qualified=True` is an explicit synthetic
fixture input; it is not a physical qualification record.

`script(command, event, synthetic_height_um=0)` accepts only these transitions:

| Event | Required current state | Result |
|---|---|---|
| `ready` | preparing, exact nonzero command | scripted ready publication |
| `synthetic_terminal` | moving, exact command; coordinate 0–100,000 µm | scripted coordinate and finished/settling publication |
| `synthetic_off` | settling, exact command | scripted idle/OFF publication |

A target command does not change the coordinate. No trajectory interpolation or
automatic convergence exists. The script supplies a synthetic observation; the
host must still obtain its fresh authenticated status/OFF report. Repeated,
out-of-order, wrong-command or fault-state scripts reject. STOP bypasses ordinary
queued work, enters settling, and still requires a separate synthetic-OFF script.

The original one-peer C ABI is `sb_contract_peer_{new,free,script,trace,phase}`.
The seven-peer fixture additionally exports `new_configured`, `decoded` and
`diagnostic`, all prefixed `sb_contract_peer_` and confined to the fixture library. The bounded trace (at most 4,096 rows) records original device
monotonic times, events, command and message IDs. Its clock can have a different
epoch than Python's clock; compare translated bounds or two device trace stamps,
not raw timestamps from different clocks. No API advances or substitutes time.

## Shared and deliberately different behavior

Shared unchanged production code: DTLS 1.2/PSK cipher and identity validation,
80-byte `wire::decode`, four-slot `Inbox` including replay/STOP floor, `Ingress`,
`ClockProbes`, `Projection`, `RadioWindow`, status serialization, and the pure
`Trajectory` duration calculation. The application uses the actual production
client, strict codecs, actor, worker, Group, ledger, HTTP server and HA integration.

The fixture uses real monotonic time. It retains the 40 ms inbox age, 100 ms source
age, maximum 10 ms clock error, 300 ms source-based lease with conservative future
clock uncertainty and the 20.5 ms permission margin. A newly wider clock bound
can shorten existing permission, never extend it. Scheduled start uses the real
translated time and rejects more than the existing 30 ms start lateness. Session
expiry uses the original trajectory duration plus 2.5 s, bounded by 240 s. Client
transport deadlines, host 30/100 ms report ages and coordinator leases are unchanged.

Differences that must not be mistaken for target qualification:

- No MotionSession or MotionExecutor is instantiated. Only their public wire
  types/constants are referenced; their implementation objects are not linked.
  There is no PWM, heartbeat, 100 µs I/O test or 20 ms control-task qualification.
- One fixture network loop publishes its scripted state with real observation
  time. It does not model the C6 sensor/control task ordering or sensor warmup.
- Initial 50 mm reference and active power/SOC observations are explicitly
  synthetic. Parked battery/source telemetry is absent/unknown. No pack, GPIO,
  encoder, current, thermal, holding or calibration measurement exists.
- READY, terminal coordinate and OFF come only from local scripts. The fixture
  does not enforce physical tracking, speed or settling dynamics. A scripted
  finished coordinate immediately after scheduled start is an application test,
  not evidence that a motor could execute that move.
- Invalid consumed control requests latch a fixture fault rather than attempting
  to reproduce every recoverable MotionSession result. It is a conservative
  negative oracle, not a conformance replacement for the strict firmware tests.
- The fixture's clock model assertion is synthetic setup even with actual
  four-timestamp exchanges. It proves neither C6 oscillator bounds nor RF timing.

The unchanged strict real-wall-clock motion-peer campaign remains separate and
its recorded host timing failures remain visible. Pinned C6 builds prove only
compilation. Physical qualification/default motor-enable records remain empty.

## Tests and lifecycle

`test_contract_peer.py` covers default refusal, wrong PSK, malformed/wrong-boot and
replayed frames, old/future source and wrong probe, original-source lease expiry,
authenticated stale-source STOP, command-bound OFF and connection replacement
without resetting the replay floor. Oversized frames are rejected by the real
client before network delivery; this is tested separately from server decoding.

`ha_tests/test_contract_control.py` runs the actual HA integration against a local
HTTP server and one DTLS actor. It checks unavailable default setup, then explicit
synthetic setup through queued prepare, scripted READY, real scheduled start,
scripted terminal, scripted OFF and resumed idle telemetry, using one handshake
and a durable 4,096-ID reservation. This one-peer test remains unchanged.

The harness starts the peer before the service, waits for first telemetry, then
starts HTTP/HA. A failed first-telemetry wait closes the service and peer. The native
constructor frees partial context state on failure; Python port selection has
a bind race and fails rather than silently retrying. The HA harness does not
claim exhaustive failure injection of every Python startup constructor. Normal
teardown stops HTTP, uses the server's ordinary service-close path, joins its
thread and frees the peer/context; the peer joins its own loop and cleanses PSK memory. Full evidence
is captured before teardown. Original failures are retained and no motion delivery
is retried. Test collection imports the actual custom integration before HA mounts
its fixture configuration, avoiding an unrelated fixture package shadow.

## Seven-peer application slice

`ha_tests/test_contract_group.py` uses the same actual application with seven
loopback peers. Explicit synthetic limits are respectively [0,100], [5,95],
[10,90], [15,85], [20,80], [25,75], [30,70] mm. The common range is [30,70] mm:
group 55% therefore requests52mm everywhere, while each own-travel percentage
would differ. The most constrained peer selects 10 mm/s and 20 mm/s² for everyone.
These are synthetic capability inputs, not a calibrated physical installation.

`ContractPeer(limits=(low_um, high_um, max_speed_um_s, max_accel_um_s2))` opts into
`new_configured`; default construction remains unchanged/unqualified. The
configured fixture requires its initial 50 mm coordinate inside a nonempty range
within 0–100 mm, and caps at 30 mm/s / 60 mm/s². Every prepare independently checks the
peer's own range/speed/acceleration; a host selection cannot override these.

`decoded_requests` is a passive, bounded (4,096 rows) copy of the actual unchanged
wire decoder's result **after** DTLS identity/session and Inbox acceptance. Rows
include original receive time and connection generation, all decoded integer
fields, boot/command/message, source/start timestamps, and physical trajectory.
Wrong authentication, malformed/wrong-boot/replayed packets create no row. The
hook reads the connection through the const Inbox accessor; it does not call a
clock-expiring snapshot. It cannot submit, retime, acknowledge or script a request. Buffer exhaustion
faults instead of overwriting evidence; it returns an uncertain service refusal
and never retries that accepted packet.

The group test checks these receiving-side records for identical 52,000 µm target,
50,000µm origin, 10,000 µm/s speed,20,000µm/s² acceleration, original source timestamp
and common scheduled start exactly 3 s later. Each peer uses a separate disposable
key and boot, one connection and distinct preexisting synthetic ledger floors.
A new job reserves 4,096 IDs per device before any prepare. Scenarios also cover
all-default qualification refusal, one missing READY preventing every commit and
start, and an explicitly wrong 60 mm terminal coordinate causing group abort and
an 8 mm spread instead of false aligned completion. Terminal/OFF remain separate
command-bound scripts; they are never physical observations.

The local `diagnostic` copy records the first fixture fault once, including the
caller timestamp and already-computed active clock bounds. It adds no clock read,
changes no predicate, and never overwrites the first fault. Clock predicate 1 is
missing current projection; 2 missing lifetime projection; 3 rounded lifetime error
exceeds 10 ms; 4 lease origin cannot subtract the lifetime uncertainty. Other result
codes retain predicate 0; the clock fields then describe the last active check.

One original seven-peer positive run faulted before start; it had no first-result
or predicate capture, and its exact cause remains unresolved. A subsequent
instrumented campaign passed all four application scenarios. This is functional
application evidence, **not reliable seven-peer timing**, a fault fix, or hardware
qualification. The original failure and later instrumented trace must accompany
any report of this slice. No original strict timing campaign or required CI check
is replaced by this fixture.

The seven-peer harness copies `Worker.calls` at evidence capture. Later cleanup
appends cannot change that captured list; the no-transport immutable-copy
regression tests append and clear, and rejects the original borrowed-list form.
This does not make separately copied worker/peer fields one atomic observation.
