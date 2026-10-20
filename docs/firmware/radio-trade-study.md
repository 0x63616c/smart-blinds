# Trade Study: Seven-blind radio supervision and idle power

**Date:** 2026-10-20
**Status:** Supporting trade study — Wi-Fi evaluation selected; calculations remain unverified
**Recommended next experiment:** Wi-Fi STA with associated automatic light sleep while idle; fully awake Wi-Fi during preflight, movement and settling. Keep Thread sleepy wake plus active Wi-Fi as a fallback.

The recommendation below preceded implementation. The separate
[motor-disabled Wi-Fi checkpoint](wifi-evaluation.md) now records its exact
implemented scope and build/test evidence. This study does not claim that
future motion integration or physical acceptance is complete.

## 1. Context

The seven-peer localhost fixture establishes protocol/control behavior, not radio feasibility. Its last local run transferred 506,048 application-body bytes in 4.651 s: **108.8 kB/s, or 870 kbit/s before networking overhead**. This already exceeds the C6's 250 kbit/s 802.15.4 PHY. Checkpoint `f8827ac` subsequently passed the 59 transport tests in CI. Earlier intermittent `executor_fault [4,4]` and source-age failures remain unresolved; the first-fault diagnostics and deliberate 30 ms stall regression remain necessary. This proposal does not explain those failures away.

The control limits stay fixed:

| Existing condition | Bound to preserve |
|---|---|
| Source-based device lease | 300 ms; reception, queue acknowledgment and retransmission cannot extend it |
| Coordinator lease generation | Every 100 ms for every queued prepare, including preparing/ready |
| Ordinary command source age / device inbox age | 100 ms / 40 ms, with conservative clock uncertainty |
| Accepted transport status source age / prepare-or-commit readiness age | 100 ms / 30 ms |
| Coordinator maximum gap from a source report or lease generation | 250 ms |
| Clock error / control update gap | At most 10 ms including quantization / at most 20 ms |
| Group meaning | One common physical bottom-edge target, all peers ready before commit |

These are separate limits: a 200 ms reporting interval would not authorize acceptance of a 200 ms old report. Local STOP, driver/thermal fault, power evidence and external watchdog remain independent of radio throughput. Unknown reset still loses position reference. Sleep does not establish a physical reference.

Project sources: `firmware/src/motion_session.cpp`, `integrations/home_assistant/coordinator.py`, `integrations/thread_transport/{clock,motion}.py`, `integrations/thread_bridge/{worker,group,mapping}.py`. All rates and energy totals below are calculations or proposed qualification targets, not physical measurements.

## 2. Options

### A. Wi-Fi associated automatic light sleep; awake during motion

The **pinned ESP-IDF v5.5.4 C6 configuration uses the internal 150 kHz oscillator** for automatic light sleep. It does not require an external 32 kHz crystal. The recommended settings include power management, tickless idle, 1 kHz RTOS ticks, a three-tick idle threshold, CPU/MAC power management, and `light_sleep_enable=true`. Its GPIO-disable-in-sleep setting must be adapted to the board's fail-off controls and GPIO0/1 button wake requirements, not copied without review. [Pinned C6 configuration](https://github.com/espressif/esp-idf/blob/v5.5.4/docs/en/api-guides/low-power-mode/low-power-mode-soc.rst#L346-L399).

Espressif reports associated automatic-light-sleep averages of **0.919 mA at DTIM1, 0.368 mA at DTIM3 and 0.172 mA at DTIM10**, measured in a shielded box. Association is retained; deep sleep disconnects. The DTIM3 modem-sleep-plus-frequency-scaling result is 13.9 mA, so merely enabling Wi-Fi power saving without CPU automatic light sleep is insufficient. These are reference measurements, not predictions for this board, peripherals, software or AP. [C6 Wi-Fi power reference](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/low-power-mode/low-power-mode-wifi.html).

