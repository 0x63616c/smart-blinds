#!/usr/bin/env bash
# Rebuild the pd12v6 board end-to-end and drop everything a reviewer needs into hw/build/review/.
#   ./scripts/review.sh            # build + layout + DRC + images + STEP
#   ./scripts/review.sh --open     # ...then open the board in KiCad
set -euo pipefail
cd "$(dirname "$0")/.."
KPY=/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KCLI=${KICAD_CLI:-$HOME/.local/bin/kicad-cli}
PCB=layouts/pd12v6/pd12v6.kicad_pcb
OUT=build/review
mkdir -p "$OUT"

echo "== ato build"
uv run ato build -b pd12v6 2>&1 | grep -E "Build (successful|failed)|Error" || true

echo "== layout (place + route + zones)"
"$KPY" scripts/layout_pd12v6.py 2>&1 | grep -v "assert\|leak\|Legacy\|best-effort\|Debug"

echo "== DRC"
"$KCLI" pcb drc --refill-zones --severity-error --severity-warning --format json -o "$OUT/drc.json" "$PCB" >/dev/null
python3 scripts/drc_summary.py "$OUT/drc.json" | tee "$OUT/drc_summary.txt"

echo "== layer images"
"$KCLI" pcb export svg --layers "F.Cu,F.SilkS,F.Mask,Edge.Cuts" --page-size-mode 2 --exclude-drawing-sheet -o "$OUT/top.svg" "$PCB" >/dev/null
"$KCLI" pcb export svg --layers "B.Cu,B.SilkS,B.Mask,Edge.Cuts" --page-size-mode 2 --exclude-drawing-sheet --mirror -o "$OUT/bottom.svg" "$PCB" >/dev/null
rsvg-convert -w 2000 "$OUT/top.svg" -o "$OUT/top.png"
rsvg-convert -w 2000 "$OUT/bottom.svg" -o "$OUT/bottom.png"

echo "== 3D renders"
"$KCLI" pcb render --side top    --quality high --zoom 1.1 -w 1800 -h 1600 -o "$OUT/3d_top.png"    "$PCB" >/dev/null
"$KCLI" pcb render --side bottom --quality high --zoom 1.1 -w 1800 -h 1600 -o "$OUT/3d_bottom.png" "$PCB" >/dev/null
"$KCLI" pcb render --side top --perspective --rotate "-35,0,25" --quality high --zoom 1.0 -w 1800 -h 1400 -o "$OUT/3d_iso.png" "$PCB" >/dev/null

echo "== STEP"
"$KCLI" pcb export step --subst-models --force -o "$OUT/pd12v6.step" "$PCB" >/dev/null 2>&1 || echo "(step export failed)"

echo "review outputs in $OUT:"; ls -1 "$OUT"
if [[ "${1:-}" == "--open" ]]; then open -a KiCad "$PCB"; fi
