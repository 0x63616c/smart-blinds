# PCB orientation correction

20 October 2026. **Confirmed CAD integration defect; enclosure revision in progress.**

The current retained enclosure and the subsequent joint-service study map local
PCB `u` to wall `+Z`, local `v` to wall `+Y`, and the populated face to wall `+X`.
Those three directions describe a reflection. A real PCB cannot occupy that
pose through rotation and translation.

The native populated KiCad GLB export independently establishes the board axes:
GLB `x = u`, `z = −v`, with the populated face along `+y`. The former mapping's
rotation determinant is −1. Keeping the same local `u/v` anchors requires the
populated face toward wall **−X**, with a proper rotation determinant of +1:

```
mechanical X = board_back_X − 1000 × glb_y
mechanical Y = board_origin_Y − 1000 × glb_z
mechanical Z = board_origin_Z + 1000 × glb_x
```

GLB coordinates are metres; enclosure coordinates are millimetres. A work-only
candidate uses `board_back_X = 111.8`, `board_origin_Y = −5` and
`board_origin_Z = 8`. Its inward-facing components need revised frame/clip
access, button placement and connector/cable paths. This candidate is not yet
accepted for promotion. No PCB copper, footprint pin pattern or component mesh
is mirrored to make the old allocation appear valid.

The previous CAD intersection checks still describe their modeled volumes,
but do not prove that the physical populated PCB fits the enclosure. Both
the published 115 × 174 × 71 mm case and the 118 × 182 × 71 mm service study
remain provisional.

The export also exposes imported-model datum differences for the USB socket,
pack header and buttons. Their model offsets must be audited against the
primary drawings and actual footprint pads. Raw imported-model interference
is not a substitute for that audit.

## Component datum audit

The primary component drawings and actual exported vertices have now been compared.
All corrections below concern illustrative models; PCB pads, copper and anchors
remain unchanged.

| Component | Confirmed model discrepancy | Drawing-based authority |
|---|---|---|
| Molex 430450600 pack header | Body is displaced −3 mm in local `u` and −1.5 mm in `v`; imported tails are 4 mm below seating instead of 3.18 mm, and modeled mating rows have an incorrect 3.082 mm pitch | SD-43045-001 Rev H: 12.65 × 9.91 mm body, 3 mm contact pitch, 7.37 mm body height plus 1.4 mm latch |
| HRO TYPE-C-31-M-12 USB socket | Mouth is 2.44 mm behind its drawing-derived position | Locator-to-mouth distance 6.25 mm; mouth at local `v = −3`; use the drawing's shell envelope and tolerances |
| XUNPU TS-1081S-AC01326 buttons | Imported offsets float terminals 0.5 mm above seating and displace the actuator by 0.37 mm; a white annotation protrudes above the real part | Body height 1.3 mm, actuator center 0.8 mm above PCB, 3.75 mm overall body/actuator length; imported locating-post pitch also differs from the drawing |

The old pack-wire row heights of 4.46/7.46 mm were derived by subtracting overall
mated and standalone dimensions that include different latch geometry. That is
not a valid shared datum, and those row positions are withdrawn. Centering 3 mm
rows in the 7.37 mm header body suggests 2.185/5.185 mm, but the drawing does not
explicitly dimension that centering. The new harness study must expose this
assumption and its sensitivity, retain the full conservative mating/latch reserve,
and avoid claiming a qualified bend radius from the previous row positions.

A separately labeled work preview applies the four model translations and removes
only the switches' nonphysical white annotation primitives. Its GLB SHA256 is
`85c49cb2ca2482f8664f97d7fc2309b795558d7f6e97eb349f85265bfbc1f071`.
Residual supplier geometry errors remain; primary drawing reserves govern clearance.
This preview is not the native unmodified board export or a fit acceptance result.

Drawing sources: [Molex header](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/430/43045/430450600_sd.pdf),
[Molex receptacle](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/430/43025/430250600_sd.pdf),
[HRO source record](../../hw/parts/blind-usb/usb-connector-geometry.json) and
[XUNPU source record](../../hw/parts/blind-control-io/README.md).
The local header drawing is Rev H; the currently indexed H1 and official STEP
were located, but their downloads failed. They have not been inspected or used
to claim the missing contact-height datum.

## Source record

- Partial PCB SHA256: `e060e662511fec93ad6645bf139d5e40db871254198c89bc9dc0241b402c2577`.
- Native KiCad 10.0.4 GLB SHA256: `9bfbfc9b29fc336cefd67b07bdeffa2479881973fb688995f276ab754ec817c9`.
- Export origin: native board coordinates `100 × 175 mm`; all populated
  component models included with STEP substitution.
- Independent axis proof and a proper-placement mesh extraction agree.
  The latter contains 194 component roots plus the board, with 392942 triangles.

The revised mechanical acceptance must include a source-bound, proper rigid
PCB transform, drawing-checked component poses, one connected mesh per printed
piece, cable and tool access, and the complete service path. Physical fit,
strength, wire flexibility and manufacturing tolerances still require prototypes.