Start with `WIFI_PS_MIN_MODEM`: its receive delay depends on the AP's DTIM. A hypothetical 100-TU beacon interval is 102.4 ms, so DTIM3 and DTIM10 imply 307.2 ms and 1.024 s intervals before losses or additional queueing. `MAX_MODEM` uses a configured listen interval but can miss broadcast traffic. During preflight/motion use `WIFI_PS_NONE` and hold the appropriate no-light-sleep/frequency locks. This minimizes sleep-induced receive delay, but does not guarantee network latency. [Pinned Wi-Fi driver behavior](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/wifi.html#wi-fi-power-saving).

**Board-specific conditions:** park the periodic motion worker only after outputs are confirmed OFF and settling is complete; stop active-rate sensing and telemetry while safely idle; preserve wake GPIOs and deliberate OFF output levels. Charge monitoring while USB-powered is a separate power state. A 10 ms idle timer, logging, an unreleased PM lock or an always-running polling task can defeat the quoted savings. Requalify clocks after every sleep transition; the active motion clock model must not inherit an idle oscillator assumption.

**AP and maintenance qualification:** measure the actual beacon/DTIM settings, missed beacons, buffered-unicast delivery, association retention and average whole-pack current over at least 24 h. Include ordinary ARP, IPv6 neighbor discovery, DHCP renewal, multicast/mDNS, HA traffic and background broadcasts. Do not disable necessary network maintenance to manufacture a low current number. Rate-limit optional discovery and idle charge telemetry; publish its source timestamp and age. OTA, credential changes and reconnect attempts cannot run during a motion session. Failed idle association uses bounded backoff, not continuous scanning.

**Proposed admission and latency policy:**

1. A remote wake request only asks for an awake window; it grants no motion permission. Local buttons wake independently of network health.
2. On an already-associated device, target wake-to-completed preflight within 1.5 s on the actual AP. This is a test target, not a vendor guarantee. Then retain the existing three-second common scheduled start.
3. Cold scan/authentication/address assignment/DTLS may take several seconds. Allow an explicit eight-second recovery-preflight deadline, with no movement and no automatic command replay. Timeout reports unavailable. A three-second common start is selected only after all members finish preflight. The few-second normal case must not be promised for AP outages.
4. Bind the authenticated identity, boot nonce, calibration, ledger reservation, connection generation, IP endpoint and motion owner before preparing. An address is a route, not identity. Resolve or change it only outside an active session. Reconnection/rekey/migration during preparation, movement or settling aborts the group; never resume the old command.
5. Return to idle sleep only after definitive terminal evidence, settled motor OFF and session teardown. An uncertain stop is not permission to sleep through evidence collection.

Wi-Fi credentials and per-device DTLS identity/key need explicit commissioning. Prefer the existing physical service/programming path for the first prototype. No default credentials, unsolicited SoftAP, hardcoded secrets, mDNS-based automatic ownership or changes to the owner's AP. Encrypted credential storage/secure-boot provisioning remain separate reviewed factory steps; no irreversible key programming is authorized by this proposal.

### B. Thread sleepy wake; Wi-Fi during preflight and motion

This retains the same C6 module but requires both Wi-Fi credentials and a commissioned Thread network/border-router path. A HomePod is not by itself proof of a working custom HA-to-Thread application path. A wake delivered through Thread would trigger Wi-Fi association while stationary, followed by **new Wi-Fi DTLS authentication, clock qualification and readiness**. The wake channel never issues prepare/commit or supervises actuation.

C6 shares one RF path. Espressif lists Wi-Fi STA plus Thread end device as supported, while Thread router coexistence is less stable; ordinary 802.15.4 receive has low RF priority. This is not simultaneous independent reception. [C6 coexistence guide](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/coexist.html). Before prepare, establish one Wi-Fi owner and freeze transport choice. During active motion, there is no fallback to Thread, scanning or reconnect. Any retained Thread maintenance traffic must be measured for interference; alternatively detach while stationary and account for the later reattach cost.

For a one-second idle Thread poll, a parent may hold wake traffic until the next poll. Plan for multiple missed polls in recovery, then the Wi-Fi association/DTLS deadline. Do not assume one-second wake or parent-buffer capacity is guaranteed on an unknown HomePod. Cold Wi-Fi preflight is incurred on each move, but its energy is relatively small compared with motor energy. This option is worthwhile if the actual AP makes option A's idle power unacceptable; it adds provisioning and state-machine complexity.

