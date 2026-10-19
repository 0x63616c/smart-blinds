# Trade Study: Position reference, sleep and recovery

**Date:** 2026-10-19
**Status:** OPEN

## 1. Context

The enclosure should remain a clean RYSE-like lower-wall unit. A motor encoder measures shaft motion, not the bottom rail directly. A saved count cannot prove that fabric stayed still during reset, and a gated encoder cannot observe backdrive/manual movement during sleep. A production workflow should preserve ordinary daily operation and controlled updates without routinely asking the owner to recalibrate, while refusing unsafe guesses after unknown position loss.

The proposed 5 mm group alignment target requires measured holding, slip and reference repeatability. No option below is physically tested. The current executable core still boots unreferenced; this document does not relax that behavior.

## 2. Options

### Option A: Validated holding mechanism, guarded chain and rare supervised recovery

Establish that the installed blind clutch holds fabric with the chain idle across the load, temperature, dwell time and disturbance envelope. Guard chain access; service/manual intervention explicitly invalidates position. If that evidence is sufficient, gate the motor encoder while stationary and retain calibrated position across an intentional sleep interval. This is conditional continuity based on a tested mechanical constraint, **not an absolute position measurement**.

For planned OTA, finish motion, stop and settle, check encoder stability, then store a transactional one-use stationary-update ticket containing calibration revision, position, expected image identity and boot transition. On the expected software reset only, consume the ticket before enabling any action. Recheck power, calibration and any available reference/index. If the transition or data disagree, remain unreferenced. Do not resume a pre-update move; a new command is required. A power-on, brownout, watchdog, panic, invalid ticket, chain service or suspected slip always takes the supervised recovery path.

Recovery UI should say “Position needs checking,” with physical buttons entering a deliberate commissioning mode. The owner uses hold-to-jog at a limited speed/current/travel budget, release to stop, places the bottom edge at the marked room datum or known endpoint, and confirms it. Never drive blindly into a hard stop. Normal button taps and HA movement remain unavailable until reference succeeds. This avoids pretending an unknown reset is ordinary sleep.

### Option B: Unique bottom-rail marker and local home sensor

A magnet on the actual bottom rail passes a fixed sensor beside one known rail position. If the unit's mounting height and lateral offset place that position within the sensor's working gap, the sensor fits locally. This directly observes the fabric endpoint and can detect discrepancies downstream of the motor. A Hall switch offers low idle current; TI's DRV5032 family has several sample-rate/current choices, so magnet speed and sensing-window width must determine the actual variant. A low sample rate can miss a narrow passing marker. [TI DRV5032 datasheet](https://www.ti.com/lit/ds/symlink/drv5032.pdf)

Calibrate the detection window and repeatability; reject disconnected/stuck signals through commissioning and plausibility checks. During normal travel, compare the measured reference crossing with encoder prediction. Queue OTA until the blind naturally parks at this reference, verify marker and stationary state before/after reboot, and make no surprise movement just to update. An unknown boot away from the marker still needs supervised recovery; automatic blind searching is not justified merely by adding a sensor.

### Option C: Unique bottom-rail marker and small wired home satellite

Use the same physical reference as B, with a small sensor at the actual endpoint and a thin cable to the lower unit. This decouples unit mounting from the rail's endpoint geometry. It adds a visible cable, connector and installation step. Failures of an unplugged cable must mean unknown reference, not home. The sensor and cable routing must remain clear of the fabric and chain.

### Option D: Continuous motion observation or mechanical absolute turn memory

Keep an encoder powered and count throughout sleep, or add independent output sensing. The C6 LP core can observe GPIO while the main processor sleeps; that needs suitable LP pins, an actual quadrature implementation and measured missed-edge/standby behavior. HP PCNT configuration alone does not establish retained counting in every sleep mode. [Espressif LP core](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-reference/system/ulp-lp-core.html), [PCNT power management](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/pcnt.html#power-management)

An always-powered 5 V encoder drawing 1 mA uses 10.8 Wh over 90 days before regulator losses; at 10 mA it uses 108 Wh. The purchased encoder's idle current is unknown, so this cannot be accepted on headline MCU sleep current. A lower-power output sensor might help but adds parts and firmware.

A single-turn magnetic angle sensor is periodic; for example AS5600 measures a magnet's 0–360° position. It cannot recover how many full drive-wheel turns occurred while unpowered. Mechanical reduction covering the entire blind travel in less than one sensed turn could retain multi-turn position, but adds gears, backlash and packaging work, and still cannot see fabric/clutch slip downstream. [ams OSRAM AS5600 datasheet](https://look.ams-osram.com/m/7059eac7531a86fd/original/AS5600-DS000365.pdf)

An optical/magnetic **chain or wheel index** is an auxiliary check within a known turn window, not an independent option for absolute recovery. A marker repeats once per loop/revolution. Mechanics can reserve a sensor mount in the guard, but an added magnet collar may not pass the 4.5 mm bead pockets; a marker within a replacement bead needs a fit test.

## 3. Comparison Table

| Criterion | A: Validated hold | B: Local rail reference | C: Wired rail reference | D: Continuous/absolute output sensing |
|---|---|---|---|---|
| Wall appearance | Existing lower unit | Small rail marker; local sensor if geometry permits | Adds sensor and wall cable | More internal parts; no rail cable |
| Added hardware | Optional guard switch; existing encoder | Sensor, magnet and mount | Sensor, magnet, cable and connector | Powered encoder/LP resources or additional sensors/gears |
| Idle energy | Lowest if holding permits rail gating | Low-power sensor possible | Similar sensor current plus cable leakage | Must measure complete sensing path |
| Unknown reset | Owner confirms reference | Can recover at physically sensed home; otherwise owner | Same, with flexible sensor location | Only sufficient if absolute multi-turn state survives; downstream slip remains |
| Controlled OTA | Conditional stationary ticket after holding validation | Defer to natural home parking; verify physical reference | Same | Requires demonstrably continuous/absolute observation across reset |
| Slip evidence | Holding/slip tests and periodic owner check | Actual fabric reference crossing | Actual fabric reference crossing | Motor/wheel observation misses downstream slip |
| Current confidence | Clutch behavior unmeasured | Rail-to-unit gap and marker mount unknown | Feasible in principle; installation compromise | Power, pin use and mechanics unmeasured |

## 4. Recommendation

**Rationale:** retain A as the lowest-cost candidate and reserve the home connector/mount. Require a two-unit holding/backdrive/slip test before permitting encoder gating with retained position. Evaluate B from actual installation geometry; it materially improves reference confidence without adding a wall cable when it fits. C remains an explicit optional fallback, not a default change to the requested appearance. Keep unknown-reset recovery strict throughout prototyping.

**What we're giving up:** A cannot prove position absolutely and may require occasional owner recovery after a crash, unplugged pack or manual service. Its controlled-update continuity is valid only under the measured holding constraint. B/C add installation parts and do not justify unattended searching from arbitrary unknown position. D spends power or mechanical complexity and still needs a strategy for downstream slip.

**When to revisit:** measured clutch drift/backdrive, encoder standby current, unit-to-bottom-rail distance, marker repeatability, chain access and the number of resets observed in endurance testing. If A cannot remain within the physical position-error budget, do not hide that in software tolerances: choose a physical reference/position observation system or revise the runtime/appearance target. Before production, demonstrate normal sleep, controlled OTA, failed OTA, brownout, battery removal, manual interference and group rejoining with measured bottom-edge error.
