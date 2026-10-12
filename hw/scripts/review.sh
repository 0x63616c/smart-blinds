#!/usr/bin/env bash
# Rebuild boards end-to-end and drop everything a reviewer needs into hw/build/review/<board>/.
#   ./scripts/review.sh                     # every board: pd12v6 and pd12v6mini
#   ./scripts/review.sh pd12v6mini          # just one
#   ./scripts/review.sh pd12v6mini --open   # ...then open it in KiCad
# For each board: ato build -> scripted layout (routed + place-only copy) -> DRC -> layer images,
# 3D renders, assembly drawing (reference designators, F.Fab) -> STEP.
set -euo pipefail
cd "$(dirname "$0")/.."
KPY=/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KCLI=${KICAD_CLI:-$HOME/.local/bin/kicad-cli}
FILTER='assert|leak|Legacy|best-effort|Debug|wxApp'

OPEN=0; BOARDS=()
for a in "$@"; do [[ "$a" == "--open" ]] && OPEN=1 || BOARDS+=("$a"); done
[[ ${#BOARDS[@]} -eq 0 ]] && BOARDS=(pd12v6 pd12v6mini)

svg2png() { "$KCLI" pcb export svg --layers "$2" --page-size-mode 2 --exclude-drawing-sheet ${4:-} -o "$3.svg" "$1" >/dev/null
            rsvg-convert -w 2000 "$3.svg" -o "$3.png"; }

for BOARD in "${BOARDS[@]}"; do
  PCB=layouts/$BOARD/$BOARD.kicad_pcb
  MPCB=layouts/${BOARD}_manual/${BOARD}_manual.kicad_pcb
  OUT=build/review/$BOARD
  mkdir -p "$OUT"
  echo "######## $BOARD"

  echo "== ato build"
  uv run ato build -b "$BOARD" 2>&1 | grep -E "Build (successful|failed)|Error" || true

  echo "== layout (routed) + place-only copy"
  "$KPY" "scripts/layout_$BOARD.py" 2>&1 | grep -Ev "$FILTER" || true
  "$KPY" "scripts/layout_$BOARD.py" --place-only 2>&1 | grep -Ev "$FILTER" || true

  echo "== DRC"
  "$KCLI" pcb drc --refill-zones --severity-error --severity-warning --format json -o "$OUT/drc.json" "$PCB" >/dev/null
  python3 scripts/drc_summary.py "$OUT/drc.json" | tee "$OUT/drc_summary.txt"
  "$KCLI" pcb drc --refill-zones --severity-error --severity-warning --format json -o "$OUT/drc_manual.json" "$MPCB" >/dev/null
  echo "(place-only copy)"; python3 scripts/drc_summary.py "$OUT/drc_manual.json" | head -2

  echo "== layer images + assembly drawing"
  svg2png "$PCB" "F.Cu,F.SilkS,F.Mask,Edge.Cuts" "$OUT/top"
  svg2png "$PCB" "B.Cu,B.SilkS,B.Mask,Edge.Cuts" "$OUT/bottom" --mirror
  svg2png "$PCB" "In1.Cu,Edge.Cuts" "$OUT/in1"
  svg2png "$PCB" "In2.Cu,Edge.Cuts" "$OUT/in2"
  svg2png "$PCB" "F.Fab,Edge.Cuts" "$OUT/assembly"
  svg2png "$MPCB" "F.Cu,F.SilkS,F.Mask,Edge.Cuts" "$OUT/manual_top"
  "$KCLI" pcb export pdf --layers "F.Fab,Edge.Cuts" --include-border-title -o "$OUT/assembly.pdf" "$PCB" >/dev/null 2>&1 || true

  echo "== 3D renders"
  "$KCLI" pcb render --side top    --quality high --zoom 1.1 -w 1800 -h 1300 -o "$OUT/3d_top.png"    "$PCB" >/dev/null
  "$KCLI" pcb render --side bottom --quality high --zoom 1.1 -w 1800 -h 1300 -o "$OUT/3d_bottom.png" "$PCB" >/dev/null
  "$KCLI" pcb render --side top --perspective --rotate "-35,0,25" --quality high --zoom 1.0 -w 1800 -h 1400 -o "$OUT/3d_iso.png" "$PCB" >/dev/null

  echo "== STEP"
  "$KCLI" pcb export step --subst-models --force -o "$OUT/$BOARD.step" "$PCB" >/dev/null 2>&1 || echo "(step export failed)"
  rm -f "$OUT"/*.svg
  echo "outputs in $OUT"
done

if [[ $OPEN -eq 1 ]]; then
  for BOARD in "${BOARDS[@]}"; do open -n -a /Applications/KiCad.app/Contents/Applications/pcbnew.app --args "$PWD/layouts/$BOARD/$BOARD.kicad_pcb"; done
fi
