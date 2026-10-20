# Compact prototype mechanical parts

For the later fixed case/cassette/controller additions, use
[the retained enclosure BOM](mechanical-retained.md). Its adjustable button plunger, face and guide bar
replace this study's original plunger and guide; the eight drive shapes are reused.

This is the retained drive/button portion of the 115 × 174 × 71 mm candidate, with a 78 mm untrimmed-holder fallback. It is **not** a complete build or purchase list: the wall/cover, controller and protected battery cassette fastening remain unfinished. No purchase or fabrication is authorized by this file.

| Item | Per device | For eight | Status |
|---|---:|---:|---|
| Recfountik JGB37-520 12 V, 111 RPM encoder motor | 1 | 8 | Owner purchase; geometry/electrical qualification pending |
| 6 × 10 × 3 mm shielded bearing, NSK MR106ZZ1 dimensional family | 1 | 8 | [Manufacturer catalog](https://www.nsk.com/common/data/ctrgPdf/bearings/e126h.pdf); exact stock/price and fit not quoted |
| M3×10 socket screws | 4 | 32 | Lower motor clamps to backplate |
| M3×12 socket screws | 6 | 48 | Four upper motor clamps, two outboard-pod feet |
| M3×10 socket screws | 2 | 16 | Removable chain guard to pod |
| M3 hex nuts | 12 | 96 | Captured for those structural positions |
| M2.5×8 socket screws | 2 | 16 | Bearing retainer |
| M2.5 hex nuts | 3 | 24 | Two bearing retainer, one wheel grub screw |
| M2.5×6 grub screw | 1 | 8 | Narrow wheel to motor D flat; verify engagement/access |
| M2×6 screws and M2 hex nuts | 2 each | 16 each | Front button rear-guide bar |
| XUNPU TS-1081S-AC01326 right-angle SMT switches | 2 | 16 | [JLC C720493](https://jlcpcb.com/partdetail/XUNPU-TS_1081SAC01326/C720493); electrical BOM owns assembly pricing |

The dimensions are nominal metric hardware allocations. Select exact screw heads/nuts and a locking method before freezing their pockets. Printed-part strengths, motor-clamp friction, bearing/shaft fit and screw access require prototype checks. The bearing supports part of the chain radial load; it does not isolate the gearbox from that load.

The source exports four motor-clamp halves, one bearing pod, one bearing retainer, one chain wheel, one chain guard, one plunger type (print two) and one button-guide bar. Those are **10 file types / 11 printed fit pieces per device**, using the default 71 mm trimmed-holder case. The 78 mm fallback needs a plunger 7 mm longer, selected by `tail_mode="untrimmed"`; that longer plunger is not in the default export bundle. A complete backplate, cover and protected pack cassette are not yet released print files. The guide shoulders and captive M2 nut bosses are modeled inside the provisional cover.

For the pack, six MYOUNG TH A5BJ001 holders are approximately **$7.35/device** at the dated 48-piece catalog quantity, before carrier PCBs and assembly. The electrical sourcing record owns the live part/assembly price. Two three-holder boards keep through-hole holders single-sided. The narrow depth requires 12 trimmed leads per device / **96 for eight**, each inspected for ≤1.5 mm pin-and-solder protrusion. A 1 mm barrier and 0.5 mm clearance each side give the 5 mm board gap. Do not assume JLC includes this clipping/inspection; request a whole-order quote or budget manual work. Untrimmed 4.5 mm tails need the 12 mm gap and the deeper cover.

The compact drive deletes the independent shaft, flexible coupling, two collars, spacer stacks and one bearing from the roughly $25/device reference drive. That is a meaningful parts-count opportunity, not a claimed exact saving: a bearing distributor quote, fasteners, printed mass, cassette hardware and labour are still missing from the whole-device cost. Contact heating/current qualification is required for both TH and SMT holder candidates.
