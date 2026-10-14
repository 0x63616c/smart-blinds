# pd12v6mini — compact pd12v6

Same job, same connectors as [pd12v6](design.md): USB-C PD asks for 20 V, a buck makes 12.6 V / 5 A,
one Micro-Fit 3.0 carries +12.6 V, GND, D+, D−. Built to be small and clean for JLCPCB assembly.

Status: rev E layout (grouped cells, hand-placed on shared centre lines, hand-routed), DRC clean (0 violations,
0 unconnected) on the zone fill as stored (what the gerbers are plotted from), routing style check
clean (`hw/scripts/check_layout.py`).
Revs B, C and D are kept for comparison in `hw/layouts/pd12v6mini_revB/`, `_revC/` and `_revD/` (static copies, not
rebuilt; B and C have the old, too-fat stored zone fills, so never send them to fab).
Rev E (after WEBENCH): 6.8 µH / 12.5 A inductor instead of 5.6 µH / 8.6 A, and a third 10 µF input cap (C9).
Source `hw/boards/pd12v6mini.ato`; layouts `hw/layouts/pd12v6mini/` (routed) and
`hw/layouts/pd12v6mini_manual/` (placed, no tracks). Regenerate: `hw/scripts/review.sh pd12v6mini`.

## Size

| | pd12v6 | pd12v6mini |
|---|---|---|
| Board | 40 × 32 mm | 47.5 × 25 mm (7 % less area; rev D was 44 × 25, rev C 42 × 25, rev B 35 × 24.5 with no group cells, rev A 33 × 20 and crammed) |
| Placed parts | 27 | 24 |
| Unique parts (JLC feeders) | 22 + CN1 | 19 + CN1 |
| Smallest via drill | 0.25 mm (+$37 at JLCPCB) | 0.3 mm (no surcharge) |

The floor is set by the two connectors: the USB-C (9 mm wide) and the Micro-Fit, whose body
covers 11 mm × 10 mm of board behind its pins. The four M2 holes sit in the corners beside them.

## What changed and why

