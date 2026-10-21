# Integrated controller schematic

Open `smart-blinds-main.kicad_sch` in KiCad 10. The index opens ten circuit sheets:
USB-C input, charger, logic supply, motor bridge, supervision, regenerative clamp,
radio/USB data, encoder input, buttons/home input, and final power/permission interfaces.
The preview workflow publishes all sheets as SVG and one eleven-page PDF.

This is the **complete captured main-controller circuit**, including 204 purchased parts
and two motor-wire solder landings. Its circuit capture is unrouted and unpowered; the separate partial routed
derivative requires explicit migration for this revision. The battery
carriers are separate boards and are not implicitly included in this schematic.

## Connectivity evidence

`tools/generate_main_schematic.py` maps preserved block drawings by component address,
uses current PCB reference numbers and adds explicitly reviewed controller/interface pages.
The layout file owns drawing positions, readable net names and reviewed symbol pin types;
the compiled PCB owns connectivity. Six existing block layouts are reused as drawing inputs,
not as a second wiring source. Only cross-sheet nets use global labels.

KiCad independently exports the full hierarchy. Verification compares all 206 circuit
features, **649 unique physical pin identities**, and all 151 net partitions with the PCB.
Repeated thermal-pad numbers represent a single logical pin identity. It rejects missing,
duplicate, split or merged nets, even if split nets retain the same visible label.
The separate main-board integration contract is also rerun against eight preserved blocks
and explicit physical-pin boundary joins. Neither check alone proves electrical operation.

Nine tests include deliberate broken pins, duplicate parts/pins, a whole I2C-net short,
a cross-sheet supply break, a wrong motor net label and a connected reserved home pin.
All source files and libraries used by generation are hashed; changed inputs abort publication.
The build checks the committed files byte for byte after recreating and exporting them.

## Seven explicit ERC findings

No exclusions or artificial power flags hide these findings. Their exact type, affected
symbol pins and sheet paths are recorded in `main.layout.json` and verified after export.

| Finding | Reason / outstanding qualification |
|---|---|
| Five power inputs not driven | External PACK, ground and USB supplies have no schematic power-source component. PD VDD passes through passive isolation; the 3V3 regulator output passes through an inductor. ERC does not infer drive through those passive parts. |
| BQ25798 ACDRV1/ACDRV2 output conflict | Both are grounded for the documented topology without external ACFETs; generic output types retain the conflict. The charger block records the manufacturer rationale. |
| Isolated charger STAT label | The output is named but unconnected; charger status is read over I2C. The same pin is isolated in the PCB. |

C6 unconnected IO4/IO5/IO15, module NC, regulator NC and the reserved home contact are
explicit no-connects and must remain isolated in both representations. Encoder and home
ESD NC terminals are groundable in the reviewed TI package; their physical pin numbers
remain visible. All connector numbers are shown for wiring review.

## Reproduce

```sh
python3 tools/generate_main_schematic.py
python3 tools/generate_main_schematic.py --check
python3 -m unittest discover -s tools -p test_main_schematic.py -v
kicad-cli sch export pdf -o controller.pdf hw/schematics/blind-main/smart-blinds-main.kicad_sch
```

The new page pin maps follow the local ESP32-C6 module, TPS70950, SN74LVC2G17,
SN74AUP1G97 and TPD2E2U06 manufacturer evidence already used by the captured blocks.
The side-switch terminal-pairing and purchased motor encoder pinout still require sample
checks. Simulation, ERC and netlist agreement do not substitute for those checks.

The monitored-PD revision powers ST VSYS from 3.3 V, joins its SDA/SCL to the owned
bus, and shares GPIO17 ALERT/INT with one explicit 10 kΩ pull-up. Factory access
requires reset/inhibit; actual shared service pads and physical qualification
remain pending. No schematic-only test authorizes charge enable.

The input-protection revision adds ten parts ahead of the guarded PD/charger path. TPS26600 OUT15 is typed power-out and OUT16 passive because both leads are one internal output; its RTN reference remains separate from GND. The exact external USB power ERC finding moves to the upstream cutoff. The new USB sheet uses A2 to preserve readable spacing. Placement/routing and transient/thermal qualification remain pending.