### C. Compact Thread only

This is a packet-budget study, **not an approved new wire protocol**. It reduces JSON and separate polls substantially but still lacks comfortable seven-peer airtime margin at the existing supervision cadence.

#### Candidate combined lease, status and clock exchange

An authenticated preflight context would bind full 64-bit boot/command IDs, calibration revision, a durably reserved 64-bit message range, full host/node time epochs and the exact authenticated connection/owner. A 16-bit context handle and message ordinal can then refer to that state without repeating every full identifier. Context reuse across reconnect/reset is forbidden. Reserve at most 4,096 ordinals for a bounded job, with the highest reserved for STOP; no wrap or uncertain-delivery reuse.

| Candidate field group | Bytes |
|---|---:|
| Lease: kind/flags, context, message ordinal | 1 + 2 + 2 |
| Original source-send time delta, actual wire-send T1 delta | 4 + 4 |
| Previous exchange ordinal and host receive T4 delta | 2 + 4 |
| **Lease application body** | **19** |
| Reply: context and echoed ordinal | 2 + 2 |
| Device receive T2, send T3, worker sample deltas | 4 + 4 + 4 |
| Last worker-consumed ordinal; packed state/result/qualification flags | 2 + 2 |
| Signed physical height in micrometres; power-observation delta; display SOC | 4 + 4 + 1 |
| **Reply application body** | **29** |

Time deltas use microseconds with checked 32-bit range, not modular arithmetic; 4,294 s covers the existing 240 s maximum session. Charge/motor decisions retain full local power evidence; compact SOC is display-only. Queue acceptance is distinguished from worker consumption and readiness by the consumed ordinal and state.

The host gets four timestamps from each reply. The next lease can return the previous T4 so the device also completes that exchange, avoiding a separate clock request/reply. This needs explicit sequencing: a new clock context must not invalidate a preceding request still in the inbox. Bind immutable clock evidence to the request or refresh only after proven consumption. Lost proof does not fabricate clock qualification. Clock growth, source age and asymmetric delay remain conservatively bounded.

Ordinary messages preserve the original coordinator source time, consume a message ordinal even on uncertain delivery, and never extend permission on a repeated reply/record. DTLS replay protection and the existing application sequence floor both remain. **STOP preserves the current off-only exception:** authenticated boot/connection binding and a new reserved message number are required, but an expired clock/source timestamp must not prevent stopping. Replayed or old-boot STOP must not affect a new session. No shortened identifier is a substitute for the full authenticated context.

#### Maximum frame size and fragmentation

