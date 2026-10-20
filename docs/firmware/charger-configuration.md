# BQ25798 configuration and readback

The portable charger module and ESP-IDF I2C component configure and verify a proposed BQ25798 profile while **holding external charge permission off and leaving `EN_CHG=0`**. They cannot enable charging. The current bring-up application compiles the component but does not instantiate it, configure I2C pins or drive GPIO22. No charger, cell or owner device has been written by this work.

The register map was derived from [TI BQ25798 SLUSDV2C, June 2026](https://www.ti.com/lit/ds/symlink/bq25798.pdf), primarily sections 7.5.1.1–21, 7.5.1.23–35, 7.5.1.42–57. It was checked against the current charger capture with the electronics designer. This is a source-reviewed, host-tested configuration proposal; it is not a validated Samsung 50E charging prescription or proof of converter behavior.

## Interface and invariants

`smart_blinds::charger::Bq25798` depends on a bounded byte-oriented `Bus` and a separate `Inhibit::hold_off()` interface. The board implementation must request and verify the reviewed OFF output state independently of I2C. It must outlive the charger object. Failure is reported; software cannot prove a transistor physically turned off from a GPIO readback alone. There is deliberately no enable method.

`configure(9 V | 15 V)` first establishes the OFF request, checks exact part/revision `REG48=0x19`, and rejects mismatched 3S/750 kHz register state. It does not rewrite a mismatched cell count to make an unknown board appear correct. These state checks do not prove the physical PROG resistor after previous software writes; first power-on qualification remains necessary.

Every profile write is immediately read back, followed by a complete second verification. Identity, register mismatch, timeout, reversed clock or bus error invalidates configuration, repeats the independent OFF request and requires explicit reconfiguration. No reset, NVM, OTP, ship-mode or charge-enable command is exposed. Reserved fields are written zero; transient commands such as watchdog reset are separate from the static image.

The C6 adapter uses address **0x6B**, an externally owned 100 kHz bus and a **10 ms timeout per transfer**. Operations have a **750 ms total budget**, and ADC polling also has an iteration cap so a stuck software clock cannot produce an infinite loop. It is a worker component and must never run in the motor-control task. These software limits are not measured hardware shutdown bounds.

CE inhibits battery charging; it does not isolate the charger's SYS input path. Writing a profile can change system power behavior even with CE off. The independent qualified USB input switch and current limit must therefore exist before using this component on a powered board. The requested 9 V/15 V profile parameter is not evidence of an actual contract.

## Proposed register image

Two-byte values are sent most-significant byte first at the register's starting address. Readback, raw power-on bytes and measured ADC scale must be checked on the physical device before any CE release. The MAX17320 reader uses a different byte order and must not be reused as a BQ word codec.

| Register | Image | Intended setting |
|---|---:|---|
| `00` | `1A` | Minimum system 9 V |
| `01–02` | `04 DD` | Charge target 12.45 V, 10 mV steps |
| `03–04` | `00 64` | Charge-current setting 1 A, 10 mA steps |
| `05` | `50` / `82` | Input-voltage regulation 8 V / 13 V for 9 V / 15 V source |
| `06–07` | `00 96` | Input-current setting 1.5 A, 10 mA steps |
| `08` | `C3` | 120 mA precharge, 71.4% VREG transition setting |
| `09` | `25` | 200 mA termination, watchdog stops charging, register reset clear |
| `0A` | `A3` | 3S, 1024 ms recharge debounce, 200 mV recharge offset |
| `0D` | `4B` | 2 h precharge timer; unused OTG current at default |
| `0E` | `3C` | Trickle/precharge/fast safety timers on, 12 h fast timer, no doubled timer/topoff |
| `0F` | `82` | Charging/ICO/backup/HIZ off; termination and automatic OVP discharge on |
| `10` | `93` | 18 V input OVP, 2 s watchdog; watchdog-reset bit clear |
| `11` | `00` | Automatic/forced D+/D− detection, HVDCP and ship controls off |
| `12` | `00` | OTG off, default forward protections/PFM retained |
| `13` | `21` | 750 kHz, input OCP on, no external ACFETs or forced VINDPM detection |
| `14` | `16` | Both input-limit mechanisms on, no ship FET, battery-only current sensing off |
| `15` | `AA` | MPPT off; unused timing fields at defaults |
| `16` | `30` | Die regulation 60°C, shutdown 85°C; input pulldowns/backup trigger off |
| `17` | `00` | Suspend charging in both JEITA cool and warm regions |
| `18` | `44` | Nominal cool 10°C/warm 40°C comparator choices; TS monitoring enabled |
| `2E` | `40` | ADC idle, one shot, 15-bit sampling, no old-value averaging |
| `2F` | `00` | Current, voltage, TS and die ADC channels enabled |
| `30` | `C0` | D+/D− ADC channels disabled; VAC1/VAC2 enabled |
| `47` | `00` | D+/D− drivers high impedance |

TI's REG09 bit 5 diagram is labelled read-only while its field description explicitly defines `STOP_WD_CHG` as read/write. The implementation follows the field description and requires successful bit readback. The selected watchdog is a secondary defense, not a replacement for external CE control or a proven maximum stop time. Expiry resets other settings; subsequent capture rejects watchdog history/default settings and cannot resume charging automatically.

## Electrical interpretation

The proposed STUSB4500 factory contract is 9 V/2.5 A or 15 V/2.5 A; 5 V fallback is blocked by the qualified input stage. The component does not implement PD negotiation or infer entitlement from BQ `VBUS_STAT`. A 1.5 A register setting is a nominal regulator target, not an exact current ceiling; TI's accuracy table has specific test points rather than a universal guarantee at this setting. Hardware input limiting, detach/hard-reset behavior and valid-contract evidence remain separate requirements.

At 9 V, 1 A into a nearly full 12.45 V pack can exceed the input budget after conversion losses and system load, so input regulation may reduce charging current. Lower current can also make the deliberately unextended 12 h timer expire before full charge. This is acceptable for the first conservative profile, but charge time and thermal behavior need measurement.

The 12.45 V target leaves planning margin below 12.6 V. Applying the datasheet's +0.65% result at its 12.6 V test point gives about 12.531 V, but that extrapolation is not a guaranteed bound at 12.45 V. Individual-cell protection and measurement remain necessary. The Semitec 103AT-2 and 5.23 kΩ/30.1 kΩ divider approximate the selected 10–40°C window; component tolerance, thermal placement and lag require validation. The hard TS cutoff is not a 40°C guarantee. The low die thresholds are proposed enclosure-protection settings and may substantially derate charging.

## Fresh capture and independent readiness

`capture()` keeps CE off, verifies the full profile, and reads watchdog/fault history **before** resetting the watchdog. It starts a fresh 15-bit one-shot, must observe ADC busy, then requires both completion status and a newly raised completion flag. It rejects stale conversions, unsafe TS states, missing power/battery, active charge/OTG/backup/detection, converter faults, timer expiry or a changed profile. Fault/history registers are read-to-clear; this component must be their sole owner or a shared register service must preserve every event.

The source audit specifically distinguishes `ADC_DONE_STAT` at `1E[5]` from `ADC_DONE_FLAG` at `24[5]`; `25` holds temperature flags. Source/battery changes or thermal history also revoke this disabled-state capture. A future active-charge monitor will need a separately reviewed lifecycle rather than relaxing these checks ad hoc.

The result contains raw status and nine ADC values plus conversion-start/read-finish times. Its conversion-start time is the conservative age boundary; read completion does not make every ADC channel newly sampled. It does not turn raw gauge values into pack approval.

The separate `assess()` function returns only `ready_for_review`. It requires all of the following, and has no output operation:

- A valid capture and source/pack evidence no older than 250 ms, with no future/reversed timestamps.
- A reviewed fixed 9 V or 15 V contract of at least 2.5 A, factory PD image verification, a nonzero contract epoch and independently qualified hardware input path. Measured BQ input must agree with the source's planning voltage envelope.
- A nonzero pack identity, physically present cells, a commissioned independent protector, healthy protection state, verified sensor placement and fresh conversions. Each cell must lie in the proposed 3.0–4.15 V operating range, pack ADC must agree with the cell sum within a provisional 150 mV, and both pack sensors must be 10°C inclusive to 40°C exclusive.
- Motor stopped. No charging while moving.

The existing `Max17320Reader::read()` is **insufficient** to populate those approval fields. It does not prove the approved NVM protection image, ADC conversion age, all protector state, sensor placement or cell identity. Those checks, independent MAX temperature/overvoltage cutoffs, absent/stuck carrier-bus handling, balanced-pack commissioning and safe recovery from low cells remain implementation/physical-validation gates. Low-cell recovery is intentionally outside this normal operating profile.

Before enabling any real charger, the integrated application still needs a reviewed CE driver, explicit charge-session lifecycle, fresh evidence refresh/revocation, safe watchdog servicing, independent hardware contract-loss shutdown and physical tests of all limits. The component's inability to enable charging is retained through this milestone.

## Verification

The host tests cover every I2C transfer failing in configuration and fresh capture, individual register-readback mutations, unknown identity/revision, wrong cell/frequency state, failed inhibit, deadline/clock failures, ADC stalls/old completion, watchdog/fault/TS states and independent readiness boundaries. Their fake bus checks that no operation happens before OFF and no write sets `EN_CHG`, `EN_OTG` or `REG_RST`.

```sh
cmake -S firmware -B work/firmware-build
cmake --build work/firmware-build
ctest --test-dir work/firmware-build --output-on-failure
```

Host tests pass. The C6 component is included in the motor-disabled bring-up target for the next pinned ESP-IDF build. No physical I2C, charging, temperature, timeout or watchdog measurement has been performed.

The separate [`capture_off()` motion observation](motion-power-evidence.md)
now verifies the OFF profile and fault status without requiring a connected USB
source or starting ADC conversion. It can feed the motion power assessor while
unplugged; it cannot authorize charging. The original charge-review capture and
source-entitlement requirements remain separate.
