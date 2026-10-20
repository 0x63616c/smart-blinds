# Component clearance envelopes

2026-10-20. Manufacturer research and assembly-clearance policy. The implementation is recorded in `hw/placement/footprint-clearances.json`; generated source outlines do not change the copper lands.

The first repair covered **15 distinct missing courtyard aliases / 98 main instances**. The subsequent [inherited-envelope repair](footprint-clearances-inherited.md) adds 30 aliases, including 80 more main-board instances. This page preserves the first batch’s dimensional evidence. The dimensions below describe the current imported footprint's **local X/Y axes before placement rotation**. Body dimensions come from manufacturer drawings or manufacturer product size tables, not STEP models. Copper bounds were independently calculated from the actual local pad positions, sizes and rotations, including custom-pad polygons and their stroke width.

Construction policy: union the stated physical package projection with **all existing copper pad extents**, expand each side by **0.25 mm**, then round outward to a **0.05 mm** grid. This is a project assembly-clearance policy, not a manufacturer land-pattern recommendation or proof of placement accuracy. Do not enlarge or otherwise alter copper as part of this courtyard change.

Two parts lack a completely bounded physical outline in the available evidence: the XUNPU switch has no general XY tolerance; onsemi's SOD-523 drawing excludes mold flash without giving its maximum. Their conditional allowances are marked explicitly below. A courtyard containing a nominal body plus an arbitrary margin must not be described as a verified manufacturer maximum.

## Implementation table

All bounds are `[xmin, ymin, xmax, ymax]` in mm, with origin and axes from the existing footprint. `Maximum package` includes terminals when they project beyond the body. `Courtyard` uses the rule above; see the special notes for conditional values.

