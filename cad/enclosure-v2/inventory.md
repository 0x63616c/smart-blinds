# Complete enclosure candidate inventory

Work-only 118 × 196 × 77 mm shell; plain integral button faces project to 78.8 mm; optional cosmetic plugs project to 79.5 mm. This is an assembly study, not a print, purchase or fabrication release. One unit is shown; plan eight complete units. White PETG remains the candidate material under the existing temperature/creep qualification plan. No strength is inferred from a closed mesh.

## Installed printed pieces

| Part | Quantity/unit | Source / role |
|---|---:|---|
| Wall backplate | 1 | `source/enclosure_case_v2.scad`; wall slots, drive mounts, two cassette cleats and four cover posts |
| Front cover | 1 | `source/enclosure_case_v2.scad`; real screw recesses, underside USB opening, two front button guides and chain exit |
| Cassette rear | 1 | Bounded capture-relief rear; same closed battery enclosure and relocated lock ear |
| Cassette front | 1 | Bounded boss/capture-relief front; same protected outlet and cassette closure |
| Cassette spacer | 1 | Frozen guarded-outlet spacer; 5 mm carrier gap, dielectric barrier slot and holder backing |
| Controller frame with inline motor tray | 1 | `source/controller_frame_v2.scad`; source frame, tray, tail seat and current-board rear-face reliefs |
| Upper controller clip | 1 | Frozen v5 enclosure clip, installed 3 mm lower |
| Lower controller clip | 1 | Frozen v5 enclosure clip, installed 3 mm lower |
| Integral front-inserted buttons | 2 | `source/front_buttons_v2.scad`; one face/flange/stem each, accessible front adjuster, no adhesive |
| Optional cosmetic plugs | 2 optional | `source/cosmetic_plug_v2.scad`; removable O-ring prototype, not needed for operation |
| Open-sided button guide bar | 1 | `source/front_buttons_v2.scad`; finite rear approach/side seating with shared nest |
| Rear lower / rear upper motor clamps | 1 each | Existing compact-direct drive source; replaceable motor fit parts |
| Front lower / front upper motor clamps | 1 each | Existing compact-direct drive source |
| Bearing block | 1 | Existing compact-direct drive source |
| Bearing retainer | 1 | Existing compact-direct drive source |
| Chain wheel | 1 | Existing compact-direct drive source; chain and shaft fit provisional |
| Chain guard | 1 | Existing compact-direct drive source |
| Removable protected-outlet guard with front clamp jaw | 1 | `source/protected_cassette_v2.scad`; separates raw links below from protected cable above |
| Adjustable backing comb | 1 | `source/protected_cassette_v2.scad`; same two M2 screws compress a compliant pad; pull force unqualified |
| Motor-tail keeper | 1 | `source/controller_frame_v2.scad`; independently retained controller-side pigtail |

**22 installed pieces / 21 distinct shapes per blind; 176 pieces for eight.** The two optional plugs make 24 pieces / 22 shapes per unit and need two additional O-rings. The corrected integral buttons remove the two separate cosmetic faces. One new button assembly nest is shared workshop tooling. The existing eight-piece holder-loading fixture is separate and has not been requalified against the revised outlet restraint.

`print-list.csv` and `evidence/inventory.json` contain fresh exact STL hashes, connected-piece checks and volumes. The base meshes total **369.2393 cm³ per unit**, equivalent to **468.9 g per unit / 3.751 kg for eight** at solid density. Optional caps add 0.0860 cm³ per unit; the new shared button nest is 3.4919 cm³. The dense solid PETG equivalent uses the historical source-listed 1.27 g/cm³ density. It is not a slicer forecast: infill, perimeters, supports, brims and waste are not determined.

## Cut material and consumables

| Item | Per unit | Eight units | Boundary |
|---|---:|---:|---|
| Dielectric barrier | 1 | 8 | Existing 1.0 mm cut sheet/shape; material and dielectric qualification still open |
| Pack clamp pad | 1 | 8 | 34.8 × 1.55 × 0.508 mm SG-30 GP silicone candidate; trim length/fit and supplier availability unqualified |
| Motor-tail pad | 1 | 8 | 5.6 × 5.7 × 0.508 mm same silicone; CAD uses 0.50 nominal for the separate keeper study |
| T18R housing tie | 1 | 8 initial | 100 × 2.5 × 1 mm manufacturer family; cut and replace during occasional module service |

