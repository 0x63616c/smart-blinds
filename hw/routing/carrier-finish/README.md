# Routed carrier silkscreen

Both routed battery boards use these project-local footprint derivatives.
The canonical parts, compiled captures and main-controller project are unchanged.
The routed projects retain their original footprint aliases and point only the
affected libraries here, so native KiCad library comparisons remain enabled.
Other footprints needed under those aliases are copied without geometry edits.
3D models still resolve to the original parts tree.

The changes remove the fuse outline end that extends over the board edge, split
the holder outline around its locating hole, remove tiny imported dots from
nonpolar resistors, and remove two FET outline strokes crossing drain lands.
Holder polarity text, FET orientation marks, pads, drills, mask/paste, fabrication
outlines, courtyards and models remain intact.

The primary has 21 graphic edits across 19 footprints; the companion has six
edits across six footprints. An independent comparison with commit `8f70213`
preserved the entire board expression after removing only UUIDs and silkscreen
graphics: all other geometry, text and settings were identical. The primary's
451 segments / 129 vias and companion's 35 segments / 12 vias are unchanged.

Each route generator applies this narrow transformation and writes the matching
libraries before recording source and derivative hashes. The route checks verify
the generated libraries, table bindings and hashes, then run native DRC and the
existing physical connectivity, geometry and injected-fault checks. Generating
either board twice reproduces its board, project, rules, table, record and libraries.

KiCad 10.0.4 reports no silkscreen clashes or library mismatches on either board.
Each retains four explicitly reported missing-courtyard findings on its board-only
NPTH mounting holes. The existing support/keepout geometry is preserved; adding
artificial courtyards just to remove those findings is not part of this cleanup.
This is neither a fabrication release nor electrical/thermal qualification.
