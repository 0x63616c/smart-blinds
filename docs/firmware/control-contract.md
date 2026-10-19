# Motion, calibration and group contract

Status: executable control/coordinator foundation; prototype limits and proposed transport contract. This document separates implemented behavior from required platform work.

## One physical coordinate system

Every blind records bottom-edge height in millimetres above the **same room datum**. Higher means further open. Each calibration stores increasing normalized quadrature counts and increasing height, with a revision identifier. Platform wiring/polarity handles motor inversion. Real calibration needs intermediate points, both directions and repeatability measurements: roller buildup changes travel per turn, and chain/clutch slip can break the encoder-to-fabric relationship. A fixed motor-RPM target does not ensure equal fabric speed.

For each blind, measure the lowest and highest safe bottom-edge positions. The group range is `[maximum of all lower bounds, minimum of all upper bounds]`. A slider value is a point in that common range. Empty intersection makes a level group impossible; it is rejected. A group target is never silently clamped differently on each member. Individual full-open/full-close actions remain separate, because the shared group endpoints may not fully open or close every blind.

An explicit **align** operation brings unequal starting levels to one common level. They travel at the same allowed cruise speed but may finish at different times. Once aligned, every member follows the same physical-height trajectory and scheduled start. Equal speed, equal start time and equal arrival time cannot all hold when initial distances differ. The coordinator rejects normal group moves if starting spread exceeds 5 mm. That 5 mm is a proposed acceptance target, not a demonstrated result.

## Nominal command timeline

The test coordinator receives fresh reports at time `t`, prepares a start at `t + 3 s`, and uses these proposed timing budgets:

| Stage | Requirement | Implementation |
|---|---|---|
| Sleep/wake | Candidate 1 s sleepy poll; physical buttons wake locally | Radio/MCU work pending |
| Prepare | All members referenced, powered, calibrated and clock-error bound ≤10 ms; current reports ≤1.5 s old | Coordinator + node core |
| Readiness | Every member acknowledges the identical geometry and per-device boot/sequence by `t + 1.7 s` | Coordinator |
| Commit | Every member acknowledges arming by `t + 2.5 s` | Coordinator + node core |
| Start | Common `t + 3 s`; node more than 30 ms late refuses to join | Node core |
| While active | Coordinator leases every 100 ms, expire after 300 ms; fresh member reports ≤250 ms old | Coordinator + node core; adapter scheduling pending |
| Control | Intended 10 ms loop; gap >50 ms disables request | Node core; actual output/watchdog pending |
| End | Every member reports measured target within 1 mm; group spread ≤5 mm | Core + coordinator; physical accuracy unproven |

The start delay is **before movement**, not a promise that a full blind travels in three seconds. Actual travel time depends on measured available speed, torque and noise. All members use the weakest member's measured safe speed/acceleration at the current pack state and expected load. A low battery or load change that prevents tracking aborts the group instead of speeding the other blinds ahead. Near the endpoint the same shared trajectory slows them together.

Wireless broadcast is not an atomic transaction. Prepare/commit plus running leases greatly reduces partial starts but cannot guarantee that every final packet is received. A device that misses a lease remains stopped; a device that loses one while moving stops when it expires. At the illustrative maximum 30 mm/s, a 300 ms lease alone allows about 9 mm of extra travel before the software stop request, plus mechanical stopping distance. **The normal 5 mm alignment goal is not guaranteed during communications faults.** After any partial move the group requires re-alignment. If any member jams or is overridden, coordinator stops the group; local protection acts before network notification.

## Wire and adapter boundary

The Python coordinator emits a versioned envelope with recipient, kind and payload. It does not currently open sockets, parse untrusted packets or install a Home Assistant integration. A transport adapter must:

1. Authenticate the peer and bind its device identity; reject oversized/unknown-version/unknown-field/invalid-type packets before constructing C++ objects. Reject NaN/infinity, out-of-range integers and retained motion commands. Do not transport uint64 IDs through a float: JSON adapters should encode them as decimal strings and parse exactly, or use an integer-preserving binary codec.
2. Send `prepare` with device boot nonce, increasing sequence, calibration revision, start time, shared origin/target height, velocity and acceleration. A retransmit must be identical. The accepted sequence is consumed even if the command later aborts.
3. Collect authenticated `prepared` and `committed` acknowledgements. Never advance a job on an ACK from a previous boot or command. A rejection or timeout aborts every member; offline members are not silently dropped.
4. Send `lease` only after **all** commit ACKs. Translate its source timestamp into the same monotonic domain as the node's `now_ms` and pass the conservative absolute error bound to `renew_lease`. A future estimate within that bound is accepted, but expiry uses the earliest possible send time (`sent_ms - error_ms`), so uncertainty never adds lease life. The bound must remain ≤10 ms. Duplicate/old packets cannot extend it. Stop leases on any member fault or lost telemetry.
5. Bind network `stop` to the active boot and sequence. The local physical stop always bypasses network gating. Publish status/ACKs with authenticated source sample time, a strictly increasing report sequence within that boot and clock-error bound. The coordinator's `SourceStamp`/`FreshnessTracker` rejects delayed, replayed or out-of-order samples and computes age conservatively; receipt time never replaces sample time. Its type is not an authentication mechanism: the adapter must authenticate the fields and bind the coordinator epoch before constructing it. Repackaging old sensor data with a new send timestamp is forbidden.
6. On coordinator restart, cancel all jobs and do not restore pending targets. Re-read each device's boot nonce and consumed sequence, get new clock estimates, and start a new explicit user action. Never replay a broker backlog on reconnect.

Use a monotonic coordinator clock with a fresh coordinator epoch; NTP/wall-clock changes must not shift scheduled motion. The adapter must invalidate outstanding work if the epoch changes, reject unreasonable offset/round-trip estimates, update the uncertainty bound while awake and fail a move if it exceeds 10 ms. These clock-estimator and authenticated-session components remain to be implemented.

## Local controls and reference loss

Suggested physical behavior: tap up/down to move locally to that blind's calibrated endpoint; any new button press while moving stops it; both buttons always stop. The core provides the endpoint/stop operations; platform debounce and wake-event handling remain pending. Each debounced press is one event, so a held button cannot repeatedly stop/restart the motor. Hold-to-jog is reserved for supervised commissioning/recovery, where release stops. Enter that mode through a distinct deliberate gesture while stationary; a long press must not first trigger an ordinary full-travel move. STOP must not clear a fault. No instant reversal: stop first, then a new action after the measured settling interval. Hardware output enable defaults off during boot, crashes and updates.

The quadrature encoder is incremental, not an absolute bottom-edge sensor. A counter saved before power loss is not proof that a blind has remained stationary. Core boot starts unreferenced. Recovery requires an actual known-height reference procedure and a synchronized counter offset. Unknown slip, excessive tracking error or count outside the calibrated range invalidates position. A home/reference input is reserved in hardware; its real location and repeatability must be designed and tested. A motor-side sensor alone does not detect downstream clutch slip. Never drive into a hard stop as a generic homing method. Initial commissioning needs a separate supervised, low-speed, travel-limited jog procedure with independent current protection; ordinary unreferenced moves are intentionally refused by the current core.

## Validation still required

Measure actual fabric heights at several positions and directions; test repeated cycles, backlash, clutch slip, chain jump, power loss, manual movement and reference repeatability. Characterize start/stop spread with seven radios, packet loss and weak signal while recording bottom-edge motion. Test depleted battery and maximum blind load. Electrical current limiting and system cutoff must operate independently of this high-level velocity controller. Firmware updates require stationary motors, sufficient pack charge, verified image/version, rollback and accessible wired recovery.
