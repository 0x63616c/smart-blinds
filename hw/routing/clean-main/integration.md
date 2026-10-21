# Source, routing and native validation boundary

The maintained runtime consists of the Python modules in this directory, five
physical/source record files, `native-boundary.json` and 43 content-addressed
model files. Python with Shapely >=2 is sufficient for pure emission and geometry
checks. Native fill, DRC and rendering require isolated Linux KiCad 10 and wxPython.

## Explicit live source

```sh
python3 hw/routing/clean-main/emit.py --source-root . --output work/clean-main-unfilled
python3 hw/routing/clean-main/check.py work/clean-main-unfilled/candidate.kicad_pcb --source-root .
# tools/build_clean_main.py performs native fill/save/DRC plus these checks:
python3 hw/routing/clean-main/check.py work/clean-main-native/candidate.kicad_pcb --source-root . --filled
python3 hw/routing/clean-main/test_faults.py work/clean-main-native/candidate.kicad_pcb --source-root . --output work/clean-main-faults.json
```

Run fresh normal and frozen circuit builds before this sequence. All 54 bound
capture/project/table/land-library hashes must agree with `source-binding.json`.
The emitter does not invoke atopile or treat an old capture as proof of changed
`.ato` source. CI recompiles first; the preview renderer also builds and checks a
fresh filled route before rendering it.

A source change fails closed until the physical records and binding are reviewed
together. Updating only hashes is not sufficient: compare the physical pin/net
graph, manufacturer lands and paste, per-part pose/model/silk, outline/keepouts,
current topology and enclosure interfaces. Keep earlier reports and failed jobs.
An explicitly selected historical `--snapshot` mode exists for archived replay
closures; the snapshot is deliberately absent from this maintained package.
There is no implicit snapshot fallback.

## Ownership

The live capture owns 206 footprints, their UUID/path and pin/net identities,
outline, stackup, setup and eight connector-foot keepouts. The reviewed records
own three protection-part pose changes, per-address sparse silk and model
bindings, two demonstrated all-SMD attribute corrections, and finite copper.
55 deduplicated physical library variants map explicitly to source addresses.

Pad comparison permits layer-set ordering, omitted zero angles/custom-poly width,
explicit disabled unused-layer removal, equivalent closed-ring start/winding and
7-decimal roundrect-ratio serialization. It does not permit changed pad size,
pin/net identity, mask/paste aperture or manufacturer land geometry. Diagnostic
child UUIDs are deterministically namespaced; the mapping is in `emission.json`.
Saved zone fills are never source records: KiCad must create them, then actual
filled-island reachability and return geometry are checked.

`native-boundary.json` retains exactly the named USBC1/U3/U4 hybrid-type findings
and the current 352 unconnected items. A changed count or finding fails review;
no library, clearance or keepout errors are silently accepted. The exact source
project rules are restored after native serialization, with both hashes recorded.

The PCB checker includes current RF/retainer reservations. The complete enclosure
service paths, wire bends and physical strength/temperature/RF tests require
separate mechanical and prototype evidence. Green geometry checks do not finish
the remaining circuit connections or qualify 1.5 A charging.
