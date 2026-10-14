#!/usr/bin/env bash
# JLCPCB upload files for a board, plotted from the fill stored in the board file (no refill:
# the stored fill is what the factory gets, see pcbkit.save_filled).
#   ./scripts/fab_export.sh pd12v6mini
# Writes hw/build/fab/<board>/:
#   <board>_gerbers.zip  copper (4 layers), paste, silk, mask, outline, PTH + NPTH drills
#   bom_jlc.csv          Comment, Designator, Footprint, JLCPCB Part #  (from the ato build BOM)
#   cpl_jlc.csv          Designator, Mid X, Mid Y, Layer, Rotation      (KiCad position file)
# Run after ./scripts/review.sh <board> so the build BOM and layout are current.
set -euo pipefail
cd "$(dirname "$0")/.."
KCLI=${KICAD_CLI:-$HOME/.local/bin/kicad-cli}
FILTER='Legacy|best-effort'
BOARD=${1:?board name, e.g. pd12v6mini}
PCB=layouts/$BOARD/$BOARD.kicad_pcb
OUT=build/fab/$BOARD
rm -rf "$OUT"; mkdir -p "$OUT/gerbers"

"$KCLI" pcb export gerbers -o "$OUT/gerbers" --subtract-soldermask \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts "$PCB" 2>&1 | grep -vE "$FILTER" || true
"$KCLI" pcb export drill -o "$OUT/gerbers/" --format excellon --excellon-separate-th "$PCB" 2>&1 | grep -vE "$FILTER" || true
"$KCLI" pcb export pos -o "$OUT/pos.csv" --format csv --units mm --side both "$PCB" 2>&1 | grep -vE "$FILTER" || true
(cd "$OUT/gerbers" && zip -q "../${BOARD}_gerbers.zip" *)

python3 - "$OUT" "build/builds/$BOARD/$BOARD.bom.csv" <<'EOF'
import csv, sys
out, bom = sys.argv[1:]
rows = list(csv.DictReader(open(bom)))
with open(f"{out}/bom_jlc.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "JLCPCB Part #"])
    for r in rows:
        w.writerow([r["Partnumber"], r["Designator"], r["Footprint"].split(":")[1], r["LCSC Part #"]])
pos = list(csv.DictReader(open(f"{out}/pos.csv")))
with open(f"{out}/cpl_jlc.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for p in pos:
        w.writerow([p["Ref"], p["PosX"] + "mm", p["PosY"] + "mm", p["Side"].capitalize(), f"{float(p['Rot']) % 360:g}"])
bom_refs = {d.strip() for r in rows for d in r["Designator"].split(",")}
cpl_refs = {p["Ref"] for p in pos}
assert bom_refs == cpl_refs, f"BOM and placement disagree: {bom_refs ^ cpl_refs}"
print(f"{len(rows)} BOM lines, {len(cpl_refs)} placed parts")
EOF
ls "$OUT"
