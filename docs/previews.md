# Source-generated previews

`docs/previews.json` registers each design's source, title and status. `tools/render_previews.py`
reads those sources and refreshes the README gallery and `docs/generated/`. It does not run the
legacy layout generators or silently modify the PCB. Missing models cause a failure, rather than
an apparently complete board image with absent components.

Supported entries are `pcb` (KiCad 3D PNG and top-layer SVG), `schematic` (all KiCad SVG sheets),
and `openscad` (rendered source PNG, with optional `defines` and dependency globs). Register new
schematics and CAD only when their real source files exist. Enclosure previews must identify
provisional purchased-part envelopes and distinguish a study from a released printable assembly.

## Local generation

Install KiCad 10 and its 3D libraries, Python 3.11+, and OpenSCAD for mechanical sources.
The renderer locates the usual macOS/Linux KiCad library; set `KICAD10_3DMODEL_DIR` for other paths.

```sh
python3 tools/render_previews.py
```

On a headless Linux machine, run under `xvfb-run -a`. Generated metadata records the source commit,
source hashes, local source dirty state, model hashes and tool versions. A local modified design
is identified as dirty; its source hash still identifies exactly what was rendered. A generated
commit's parent is the source commit, so its image metadata intentionally points to that parent.

## CI and release meaning

Pull requests generate downloadable artifacts without publishing to the branch. On `main`, a
separate publishing job with write permission commits only the README gallery and generated
assets, provided the branch still points to the source revision. Concurrent newer edits prevent
publishing stale previews. Generated-only commits do not retrigger this workflow.

A passing preview workflow confirms export/render success. It does not run the full electrical,
firmware, mechanical or physical validation gates. The first gallery contains only the inherited
PD12V6Mini reference; fresh controller and enclosure sources are under development.
