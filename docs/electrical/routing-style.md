# Placement and routing requirements

Owner direction, 20 October 2026, after inspecting the current main PCB in KiCad.
The published partial route does not meet these requirements and is a historical
electrical checkpoint, not the accepted final layout.

## Component placement

Every component origin must lie on a 0.25 mm grid, with rotation in multiples of
90 degrees. Use one documented board datum. For the existing main board,
`u = x − 100 mm`, `v = 175 mm − y`; its origin is also on the absolute KiCad grid.
Do not alter a footprint's manufacturer-defined pad positions, pitch or geometry
to satisfy a placement grid. Move the whole footprint.

Arrange related parts in aligned rows with consistent spacing. Grid membership
alone does not establish a good layout. Recheck assembly courtyards, electrical
clearances, decoupling loops, thermal areas and service access after placement.

The previous mechanical anchors are not exempt. Connector moves must be
explicitly carried into CAD, mating-plug envelopes, cable routes, enclosure
openings and removal checks.

## Edge connectors

Place all cable connectors at the PCB perimeter, with mating openings facing
outward. Plug insertion and cable departure must leave the board directly,
without passing across components. Verify the actual connector drawing and
mating direction; an imported 3D model alone is insufficient evidence.

Reserve the plug, latch/tool access, wire bend and withdrawal volume beyond the
edge. Internal battery and sensor connectors follow this rule as well as USB-C.
Their cables can remain inside the enclosure; they must still exit the PCB
outward. Keep the antenna and mounting areas clear.

The USB-C socket should overhang a clean board edge. **Do not retain the
protruding PCB tongue underneath it.** The owner clarified that it is the PCB
tab, not the metal socket overhang, that must disappear. Keep all solder lands
and retention holes properly supported and verify cable insertion and overmold
clearance. Add small radii to the board's outer corners and coordinate the new
outline with the enclosure supports.

## Copper geometry

Use a 0.05 mm routing grid. Straight connector escapes should be parallel and
follow the pad axes before turning into orderly routing lanes. All segments must
be horizontal, vertical or exactly 45 degrees. Use consistent, electrically
appropriate widths and spacing. Eliminate arbitrary-angle shortcuts, unnecessary
jogs and diagonal departures from pads.

Manufacturer pad centres can fall between routing-grid points. An exact-pad
escape may use a short axis-aligned connection and 45/90-degree transition to the
routing grid. Such transitions must be recorded against their pad endpoints;
they are not permission for off-grid trunks or arbitrary slopes. A two-nanometre
comparison tolerance only accommodates historical file serialization.

No top-layer trace may pass underneath a component body, even if it shares that
component's net. Only the connection into that component's own pad is allowed.
Route around the body or use a suitable inner/bottom layer. Exposed-pad terminal
connections remain required; blanket same-net or whole-footprint exemptions are
not allowed. Top-layer fills are separate from trace routing and still require
their normal electrical and thermal review.

Preserve a continuous ground reference beneath USB data. Do not use the ground
plane indiscriminately as an extra signal-routing layer to meet an appearance
requirement. Keep switching loops, sense returns, surge paths and thermal copper
electrically sound.

## Rework and acceptance

Establish the outward-facing connector arrangement and coordinated enclosure
changes first, then complete the gridded component placement and reroute.
Previous exact-path checks must be replaced with reviewed checks of the new
physical connections; no old check can simply disappear because a route moved.

Before accepting the revised board, verify the circuit graph, all physical
connections, grid/angle rules, connector escape directions, top-body restrictions,
reference continuity, clearance, ordinary-via solder-land margins and mechanical
fit. Inspect native KiCad views and rendered boards. Automated routing or a
visually tidy preview alone does not establish electrical or manufacturing
readiness.

### Repeated visual review

The owner explicitly requires several review-and-fix passes. Capture the
actual board at each pass: a top view, a low oblique view showing model seating
and connector mouths, and bottom/individual copper-layer views where needed.
Record the source hash, specific findings, changes, and unresolved items.
Reinspect the changed result rather than treating a first attractive render
as acceptance.

Review aligned component groups, consistent spacing, orderly connector
escapes, unnecessary trace bends, usable mounting areas, rounded outline and
cable access. Keep labels sparse. Placement changes must still preserve short
decoupling and switching loops and the other electrical requirements above.

Audit every populated model for a resolvable source, units, scale, rotation,
pin-one orientation where applicable, pad/terminal alignment and seating
height. Distinguish physical geometry from imported decorative annotations.
Use manufacturer drawings and conservative tolerance envelopes for fit;
an imported model's bounding box is not a dimensional specification.
Model-only repairs must preserve the complete non-model board data.

## Baseline audit

The main board with SHA-256
`e060e662511fec93ad6645bf139d5e40db871254198c89bc9dc0241b402c2577`
contains 1,013 segments and 255 vias. A read-only geometry audit finds
**387 segments outside horizontal/vertical/45-degree directions**:
310 on the top layer, 71 on the bottom and six on In2.
Of its 196 component origins, 152 are off the new quarter-millimetre placement
grid. Nearest-grid rounding is only a starting proposal; it is not accepted
placement until clearance and electrical checks pass.

A conservative top-body screening also flags many routes for review. It uses
reviewed body-and-lead envelopes where available and courtyard fallbacks
elsewhere; these are not exact body-intersection counts. Exact component-body
boundaries and pad-entry corridors must be reviewed before enforcing that check.
No board geometry was changed by this audit.
