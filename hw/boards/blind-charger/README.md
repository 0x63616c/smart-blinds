# Charger circuit capture

This is an original 35-component BQ25798 charger/power-path subcircuit. It is a
reviewable intermediate, not a complete charger product or a fabrication release.
The generated PCB has no final outline, placement or routing. Native schematic
export is maintained separately by the project integrator.

## Interfaces and operating policy

- `source`: 5–20 V from a protected USB-PD input stage; never connect this directly
  to an unqualified USB connector. Input switching, inrush and contract-loss
  handling remain separate work.
- `battery`: protected 3S PACK, 9–12.6 V operating envelope. The motor also uses
  PACK, not SYS, so motor current/regeneration does not traverse the charger BATFET.
- `system`: electronics supply, provisionally 8.8–13.2 V. TI specifies up to
  13.04 V at the 12.6 V 3S test point with charging disabled. Battery-only path
  drop, switching ripple and transients still require qualification.
- `logic`: externally supplied 3.3 V. `allow_charge_n` is active LOW: a pulled-up
  request turns the PNP off, the NFET gate is pulled down, and CE is pulled to
  REGN. No 3.3 V supply also leaves the NFET off. This agrees with GPIO22's reset
  pull-up. Full-temperature leakage and supply-ramp behavior need bench testing.
- `sda/scl`: 0x6B, with external pull-ups. `irq_n/status_n` are open-drain outputs.
  The fixed address differs from MAX17320 0x36/0x0B and HUSB238 0x08.
- `ntc/ntc_return`: dedicated two-wire Semitec 103AT-2 10 kΩ thermistor. This must
  be thermally coupled to the cells. The gauge needs independent sensors.

PROG selects 3S/750 kHz. Initial charge current is 1 A. A proposed 12.45 V charge
setpoint leaves voltage-error margin relative to 12.6 V, but applying TI's 12.6 V
accuracy test point to 12.45 V is only a planning assumption. Pack-level voltage
cannot replace individual-cell overvoltage protection.

The host must configure and read back cell count, charge voltage/current, source
current/voltage limits, JEITA suspend settings and all relevant fault state before
asserting permission. Disable automatic D+/D− detection/HVDCP; native USB data
belongs to the MCU. Disable backup/OTG and other unused modes. Do not charge while
moving. A bus fault or USB contract reset must not preserve old charging permission
or a stale high input-current entitlement; hardware integration for this remains open.

## Temperature findings

The 5.23 kΩ / 30.1 kΩ network is TI's nominal thermistor network. Its default hard
hot threshold is about **60°C**, not 45°C. The default cold threshold can be below
0°C once tolerances are included. The proposed host policy suspends charging below
10°C and at the configurable 40°C warm threshold, with independent MAX17320
hardware charge-temperature cutoffs. The complete protector configuration is not
implemented yet.

Open NTC produces a ratio above the cold threshold; shorted NTC produces a ratio
below the hot threshold. Nominal-table calculations do not cover sensor tolerance,
cell-to-sensor gradients, thermal lag or assembly mistakes.

## Review record

The repository hardware-review checklist was applied in four separate passes;
no spare agent slot or LSP service was available. The parent performs an additional
independent review/native schematic export.

| Pass | Evidence and findings |
|---|---|
| Connectivity | Checked all 29 BQ pads against TI SLUSDV2C pin table. Both VBUS and BAT pads are connected; pad 29 is **PMID, not ground**. ACDRV1/2 ground and VAC1/2 to VBUS match the no-external-ACFET instructions. QON and D+/D− are intentional NC. PNP pins are B1/E2/C3; AO3400A G1/S2/D3. |
| Datasheet | 13.7 kΩ selects 3S/750 kHz; 2.2 µH inductor, two 47 nF bootstrap caps, 4.7 µF REGN and 1 nF SDRV follow TI guidance. Bulk ceramic counts follow the application circuit; effective biased capacitance remains unverified. |
| Ratings | Source/MPN/BOM-bound calculation checks cover divider corners, resistor dissipation, voltage ratings and a 4.39 A planning inductor-peak bound. They do not model the BQ control loop. The 100 Ω BATP resistor is a sense filter; its input leakage is not specified as a maximum, so no fabricated worst-case dissipation claim is made. |
| Integration | Fresh build succeeds. No fabrication routing, DRC, native ERC, thermal proof or real charging test has been completed for this block. REGN capacitor uses active-production CL21A475KAQNNNE, 4.7 µF/25 V/0805, after replacing an NRND candidate. |

The regulator input estimate is a planning envelope, not permission for a full
3 A continuous input at every voltage/ambient. Inductor saturation is specified
at 30% inductance drop; its 7 A rating corresponds to 40°C rise in the manufacturer's
fixture. Neither guarantees board or enclosure temperature.

## Reproduce

Run `ato build -v` from this directory with atopile **0.15.9**, then run
`python3 hw/sim/blind-charge/checks.py` from the repository root. Add `--write` to
refresh its tracked result. The checker fails on changed physical parts, rail
expressions or a mismatched generated BOM. No online part picking is required.

The Ato source uses imported fixed-part wrappers. Their electrical ratings are
recorded in `charger-ratings.json` and checked externally because these wrappers
do not expose rated parameters to the Ato solver. A successful build by itself
does not prove those ratings or the circuit's safe operation.

## Primary sources

- [TI BQ25798 SLUSDV2C](https://www.ti.com/lit/ds/symlink/bq25798.pdf): pins pp4–6,
  regulation pp10–11, REGN/logic p19, PROG table and startup pp28–31,
  application-component selection pp133–135.
- [Semitec AT thermistors](https://www.semitec-global.com/uploads/2022/01/P12-13-AT-Thermistor.pdf).
- [AO3400A](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf)
  and [onsemi MMBT3906](https://www.onsemi.com/pdf/datasheet/mmbt3906lt1-d.pdf).
- [SHOUHAN CYA0630 manufacturer drawing](https://atta.szlcsc.com/upload/public/pdf/source/20250922/76986EE95556632A8212F631091E723A.pdf).
- [Samsung 10 µF/50 V](https://product.samsungsem.com/mlcc/CL31A106KBHNNN.do),
  [REGN capacitor lifecycle](https://product.samsungsem.com/mlcc/CL21A475KAQNNN.do),
  [Yageo 13.7 kΩ specification](https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-0713K7L).
