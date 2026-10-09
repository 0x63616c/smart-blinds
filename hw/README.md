# hw

atopile project. One build target per board in `ato.yaml`.

- `boards/` — one `.ato` per board, each with an `App` module
- `parts/` — local part definitions (fetched with `scripts/fetch_part.py Cxxxx`, no atopile login)
- `layouts/<board>/` — KiCad layout for each board (committed)
- `scripts/` — placement/routing scripts and the review pipeline
- `datasheets/` — PDFs + text extracts used while designing
- `build/` — generated outputs (ignored)

## Workflow

```
uv run ato build -b pd12v6      # compile .ato -> netlist/BOM, sync layout
./scripts/review.sh             # build + place/route + DRC + images + STEP into build/review/
./scripts/review.sh --open      # ...and open the board in KiCad
```

The layout is fully scripted (`scripts/layout_pd12v6.py` + `routes_pd12v6.py`) and idempotent:
rerunning regenerates the same board, so edit the script rather than the .kicad_pcb.
Scripts run under KiCad's bundled Python (KiCad 10). Design notes: `../docs/pd12v6/design.md`.
