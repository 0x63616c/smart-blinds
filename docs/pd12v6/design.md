# pd12v6 — USB-C PD → 12.6 V / 5 A supply

Status: rev A layout complete, DRC clean (0 violations, 0 unconnected), awaiting review.
Source: `hw/boards/pd12v6.ato`.
Layouts: `hw/layouts/pd12v6/` (placed **and routed**) and `hw/layouts/pd12v6_manual/`
(same placement, zones and silk, **no tracks** — for routing by hand).
Regenerate everything: `hw/scripts/review.sh` (add `--open` to launch KiCad).

## What it is

A USB-C Power Delivery sink that asks a 65 W or 100 W charger for 20 V and bucks it to
a fixed 12.6 V. One Micro-Fit 3.0 connector carries the 12.6 V, GND and the USB 2.0
D+/D− pair to the downstream pack board. It is **not** a charger and has **no current
limit**: balancing, CC/CV termination and protection live on the pack board.

## Requirements → decisions

| Requirement | Decision | Why |
|---|---|---|
| Works on 65 W and 100 W chargers | Request the **20 V** PD profile (CH224A, CFG1 = 120 kΩ) | Both charger classes offer 20 V. The buck draws ~3 A at 20 V for 5 A out, so a 65 W brick (3.25 A) is enough. |
| 12.6 V at 2–5 A | TPS54560 (60 V / 5 A buck), 12.56 V set by 147 k / 10 k on FB | Headroom for 20 V in, 5 A switch, 0.8 V reference. 12.56 V keeps a 3S pack a hair under 4.2 V/cell. |
| Keep it simple | No current limiter on this board | The buck's own ~6 A cycle-by-cycle limit protects it; an overdrawn 65 W charger just drops its PD contract. The pack board sets charge current. |
| Don't brown-out the charger | UVLO: EN divider 820 k / 56 k → start ≈ 17.8 V, stop ≈ 15 V | Buck stays off on plain 5 V USB and only runs once 20 V is granted. |
| One cable to the pack board | Molex Micro-Fit 3.0 2x2 right angle (43045-0400): 1 +12.6 V, 2 GND, 3 D+, 4 D− | 8.5 A per pin, keyed, latching, right angle so it faces out of the board edge. Crimp with the Micro-Fit tool. |
| Fits in the hand | 40 × 32 mm, 2 mm corner radius, 4 × M2 grounded holes, 4-layer | Size set by the USB-C, inductor and Micro-Fit, not by routing. |
| USB-C overhangs the edge | USB-C at x = 4.2 mm, shell past Edge.Cuts | Cable plugs in without hitting an enclosure wall. |
| Indicate state | LED2 "PD" (red) on CH224A PG, LED1 "ON" (green) on VOUT | Tells "no PD contract" from "buck not running". |
| JLCPCB in stock, black | All parts by LCSC ID (`hw/build/builds/pd12v6/pd12v6.bom.csv`); black mask set in the `.kicad_pro` | |

## Every part and why it is there

| Ref | Part | Job |
|---|---|---|
| USBC1 | USB-C 16-pin receptacle | Power and data in. Only VBUS, GND, CC1/CC2, D+/D− are used. |
| D2 | SMBJ24A TVS | Clamps VBUS surges above ~24 V at the connector (hot-plug, cable inductance). |
| U2 | CH224A PD sink | Negotiates 20 V over CC1/CC2. Single-resistor mode: CFG1 = 120 kΩ (R1) selects 20 V. Pulls PG low once the contract is made. |
| C9 | 1 µF 0603 | VBUS decoupling at the CH224A. |
| R1 | 120 kΩ | CFG1 → GND, selects 20 V. |
| R6, LED2 | 10 kΩ + red 0603 | "PD" indicator from VBUS through PG (active low). |
| C4, C5 | 2 × 10 µF 50 V 1210 | Buck input bulk, right at U1 VIN/GND. |
| C6 | 100 nF 0603 | Buck input HF decoupling at the VIN pin. |
| U1 | TPS54560 (SOIC-8 EP) | 60 V / 5 A synchronous-top buck controller, 2.5 MHz capable, run at ~400 kHz. |
| C1 | 100 nF 0603 | Bootstrap cap, BOOT → SW. |
| R7 | 240 kΩ | RT/CLK: sets ~400 kHz switching. |
| R8, R9 | 820 kΩ / 56 kΩ | EN divider from VBUS: UVLO ≈ 17.8 V on, 15 V off. |
| R2, C3, C2 | 20 kΩ, 8.2 nF, 47 pF | Type-II compensation on COMP (datasheet §8.2.2.11 with ~56 µF derated Cout). |
| R3, R4 | 147 kΩ / 10 kΩ | Feedback divider: 0.8 V × (1 + 147/10) = 12.56 V. |
| D1 | SS56 Schottky (SMA) | Catch diode, SW → GND, 5 A / 60 V. |
| L1 | Sunlord MWSA0603S-100MT 10 µH | Output inductor, 7 × 6.6 mm shielded, ~6 A sat. |
| C7, C8 | 2 × 47 µF 25 V 1210 | Output bulk, one at the inductor and one at the connector. |
| R5, LED1 | 4.7 kΩ + green 0603 | "ON" indicator from VOUT. |
| CN1 | Molex Micro-Fit 3.0 43045-0400 | Output to the pack board. Pin numbers are printed on the back silk. |
| H1–H4 | M2 holes, plated, GND | Mounting. |

