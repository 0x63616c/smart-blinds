# Monitored USB-PD circuit revision

2026-10-20. **Circuit and schematic candidate; not a charging or fabrication release.**

The STUSB4500 is supplied directly from the existing always-on 3.3 V rail through
VSYS pin 22. Its raw-VBUS VDD diode, internal regulator bypasses, both dead-battery
CC connections and autonomous VBUS_EN_SNK/eFuse gate remain unchanged. The new
1 µF CL10A105KB8NNNC bypass uses an existing part SKU. No additional active IC is
introduced. Direct dual supply follows ST's supported architecture; it does not
establish a zero reverse-current path during rail collapse or USB-only startup.

ST SDA/SCL now join the single firmware-owned bus shared with the charger and
protected pack. The two 100 kΩ factory pull-downs are removed. The existing 4.7 kΩ
host pull-ups remain the only captured bus pull-ups. The 7-bit addresses are
ST 0x28, BQ 0x6B, MAX normal 0x36 and MAX shadow 0x0B. Service equipment must not
become a second concurrent bus owner or back-power an unpowered rail.

ST ALERT and BQ INT now share MCU GPIO17 (module pin 24). The earlier circuit had
no pull-up on that net; this revision adds an explicit 10 kΩ C25744 resistor to
3.3 V. Firmware must examine both devices through the same owner when the shared
line asserts. The line does not identify the source, and read-clear histories
must not be consumed by an independent task. Actual charging remains disabled
until the separately reviewed policy, factory identity, source lifecycle,
pack, temperature and readback conditions are implemented and qualified.

## Circuit evidence and limits

The main capture remains 196 footprints / 609 unique physical pins, including
two non-purchased solder landings. The standalone USB block changes from
33 / 113 to 32 / 111. The exact purchased-part delta is two fewer C25741
100 kΩ resistors, one additional C15849 1 µF capacitor and one additional
C25744 10 kΩ resistor; all three SKUs already occur elsewhere in the system.
There is no new feeder SKU. This is a component-demand delta, not an updated
assembly quote.

The native main hierarchy exports the same full pin partition and retains the
same seven explicit ERC findings: five external/undriven supply nets, the
BQ datasheet-required ACDRV-to-ground output-type conflict, and its unused STAT
label. The standalone USB sheet has eight explicit external-power/bus/alert
findings. Neither uses artificial power flags or ERC exclusions to conceal them.
The source and pin contracts, 23 integrated fault controls, five standalone USB
fault controls and nine native schematic fault controls are separate checks.

`hw/boards/blind-main/shared-power-bus.json` records the conditions for the
fixed-point calculations. With the 3.234–3.366 V rail and the resistor tolerance
and temperature allowance, interrupt sink current is at most 343 µA and the
stated maximum VOL gives 0.4085 V margin to the MCU input-low limit. A high state
has a total sink-leakage budget of 79.46 µA. A proposed 10 µA total leakage
qualification allowance leaves 0.707 V margin; **that allowance is not a
guaranteed combined part maximum**. ST does not specify an ALERT leakage bound,
BQ's listed INT leakage condition is 1.8 V, and the MCU table is at 3.3 V/25 °C.

The shared I2C maximum-table calculation has a more important limitation:
ST's VIL limit is 0.35 V, while the cited SDA VOL maxima are 0.4 V. It therefore
has a negative 0.05 V table margin. Lower actual sink current may produce a lower
VOL, but this must be measured across supply, temperature, all bus participants,
pack 150 Ω resistors and the actual cable. The change does not claim a guaranteed
low-level, rise-time, powered-off or hot-insertion interface from those tables.

ST lists 140 µA typical / 165 µA maximum VSYS idle current at 3.3 V under the
specified disconnected/no-communication 25 °C condition. At an assumed 85%
conversion efficiency this is 0.783–0.922 Wh over 60 days. It is part of total
whole-pack standby, not an extra term to add again to a measured total standby
current. Activity and whole-temperature current remain unmeasured.

The selected VSYS bypass has a conservative *planning estimate* of 0.451 µF using
Samsung's typical 5 V curve (above the intended rail), then tolerance, temperature
and aging allowances. That is not a production minimum. The earlier 9.741 µF
raw-local capacitance subtotal excludes this host capacitor and the wider host
rail; unspecified internal reverse feed prevents using it as a whole-system
USB inrush bound. Verify USB-only/dead-pack boot, rail collapse, reconnect,
reverse leakage, reset behavior and startup before enabling charge.

## Physical migration boundary

The maintained pipeline now rebuilds from the revised capture. `usb_input.py`
uses PD pin25 as ground and removes the old pin22-to-exposed-pad branch;
`usb-control-routes.json` removes the two obsolete pull-down branches. The
corresponding pin and via inventories are updated explicitly. Exact circuit,
footprint, keepout and connected-copper comparisons remain enabled.

Relative to the prior1022-segment/257-via checkpoint, exactly nine segments and
two vias are removed. All1268 surviving copper items keep their geometry, and
all194 common footprints keep their placement and pad geometry. The result has
1013 segments,255 vias and122 unconnected items. All47 existing fault controls
pass, including the previous quiet-return, USB, clamp and supervision checks.
Native DRC has no accepted copper, courtyard, hole, mask-bridge or keepout
failure;258 silk/text, four library and five type findings remain.

