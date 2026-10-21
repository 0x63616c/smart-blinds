# Current enclosure candidate

The current case is **118 × 196 × 77 mm**, with a removable protected battery
cassette and an inward-facing 54 × 80 mm controller. Plain front buttons project
to 78.8 mm. The USB-C opening is underneath; the motor, encoder and pack wiring
have modeled service paths. This is prototype geometry, not a fabrication release.

[CAD package](../../cad/enclosure-v2/) · [Printed parts and hardware](../../cad/enclosure-v2/inventory.md) ·
[Print list](../../cad/enclosure-v2/print-list.csv) · [Service sequence](../../cad/enclosure-v2/service.md)

There are 22 installed printed pieces, comprising 21 shapes, per blind: 176
pieces for eight units. Two cosmetic button plugs are optional. One button
assembly nest is shared tooling. The older eight-piece holder-loading fixture
is separate and has not been requalified against this cassette's revised outlet.

The source-bound local review passed 17 geometry checks, including the actual
206-part controller with 120 rear vias, fasteners, button insertion, cassette
removal and sampled cable parking. Four original cassette-overlap witnesses
remain as positive controls. Only the front and rear cassette shapes changed in
the final clearance correction; the other 28 export roles retain their geometry.
See the [review handoff](../../cad/enclosure-v2/handoff.md).

CI rebuilds the parts and checks them against the native board produced in the
same run. A different board hash, pose set or via layout requires a deliberate
mechanical review; the old fit result cannot approve a newer PCB automatically.
The imported human-reviewed checkpoint remains separate from fresh CI reports.

The drawings still use provisional motor and holder dimensions. Two cassette
source operands remain exact inherited meshes, so the cassette is not freely
resizable. The assembly pictures use simple envelopes for prominent PCB parts;
the separate KiCad view shows the populated board. Nominal clearances do not
establish print strength, creep, insulation, catch access, cable strain relief
or loaded handling. The optional home-sensor route and physical assembly tests
remain unfinished.

The earlier 115 × 174 × 71 mm enclosure and its known board-orientation error
remain historical comparisons. Their fit or material estimates do not apply
to this revision.