802.15.4 permits a **127-byte PSDU**, excluding the six-byte PHY header. In the assumed secured short-address frame, MAC overhead is 21 bytes: nine-byte addressing/header, six-byte auxiliary security header, four-byte MIC and two-byte FCS. An immediate MAC ACK is five PSDU bytes, plus its PHY header. Extended addresses, information elements and enhanced ACKs can add bytes. [RFC 4944](https://www.rfc-editor.org/rfc/rfc4944), [pinned OpenThread frame definitions](https://github.com/espressif/openthread/blob/a12ff0d0f54fd41954b45047fcdd08f302731c5f/src/core/mac/mac_frame.hpp).

DTLS 1.2 PSK-AES128-CCM8 adds 13-byte record header, eight-byte explicit nonce and eight-byte authentication tag: **29 bytes**. A 16-byte tag adds eight bytes. The currently tested CCM8 suite/tag remains a production security decision, not a reason to weaken a global crypto policy. [DTLS record format](https://www.rfc-editor.org/rfc/rfc6347.txt), [CCM suites](https://www.rfc-editor.org/rfc/rfc6655).

An optimistic CoAP request uses nine bytes: four-byte base, two-byte token, a one-character resource option and payload marker. Reply uses seven. This assumes a versioned resource fixes the binary format, no extra options, and a NON exchange without a separate CoAP ACK. Existing resource paths/tokens are larger. Default CoAP confirmable retransmission starts at seconds and is unsuitable as an active-motion retry policy. Preflight may use normal reliability; an active exchange needs bounded cancellation and application sequence semantics. [CoAP specification](https://www.rfc-editor.org/rfc/rfc7252).

The IPHC/UDP allowance varies with actual addresses, prefix contexts and hop limit. Ordinary UDP ports require seven compressed bytes; special compressed ports can save three, but are not configured here. Never assume both IPv6 addresses disappear, nor replace a stable application address with a changing routing locator just to improve the estimate. [RFC 6282](https://www.rfc-editor.org/rfc/rfc6282), [pinned compression implementation](https://github.com/espressif/openthread/blob/a12ff0d0f54fd41954b45047fcdd08f302731c5f/src/core/thread/lowpan.cpp).

| IP/UDP assumption | Header bytes | Lease / reply PSDU, no mesh header | With five-byte short-address mesh header |
|---|---:|---:|---:|
| Compressed prefixes, two inline 64-bit IIDs, elided hop limit | 25 | 103 / 111 | 108 / 116 |
| One full LAN address, one IID, context byte, inline hop limit | 35 | 113 / 121 | 118 / 126 |
| Two full addresses, inline hop limit, no context byte | 42 | 120 / **128** | 125 / **133** |
| Uncompressed IPv6/UDP plus dispatch | 49 | 127 / **135** | **132 / 140** |

Bold sizes do not fit. Even the 126-byte reply has only one byte of headroom: a Content-Format option, extended MAC address or larger authentication tag can require fragmentation.

Example: the 42-byte-header reply contains 107 compressed datagram bytes. With 21-byte MAC, five-byte mesh header and four-byte first-fragment header, first-fragment capacity is 97. Eight-byte uncompressed-offset alignment allows 90 compressed bytes; the 17 remaining bytes need a second fragment with five-byte fragmentation header. Result: **120-byte and 48-byte PSDUs**, two PHY headers, two ACKs and two channel-access attempts. Fragment loss also delays/requires retransmission or loses the entire status. This case is calculated using RFC 4944 offset rules, not a packet capture.

#### Seven-peer airtime

At 250 kbit/s, each byte costs 32 µs. With immediate ACK, one data frame of PSDU length L has raw RF occupancy `(L + 6 + 5 + 6) × 32 µs`. This excludes ACK turnaround, interframe spacing, channel assessment, backoff and failed ACK waits.

For a separate **serial-service planning estimate**, add 192 µs turnaround, a conservative 640 µs interframe allowance, 128 µs CCA and 1,120 µs mean initial backoff per data frame. The mean is 3.5 periods × 20 symbols × 16 µs at minimum backoff exponent three. Backoff does not itself occupy RF and may overlap other traffic; this column is neither measured utilization nor a worst-case bound. The pinned stack has default direct-frame retry limit 15, indirect-frame retry limit zero, and software ACK-timeout fallback 16 ms; actual C6 hardware capabilities and effective retry policy must be recorded. [Pinned MAC policy](https://github.com/espressif/openthread/blob/a12ff0d0f54fd41954b45047fcdd08f302731c5f/src/core/config/mac.h), [timing definitions](https://github.com/espressif/openthread/blob/a12ff0d0f54fd41954b45047fcdd08f302731c5f/src/core/mac/sub_mac.hpp#L528-L536), [ACK turnaround reference](https://onlinedocs.microchip.com/oxy/GUID-4B3D771E-5647-4191-AD45-C897B0D23071-en-US-3/GUID-5A6CBE5B-589F-4819-9C8E-FB38C636D8D8.html).

Assume seven peers, the 35-byte IP/UDP case, no fragmentation, established DTLS, one contention domain. One-hop uses 113/121-byte PSDUs; two-hop uses 118/126 on each hop. All percentages below are per second.

| Hops | Lease / reply interval | Raw RF occupancy | Serial-service estimate | Service with 25% extra attempts |
|---:|---:|---:|---:|---:|
| 1 | 100 / 100 ms | **60.03%** | **89.15%** | **111.44%** |
| 1 | 100 / 200 ms | 44.58% | 66.42% | 83.02% |
| 1 | 150 / 150 ms | 40.02% | 59.43% | 74.29% |
| 1 | 200 / 200 ms | 30.02% | 44.58% | 55.72% |
| 2 | 100 / 100 ms | **124.54%** | 182.78% | 228.48% |
| 2 | 100 / 200 ms | 92.51% | 136.19% | 170.24% |
| 2 | 150 / 150 ms | 83.03% | 121.86% | 152.32% |
| 2 | 200 / 200 ms | 62.27% | 91.39% | 114.24% |

For three hops in the same contention domain, multiply the two-hop rows by 1.5. Spatial reuse is not assumed. The 25% attempt factor is a planning scenario, not a bound for correlated interference. Healthy steady-state traffic excludes DTLS handshakes, routing/management, errors, empty CoAP ACKs and idle-device traffic. Suppressing alternate replies would require a reviewed standard No-Response/application policy; a two-byte No-Response option on 35 suppressed requests/s adds 0.224 percentage points of raw airtime. [No-Response option](https://www.rfc-editor.org/rfc/rfc7967).

The 150/200 ms lease rows are **comparisons, not approved changes**. A 150 ms interval cannot tolerate a completely lost update before the following update meets the 300 ms expiry; a 200 ms reply leaves only 50 ms before the coordinator's 250 ms telemetry-gap limit. With 100 ms replies, one missing reply can fit before a following reply at ~200 ms plus bounded delivery; two consecutive losses abort. Sampling age, clock uncertainty and early device cutoff reduce that nominal margin.

The clock budget is independently tight. Device motion evaluates uncertainty through `now + 100 ms + 300 ms`. With the worst permitted 10,000 ppm growth, 1,000 µs timestamp guard and integer quantization, usable error is effectively ≤9 ms. Approximate network-only RTT condition is `0.51 × RTT_ms + 0.01 × model_age_ms ≤ 4`. That permits ~7.84 ms at age zero, ~5.88 ms at age 100 ms and ~3.92 ms at age 200 ms. A 113/121-byte request/reply already consumes ~8.58 ms of RF time including ACKs, before contention. Exact timestamp placement changes the RTT portion, but there is clearly no generous margin. A tighter physical clock model may be qualified; it must not be invented to make Thread fit.

#### Sleepy receiver cost

A conventional SED polls its parent for downlink traffic. MAC frame-pending signaling and parent queues are part of the delivery path, not proof that the application processed a command. [Sleepy-device behavior](https://docs.silabs.com/openthread/2.6.3/openthread-sleepy-devices/02-sleepy-end-devices-seds), [OpenThread poll/RX APIs](https://openthread.io/reference/group/api-link-link).

Using a 22-byte secured poll PSDU, poll+ACK raw RF cost is `(22+17)×32 = 1.248 ms`. Seven devices polling once a second add 0.87% raw occupancy. Polling every 20 ms adds **43.68% before command traffic**; source delivery still has parent buffering, access and retries. Therefore use active RX while moving for the Thread-only comparison. A one-second idle poll is suitable only for wake/preflight; queued motion packets cannot inherit its multi-second latency. Parent queue lifetime/capacity, child limits, detach behavior and seven simultaneous wakes require measurement. Enhanced pending-data delivery or CSL could improve polling overhead but is not assumed available or qualified here.

Restricting operation to one hop and three peers per independently placed/channel-separated network would reduce 100/100 ms raw occupancy to 25.73% per three-peer network. It requires extra border-router infrastructure and a reviewed channel plan. Multiple parents on the same channel do not create independent capacity. Reducing group size would violate the seven-blind requirement.

### D. Wi-Fi deep sleep with periodic reassociation

This is different from associated light sleep. To notice commands within three seconds, repeating association at that cadence is expensive. At an assumed 150 mA awake rail current and 90% conversion efficiency, merely 0.1 / 0.25 / 1.0 seconds awake per three-second period costs **0.44 / 1.10 / 4.40 Wh/day**. These are optimistic hypothetical awake durations, not demonstrated association times; the complete 60-day budget is only 1.44 Wh/day. Deep-sleep resets/reference recovery also add complexity. Reject this as the first implementation.

## 3. Comparison table

| Criterion | A: Associated Wi-Fi | B: Thread wake + Wi-Fi | C: Thread only | D: Periodic Wi-Fi reconnect |
|---|---|---|---|---|
| Existing C6 board | No new component | No new component | No new component | No new component |
| Setup | Wi-Fi + device authentication + HA | Same, plus Thread credentials/border router | Thread credentials/border router + HA | Wi-Fi + device authentication + HA |
| Seven-peer motion bandwidth | Stronger candidate; actual AP latency still must pass | Same Wi-Fi motion test plus coexistence | Little one-hop margin; multi-hop fails at existing cadence | Same only once awake |
| Idle power | AP/background-traffic dependent; credible low reference values | Polling/parent/coexistence dependent | Polling/parent dependent | Poor at a three-second response target |
| Normal wake delay | AP DTIM plus preflight | Parent poll plus cold Wi-Fi preflight | Parent poll plus preflight | Reconnect interval plus preflight |
| Complexity | One network/one owner | Two networks and explicit stationary handoff | New compact protocol + stringent topology | Frequent boot/reconnect/reference handling |
| Main remaining gate | Whole-board power, AP latency, active clock and supply transients | Those gates plus Thread commissioning/coexistence | Airtime, timing, loss and parent-buffer proof | Energy and reference behavior |

### Energy comparison for the 60-day target

C6-WROOM-1 module reference values at 3.3 V include Wi-Fi RX 78 mA (HT20), Wi-Fi TX peaks 251–382 mA across listed modes/powers, 802.15.4 RX 73 mA, and TX 117 mA at 0 dBm / 185 mA at 12 dBm / 302 mA at 19 dBm. These active RF test values are not application averages; TX uses continuous duty and RX has CPU idle/peripherals disabled. The module contains a 40 MHz crystal and calls for a supply able to provide at least 0.5 A. [Module datasheet v1.4, sections 1, 6.2 and 6.4](https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.html).

Own scenario assumptions: six 50E cells → nominal 108 Wh, usable fraction 80% → **86.4 Wh**; one 3,048 mm full open-close cycle/day, 20 mm/s and 40 mm/s² → **305.8 s moving/day**. Add 20 s/day for two preflights; awake total 325.8 s, idle 23.9095 h. Use a provisional 90% 3.3 V converter efficiency, with 80–95% sensitivity, and 0.5 mA **total pack idle current** at nominal 10.8 V.

`E_day = 10.8 × I_motor_branch × 305.8/3600 + 10.8 × 0.0005 × 23.9095 + 3.3 × I_awake_rail × 325.8/3600 / efficiency`

Do not double-count active MCU energy if a future measured moving-pack current already includes it. Motor-branch current, not winding current during PWM on-time, belongs in this equation.

| Active 3.3 V current assumption | Active rail cost/day, converted to pack | Maximum motor-branch average for 60 days | Days at 1.5 A motor branch |
|---|---:|---:|---:|
| 73 mA, RF-RX-only reference, not full application | 0.0242 Wh | 1.403 A | 56.49 |
| 100 mA application scenario | 0.0332 Wh | 1.393 A | 56.16 |
| 150 mA Wi-Fi/application scenario | 0.0498 Wh | 1.375 A | 55.56 |
| 200 mA application scenario | 0.0664 Wh | 1.357 A | 54.98 |

The 73→150 mA difference costs **1.53 Wh over 60 days**, less than 2% of assumed usable capacity. Motor load and standby dominate. At 150 mA awake, the 90-day stretch permits only ~0.851 A motor-branch average under these assumptions. The 60-day goal is not established at 1.5 A.

These examples are now executable in [the energy calculation](../../hw/sim/blind-control/README.md), with assumptions in the shared planning profile and a source-generated wake-cost chart. That model distinguishes this motor-branch calculation from the earlier **total moving-pack current** sweep. It also subtracts service wake time from idle: an additional assumed 100 ms awake at 150 mA every three seconds reduces the example to 43.44 days. Actual task duration/current and whether the measured idle average already includes it must be established before applying that penalty.

Converting Espressif's idle references at nominal pack voltage and 90% efficiency:

| Vendor rail reference | Equivalent pack current, MCU contribution only | Contribution/day |
|---|---:|---:|
| Auto light sleep DTIM1: 0.919 mA | 0.312 mA | 0.0806 Wh |
| Auto light sleep DTIM3: 0.368 mA | 0.125 mA | 0.0323 Wh |
| Auto light sleep DTIM10: 0.172 mA | 0.058 mA | 0.0151 Wh |
| Modem sleep + DFS DTIM3: 13.9 mA | 4.719 mA | 1.219 Wh |

DTIM3 leaves approximately **0.375 mA** of the proposed 0.5 mA whole-pack idle budget for gauge, regulator losses/quiescent current, dividers, protection, leakage, retained GPIOs and actual application overhead. At 80–95% efficiency, its MCU-only equivalent is ~0.141–0.118 mA. This is a target to measure, not proof the allowance suffices. Rail peak-current/decoupling qualification remains open even though average energy is acceptable.

## 4. Recommendation

**Rationale:** evaluate option A first. It preserves the C6 hardware and current control safety limits, removes the unconfirmed Thread/HomePod commissioning dependency, and has a credible low-power mode without an external 32 kHz crystal. Choose this software transport change before redesigning the safety protocol around a saturated PHY. Existing 80-byte commands and source-stamped JSON can be retained for initial interoperability; compact combined traffic can follow as an optimization, not a prerequisite for hiding a Thread capacity deficit.

**Trade-off:** whole-pack idle current and receive latency now depend on the actual AP/network. Even Wi-Fi is not a real-time guarantee: active loss/clock failure must still stop safely. The local fixture's 870 kbit/s body rate is ~14.5% of a hypothetical 6 Mbit/s PHY before Wi-Fi overhead, so do not call the current JSON cadence comfortably proven on a weak legacy link. Measure/reduce actual airtime and require link admission; compact 19/29-byte paired messages would need only ~122 kbit/s of IPv6/UDP datagram bytes across all seven peers before Wi-Fi MAC overhead. Neither number is a Wi-Fi packet-capture result.

**When to revisit:** if actual whole-pack idle exceeds 0.5 mA, first inspect PM locks, sensing cadence and background traffic; then evaluate option B. If active packet timing, clock bounds or supply transients fail, stop and address that evidence. Do not widen the 300/100 ms safety limits or silently substitute an optimistic oscillator model. Thread-only remains a research alternative under explicit topology/cadence constraints, not the selected seven-device transport.

**Next implementation unit, after review:**

1. Add a separate motor-disabled C6 Wi-Fi evaluation target with no credentials/default network. Pin a maintained libcoap/Mbed TLS component and retain existing authenticated application semantics. Espressif's CoAP server example supports C6 and DTLS; compatibility, exact version/hash, cookie/session identity callbacks and CCM8 policy still need source/build review. [Vendor component example](https://components.espressif.com/components/espressif/coap/versions/4.3.1~3/examples/coap_server?language=en), [current component examples](https://components.espressif.com/components/espressif/coap/versions/4.3.5~6/examples?language=en).
2. Extract transport-independent resource decoding/owned-inbox interfaces carefully; preserve the existing Thread target. Add an explicit idle/awake/preflight/active/settling/fault owner state, PM-lock accounting, bounded idle reconnect/backoff and clock invalidation on sleep/network change. The default image remains unable to arm I/O.
3. Host-test network loss, delayed wake, duplicate/out-of-order traffic, reconnect while active, expired session, stale STOP, address change, missing credentials, lost PM lock and queued-command cancellation. Cross-build with the pinned IDF and check dual-OTA slot/RAM budgets. Retain all existing group and clock tests and unresolved first-fault diagnostics.
4. Physical acceptance later: actual seven-device DTLS traffic on the intended AP, same-time local buttons, induced AP loss and congestion, GPIO OFF/wake behavior, first-fault timing, active clock bounds, module supply transients, 24-hour whole-pack idle measurement and full-movement energy. No owner devices/networks are touched by the implementation checkpoint.

The smallest justified architecture change is **which existing C6 radio carries the active control session**. No new PCB part, HomePod assumption, weaker lease, homemade cryptography or fabricated hardware qualification is needed to build the next reviewable software checkpoint.
