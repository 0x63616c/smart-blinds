# USB input protection revision — isolated circuit candidate

The proposed prototype circuit adds an autonomous TPS26600 cutoff before every old raw-powered USB control/power branch. A TVS1800 protects its output; the existing TPS259470 remains the contract-gated charger switch. This retains the sustained 21 V input-fault requirement. It is a source-reviewed, compiled **unrouted and unpowered candidate**, not evidence of pulse coordination or a fabrication release. It addresses the USB gap in [the transient review](transient-review.md); the regenerative-load problem remains separate and unresolved.

```
USB VBUS ── raw ESDA25P35 + 4.7u ── TPS26600 ── GUARDED ── TPS259470 ── BQ25798
                                               │             ▲
                                      TVS1800 + 4.7u          │ PD permission
                                               │             │
                                        STUSB4500 VDD/monitor ┘
MCU 3.3V ── STUSB4500 VSYS; shared SDA/SCL/ALERT remain unchanged
```

The raw suppressor's specified 41 V clamp now faces the 60 V operating / 62 V absolute-maximum upstream switch. The guarded TVS has a specified maximum 24.7 V clamp at its stated 35 A, 8/20 µs, 125°C test condition, below the 28 V absolute limits of ST VDD and the downstream switch. Those comparisons do **not** establish assembled fast-edge overshoot, absorbed energy, negative-edge behavior or immunity. TPS26600 OVP response is 6 µs typical with no published maximum in the selected datasheet. Absolute-maximum headroom is not a normal-operating specification. [TI TPS2660 Rev G §§7–12](https://www.ti.com/lit/ds/symlink/tps2660.pdf), [TI TVS1800](https://www.ti.com/lit/ds/symlink/tvs1800.pdf), [ST ESDA25P35](https://www.st.com/resource/en/datasheet/esda25p35-1u1m.pdf).

## Why this circuit

| Option | Result for two prototypes |
|---|---|
| TVS1800 plus a fuse, with the old input switch | Rejected. A sustained 20/21 V source can drive the 18 V shunt indefinitely. Source current limiting can prevent a fuse opening; TVS1800's 18 mA absolute DC breakdown-current limit is not a continuous shunt-regulator rating. No fuse coordination was established. |
| Replace TPS259470 with TPS26600; power ST directly from raw through a resistor/Zener branch | Rejected before capture. ST's maximum active/startup draw is not specified sufficiently to bound that passive branch at minimum initial 5 V and maximum raw fault voltage. Leaving ST VDD, monitor or gate pull-up on raw retains the original exposure. Gating the only switch also creates a dead-pack negotiation dependency. |
| One upstream TPS26600 plus a discrete PD-gated reverse-blocking PFET pair | Evaluated but not selected. A priced pair of DMP3013SFV-7 devices alone is about $2.036 at the observed ten-piece tier versus $1.4118 for the retained gated switch. It still needs gate protection, controlled inrush, reverse-state analysis and SOA evidence. Its 4.5 V gate, 25°C maximum resistance gives 0.0765 W pair loss at 1.5 A, not a hot/inrush guarantee. Cheaper AO4805 has no guaranteed 4.5 V maximum RON in the reviewed table; the attractive AOSD21307 snapshot has no stock. A cheap AO3401A pair also needs a new clamp/slew/SOA design. These incomplete alternatives have no honest complete-board cost or accepted area figure. |
| **Upstream cutoff + guarded ST + existing gated switch** | Selected as the bounded capture. Ten added placements, four new SKUs, exact 42-part USB block. Retains already reviewed downstream permission, slew control and reverse blocking; adds heat and area quantified below. |

