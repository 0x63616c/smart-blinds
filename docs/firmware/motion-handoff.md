# Physical motion-to-idle handoff

The device handoff connects the actual Wi-Fi motion policy and the existing
C6 control/sensor workers at completion. The separate [physical-control actor](physical-control.md)
now consumes it without commissioning a device or enabling any default qualification record.
The existing fifteen-field motion-status contract is unchanged.

## Resolved completion dependency

Previously the radio policy held operation awake until the runtime reported
physical OFF and a clean sensor-owner park acknowledgment. The runtime kept the
sensor session enabled while that radio policy was awake. A composed test using
the actual worker sources reproduced this circular wait after an authenticated
STOP of a rejected clockless prepare: the session was idle/stopped, but both PM
locks and the active charger-monitor watchdog remained held.

The copied local Network publication now distinguishes operation ownership from
preflight awake demand. Only a definitive finished/stopped **idle** session can
close sensing while operation ownership remains awake. Settling continues its
existing observations. Physical OFF readback, matching clean sensor ACK, current
source event/epoch and ingress/revocation fences must all pass before policy idle
and PM release. Any queued ordinary or STOP record prevents handoff; inspecting
that pending state does not consume STOP. A fresh preflight resumes sensing.

Radio cooldown is unchanged: cancellation retains the original ten-second wake
window deadline plus five seconds. A second explicit command before that boundary
is refused. The future actor must expose that condition, not silently retime,
retry or queue a motion intent for later execution.

## Authenticated observation endpoint

`POST /v1/handoff` receives exactly sixteen bytes: expected boot and nonzero
strictly increasing nonce, both unsigned big-endian 64-bit values. The nonce is
consumed before reading the publication, including a failed reply. Replayed or
older nonces and wrong boot reject. Nonce history belongs to the authenticated
connection; a new connection never inherits motion authority.

The version-one response contains exactly:

- `version` (integer 1), `boot`, `nonce`, `responded_us`, `sampled_us`, `command`,
  `received_message` (the latter six values are sixteen-digit lowercase hex).
- `phase`, `result`, `reference_valid`, `height_mm`, `settled_off`. Height is the
  actual retained terminal coordinate or null, never a requested target.

`sampled_us` is the original control-owner parking observation, including zero
before any publication. `responded_us` is sampled after the completed copy. A
request may notify the control owner to make another actual OFF observation; it
cannot restamp a cached value, wake the gauge, refresh a clock/lease, release PM,
change a replay floor, or admit motion. The source value remains visible when
stale, with `settled_off=false`.

`settled_off=true` requires idle finished/stopped, qualified I/O, the same DTLS
connection, actual OFF no older than the unchanged 30 ms physical parking bound,
matching activity/revocation, an empty ordinary/STOP inbox, completed sensor park,
matching source event and acknowledgment, no source service in progress and the
same live bus epoch. A fault, pending STOP, failed OFF or source transition cannot
be repaired by a later successful word/read. Reference validity is separately
reported, never synthesized by handoff.

`received_message` is the producer's accepted per-boot message floor, including
STOP and discarded records. It does **not** replace the host durable ledger:
uncertain sends and reserved unused IDs remain burned even if never accepted by
the device. Terminal `command`/`result` remain the actual core history; a rejected
prepare can leave the preceding command (including zero), not a fictional job.

## Persistent actor consumer

The host must correlate nonce, boot, its existing sole DTLS handle, its observed
terminal command and accepted-message history. It must bound observation age at
receipt from the original device interval plus the measured full round-trip,
with the existing qualified clock-rate bound accounted for. Missing or ambiguous
handoff closes the job/owner; it must not trigger reconnect or replay. Handoff is
only an OFF/ownership observation. Every subsequent job still needs the existing
fresh clock, power, physical reference, local selection and durable reservation.

The separate physical-control implementation adds an explicit combined host
handle, HA covers and increasing next-reservation adoption. Telemetry-only handles
remain telemetry-only. The source and physical OFF contract above is unchanged.

## Verification scope

Actual C6 worker sources are exercised with injected SDK/I/O on the host: default
empty records, rejected prepare plus STOP, matching closure before release,
same-owner later wake, nonce replay, old physical source stamp, queued backlog,
ingress/source mutation during copy, blocked sensor bus and terminal actual-OFF
failure. Separate portable tests retain successful motion/STOP/settling coverage.
The composed actual-I/O fixture intentionally performs zero motor actuation; its
encoder fixture does not emulate qualified travel. Default and explicit bench
compile images are cross-built in pinned ESP-IDF, never flashed. No measured
radio/physical timing, motor movement or power consumption is claimed.