| Actual footprint source (under `hw/parts/`) | Main instances / exact part | Maximum package in local axes | Existing copper bounds | Implemented courtyard bounds |
|---|---:|---|---|---|
| `blind-controller-common/R0402.kicad_mod` | 35 / 0402WGF1002TCE | X 1.10, Y 0.55 | `[-0.715,-0.270,0.715,0.270]` | `[-1.00,-0.55,1.00,0.55]` |
| `UNI_ROYAL_0402WGF3903TCE/R0402.kicad_mod` | 2 / 0402WGF3903TCE | X 1.10, Y 0.55 | `[-0.715,-0.270,0.715,0.270]` | `[-1.00,-0.55,1.00,0.55]` |
| `blind-usb/R0402.kicad_mod` | 1 / 0402WGF1651TCE | X 1.10, Y 0.55 | `[-0.715,-0.270,0.715,0.270]` | `[-1.00,-0.55,1.00,0.55]` |
| `UNI_ROYAL_0603WAF1001T5E/R0603.kicad_mod` | 6 / 0603WAF1001T5E | X 1.70, Y 0.90 | `[-1.155,-0.430,1.155,0.430]` | `[-1.45,-0.70,1.45,0.70]` |
| `blind-controller-common/C0402.kicad_mod` | 25 / CL05B104KB54PNC | X 1.05, Y 0.55 | `[-0.670,-0.270,0.670,0.270]` | `[-0.95,-0.55,0.95,0.55]` |
| `SAMSUNG_CL10A105KB8NNNC/C0603.kicad_mod` | 4 / CL10A105KB8NNNC | X 1.70, Y 0.90 | `[-1.100,-0.450,1.100,0.450]` | `[-1.35,-0.70,1.35,0.70]` |
| `blind-power/C1206.kicad_mod` | 15 / CL31A106KBHNNNE | X 3.40, Y 1.80 | `[-2.335,-0.865,2.335,0.865]` | `[-2.60,-1.15,2.60,1.15]` |
| `blind-usb/C1206.kicad_mod` | 2 / CL31A475KBHNNNE | X 3.40, Y 1.80 | `[-2.335,-0.865,2.335,0.865]` | `[-2.60,-1.15,2.60,1.15]` |
| `blind-usb/SOT-323-3_L2.1-W1.3-P1.32-LS2.1-BR.kicad_mod` | 1 / ESDA25W | X 2.40 terminal span, Y 2.20 body | `[-1.255,-0.910,1.255,0.910]` | `[-1.55,-1.35,1.55,1.35]` |
| `blind-encoder/SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR.kicad_mod` | 1 / TPS70950DBVR | X 3.00 terminal span; Y 3.55 including allowed body flash | `[-1.850,-1.250,1.850,1.250]` | `[-2.10,-2.05,2.10,2.05]` |
| `blind-usb/DFN1610-2_L1.6-W1.0-P1.05-RD.kicad_mod` | 1 / ESDA25P35-1U1M | X 1.65, Y 1.05 | `[-0.820,-0.450,0.820,0.450]` | `[-1.10,-0.80,1.10,0.80]` |
| `blind-control-io/SW-SMD_4P-L3.5-W3.0-P1.6-LS4.6.kicad_mod` | 2 / TS-1081S-AC01326 | No declared XY maximum. Nominal overall `[-2.30,-1.50,2.30,2.25]` includes actuator | `[-2.600,-1.300,2.600,1.300]` | **Conditional** `[-2.85,-1.85,2.85,2.60]`: adds assumed 0.10 mm per physical side before the separate 0.25 mm clearance |
| `blind-usb/VQFN-10_L2.0-W2.0-P0.45-TL.kicad_mod` | 1 / TPS259470LRPWR | X 2.10, Y 2.10 | `[-1.270,-1.250,1.260,1.250]` including custom polygon strokes | `[-1.55,-1.50,1.55,1.50]` |
| `blind-usb/SOD-523_L1.2-W0.8-LS1.6-RD.kicad_mod` | 1 / RB521S30T1G | X 1.70 terminal span; Y 0.90 body **excluding unspecified flash** | `[-0.950,-0.180,0.950,0.180]` | **Conditional** `[-1.20,-0.80,1.20,0.80]`: adds assumed 0.10 mm per body side before separate clearance. Unqualified drawing-only result would be `[-1.20,-0.70,1.20,0.70]` |
| `blind-usb/QFN-24_L4.0-W4.0-P0.50-BL-EP2.8.kicad_mod` | 1 / STUSB4500QTR | X 4.05, Y 4.05 | `[-2.350,-2.350,2.350,2.350]` | `[-2.60,-2.60,2.60,2.60]` |

The main PCB still carries legacy library aliases for some common parts. Its `fp-lib-table` resolves `UNI_ROYAL_0402WGF1002TCE:R0402` and `SAMSUNG_CL05B104KB54PNC:C0402` into `blind-controller-common`, and `SAMSUNG_CL31A106KBHNNNE:C1206` into `blind-power`. Update the resolved source and its `.pretty` counterpart, not the preserved e8s reference footprint merely because the PCB alias has the older name.

## Manufacturer evidence and axis interpretation

### Royalohm / UNI-ROYAL chip resistors