The discrete comparison does not claim that a cheaper implementation is impossible. It avoids treating an unfinished gate/soft-start network as an equivalent complete solution. Manufacturer evidence: [DMP3013SFV](https://www.diodes.com/assets/Datasheets/DMP3013SFV.pdf), [AO4805](https://aosmd.com/sites/default/files/res/datasheets/AO4805.pdf), [AO3401A](https://aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf). Exact cached catalog observations are in the candidate sourcing report.

## Exact circuit and behavior

TPS26600 IN1/2 and UVLO3 connect to raw VBUS. UVLO must not go to RTN: that selects the inappropriate factory ~15 V undervoltage threshold and prevents 5 V startup. OUT15/16 feed GUARDED. GND9 returns to system ground; **RTN8 and EP17 form their own local reference/thermal island**, not system ground. OVP, ILIM, MODE and slew components return only to RTN. SHDN is intentionally open, using its specified internal bias; NC4/13, IMON10 and FLT14 are unused. The physical pin contract covers all of them.

The OVP network is 390k 1% plus 30.1k 0.1% / 25 ppm. A conservative ±100°C resistor excursion and ±100 nA threshold-pin leakage give a rising interval **15.936–17.511 V**, leaving 186 mV above 15 V +5%. Falling thresholds span **14.776–16.085 V**. Therefore recovery after a 21 V fault may require returning to initial 5 V or unplug/replug; merely dropping to an upper-tolerance 15 V does not guarantee recovery. No 20 V PDO is requested or accepted.

ILIM uses existing **1.2k + 4.7k** parts in series, not a new 5.62k SKU whose observed private-order minimum exceeded stock. Scaling TI's characterized 5.36k current-limit bounds through its resistor equation gives **1.879–2.178 A** with the stated resistor allowance. This is a conditional calculation for a 5.9k network, not a separately specified TI test point. It brackets the 1.65 A charger planning maximum and remains below the 2.5 A contract after the 25 mA auxiliary reserve. Startup/current-limit interaction and source current behavior still require tests. The 402k MODE resistor selects **active current limiting with latch-off after thermal shutdown**, not instantaneous circuit-breaker action. Reset that latch by cycling the source below POR; MCU control of SHDN is not added. [TPS2660 §§9.3.1, 9.3.5, 9.3.8](https://www.ti.com/lit/ds/symlink/tps2660.pdf).

The six existing terminals moved from RAW to GUARDED are: downstream eFuse IN, VDD diode anode, enable-PNP emitter, its emitter/base pull-up, downstream OVP-divider input and ST source-discharge-chain input. Raw TVS, raw cap and connector remain raw. ST observes the guarded voltage, so a cutoff presents source loss to its monitor while battery-backed VSYS can keep host status alive. Shared I2C/ALERT, NVM requirements, dead-pack autonomous negotiation and default charge inhibition remain unchanged. Firmware must not interpret a stale PD contract as permission after guarded-input loss.

## Port scope, discharge and recovery

The revision protects **VBUS-fed branches only**. CC1/CC2 and their ST dead-battery connections remain directly attached to the connector through the existing ESDA25W shunt network. SBU1/SBU2 remain unconnected. D+/D− remain connected to the existing main-controller ESD/series-resistor path. None is in series with TPS26600: CC/SBU/data ESD, foreign voltage and VBUS-short exposure have not been solved by moving VBUS behind the cutoff. The raw connector and its 20 V nominal rating also require review against the 21 V fault condition; no continuous 21 V connector rating is asserted.

The ST source-discharge chain now discharges **GUARDED**, not the raw connector side of the open cutoff. Its separate DISCH chain still drains the charger side of the gated switch. TPS26600 reverse blocking keeps those nodes from being a deliberate path back to a disconnected connector. The raw 4.7 µF capacitor is not actively discharged by the ST chain. Confirm raw-node decay/reattach requirements and leakage before claiming USB timing compliance. Battery-present VSYS keeps ST alive while guarded VBUS falls; test that source loss revokes the sink gate and the owned runtime invalidates its previous authorization. An OVP or thermal-latch event may require a genuine source power cycle, not just a firmware PD reset. Do not infer immediate guarded-rail decay from the 100k bleed.

Both GUARDED and output DC annotations are now **0–17.6 V**, including off and ramp states. The former 8.1–18.8 V output annotation is removed: a passive downstream switch cannot raise the guarded DC rail, and its undervoltage threshold is not an output guarantee. Both series drops can lower a minimum-tolerance 9 V source below 8.1 V under load. Charger VINDPM/source-good policy must accommodate measured input voltage; these annotations neither authorize charging throughout the interval nor bound transient peaks or reverse-fed voltages.

For a depleted/absent battery, raw CC dead-battery termination remains available. The ungated upstream cutoff starts from 5 V; its slew charges the guarded rail and ST VDD before any PD permission. The downstream switch remains blocked for the initial 5 V profile and only supplies BQ after the programmed higher-voltage contract. BQ CE stays inhibited during MCU boot, profile/readback checks and missing-pack handling. This preserves the intended autonomous sequence, but requires actual cold/dead-pack testing because upstream voltage drop and delay were added. Invalid/unprogrammed ST NVM is still a fixture-inhibit case, not an accepted autonomous configuration.

## Startup, reverse behavior and heat

The 47 nF upstream slew capacitor gives a planning slope of **1.598–4.334 V/ms**, using TI gain/current bounds and stated tolerance/temperature/aging allowances. Conservatively referring all guarded/ST reservoirs to VBUS gives 9.7405 µF upper planning capacitance and **42.22 mA capacitor-only startup current**. Raw uncontrolled capacitance is 5.9455 µF under that allowance. Active ST startup current and the later charger load are not included in that estimate.

The downstream 1 nF slew capacitor remains. Its typical ~2 V/ms slope would draw ~51 mA into the derated-upper 20.1 µF local VBUS bank; that is **not the complete charger inrush**. PMID capacitance/internal charging paths and active BQ behavior must be included in the measured startup. No instantaneous gate-only PFET replacement is assumed. Verify 5 V dead-pack boot, 9/15 V negotiation, capacitor charging, attach/reset, overload latch and maximum current before raising the bench current limit. The old VDD start-margin calculation omits upstream drop and uses a 25°C diode specification, so it remains only a reference calculation, not a cold-start guarantee.

TPS26600 provides integrated reverse blocking and reverse-input protection; TPS259470's downstream reverse blocking remains. No alternate raw bypass path was introduced. Guaranteed static leakage during **OVP-off** is not supplied by the shutdown-only leakage specification; the 100k bleed is not proof of output discharge time. A nominal 17.6→0.8 V RC calculation is 2.38 s before leakage/active load; actual discharge and PD timing must be measured.

Added cutoff dissipation, including maximum stated on-current at 15.75 V:

| Through current | Added dissipation using 250 mΩ full-temperature RON maximum |
|---:|---:|
| 1.0 A | 0.256 W |
| 1.5 A | 0.569 W |
| 1.65 A | 0.687 W |

The TI 38.6°C/W test-board figure gives about 22°C rise at 1.5 A; it is not the actual board/enclosure thermal resistance. RTN copper and stitching, separation from battery/temperature sensing, and actual enclosure temperatures must be established. The added nominal courtyard sum is **80.81 mm²**, excluding thermal copper, routing, connector/RF/fixture exclusions and packing inefficiency. No claim is made that the unchanged controller outline accommodates this addition yet.

## Parts and batch cost

The captured USB block consumes about **$7.136** of parts at the recorded small-quantity prices, versus $5.0413 before the change. The increment is **$2.0947 per board**, or $4.1894 for two / $16.7576 for eight before waste and assembly. This is not the amount a small private-stock purchase necessarily costs.

| New SKU | Observed overseas stock / available | Private prebuy minimum | Minimum purchase cost, two-board scenario |
|---|---:|---:|---:|
| TPS26600PWPR C544399 | 5,934 / 5,690 | 6 | $9.2652 |
| TVS1800DRVR C2649846 | 1,977 / 1,876 | 29 | $9.3380 |
| RT0402BRD0730K1L C852714 | 11,764 / 9,815 | 319 | $9.0277 |
| 0402WGF4023TCE C25785 | 66,615 / 59,869 | 5,640 | $9.0240 |

That four-SKU private-stock scenario totals **$36.6549 for two**, or **$39.7433 for eight**, before reused SKUs, assembly, shipping/tax and waste. The precision resistor and 402k list minimum placements of 20, TVS five, TPS zero. All four observations indicate Extended/overseas, not verified in-house Economic-PCBA eligibility. A quote must resolve procurement route and feeder charges; no $3-per-SKU fee is assumed universally. Existing 1.2k and 4.7k stock was refreshed on 2026-10-20: 569,844 and 15,287,641 overseas units respectively; they also have private prebuy/placement rules, but already occur elsewhere in the board. [Machine-readable sourcing and exact URLs](../../bom/electronics-usb-protection-candidate.json).

## Evidence and boundary

- Independent source/BOM/pin partition checks cover the 42-part, 151-pin USB block; ten new deliberate connection faults plus five retained faults are rejected.
- Main integration covers 206 components / 649 pins; independent integration fault tests preserve the other blocks.
- TI primary pin/land transcription is checked against both compiled captures, including mask/paste distinction and a separate RTN thermal pad; five land faults are rejected.
- Native schematic export compares every physical pin and net partition with the compiled PCB. Expected boundary ERC findings remain explicit, without fabricated power flags.
- These captures are unrouted. The maintained physical route pipeline still needs a reviewed graph migration: six old raw terminals must be disconnected from raw, connected to guarded, and all new current/thermal/bypass paths laid out. A post-edit of the final routed PCB is not sufficient.
- No component purchase, fabrication, charging or surge test was performed. Regenerative stuck-on/sustained-back-drive behavior remains an unresolved wall-product architecture issue; an external dump resistor can be prototype instrumentation only.
