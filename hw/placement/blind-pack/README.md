# Retained battery-carrier placement study

**Unrouted and unqualified.** The two 86 × 104 × 1.6 mm boards now have an
explicit placement that follows the retained cassette's support lands, corner
holes, holder positions, raw-wire channels and antenna exclusion. The primary
has 50 electrical footprints; the companion has 10. Each also has four
board-only, non-plated M3 clearance holes excluded from the purchase and
placement lists.

All purchased parts face outward from the cassette's central insulating
barrier. The companion's component view is mirrored horizontally relative to
the primary: compare them using the shared assembly coordinates in
`placement.json`, rather than assuming the same left-to-right KiCad view.
Holder positive terminals face the lower end, beside their individual branch
fuses. No component or ordinary wiring is allocated in the 5 mm central gap;
terminal and solder protrusion must stay within 1.5 mm on each board.

The protection IC, FET pair, shunt, balancing parts and fuses occupy the primary
lower end strip. Signal-entry clamps and retained wire landings occupy its
upper end. This placement is a starting point for routing. In particular, the
shunt-to-gauge Kelvin pair, cell-sense filters, FET gate paths and current-path
copper still need a routing review. All 50 primary and 10 companion electrical
footprints have courtyards enclosing their actual pads. The 30 primary and
three companion instances covered by the shared envelope manifest also match
its reviewed maximum body/lead dimensions and pad extents, with a 0.25 mm
clearance margin. The AON7400A molding allowance remains conditional because
the manufacturer's package limits exclude molding flash.

The revised envelopes required moving all six branch fuses 0.5 mm toward the
lower board edge and rearranging five small parts around the primary gauge.
The holders, board outline, mounting holes, support areas, raw links and
protected harness landings are unchanged. Actual KiCad DRC reports no
courtyard overlap, malformed/missing courtyard or keepout findings. This
does not establish solderability, manufactured fit or acceptable FET, fuse,
shunt and holder temperature.

Two bare support bridges on the companion join its interrupted lower support
lands to the cassette wall. Their local rectangles are X=26.4–29.6 and
52.4–55.6 mm, Y=0–2.2 mm. Both copper layers prohibit pads, tracks, vias, fills
and component footprints there. These areas belong only to the companion;
the primary has electronics in the corresponding lower strip.

The four raw current-link pads match cassette channels at global X=20, 38, 56
and 74 mm, Y=106 mm. They are permanently retained internal wires. The primary
protected harness pads, in contact 1–6 order, are at local X=47, 53, 59, 65, 71
and 77 mm, Y=94.8 mm. Their individual route to both strain ties remains a
mechanical qualification item. Contact numbers, not wire colours, define the
connections.

`checks.py` examines the actual KiCad boards, not just the placement plan. It
checks every electrical component's position, rotation and side, the unchanged
pin graph, holder polarity, the rounded outline, thickness, mounting holes,
both-layer support/RF rule areas and raw-link channel alignment. Sixteen altered
board cases must be rejected: reversed holder, plated mounting hole, duplicate
electrical address, changed outline corner, missing RF area, allowed copper in
that area, a shrunken RF area, a complete raw-to-protected positive net merge,
missing courtyard, a shrunken reviewed envelope, a courtyard omitting a pad,
a companion-only bridge copied onto the primary, and
missing, shrunken, copper-permissive or single-layer companion bridge areas.
KiCad DRC is a separate check. The final all-severity reports retain 26 primary
silkscreen findings and six companion silkscreen findings, plus 77 and nine
unconnected items respectively. Three fuse silkscreens on each board now
violate the lower-edge clearance and need cleanup before fabrication. These
are recorded in `drc-summary.json`, not waived.

The maximum holder-body envelopes leave 0.5 mm between adjacent holders and
only 0.2 mm to the nearest corner support. These are drawing-based gaps, not
fit acceptance. A possible 0.5 mm upward holder shift will be considered with
the protected-wire fan after the present retained-cassette checkpoint. Holder
fasteners, cell-insertion backing fixture, actual cell/holder fit, reverse
insertion, wire trimming, insulation, thermal behaviour and fault clearing
remain open. The four-link partition is not tolerant of an arbitrary open
middle-node link; see the primary carrier README.

## Reproduce

From the repository, use KiCad's Python runtime (the system Python need not
provide `pcbnew`):

```sh
/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 tools/apply_pack_placement.py primary
/Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9 tools/apply_pack_placement.py companion
python3 hw/placement/blind-pack/checks.py
```

The replayer refuses routed copper and copper zones. It writes through a
KiCad-10 temporary file, then uses the checked compatibility converter to keep
the pinned atopile 0.15.9 format. The independent graph must remain unchanged
before the result is written. Supply `--output` to write a work copy instead.
Run a normal atopile build from each carrier board directory after replay.
The compiler refreshes footprint serialization and removes the four purely
mechanical holes. Restore those exact holes without touching the circuit:

```sh
python3 tools/restore_pack_holes.py primary
python3 tools/restore_pack_holes.py companion
python3 tools/check_pack_frozen.py --ato /path/to/pinned/ato
python3 hw/sim/blind-pack/checks.py --check
python3 hw/placement/blind-pack/checks.py
```

The frozen wrapper copies the complete parts tree, board sources and layouts
into an isolated directory. It removes only the four checked NPTH footprints
**in that copy**, then runs atopile frozen. The canonical PCB is never
stripped or restored by that wrapper; its bytes must remain unchanged. A
separate geometry check includes the real mounting holes, outline and rule
areas. Calling `ato build --frozen` directly on the final carrier is unsupported
because that compiler unconditionally deletes non-circuit footprints. This is
an explicit circuit-only frozen check plus a complete placement check, not a
claim that the compiler understands the mechanical features.

Each circular bare support land uses four single-polygon quarter-ring rule
areas. The pinned compiler retains only one polygon per rule area, so a native
annulus with an inner polygon would lose its screw-hole void during rebuild.
The quarter rings retain the same 7.6 mm outer exclusion and 3.6 mm inner void.

Run KiCad DRC on the final canonical boards after restoration. Do not use the
replayer or restoration helper on routed copper. These checks do not establish
manufacturing readiness or physical safety.
