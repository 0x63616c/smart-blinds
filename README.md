# e8s

Hardware project: battery packs built from Samsung 50E 21700 cells (8 × 3S2P), the boards that feed and charge them, and the parts that hold them.

| Dir | What |
|---|---|
| `hw/` | atopile project. One build target per PCB. See `hw/README.md`. |
| `cad/` | 3D-printed parts, one folder per object. |
| `docs/` | Design notes, trade studies, exported schematics. |

## Boards

| Board | What | Notes |
|---|---|---|
| `pd12v6` | USB-C PD (20 V) → 12.6 V / 5 A, Micro-Fit 3.0 out (12.6 V, GND, D+, D−), 4-layer | `docs/pd12v6/design.md` |
| `pd12v6mini` | Same circuit job in 47.5 × 25 mm: TPS56637, 0402, ENIG, grouped INPUT / BUCK / PD / OUTPUT cells | `docs/pd12v6/mini.md` |

## Setup

```
uv sync                       # installs atopile
uv run ato build -b pd12v6
hw/scripts/review.sh --open     # every board: regen + DRC + renders, then open in KiCad
```

KiCad 10 is used for viewing layouts; `kicad-cli` is symlinked into `~/.local/bin`.
