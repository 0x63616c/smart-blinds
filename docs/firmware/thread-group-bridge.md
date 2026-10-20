# Host group bridge checkpoint

The separate [thread_bridge library](../../integrations/thread_bridge/README.md)
joins the existing physical-height coordinator to real DTLS sessions and the reviewed
80-byte motion protocol. The test peer uses the real portable ingress, motion session,
controller and executor with explicitly synthetic I/O, pack data and reference records.
It is libcoap/OpenSSL on localhost, **not a C6/OpenThread interoperability result**.

A seven-peer test uses different physical ranges and encoder-to-height slopes. Their
shared range is 0–140 mm; group 50% requests 70 mm for every peer, rather than each
blind's individual midpoint. Coordinated preparation/commit, 100 ms source-timed
leases, settling and definitive completion are exercised. Fault tests abort the group
on a failed power report, unavailable control worker, worker exit or uncertain commit
response. No test accesses an owned device, battery pack or Home Assistant instance.

A local observation during development was 4.65 s end-to-end, 0.002 mm synthetic final
spread, 1.13 ms p95 host request duration, and approximately 496 kB of application
bodies over that interval. These are properties of the synthetic localhost run, not
mechanical accuracy, radio latency or guaranteed scheduling bounds. Tests emit their
own current measurements rather than asserting these incidental timings.

## The radio budget fails at the current cadence

About 106 kB/s of application bodies alone is already over three times a 250 kbit/s
PHY's theoretical 31.25 kB/s raw bitrate ([Espressif C6 datasheet, 802.15.4 PHY](https://documentation.espressif.com/esp32-c6_datasheet_en.html)), before any radio/IP/security overhead or
mesh forwarding. The current 30 ms JSON status polling and separate clock exchanges
therefore cannot be the production seven-blind Thread schedule. The test is useful
for end-to-end correctness only. It neither proves the battery target nor authorizes
commissioning. A compact binary source-stamped status and bounded combined exchange
need a separately reviewed airtime, parent-poll and loss-budget design plus real C6
interoperability and radio measurements.

## Source changes and verification boundary

- Added opt-in group owner, bounded peer workers, explicit commissioned selection,
  durable sequence-range ledger, strict source translation and common wire precision.
- Added an explicit post-preflight transport deadline setter; existing client defaults
  and evaluation-only client access remain unchanged.
- Coordinator now accepts observed `settling`, but completion still requires actual
  idle endpoint evidence. Adapter additionally requires definitive `finished`.
- Portable motion session retains definitive `finished`/`stopped` through rejected
  ordinary requests in settling/idle, while consuming their replay IDs. A valid next
  preparation replaces the result; STOP and faults retain their existing priority.
- Native geometry/counter helpers exist only with the test-fixture build flag.

Earlier local validation passed 58 Python ledger/adapter/real-DTLS/clock tests,
11 portable CTest targets, 24 coordinator/freshness tests, 9 existing bridge tests,
and 7 HA framework tests. The portable motion-session tests also passed ASan/UBSan.
Independent review then reproduced two failures in the 58-test batch: the second
explicit job stopped with executor code 4 on both peers, and a seven-peer power-fault
test failed preflight on source-time freshness. The main seven-peer positive case
passed in that same review run. That failed run is not erased by later passing runs.

Executor code 4 is `Fault::clock`, which rejects backwards/non-advancing time or a
control update gap exceeding 20 ms. It is not the 100 µs I/O-operation fault. The
review run did not capture its actual gap or the rejected source age, so the precise
cause of those two historical failures is unresolved. A subsequent instrumented
58-test diagnostic run passed; this is not evidence of a fixed defect.

The fixture now preserves the **first** executor fault's start/end gaps, cycle
execution duration, maximum interval between clock reads and clock reversal flag.
These are included in positive test failures. Source-age exceptions include their
computed age and unchanged bound. A separate real-wall-clock 30 ms stall regression
reproduces `Fault::clock`, verifies immediate output inhibition/reference loss, and
verifies the fault cannot catch up or resume. Native synthetic I/O continues using
wall time: there is no snapshot-clock replacement, timing-bound relaxation, retry,
skip, or production protocol change. A desktop scheduling stall can legitimately
fail these strict real-time positive tests; hardware timing remains unvalidated.

With the retained diagnostics and deliberate-stall regression, the final local
59-test batch passed in 25.162 s. Its seven-peer observation was 506,048 application
body bytes over 4.651 s; the radio-budget failure above remains. This passing run
does not establish the historical failures' exact cause.

Fresh pinned C6 CI is required for the portable session change. The default images
still contain no qualification/reference records and configure no motor or charger
outputs. Physical firmware integration, production commissioning, complete idle
local controls, actual radio scheduling and hardware qualification remain separate
acceptance work.
