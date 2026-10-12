# pd12v6mini — compact pd12v6

Same job, same connectors as [pd12v6](design.md): USB-C PD asks for 20 V, a buck makes 12.6 V / 5 A,
one Micro-Fit 3.0 carries +12.6 V, GND, D+, D−. Built to be small and clean for JLCPCB assembly.

Status: rev B layout (hand-placed, hand-routed, every part labelled), DRC clean (0 violations, 0 unconnected).
Source `hw/boards/pd12v6mini.ato`; layouts `hw/layouts/pd12v6mini/` (routed) and
`hw/layouts/pd12v6mini_manual/` (placed, no tracks). Regenerate: `hw/scripts/review.sh pd12v6mini`.

## Size

| | pd12v6 | pd12v6mini |
|---|---|---|
| Board | 40 × 32 mm | 35 × 24.5 mm (33 % less area; rev A was 33 × 20 but crammed) |
| Placed parts | 27 | 23 |
| Unique parts (JLC feeders) | 22 + CN1 | 19 + CN1 |
| Smallest via drill | 0.25 mm (+$37 at JLCPCB) | 0.3 mm (no surcharge) |

The floor is set by the two connectors: the USB-C (9 mm wide) and the Micro-Fit, whose body
covers 11 mm × 10 mm of board behind its pins. The four M2 holes sit in the corners beside them.

## What changed and why

| Part | pd12v6 | pd12v6mini | Why |
|---|---|---|---|
| Buck | TPS54560 (SOIC-8 EP) + SS56 catch diode + RT resistor + 3-part compensation | **TPS56637** (3 × 3 mm, LCSC C841386) | Synchronous (no diode), internal compensation, fixed 500 kHz. 5 parts gone. |
| Inductor | 10 µH, 7.1 × 6.6 mm | **5.6 µH, 5.5 × 5.3 mm**, Isat 8.6 A, 24 mΩ (C18236291) | TI's table 4 value for a 12 V output. Only 5.6 µH met Isat ≥ 7 A and DCR < 25 mΩ in stock. |
| TVS | SMBJ24A (SMB) | **SMAJ22A** (SMA, C134971) | Smaller, and the TPS56637 is a 28 V part (32 V abs max) so the clamp must be lower. |
| Input caps | 2 × 10 µF 1210 X7R | **2 × 10 µF 50 V 1206 X5R** (C13585, JLC Basic) | Smaller and Basic. |
| Output caps | 2 × 47 µF 1210 | same | ≈ 30 µF effective at 12.6 V meets TI's 25–100 µF; 1206 22 µF would need four. |
| Passives, LEDs | 0603 | **0402** | JLCPCB assembles; nobody hand-solders this board. |
| PD sink | CH224A | CH224A (unchanged) | The 2 × 2 mm CH224Q is out of stock at JLC and LCSC. Swap it in later; same pins and resistor. |

Design values (TPS56637 datasheet SLVSEG1A):
- Vout = 0.6 V × (1 + 200 k / 10 k) = **12.6 V**.
- UVLO on EN: 390 k / 27 k, Ip 1 µA, Ih 4 µA → starts at **17.8 V**, stops at **15.3 V**.
  The buck stays off on 5 V USB, and EN stays below 5.5 V at 21 V in.
- Feed-forward 100 pF + 20 k across the top resistor (table 4, 12 V row).
- MODE tied to GND: Eco-mode at light load. PG unused.
- Ripple at 21 V in: 1.8 A p-p, peak 5.9 A against 8.6 A Isat.

## Layout and look (rev B)

- **Grouped by job:**
  - INPUT (USB-C, TVS) on the left.
  - BUCK along the top: input caps → TPS56637 → boot cap → inductor. Its six tuning parts sit in
    one 2 mm-pitch row underneath, signal pad up, labels on one line.
  - PD controller on the centre line, with two mirrored status columns under it:
    PG → R6 → LED2 "PD" and VOUT → LED1 → R5 "ON".
  - OUTPUT caps mirrored above and below the Micro-Fit.
- **Every part is labelled on the top silk** on a consistent grid. LEDs also carry "PD" / "ON".
- **White inset outline on both sides,** broken at the connectors. M2 holes sit inside it in the
  corners. Matte black mask, ENIG. Choose ENIG on the JLCPCB order form too.
- **Routing:**
  - Traces come in one width per job: 0.2 mm signals, 0.3 mm power into 0402 pads,
    0.6 mm power into big pads. Heavy current runs in shaped copper areas.
  - Every track leaves its pad straight along the pad axis, and every corner is the same
    45° chamfer (`path()` in the routes script).
  - The top only carries pad-to-pad links. USB data runs on B.Cu, CC2 hops on In2, and
    VBUS/VOUT reach far pins through In2.
- **One via size (0.5/0.3), tented.** GND vias only sit beside pads that need them.

## Layers

- **F.Cu:** VBUS island under the input caps and VIN, SW copper area to the inductor, wide VOUT to the
  Micro-Fit, all signals, solid GND pour.
- **In1.Cu:** unbroken GND.
- **In2.Cu:** VBUS pour on the left, VOUT pour on the right. Every far pin is reached with one via.
- **B.Cu:** USB D+/D− under the PD controller to Micro-Fit pins 3/4, CC2 crossing, GND pour.

## Cost against pd12v6 (8 boards, JLCPCB assembled, black mask, before shipping)

Prices checked 2026-10-12. pd12v6 figures come from JLCPCB's quote page and price list. The
mini figures are **estimates** derived from them using JLC part prices; not yet quoted.

| | pd12v6 as designed | pd12v6 with 0.3 mm vias | pd12v6mini |
|---|---|---|---|
| Total | $168–185 | $131–148 | **≈ $134–151** |
| + ENIG instead of HASL | +$12 | +$12 | +$12 |

Where the mini's difference comes from:
- **Parts:** about $1 more per board. The TPS56637 is $2.23 against $0.97, partly offset by
  dropping the diode and compensation parts and using Basic 1206 caps. That's about +$8 for 8.
- **Feeder loading:** 3 fewer unique parts at $1.53 each, about −$5.
- **Small-drill surcharge:** none (pd12v6 pays $37 for its three 0.25 mm vias).
- **Bare PCB:** the same price bracket. Both are under 50 × 50 mm, and Standard PCBA panelises both.

## Known limits / to check

- **Not current limited:** same as pd12v6. The TPS56637 valley limit is 6.3–8.6 A.
- **The 390 k EN resistor (C25782) has only ~2.7 k in stock.** Plenty for 8 boards, but no Basic part
  exists for it. A FOJAN equivalent (C2909352) has 478 k in stock.
- **Black mask on 4 layers likely forces JLC Standard PCBA** (Economic is green-only on 4-layer).
- **Inductor ratings are from JLC listings,** not the datasheet. The body is probably ~5 mm tall.