| Part | pd12v6 | pd12v6mini | Why |
|---|---|---|---|
| Buck | TPS54560 (SOIC-8 EP) + SS56 catch diode + RT resistor + 3-part compensation | **TPS56637** (3 × 3 mm, LCSC C841386) | Synchronous (no diode), internal compensation, fixed 500 kHz. 5 parts gone. |
| Inductor | 10 µH, 7.1 × 6.6 mm | **6.8 µH, 6.4 × 6.6 × 6.0 mm**, Isat 12.5 A, Irms 10 A, 11 mΩ typ / 13 max (PROD PSTMAA666460-6R8MB, C55172548) | WEBENCH's value, and Isat clears an overload: U1 holds the *valley* at up to 8.6 A, so the peak reaches ≈ 10 A. Rev D's 5.6 µH part (C18236291) saturated at 8.6 A. |
| TVS | SMBJ24A (SMB) | **SMAJ22A** (SMA, C134971) | Smaller, and the TPS56637 is a 28 V part (32 V abs max) so the clamp must be lower. |
| Input caps | 2 × 10 µF 1210 X7R | **3 × 10 µF 50 V 1206 X5R** (C13585, JLC Basic) | Smaller and Basic. A 1206 keeps only ≈ 4.5 µF at 20 V, so three give ≈ 13 µF (WEBENCH's minimum; TI asks for > 10 µF). |
| Output caps | 2 × 47 µF 1210 | same | ≈ 30 µF effective at 12.6 V meets TI's 25–100 µF; 1206 22 µF would need four. |
| Passives, LEDs | 0603 | **0402** | JLCPCB assembles; nobody hand-solders this board. |
| PD sink | CH224A | CH224A (unchanged) | The 2 × 2 mm CH224Q is out of stock at JLC and LCSC. Swap it in later; same pins and resistor. |

Design values (TPS56637 datasheet SLVSEG1A):
- Vout = 0.6 V × (1 + 200 k / 10 k) = **12.6 V**.
- UVLO on EN: 390 k / **30 k**, Ip 1 µA, Ih 4 µA → starts at **16.1 V** (17.6 V worst case), stops at **13.7 V**.
  The buck stays off on 5, 9, 12 and 15 V supplies, and EN stays below 5.5 V at 21 V in.
  It was 27 k until rev D. That started at 17.8 V typical, but at **19.4 V worst case** (EN threshold at its
  1.26 V maximum, resistors 1 % the wrong way). A 20 V PD source may deliver as little as 19.0 V, so an
  unlucky chip on a low charger would never start. 30 k (C25776, Extended) leaves 1.4 V of margin.
- Feed-forward 100 pF + 20 k across the top resistor (table 4, 12 V row).
- MODE tied to GND: Eco-mode at light load. PG unused.
- Ripple at 21 V in: 1.5 A p-p, peak 5.7 A in normal use. In overload the valley limit (6.3–8.6 A) plus ripple
  puts the peak near 10 A, still under L1's 12.5 A Isat.

## Simulation (ngspice, `hw/sim/`)

TI's TPS56637 model (SLVMD48) is PSpice-encrypted, so ngspice cannot run it. `buck_pd12v6mini.cir` stands
U1 in with its two switches (26 / 12 mΩ), 500 kHz and its 2 ms soft start, under a peak-current-mode loop;
everything else is the board's real values. `uvlo_pd12v6mini.cir` sweeps the EN divider at the datasheet limits.

| Check | Result |
|---|---|
| Output at 1 A and 5 A | 12.60 V |
| Output ripple at 5 A | ≈ 15 mV peak-to-peak |
| L1 current at 5 A | 4.2–5.8 A with the rev D 5.6 µH part (not re-run for rev E's 6.8 µH) |
| Start-up | 2 ms ramp, 25 mV overshoot |
| Load step 1 → 5 A | dips to 11.8 V, back in ≈ 0.3 ms (stand-in loop; the real D-CAP3 loop is faster) |
| Input at 5 A out | 3.3 A from the charger |
| Buck turn-on (30 k) | 16.1 V typical, 17.6 V worst case; off at 13.7 V |

Run: `cd hw/sim && ngspice -b buck_pd12v6mini.cir && uv run --with pandas --with matplotlib python plot_buck.py`.

### TI WEBENCH (real TPS56637 model), 2026-10-13

First run, rev D parts:


WEBENCH Power Designer, 17–21 V → 12.6 V / 5 A, with the board's parts entered as custom parts: L1 5.6 µH /
24 mΩ / 8.6 A; Cout 2 × 15 µF effective, 3 mΩ (47 µF 1210 at 12.6 V); Cin 2 × 4 µF effective, 3 mΩ
(10 µF 50 V 1206 at ~20 V, estimated); 200 k / 10 k, 100 pF + 20 k, 100 nF boot, MODE = Eco-mode.
The derated capacitances are estimates. EN/UVLO is not modelled (Vin steps straight to 19 V).

| Check | Result |
|---|---|
| Start-up (19 V in, 5 A load) | 1.73 ms, no overshoot, settles at 12.61 V; inductor peak 6.03 A |
| Load step 5 → 0.5 → 5 A (40 µs edges) | +0.09 V / −0.13 V, settles in 0.42 / 0.37 ms, no ringing |
| Steady state (19 V, 5 A) | 12.60 V, 11.8 mV p-p ripple, inductor 1.43 A p-p, 523 kHz |
| Estimates at 20 V, 5 A | 97 % efficient, 1.9 W lost (U1 1.3 W, L1 0.6 W), **3.25 A from the charger**, U1 ≈ 94 °C at 30 °C ambient |

What it flagged (all fixed in rev E except the last):
- **L1 below its recommendation.** WEBENCH recommends 6.8 µH at this operating point. Checking the datasheet
  turned up the bigger problem: the overcurrent limit acts on the current *valley* (6.3–8.6 A), so in an overload
  the peak reaches ≈ 10 A, past the 5.6 µH part's 8.6 A Isat.
- **Input capacitance below its recommendation.** WEBENCH asks for ≥ 13 µF effective; the two 1206s give
  roughly 8 µF at 20 V. Its estimate of input ripple is 0.27 V p-p.
- **65 W chargers are at their limit at 5 A.** 3.25 A at 20 V is exactly a 65 W PD source's maximum; keep
  the pack board's charge current ≤ ~4.8 A on a 65 W charger, or use a 100 W one.

Second run, rev E parts (L1 6.8 µH / 13 mΩ max / 10 A; Cin 3 × 4.5 µF effective):

| Check | Result |
|---|---|
| Load step 5 → 0.5 → 5 A | +0.10 V / −0.12 V, settles in 0.28 / 0.14 ms (faster than rev D), no ringing |
| Start-up (19 V in, 5 A load) | 1.73 ms, settles at 12.61 V; inductor peak 5.74 A (was 6.03 A) against 12.5 A Isat |
| Estimates | 97.4 % at 21 V; Vout ripple 9.8 mV, Vin ripple 0.16 V p-p (was 0.27 V); at 20 V, 5 A: 1.64 W lost (U1 1.3 W, L1 0.33 W), 3.23 A from the charger, U1 ≈ 94 °C at 30 °C ambient |

## Layout and look (rev E)

- **Reads left to right like the schematic.** The inset outline is divided into four titled cells:
  - **INPUT**: the USB-C, and the TVS (D1) hanging off the VBUS strip, fed from its cathode end.
  - **BUCK** (top middle): three input caps (C3, C4, C9) → C5 → TPS56637 → boot cap → inductor on one centre line. Its six
    tuning parts sit in one 2.2 mm-pitch row underneath, signal pad up. Each input cap has a 20 V via above
    and a GND via below, in line with its pads.
  - **PD** (bottom middle): CH224A with its CC / VBUS vias in one column on the left, R1 on pin 9's line,
    the PD LED chain on pin 10's line and C8 on pin 1's line.
  - **OUTPUT**: C6 above and C7 below the Micro-Fit, each with a pad straight in line with a pin. The ON LED
    sits at the bottom on the same line as the PD LED, mirroring it.
- **Labels:** every part has its reference on the top silk at 0.8 mm, always on the same side within a row.
- **Power path as top copper:** USB-C → D1 → up the INPUT edge → along the input caps → U1, then
  L1 → C6 → straight down into pin 1.
- **Routing:**
  - Traces come in one width per job: 0.2 mm signals, 0.3 mm power into 0402 pads, 0.6 mm power into big pads.
  - Every segment is at 0°, 45° or 90°, and every pad is entered along its axis (script-checked).
  - Vias sit in line with the pad they serve, never hung off the side of a track.
  - No top copper runs under a part body except into that part's own pad, through the body's overhang
    (script-checked). U1's AGND pin drops to the GND plane through its own via instead of a link under the chip.
- **One via size (0.5/0.3), tented.** Matte black mask, ENIG. Choose ENIG on the JLCPCB order form too.
- **3D models:** KiCad's own models for D1, U2, L1 (the Chilisin 5040 scaled to the PSTMAA666460's 6.4 × 6.6 × 6.0 mm) and the
  USB-C (GCT USB4105, same 16-pin family, shell legs within 0.2 mm). U1 keeps its EasyEDA model, since KiCad has
  no TI RPA package. These only change the renders and STEP, not the board.

## Layers

- **F.Cu:** parts, the power path copper (VBUS, SW, VOUT), short pad-to-pad links, solid GND pour.
- **In1.Cu:** unbroken GND.
- **In2.Cu:** VBUS on the left and under the PD cell, VOUT top right and under the OUTPUT cell. CC1 hops here,
  from the USB-C to the CH224A.
- **B.Cu:** the USB D+/D− pair along the centre line, fanned out at 45° into Micro-Fit pins 3/4 and entering
  them straight. CC2 also runs here, down the INPUT cell and across under the back text (not through it).
  The rest is a GND pour. Pin names and the warning are on the back silk.

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
- **Board size:** rev E is 47.5 × 25 mm, still under 50 × 50, so the same price bracket.
- **Rev E parts:** the new inductor is $0.61 against $0.85; the third input cap is a Basic part already on the
  board (no new feeder), about $0.16. Net about the same.
- **Feeder loading:** 3 fewer unique parts at $1.53 each, about −$5.
- **Small-drill surcharge:** none (pd12v6 pays $37 for its three 0.25 mm vias).
- **Bare PCB:** the same price bracket. Both are under 50 × 50 mm, and Standard PCBA panelises both.

## Ordering (JLCPCB), in progress 2026-10-14

Files: `hw/scripts/fab_export.sh pd12v6mini` writes the gerber zip, `bom_jlc.csv` and `cpl_jlc.csv` to
`hw/build/fab/pd12v6mini/`, plotted from the stored fill.

Quote so far (jlcpcb.com quote page, signed out; nothing in the cart yet):
- JLC read the zip as 4 layers, 47.5 × 25 mm.
- Settings: 10 PCBs (it sells 5 or 10), 1.6 mm, black, ENIG 1 µ", 1 oz outer / 0.5 oz inner, vias plugged
  (the default; tented is not offered on 4 layers), 0.3 mm min via, mark removed.
- **Bare PCB: $33.10** (black +$8, ENIG +$16.90). Shipping estimate: DHL $31.44.
- Assembly on, top side, **PCBA qty 8**. Economic PCBA is greyed out, so it is Standard, and JLC adds edge rails:
  the panel becomes 71.5 × 71 mm, and the PCB price rises to **$39.80** before any assembly charges.
- Next: sign in (Calum does this; agents don't enter passwords), upload `bom_jlc.csv` and `cpl_jlc.csv`, check
  part rotations in JLC's placement preview, read the assembled price, then **save to cart only** (no checkout).

Build-it-yourself parts for 8 boards from LCSC, 2026-10-14: **≈ $54.50**. This includes spares and LCSC's minimum
pack sizes; U1 alone is $22.78. LCSC itself showed 0 stock for C307331, C13585, C52923 and C25776, so a DIY order
needs equivalents for those. A stencil and the bare PCBs come on top. U1 (VQFN-HR) needs paste and a hot plate,
not an iron.

## Known limits / to check

- **Not current limited:** same as pd12v6. The TPS56637 valley limit is 6.3–8.6 A.
- **The 390 k EN resistor (C25782) has only ~2.7 k in stock.** Plenty for 8 boards, but no Basic part
  exists for it. A FOJAN equivalent (C2909352) has 478 k in stock.
- **Black mask on 4 layers likely forces JLC Standard PCBA** (Economic is green-only on 4-layer).
- **Inductor ratings are from the PROD datasheet** (LCSC): 6.8 µH ±20 %, DCR 11 typ / 13 max mΩ, Irms 10 A
  (40 °C rise), Isat 12.5 A (30 % drop), 6.0 mm tall max. PROD is a small maker; COILMX MSY6060-6R8M-V
  (C55251214, 12 A, 17 mΩ, 6.7 × 6.5 mm) is a backup of the same size; it would need its own footprint.