The silicone candidate is [Stockwell SG-30 GP, 30 Shore A](https://www.stockwell.com/data-sheets/sg-series-solid-silicone.pdf). The selected .020 inch sheet is .508 mm nominal. Compression adjustment establishes modeled contact only; actual wire OD, pad thickness, screw setting, friction, insulation damage and creep need pull/temperature tests. The T18R manufacturer's stated body/head dimensions are the basis for the tray relief; its routing and locking-head handling still need a sample.

## Nominal hardware allocation

| Item | Per unit | Purpose |
|---|---:|---|
| M3×60 socket screw + M3 nut | 4 pairs | Cassette closure; two also retain frame feet |
| M3×10 socket screw + M3 nut | 4 pairs | Front cover |
| M3×6 socket screw + M3 nut | 1 pair | Single cassette lock |
| M3×8 socket screw + M3 nut | 1 pair | Removable protected-outlet guard |
| M2×8 countersunk screw + M2 nut | 2 pairs | Controller clips, accessible only after joint module is removed and supported |
| M2×8 socket screw + M2 nut | 2 pairs | Pack clamp adjustment; top-loaded nut traps, no print-around assembly |
| M2×8 socket screw + M2 nut | 2 pairs | Motor-tail keeper |
| M2×8 socket button adjuster | 2 | One specified captive M2 locking nut each; no separate jam nut |
| M2×5 countersunk screw + M2 nut | 2 pairs | New button guide bar |
| M3×10 socket screw | 6 | Four lower motor clamps and two chain guard |
| M3×12 socket screw | 6 | Four upper motor clamps and two bearing-pod feet |
| M3 nut | 12 | The drive screws above |
| M2.5×8 socket screw + M2.5 nut | 2 pairs | Bearing retainer |
| M2.5×6 grub screw + M2.5 nut | 1 pair | Chain wheel to shaft flat |
| 6 × 10 × 3 mm shielded bearing | 1 | Outboard support shares radial load with gearbox; does not isolate it |
| Wall screw, washer and wall-specific anchor | 3 sets | 4.8 mm plate slots, 10 mm head-pocket width; head+washer stack ≤5.0 mm above Z3 plane |

Multiply these quantities by eight for the batch. Exact screw head, nut and tolerance selection, locking method, insertion sequence and tool fit remain prototype gates. The obsolete independent frame-foot M3 screws and old four-tie scheme are not additional requirements.

## Harnesses and assembly boundary

- Pack: one Molex 2147561061 six-way 150 mm female pigtail; all permanent pad terminations are made with both carriers empty. Contact identities remain PACK+, PACK−, SDA, SCL, charger NTC, NTC return. The six original fan centerlines are unchanged; final trim lengths still need a physical forming fixture and verified row datum.
- Motor fixed side: candidate Molex 2147581022, 300 mm male-to-pigtail, 18 AWG. Current centerline lengths are about 206.1 and 209.6 mm. No unknown motor factory-lead length is credited. Exact stripping/splicing and connector ear variant remain open.
- Controller motor side: existing female pigtail to retained solder pads; short formed centerlines are about 42.3 and 34.0 mm, before termination allowances.
- Encoder: candidate 151340403, 300 mm four-way PicoBlade cable, one end retained and the far housing removed. Do not halve it. Current centerline is about 260.4 mm. Motor-side pinout/termination and actual wire bundle construction remain open.
- Optional home harness: not fitted or shown. A real home sensor, upper route and sensor mounting remain unfinished; the PCB connector remains available.

The cable sources are recorded in [the local cable provenance](references/motor-service-cables.md). Catalog stock is time-sensitive. No crimp tool is assumed, but harness trimming, solder termination, insulation, continuity/identification and pull inspection remain actual build operations. No cost estimate should silently omit them.

## Button consumables and hardware boundary

The proposed locking nut geometry is Accu HNN-M2-A2, 4.00 mm maximum across flats and 2.80 mm maximum height. Its CAD trap is 4.40 mm AF ×3.20 mm; ordinary M2 nuts with 4.5 mm flats are not substitutions. Actual prevailing torque, hot-window behavior, print strength and release friction require testing. See the provenance copy `references/button-hardware.md`. Optional plugs use 2.5 mm ID ×1.0 mm section silicone O-rings and add no adhesive; nominal 15% squeeze is only a candidate contact scenario, not proven retention.
