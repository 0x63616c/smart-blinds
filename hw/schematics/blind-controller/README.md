# Native KiCad motor circuit study

Open `motor-test.kicad_pro` in KiCad 10, then its schematic. This is the first viewable
block of the fresh design, not the complete smart-blind controller. The associated
atopile PCB has no placement, routing, outline or manufacturing approval.

Connectivity comes from `hw/layouts/blind-controller/motor-test/motor-test.kicad_pcb`.
The page-layout JSON supplies component positions, readable net names, displayed fixed-part
values and reviewed electrical pin types. It cannot add or omit a physical component or pin.
Imported resistor/capacitor pins are corrected to passive, and the DRV8874 inputs, outputs,
power pins and open-drain fault signal are typed explicitly. Pin names and numbers must agree
with the imported library. The original manufacturer pin functions are in TI SLVSF66A page 3.

Regenerate from the repository root:

```sh
python3 tools/verify_motor_build.py
python3 tools/generate_schematics.py hw/schematics/blind-controller/motor-test.layout.json
python3 tools/generate_schematics.py hw/schematics/blind-controller/motor-test.layout.json --check
python3 -m unittest discover -s tools -p test_schematic_graph.py -v
```

KiCad independently exports the generated schematic to a netlist. All **43 physical pin
connections across 14 components** must match the PCB, including isolation of the deliberately
floating IMODE pin. The checker rejects shorted direction inputs, a missing bulk capacitor
and a PCB connection hidden behind a schematic no-connect mark. Generation uses deterministic
identifiers and records input hashes; a source change during generation aborts publication.

The block currently has **four ERC boundary findings**, not a clean ERC result:

| Finding | Why it remains visible |
|---|---|
| VM power input undriven | External protected supply is not part of this block |
| PGND power input undriven | External supply return is not part of this block |
| MOTOR_A label has one pin | Motor connector/load is not part of this block |
| MOTOR_B label has one pin | Motor connector/load is not part of this block |

The exact finding types and affected items are checked; they are not ERC exclusions. The
complete controller must supply the missing interfaces and pass whole-board review. No power
flag is inserted merely to hide an absent supply. The native regeneration check compares the saved
PCB graph. CI first freshly compiles the motor source with pinned atopile 0.15.9
(Python 3.14), requires a frozen match to that PCB, and checks selected-part ratings
against the resulting BOM. The build records only the motor dependencies, avoiding
a false dependency on unrelated draft power components.

Electrical validation still needs the regeneration clamp, power/MCU integration, thermal copper,
component pulse/temperature qualification, actual motor measurements and prototype tests.
The imported generic footprint and 3D geometry also need package-drawing review before layout.
Keep electrical changes in atopile and drawing changes in the JSON; direct edits to the generated
schematic/library files are overwritten. Do not use this standalone study to update a fabrication PCB.

Sources: [TI DRV8874 datasheet](https://www.ti.com/lit/ds/symlink/drv8874.pdf),
[KiCad schematic format](https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/).
