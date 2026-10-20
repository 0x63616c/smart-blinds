# Source-generated previews

`docs/previews.json` registers each design's source, title and status. `tools/render_previews.py`
reads those sources and refreshes the README gallery and `docs/generated/`. It does not run the
legacy layout generators or silently modify the PCB. Missing models cause a failure, rather than
an apparently complete board image with absent components.

Supported entries are `pcb` (KiCad 3D PNG and top-layer SVG), `schematic` (all KiCad SVG sheets),
`footprints` / `holder-footprints` (the CAD comparisons at a common scale), `energy`
(fresh planning arithmetic as PNG/SVG/JSON), and `openscad` (colored source-preview PNG, with optional `defines`, seven-value OpenSCAD `camera`, and dependency globs). Register new
schematics and CAD only when their real source files exist. Enclosure previews must identify
provisional purchased-part envelopes and distinguish a study from a released printable assembly.

## Local generation

Install KiCad 10 and its 3D libraries, Python 3.11+ with Matplotlib, and OpenSCAD for mechanical sources.
The renderer locates the usual macOS/Linux KiCad library; set `KICAD10_3DMODEL_DIR` for other paths.

```sh
python3 tools/render_previews.py
```

On a headless Linux machine, run under `xvfb-run -a`. Generated metadata records the source commit,
source hashes, local source dirty state, model hashes and tool versions. A local modified design
is identified as dirty; its source hash still identifies exactly what was rendered. A generated
commit may follow unrelated edits, so image metadata identifies the actual render source commit.
Generation refuses to publish if registered sources or PCB models change during rendering.
Optional `collapsed: true` entries remain available under expandable README details, keeping
alternate internal layouts and inherited references below the primary product views.

## CI and release meaning

Pull requests generate downloadable artifacts without publishing to the branch. On `main`, a
separate publishing job with write permission commits only the README gallery and generated
assets, provided the registered design inputs still match the render source revision.
Unrelated commits preserve the current README prose. If another commit lands during the push,
publication fetches the new branch and rechecks inputs in a disposable worktree before trying
again, with at most three attempts. Changed design inputs defer publication to their newer run;
other push failures are not treated as concurrent edits. Generated-only commits do not retrigger
this workflow. Local-repository tests exercise actual rejected pushes and concurrent updates.

A passing preview workflow confirms export/render success. It does not run the full electrical,
firmware, mechanical or physical validation gates. The gallery includes provisional enclosure studies and the inherited PD12V6Mini reference.
OpenSCAD images use its colored preview renderer; full part geometry/mesh checks are separate.
PCB renders explicitly pass KiCad's `--use-board-stackup-colors` flag, so saved
black solder-mask and white silkscreen choices appear in the gallery. On the
verified KiCad 10 build, omitting this flag renders the green preset despite the
help text describing a true default. Passing an explicit `true` value throws a
CLI type error; use the bare flag. This changes rendering, not fabrication orders.
The fresh integrated controller is under development.

The first native motor schematic is generated separately with
`python3 tools/generate_schematics.py hw/schematics/blind-controller/motor-test.layout.json`.
Its independently exported KiCad netlist must match every PCB pad, and ERC must match the
explicit open-block findings. CI rejects a stale drawing or changed connection. The recorded
ERC boundary findings are not exclusions and do not count as a clean whole-board ERC result.

OpenSCAD entries can set `render_mode` to `render` for exact intersection geometry and correct section-view bounds; the default `preview` is faster for full assemblies.
