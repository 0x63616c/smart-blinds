# Current controller: source-driven partial route

Reviewed 21 October 2026. Working board: **54 × 80 mm**, four copper layers,
206 components and 649 distinct physical pin identities. The earlier body was
54 × 68.5 mm: the additional 11.5 mm is about 17% more board area, with no width
increase. Whole-enclosure size and assembly still need their own checks.

The placement uses a 0.25 mm origin grid and right-angle rotations. Implemented
routes follow the 0.05 mm grid and 45°/90° directions, with outward connector exits.
Top-layer body transit is rejected; the narrowly enumerated own-terminal entries
at exposed pads are checked by owner, rail, width and finite geometry.

## What changed

The current circuit capture, corrected watchdog/eFuse lands and native schematic
have been reconciled. The land-repair builds preserve the reviewed physical geometry. Eight affected
normal/frozen build pairs also pass after the catalog metadata cleanup; both
carrier circuits pass the separate isolated frozen-build checks. The route is emitted from that unrouted capture plus
owned segment/via/zone records, per-part sparse silkscreen and model bindings.
No completed PCB or chain of experimental scripts is a runtime dependency.

The raw-input TVS is close to the USB-C terminals, with a short actual top-layer
power and ground path. The protection return has more actual filled copper and
thermal-wing vias; the direct ground-return corridor remains continuous. These
are geometry improvements, not a qualified thermal/current or surge result.

Each source component maps to an explicit reviewed library variant. Two all-SMD
parts had incorrect through-hole assembly metadata; their scoped overlays correct
it. The SC-70-6 library export initially omitted a format-version header, causing
KiCad to parse its three-point arc incorrectly. Adding the required header fixed
that native load failure without moving or reshaping the footprint.

## Catalog metadata correction

The shared resistor land pattern carried a copied supplier code. On the main
board it conflicted with 22 selected 100 kΩ, 4.7 kΩ and 22 Ω resistors. The picked
manufacturer numbers and authoritative BOM codes were already correct.
Removing the generic field from the template and all 28 main instances preserves
all other source nodes. The corresponding 71 instances across nine captures were
cleaned consistently. A maintained check now rejects conflicting supplier aliases.

The source-derived output preserves all geometry, lands, net memberships,
placement, models and copper. Removing the property changes 224 diagnostic child
UUIDs through the existing deterministic enumeration; these exact remaps were
compared rather than ignoring arbitrary UUID differences. The 55 physical library
variants are unchanged. Both carrier route receipts and native checks were
refreshed; the companion PCB is byte-identical. Component quantities, selected
parts and the cost CSV are unchanged. Current availability is not established.

## Evidence and remaining work

- Native KiCad 10.0.7 loads all 55 physical library variants and all 43 distinct
  model contents. The saved board contains 516 segments and 120 vias.
- Native DRC retains 352 open connections and three named hybrid component-type
  findings (USBC1, U3, U4). No other native findings are accepted by the new build.
- Saved-file checks cover the circuit graph, lands/paste, poses, model transforms,
  47 physical endpoint groups, finite own-terminal entries, body/land clearance,
  reference reservations, actual filled-island reachability, quiet-star topology,
  RF exclusions and retainer reservations.
- Focused fault controls deliberately disconnect endpoints, bypass CC protection,
  detach thermal copper, cut a return corridor, intrude under a component and
  modify source/lands/models. Physical connectivity controls disable exact copper
  inventory equality so a missing-record check cannot masquerade as reachability.

The main captured source SHA is
`8e9b62fa83b8f93db20f158db963ba7c1ec61f060fb912db3244ae97749c228a`.
The current saved native output SHA is
`03a6b3dc624e2cf0e83f8cfdd90f64dc52071fb2b8387deb0e22949903981e74`.
The maintained build emits its own full native and physical-check receipts.

Remaining routing, motor energy-path review, charging/current/thermal/surge tests,
USB signal integrity, RF performance, sample motor/holder fit and physical assembly
are not proven. The historical component demand is not a current JLCPCB quotation.
No purchase or fabrication release is implied by this review.