This migration adds no routed branch. The new VSYS bypass and interrupt pull-up
are space allocations; the long owned bus, ALERT and factory targets remain
physical routing work. In the derivative the capacitor is atUV(44,8.25), its
centre6.08mm fromVSYS; that does not establish adequate local decoupling.
The unrouted capture stages it atUV(38,3) and the pull-up at(46.905,17.47), both
with checked assembly clearances. Routing deliberately relocates those two new
parts to its separate staging plan. Existing capture placements are preserved.
Four empty KiCad Datasheet/Description fields were added explicitly for the two
new parts; strict property/graph comparisons were not weakened. Normal and
frozen main builds and native schematic checks pass after that normalization.

## Proposed factory fixture contract — pads not captured yet

Factory programming is performed on a detached controller, with battery pack,
motor and encoder disconnected. The fixture holds MCU EN low, holds the charger
permission inactive and its CE-drive MOSFET gate low, and clamps eFuse UVLO low
so unknown PD NVM cannot energize the downstream charger. The fixture supplies
current-limited 3.3 V directly to the host rail; it must not also attach another
3.3 V source. Raw USB may supply ST VDD after these hardware inhibits are present.
No fixture pull-up may drive the bus above the host rail or while that rail is off.
ST RESET is active high and has the existing 10 kΩ pull-down; allow at least the
documented NVM-load interval after a valid reset/power transition before reads.

The following proposed exposed B.Cu targets use no purchased components. Their
exact coordinates and clearance screen are in the separate fixture-pad plan.
They are **not present in the schematic or PCB** yet. A connected pad should be
an explicit electrical feature excluded from BOM and placement files, not a
`board_only` mechanical feature that disappears from the pin graph.

| Target | Physical endpoint | Fixture behavior |
|---|---|---|
| GND | ST pin10 / common ground | First-contact reference |
| 3V3 | ST pin22 / MCU pin2 | Current-limited fixture supply and readback |
| MCU_EN | MCU pin3 | Open-drain hold low before bus access |
| PD_RESET | ST pin6 | Controlled high reset; release to existing pull-down |
| SDA | ST pin8 | Single owned open-drain service bus |
| SCL | ST pin7 | Single owned open-drain service bus |
| CHARGE_ALLOW_N | MCU GPIO22 | Hold inactive high while MCU reset |
| CE_GATE | AO3400A charger.q_charge gate | Independent low clamp; do not fight an active PNP drive |
| CE_N | BQ pin13 | High-impedance observation, rated for REGN-level voltage |
| EFUSE_UVLO | TPS259470 pin1 | Low clamp during NVM programming |
| BOOT_N | MCU GPIO9 | Optional low for controlled USB/ROM recovery |

An absent REGN supply makes a low CE_N reading unsurprising; it does not mean
charging is enabled. CE readback needs a separately controlled powered test with
a battery emulator/current-limited source, before connecting real cells. The
fixture must verify the inactive permission and low gate before that phase.
Do not force CE high against its drain transistor. A fixture fault or simultaneous
bus master is not covered by the circuit calculation.


Proposed local target centres (u, v), millimetres, are:

| Target | u | v |
|---|---:|---:|
| GND | 46.0 | 8.0 |
| 3V3 | 34.0 | 14.0 |
| MCU_EN | 6.0 | 50.0 |
| PD_RESET | 44.0 | 4.0 |
| SDA | 44.0 | 14.0 |
| SCL | 46.0 | 4.0 |
| CHARGE_ALLOW_N | 22.0 | 50.0 |
| CE_GATE | 22.0 | 16.0 |
| CE_N | 30.0 | 28.0 |
| EFUSE_UVLO | 24.0 | 8.0 |
| BOOT_N | 26.0 | 50.0 |

The screen uses 1.2 mm round B.Cu copper, 1.4 mm mask openings and at least
0.25 mm clearance to existing back-layer copper. It also excludes all current
rule areas. Targets are scattered near their endpoints rather than presented as
a proven single connector grid; the MCU EN target needs about 15 mm of onward
routing to remain outside the RF reservation. See
`monitored-pd-fixture-plan.json` for exact endpoints and the board hash.

The pin grid, pogo travel, locating features, front-side support, fixture wiring,
and assembly/test sequence still need a physical design. Proposed backside
clearance is assessed on the detached board; it grants no access through the
installed enclosure. Test targets must preserve antenna, mechanical and solder
clearances and the same-net via-to-solder-land guard.

## Primary sources

- [STUSB4500 DS12499 Rev8](https://www.st.com/resource/en/datasheet/stusb4500.pdf):
  pin table, VSYS §2.2.14, operating limits and Table22. Current web PDF checked;
  the older locally cached Rev7 is not represented as Rev8.
- [ST software guide UM2650 Rev2](https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/Doc/User_manuals/um2650-the-stusb4500-software-programing-guide-stmicroelectronics_v2.pdf):
  reset/startup, status ownership and policy readback.
- [TI BQ25798 SLUSDV2C](https://www.ti.com/lit/ds/symlink/bq25798.pdf):
  INT pin21, CE pin13, digital electrical characteristics and charge control.
- [ESP32-C6-WROOM-1 v1.4](https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf):
  module pin mapping and Table6-3 input conditions.
- Samsung's exact CL10A105KB8NNNC curve extraction is retained in
  `hw/sim/blind-usb/capacitor-bias.json`; the curve is typical, not a minimum.
