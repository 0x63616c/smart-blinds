# Current 54 × 80 mm controller route

This is the maintained **206-part / 649-pin partial route**. It starts from the
current unrouted circuit capture and applies reviewed per-part physical records,
516 segments, 120 vias and six unfilled copper-zone definitions. It does not read
a previously completed PCB or import the historical experimental route chain.

**352 connections and three named hybrid-footprint type findings remain.** This
is not a fabrication release. Current, thermal, surge, RF, USB signal integrity
and physical motor/holder/assembly qualification remain unfinished.

## Build

Run the current source normal/frozen builds first. From the repository root:

```sh
ato build hw/boards/blind-main -b main-test -v
ato build hw/boards/blind-main -b main-test --frozen -v
# Linux CI, with KiCad 10, wxPython, Shapely >=2 and Xvfb installed:
xvfb-run -a /usr/bin/python3 tools/build_clean_main.py --output work/clean-main-native --faults
# On macOS use the isolated runner instead of the command above:
tools/kicad-run --timeout 900 -- python3 tools/build_clean_main.py --output work/clean-main-native --faults
```

Use a new output directory for each attempt. Open the resulting
`candidate.kicad_pro` in KiCad. The output includes its footprint library, all
models, the filled PCB, original unfilled emission, native DRC, physical-check
receipt and fault-test results. No canonical circuit capture is overwritten.
To include the linked native schematic, make a separate review package:

```sh
tools/kicad-run --timeout 600 -- python3 tools/package_clean_main.py --source work/clean-main-native --output work/clean-main-linked --render
```

Open `work/clean-main-linked/smart-blinds-main.kicad_pro`. The packager verifies
native schematic parity and proves its metadata-only transformation preserves
all board and schematic geometry. For pure emission/checking and source updates,
see [integration](integration.md).

## What the checks establish

The saved-board checks cover the circuit graph, all physical lands/paste,
placement, model content/transform, 47 routed endpoint groups, every required
conductor's reachability, finite own-terminal entries, drill/land clearance,
CC-protection cutsets, actual filled-island connections, quiet-star topology,
reference copper, RF exclusions and retainer reservations. All 55 exported
physical library variants must load in KiCad; there is no library-error waiver.
The three retained type findings are bound to specific footprint UUIDs.

The source-driven migration passed 28 deliberate fault controls and an
independent saved-board review. Physical disconnection tests disable exact copper
inventory equality so a missing-record check cannot stand in for reachability.
The workflow preserves the exact reviewed project rules after native save.

The protection return contains 89.0973 mm² of actual B.Cu fill and 74.4352 mm² of
In2.Cu fill, joined by seven reviewed thermal-wing vias. The measured interior
return corridor is approximately 0.31592 mm wide after subtracting drill voids
and trimming terminal annuli. These are geometric results, not current ratings.
Nominal minimums equal the reviewed rules: 0.15 mm foreign copper, 0.20 mm
via-drill to SMD land, and 0.25 mm hole-to-hole. Manufacturing tolerance has not
been qualified.

The [review record](../../../docs/reviews/2026-10-21-clean-layout/source-driven-route.md)
documents the source/land reconciliation and diagnosed library-format failure.
The smaller [196-part route](../blind-main/) is historical and does not validate
this controller.
