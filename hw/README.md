# Hardware

**Inherited references:** PD12V6 and PD12V6Mini are USB-C power supplies. They are not complete
battery chargers or the new integrated smart-blind controller. See [the current brief](../docs/brief.md).

atopile project. One build target per board in `ato.yaml`.

- `boards/` — one `.ato` per board, each with an `App` module
- `parts/` — local part definitions (fetched with `scripts/fetch_part.py Cxxxx`, no atopile login)
- `layouts/<board>/` — KiCad layout for each board (committed)
- `layouts/<board>_manual/` — same placement, no tracks: the copy to route by hand (atopile allows one layout per folder)
- `scripts/` — placement/routing scripts and the review pipeline
- `datasheets/` — PDFs + text extracts used while designing
- `build/` — generated outputs (ignored)

## Workflow

```
uv run ato build -b pd12v6      # compile .ato -> netlist/BOM, sync layout
./scripts/review.sh             # build + place/route + DRC + images + STEP into build/review/
./scripts/review.sh --open      # ...and open the board in KiCad
```

Each board's layout is fully scripted (`scripts/layout_<board>.py` places, `routes_<board>.py` routes,
shared plumbing in `scripts/pcbkit.py`) and
idempotent: rerunning regenerates the same board, so edit the scripts rather than the .kicad_pcb.
`layout_<board>.py --place-only` writes the hand-route copy (`layouts/<board>_manual/`); it keeps
placement, zones, outline and silk and drops every track and via. The review script runs both.
Scripts run under KiCad's bundled Python (KiCad 10). Design notes: `../docs/pd12v6/design.md`, `../docs/pd12v6/mini.md`.