## Layout rules used (so the board stays tidy when edited)

- One grid: parts sit on 0.5 mm, small passives in rows at constant 2.5 mm pitch, all
  rotated 0/90/180/270 only.
- Signal flow is left to right: USB-C → PD sink → buck → inductor → Micro-Fit.
  Both connectors face outward off their board edge.
- Footprint silk is stripped; the only silk is reference designators (centred above
  the part), pin-1 dots, cathode bars, the inset white frame, the title block, and
  "PD IN" / "12.6 V OUT". The back carries the Micro-Fit pinout and the "not current
  limited" note.
- Layers: F.Cu carries every current path (VBUS bus, SW node, VOUT) and the buck
  small-signal parts; In1.Cu is an unbroken GND plane; In2.Cu has a VBUS pour under the
  input half and a VOUT pour under the output half; B.Cu carries only the USB D+/D−
  pair, CC2 and the FB crossing, with GND fill elsewhere.
- Widths: VOUT 1.5 mm, VBUS 0.5–0.8 mm, SW 0.8 mm, signals 0.2 mm. Vias 0.6/0.3,
  power 0.8/0.4, three 0.45/0.25 vias between the USB-C 0.5 mm signal pads.
- SW loop is U1 pin 8 → D1 → L1 pad 1 with D1's GND tied to the plane by two power vias.
- Every GND pad gets its own via to In1 within 1 mm; GND stitching vias ring the edge.
- DRC severities relaxed in the `.kicad_pro`: `lib_footprint_mismatch` (silk is
  stripped on purpose) and `starved_thermal` (U1 pin 7 reaches the EP by a track). The
  manual copy also ignores `unconnected_items` and `isolated_copper`.

## Toolchain quirks (so the scripts stay repeatable)

- atopile 0.15.9 only parses the KiCad 9 file grammar. KiCad 10's pcbnew writes a v10
  file, so `layout_pd12v6.py` downgrades it after saving: version/generator header,
  `tenting`/`covering`/`plugging`/`capping`/`filling` tokens, and the net table that
  KiCad 10 dropped (`(net N "NAME")` on pads, `(net N)` on tracks, `(net N)` +
  `(net_name …)` on zones).
- KiCad 10 SWIG: any `Remove()` invalidates other wrappers. The script does all removals
  first, saves, reloads, then continues.
- atopile allows one layout per folder, hence the separate `layouts/pd12v6_manual/`
  (its own `.kicad_pro` + `fp-lib-table` are copied by `--place-only`).
- `kicad-cli pcb drc` must be run with `--refill-zones` or it reports hundreds of
  bogus zone clearance errors. Renders only find 3D models when run on a file inside
  a layout folder (`${KIPRJMOD}` paths).
- No atopile login is used; parts are fetched with `hw/scripts/fetch_part.py Cxxxx`.
  The Molex footprint's STEP offset was patched by hand to seat the model.

## Review outputs (`hw/build/review/pd12v6/`, regenerated by `review.sh`)

`top.png`, `bottom.png`, `in1.png`, `in2.png` (copper + silk per layer), `manual_top.png`
(the hand-route copy), `assembly.png/.pdf` (reference designators), `3d_top.png`, `3d_bottom.png`,
`3d_iso.png`, `pd12v6.step`, `drc.json`, `drc_manual.json`, `drc_summary.txt`.

A smaller version of this board is in [mini.md](mini.md).
