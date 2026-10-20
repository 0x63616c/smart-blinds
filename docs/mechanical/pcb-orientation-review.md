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
