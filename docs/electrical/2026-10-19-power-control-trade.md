# Trade Study: integrated power and control

**Date:** 2026-10-19
**Status:** OPEN — architecture recommendation, component selection and physical validation pending

## 1. Context

Eight identical controllers are budgeted for seven blinds. Each uses a 3S2P pack of Samsung 50E cells, the purchased 12 V JGB37-520 encoder motor, physical buttons, USB-C charging and coordinated Home Assistant control. Small total enclosure size and total eight-unit cost matter more than the smallest individual IC. No archived Packmule or Smart Shades circuitry is adopted.

We need independent battery protection, cell balancing, temperature-qualified charging, credible charge percentage, current-limited motor operation and measurable standby consumption. The unknown motor current and encoder interface are explicit design inputs to verify before fabrication. The inherited PD12V6Mini is a power supply, not a battery charger.

## 2. Options

### A: fixed 15 V PD, standalone buck charger, integrated smart pack

A CC-line PD sink requests 15 V; BQ24133 charges the protected 3S pack. BQ40Z50-R2 supplies gauging, protection and balancing. DRV8874 drives the motor directly from protected battery voltage. The controller uses a low-quiescent-current 3.3 V buck.

BQ24133 accepts 4.5–17 V operating input, charges up to 2.5 A and supports a thermistor and external power-path FETs. Its external system path can pass adapter voltage, so the 12 V motor must not be connected directly to that path. A 5 V USB source cannot charge 3S through a buck-only converter. [TI datasheet](https://www.ti.com/lit/ds/symlink/bq24133.pdf)

### B: wide-input buck-boost charging, integrated smart pack

A CC-line PD sink plus BQ25798 supports USB sources below or above pack voltage. A BQ40Z50-R2 and protection MOSFETs manage the pack. The motor connects to protected pack power; charger SYS feeds the logic supply. Charging pauses during motor motion, which avoids motor load confusing charge termination at the battery node.

BQ25798 has an integrated switching bridge, configurable cell count, input current control and an NTC input. Hardware PROG selects 3S defaults, and CE remains disabled until the controller checks the pack and input capability. PD negotiation remains a separate function; this charger is not a PD sink controller. [TI datasheet](https://www.ti.com/lit/ds/symlink/bq25798.pdf)

The cheaper BQ25792 is a close candidate without solar MPPT. It is listed at JLC, but its official product/datasheet endpoints returned 404 during this review. Do not switch to it until its current lifecycle and exact supported documentation are verified. The BQ25798 primary datasheet downloaded successfully.

### C: fixed 15 V charging, separate protector and host-computed fuel estimate

Use a standalone charger, a lower-cost cell protector/balancer, and a separate current integrator or monitor. Firmware estimates remaining capacity. A BQ76905 is an example of a small monitor/protector with current integration, but uses low-side protection FETs: USB, debug and signal ground paths then need careful treatment. A BQ76942 provides high-side drivers but occupies a 7 × 7 mm TQFP body and costs more in the current shortlist. [BQ76905](https://www.ti.com/product/BQ76905), [BQ76942](https://www.ti.com/product/BQ76942)

This approach requires more independent interfaces or more host battery-estimation work. It is not acceptable to turn terminal voltage directly into a precise percentage while the motor is running.

## 3. Comparison Table

| Criterion | A: 15 V buck | B: buck-boost | C: separate battery functions |
|---|---|---|---|
| USB charging experience | Requires a suitable 15 V PD source | Can support slower 5 V charging within negotiated/advertised current | Same 15 V requirement in the compared implementation |
| Charger IC public JLC price, 1+ | BQ24133 $2.9586 | BQ25798 $2.8378 in first live snapshot; refresh was rate limited | BQ24133 $2.9586 plus separate pack functions |
| Battery percentage | Gauge must be configured and learned | Same gauge and commissioning | Host estimator and calibration required |
| Pack protection grounding | High-side gauge FETs retain system ground | Same | Small low-side options complicate USB/debug grounding |
| Space | Charger plus input/power-path FETs and passives | Integrated bridge, but several power capacitors and inductor still dominate | Savings in one IC can be lost in extra ICs, isolation and passives |
| Idle consumption | Must measure complete pack and controller | Charger battery-only current is small; radio and gauge mode still matter | Depends on every monitor and their measurement duty cycle |
| Firmware cost | Simple charger; gauge setup remains | Charger register policy plus gauge setup | More custom state-of-charge and protection-interface work |
| Main unknown | PD compatibility and layout/thermal performance | Reset defaults, input current policy, power-path transients | Entire protection/gauging partition and its true cost |

The [live sourcing snapshot](../../bom/electronics-sourcing-snapshot.json) distinguishes overseas inventory, presale quantity, library class and assembly eligibility. Search-engine stock snippets were stale. No inventory is reserved and none of these numbers is a manufacturing quote.

Radio module cost is a separate, important trade:

| Candidate | Package body | Live JLC eligibility | Availability evidence | Implication |
|---|---:|---|---|---|
| ESP32-C6-MINI-1-N4 | 13.2 × 16.6 mm | Standard Only, X-ray required | Overseas 1, presale 0 | Smallest module does not currently make the cheapest assemblable board |
| ESP32-C6-MINI-1-H4 | Same outline | Standard Only, X-ray required | Overseas 0 | Alternate temperature grade does not solve current sourcing |
| ESP32-C6-WROOM-1-N4 | 18 × 25.5 mm | Economic and Standard | Overseas 190 in snapshot | Preferred cost/availability candidate; verify final BOM and enclosure RF clearance |

All retain Wi-Fi and IEEE 802.15.4 capability. Transport remains open: Thread polling with a powered border router, or Wi-Fi modem/automatic light sleep. Existing compatible HomePod hardware could avoid buying a router, but its model and commissioning path are unverified. Do not use deep-sleep chip current as an always-connected Wi-Fi budget. [Espressif module documentation](https://www.espressif.com/sites/default/files/documentation/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf), [sleep documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-reference/system/sleep_modes.html)

## 4. Recommendation

**Rationale:** develop B with a C6 WROOM module and BQ40Z50-R2 first. It preserves usable USB-C charging, measures state of charge with a dedicated gauge, and currently preserves a cheaper assembly tier. The 75 × 35 mm PCB is an allocation to test, not a routed-size claim. Direct battery motor drive avoids another high-power converter; closed-loop speed must be limited by the weakest calibrated blind at low battery.

**What we are giving up:** WROOM uses about 240 mm² more body area than MINI. The smart gauge needs chemistry selection, calibration and a learning cycle; allow development tooling and time in the budget. A protected, fused, insulated pack with sense wires is more involved than six loose holders. A charger and gauge do not eliminate prototype charging, thermal or fault testing.

**When to revisit:** motor current exceeds the driver/thermal envelope; low-battery torque cannot meet the common speed; module stock or assembly tier changes; the enclosure cannot keep the antenna away from metal; gauge development tooling costs outweigh its benefit; or measured radio power misses 60 days. A regulated motor rail or larger driver is a fallback only when measurements justify it.