[Royalohm thick-film chip resistor manufacturer sheet](https://www.royalohm.com/assets/pdf/products/smd/1.pdf), PDF p1, printed catalog p10:

- Imperial 0402 (metric 1005): L = 1.00 +/-0.10, W = 0.50 +/-0.05, H = 0.35 +/-0.05 mm.
- Imperial 0603 (metric 1608): L = 1.60 +/-0.10, W = 0.80 +/-0.10, H = 0.45 +/-0.10 mm.
- The generic package sheet applies across these resistance values. Do not confuse the imperial type row with its following metric-size row.
- Existing two pad centres lie on local X (0402 +/-0.43; 0603 +/-0.75), so **L is X and W is Y**. Wraparound terminals are part of the stated overall chip dimensions.
- This is dimensional family evidence. It is not a new electrical-rating or lifecycle review. The downloaded primary sheet does not show a revision date on the dimensional page.

### Samsung MLCCs

Current manufacturer size tables identify the exact suffix families and explicitly list the selected package codes:

- [CL05B104KB54PNC](https://product.samsungsem.com/mlcc/CL05B104KB54PN.do): L 1.00 +/-0.05, W 0.50 +/-0.05, T 0.50 +/-0.05 mm.
- [CL10A105KB8NNNC](https://product.samsungsem.com/mlcc/CL10A105KB8NNN.do): L 1.60 +/-0.10, W 0.80 +/-0.10, T 0.80 +/-0.10 mm.
- [CL31A106KBHNNNE](https://product.samsungsem.com/mlcc/CL31A106KBHNNN.do): L 3.20 +/-0.20, W 1.60 +/-0.20, T 1.60 +/-0.20 mm.
- [CL31A475KBHNNNE](https://product.samsungsem.com/mlcc/CL31A475KBHNNN.do): same declared dimensional limits as the 10 uF 1206 above.

In all four footprints the terminal centres are along local X. Thus **L is X, W is Y**, and the end terminations are included in L. The 1206 maximum body width is 1.80 mm, slightly greater than the 1.73 mm pad width; use the former in the union. Samsung describes its web data as design-reference data subject to change; retain an approved production part specification before fabrication.

### ESDA25W SOT323-3L

[ST ESDAxxxWx datasheet, Rev 2](https://www.st.com/resource/en/datasheet/esdaxxxwx.pdf), p7, section 3.1: D max 2.20, E max 1.35, H max 2.40, A max 1.10 mm. The old `esda25w.pdf` endpoint failed during this review; the live family datasheet is the manufacturer source.

The two pins on one side of the imported footprint sit at X +0.84, Y +/-0.66; the third sits at X -0.84, Y 0. Pad rotations are 90 degrees, so the actual pad span is 2.510 by 1.820, not the unrotated size tuple. **H is local X; D is local Y.** The body alone is X 1.35 by Y 2.20. The manufacturer drawing gives no additional mold-flash exclusion in this dimensional table.

### TPS70950DBVR SOT-23-5

[TI TPS709 datasheet](https://www.ti.com/lit/ds/symlink/tps709.pdf), local `work/datasheets/tps709.pdf`, PDF p33, DBV0005A, drawing 4214839/K 08/2024:

- Overall terminal span 2.60--3.00 mm; body width 1.45--1.75 mm.
- Body length 2.75--3.05 mm; maximum height 1.45 mm.
- **Note 4 excludes mold flash/protrusions/gate burrs from the body dimensions and permits 0.25 mm per side.** Use 3.55 mm maximum occupied body length for clearance; body width including this allowance is 2.25 mm, still inside the 3.00 mm terminal span.
- Existing pad columns lie at X +/-1.30 with rows at Y -0.95, 0, +0.95. Therefore **terminal span and body width are local X; long body length is local Y**. This is why the final courtyard is taller than a nominal 3.05 mm body calculation.

### ESDA25P35-1U1M QFN-2L

[ST ESDAxxPxxx-1U1M datasheet, DS14419 Rev 4](https://www.st.com/resource/en/datasheet/esda25p35-1u1m.pdf), p9, Table 11 and Figure 13: D max 1.65, E max 1.05, A max 0.60 mm. Revision history says the mechanical table changed in March 2025; use this revision rather than older copied nominal bounds.

Existing terminal centres are X +/-0.52; the pad size 0.90 by 0.60 is rotated 90 degrees. The resulting copper projection is X +/-0.82, Y +/-0.45. **D is X, E is Y.** Body, rather than pads, determines both axes of the union.

### XUNPU TS-1081S-AC01326 side switch

Local manufacturer-authored family drawing `work/datasheets/TS-1081S-AC01326.pdf`, p1, visually inspected through `TS-1081S-AC01326.png`; obtained through the [exact JLC listing](https://jlcpcb.com/partdetail/XUNPU-TS_1081SAC01326/C720493). Its branding is XUNPU and its printed domain is xunpudianzi.com.

- Body nominal 3.50 by 3.00 mm; terminal-to-terminal nominal span 4.60 mm.
- Full depth including the unpressed actuator is nominal 3.75 mm.
- Code `013` selects nominal 1.30 mm height. AC variant has two 0.60 mm locating posts.
- Terminal centre rows are Y +/-0.80 and columns X +/-2.00 in the imported footprint. The two locating holes are Y +/-0.90. The imported actuator silk is on **+Y**, agreeing with the family drawing orientation.
- With the body centred at Y = 0, its rear is -1.50 and the actuator's nominal forward extreme is -1.50 + 3.75 = **+2.25**. The existing actuator silk ends at +2.10 and must not be used as the physical limit.
- No general tolerance is stated for 3.50, 3.00, 3.75 or 4.60 in the available drawing. The proposed table's extra 0.10 mm per physical side is an explicit engineering allowance, not a sourced maximum. This produces a provisional physical projection of X +/-2.40, Y -1.60..+2.35; copper governs X.
- Keep the separate plunger/actuation corridor and the already documented 0.30 mm maximum operating-travel reservation. A courtyard does not establish switch contact pairing, insertion loads, exact actuator fit or operation life.

### TPS259470LRPWR RPW0010A

[TI TPS25947 datasheet](https://www.ti.com/lit/ds/symlink/tps25947.pdf), local `work/datasheets/tps25947.pdf`, PDF pp72--73, drawing 4225183/A 08/2019:

- Package X/Y maximum 2.10 by 2.10 mm; height maximum 1.00 mm.
- The footprint has pin 1 at upper-left, pin 4 lower-left, pin 7 lower-right, pin 10 upper-right, matching the top-view example after comparing pin numbers rather than the bottom-view package artwork.
- Both body dimensions are square, so rotation does not change the envelope. Existing pad centres 5/6 lie near X -0.23/+0.26 with long pads along Y, establishing the local axes.
- **Custom corner pads matter:** their filled polygon strokes are 0.10 mm wide. Including half that stroke produces copper bounds X -1.270..+1.260, Y -1.250..+1.250. Ignoring those polygons or looking only at each 0.01 mm custom-pad anchor would grossly understate the copper envelope.
- This review computes the current land union; it does not reapprove the exact RPW pad contour, paste or thermal routing.

### RB521S30T1G SOD-523

[onsemi RB521S30T1G datasheet](https://www.onsemi.com/pdf/datasheet/rb521s30t1-d.pdf), local `work/datasheets/rb521s30t1.pdf`, PDF p3, mechanical case 502 Issue F, document 98AON11524D dated 2024-02-08, visually inspected:

- D body maximum 1.30, E body maximum 0.90, H terminal span maximum 1.70, A height maximum 0.70 mm.
- Pad 1 cathode is at X -0.65 and pad 2 anode at X +0.65, so **H/D are local X; E is local Y**.
- Note 4 says D and E exclude mold flash, protrusions and gate burrs; the available case drawing gives no additional bound. The table's extra 0.10 mm per body side is a provisional allowance, not a manufacturer guarantee. It only changes the final Y courtyard because the copper X span already exceeds the terminal span.
- A manufacturer-controlled flash bound or received-part inspection remains necessary if claiming a complete maximum physical outline.

### STUSB4500QTR QFN-24 EP

[ST STUSB4500 datasheet](https://www.st.com/resource/en/datasheet/stusb4500.pdf), local `work/stusb4500-primary/Doc/stusb4500_datasheet_v4.pdf`, DS12499 Rev 4 pp31--32, Table 23:

- D/E maximum 4.05 by 4.05 mm; A maximum 1.00 mm. Bottom exposed pad D2/E2 maximum 2.80 by 2.80 mm.
- Existing pins 1--6 are on local +Y, pins 7--12 on +X, pins 13--18 on -Y and pins 19--24 on -X. D/E are symmetric here, so the 4.05 mm square is independent of orientation.
- Peripheral copper extends to +/-2.35 on both axes; it governs the union. The exposed pad is already entirely inside it.

## Source fingerprints

The following local PDFs were read, without modification:

| File | SHA-256 |
|---|---|
| `work/datasheets/tps25947.pdf` | `8f96de389903091650d4f462dcfad3210071c3ae7093623a7978f34baf8a65b4` |
| `work/datasheets/rb521s30t1.pdf` | `6ed625f14a4b041c539f885f623acc6a391339877726cc8140c846b02a70cd86` |
| `work/datasheets/tps709.pdf` | `8c14e3efae738a27b857b789aa87369de9037a8ef3616a9f71a423587cdc6949` |
| `work/stusb4500-primary/Doc/stusb4500_datasheet_v4.pdf` | `2e6554e27dc9af6679cb275577f10c563791799f17f6f6cddc8cb6c177d0eba7` |
| `work/datasheets/TS-1081S-AC01326.pdf` | `d88d1922544c8c7defc626142eb1b4b61d931e79635033316ffe962d98322a5b` |

The report does not certify the imported solder lands, the two provisional physical allowances, completed placement, routing, solderability or thermal performance. After implementation, rebuild the compiled instances, verify the copper graph did not change, and run complete courtyard/keepout checks on the actual placed PCB.

## Verification and placement changes

All 15 source families and their explicit library mirrors are generated by
`tools/complete_courtyards.py`. The source check is idempotent and preserves all
existing pads, nets and other drawing primitives. Compiled coverage is now
196/196 main, 50/50 primary carrier and 10/10 companion carrier. The complete
physical-pin graph was unchanged across all 15 circuit captures.

The new outlines exposed four main-board overlaps. The pack connector moved
2.2 mm in local v, with its case cable path adjusted to match. The encoder
regulator and output capacitor moved slightly to clear adjacent passives.
The encoder cable corridor now follows the modeled wire sweep plus a 0.5 mm
allowance; the separate over-board continuation has a component-height restriction.

`tools/check_footprint_clearances.py --drc` checks compiled outlines, cable
reservations and actual KiCad 10 courtyard/keepout findings on all three boards.
It rejects disabled overlap/keepout categories and includes excluded findings.
KiCad defaults missing-courtyard reporting to ignored, so complete electrical
footprint coverage is independently required by the same checker. Other
manufacturing and unrouted findings are reported explicitly, not waived.
Thirty-one fault tests cover generation, rotated/custom copper, malformed
coordinates, reserved corridors, disabled DRC categories and incomplete reports.

## Inherited-envelope repair

The subsequent audit found inherited outlines that stopped at nominal body edges
and omitted pad tips: 80 main-board instances, 24 primary-carrier instances and
three companion fuses. Manufacturer research now covers all 30 replacement aliases
in the [second dimensional record](footprint-clearances-inherited.md), including
local axes, custom copper and two further conditional molding allowances. The
combined source manifest contains 45 reviewed aliases; four package families
retain explicitly provisional bounds.

The source tool replaces only the fingerprinted original outlines and requires
matching canonical/mirror pads. It also fingerprints reviewed pad geometry for
the replacement batch. All 15 circuit captures rebuilt with unchanged electrical
pin graphs. Every compiled electrical pad is independently required to fit inside
its outline, including aliases outside the replacement list.

The main board needed 13 small part movements and retains its 54 × 68.5 mm outline,
connector/button anchors and cable reservations. Its actual KiCad DRC reports zero
courtyard/keepout findings against the corrected set. Carrier placement results
are recorded separately in `hw/placement/blind-pack/`. Manufacturing, thermal,
physical tolerance and the four conditional package bounds remain open; these
checks do not promote an unrouted study into a fabrication-ready board.
