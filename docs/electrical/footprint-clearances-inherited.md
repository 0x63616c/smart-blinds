# Inherited component clearance envelopes

2026-10-20. Manufacturer evidence for the second source-outline repair.
The first missing-outline batch is recorded in [Component clearance envelopes](footprint-clearances.md).
The authoritative implementation is [the clearance manifest](../../hw/placement/footprint-clearances.json).

`work/existing-courtyard-audit.json` identifies 80 instances / 23 aliases on the
main board, 24 / 10 on the primary carrier and 3 / 1 on the companion. The union
is **30 aliases**. Those counts are a copper-containment audit, not a claim that
all other physical-body envelopes are correct. Exact purchased part numbers
below were read from the current boards' `Partnumber` properties.

The implementation replaces a reviewed nominal-body courtyard with
the union of manufacturer maximum body/lead projection and actual copper,
expanded by 0.25 mm per side and rounded outward to 0.05 mm. Preserve the
complete original pad AST and circuit graph. Inspect local axes: the compiler's
pad rotation includes its parent footprint rotation, whereas source library
pad rotation is local. Do not apply source rotation math directly to a compiled
pad without removing the parent angle.

## Priority passive groups

All dimensions and bounds below are in footprint-local XY, before placement.
For these two-terminal chip footprints the terminal centres run along X, so
manufacturer L is X and W is Y. “Candidate” distinguishes a calculated assembly outline from physically verified
component fit. All package allowances remain explicit.

| Alias/group | Purchased parts and source basis | Maximum body X × Y, mm | Actual pad bounds ±X, ±Y, mm | Candidate courtyard ±X, ±Y, mm |
|---|---|---:|---:|---:|
| `blind-carrier:R0402` | Royalohm 0402WGF100JTCE, 0402WGF1500TCE | 1.10 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-control-io:R0402` | Royalohm 0402WGF1001TCE, 1003TCE, 220JTCE, 4701TCE | 1.10 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-core:R0402` | Royalohm 0402WGF1201TCE | 1.10 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-power:R0402` | Royalohm 0402WGF1000TCE, 3012TCE, 3302TCE, 5231TCE **and Yageo RC0402FR-0713K7L** | 1.10 × 0.55 union; Yageo alone is 1.05 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-regen:R0402` | Royalohm 0402WGF3303TCE, 8202TCE | 1.10 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-regulator:R0402` | Royalohm 0402WGF2612TCE | 1.10 × 0.55 | 0.713, 0.270 | 1.00, 0.55 |
| `blind-regen:R0603` | Royalohm 0603WAF1005T5E | 1.70 × 0.90 | 1.153, 0.432 | 1.45, 0.70 |
| `blind-carrier:R1206` | Royalohm 1206W4F1000T5E | 3.25 × 1.70 | 2.084, 0.8505 | 2.35, **1.15** |
| `blind-supervisor:C0402` | Samsung CL05C121JB5NNNC | 1.05 × 0.55 | 0.670, 0.270 | 0.95, 0.55 |
| `blind-carrier:C0805` | Samsung CL21B474KBFNNNE | 2.10 × 1.35 | 1.705, 0.675 | 2.00, 0.95 |
| `blind-power:C0805` | Samsung CL21A226MAYNNNE, CL21A475KAQNNNE | **2.20 × 1.45** union | 1.705, 0.675 | 2.00, **1.00** |
| `blind-core:C0402` | FH 0402B223K500NT | 1.05 × 0.55 | 0.670, 0.270 | 0.95, 0.55 |
| `blind-power:C0402` | FH 0402B102K500NT and 0402B473K500NT | 1.05 × 0.55 | 0.670, 0.270 | 0.95, 0.55 |

The R1206 pad width is 1.701 mm. Its half-width plus 0.25 mm is 1.1005 mm,
which rounds outward to 1.15 mm. Do not silently round it down to 1.10.

Primary sources:

- [Royalohm thick-film chip resistor sheet](https://www.royalohm.com/assets/pdf/products/smd/1.pdf).
  The 0402, 0603 and 1206 rows give L/W maxima above. The 0402/0603 dimensions
  were directly reviewed in the first batch; the indexed manufacturer 1206
  table gives L=3.10±0.15 and W=1.55+0.15/−0.10. The current direct endpoint
  intermittently times out, so retain the downloaded manufacturer sheet when
  it can be recovered rather than substituting a different resistor family.
- [Exact Yageo RC0402FR-0713K7L sheet](https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-0713K7L)
  gives L=1.00±0.05 and W=0.50±0.05. This mixed-manufacturer alias is bounded by
  the slightly longer Royalohm maximum, but that conclusion is now sourced.
- [Samsung CL05C121JB5NNNC](https://product.samsungsem.com/mlcc/CL05C121JB5NNN.do):
  L=1.00±0.05, W=0.50±0.05.
- [Samsung CL21B474KBFNNNE](https://product.samsungsem.com/mlcc/CL21B474KBFNNN.do):
  L=2.00±0.10, W=1.25±0.10.
- [Samsung CL21A226MAYNNNE](https://product.samsungsem.com/mlcc/CL21A226MAYNNN.do):
  L=2.00±0.20, W=1.25±0.20.
- [Samsung CL21A475KAQNNNE](https://product.samsungsem.com/mlcc/CL21A475KAQNNN.do):
  L=2.00±0.15, W=1.25±0.15. The 22 µF part is therefore the governing member
  of `blind-power:C0805`; 0805 nominal size alone is insufficient.
- [FH 0402B223K500NT](https://fhcomp.com/zh-cn/product_info/?prod_code=0402B223K500NT),
  [FH 0402B102K500NT](https://www.fhcomp.com/en/product_info/?prod_code=0402B102K500NT),
  and [FH 0402B473K500NT](https://fhcomp.com/en/product_info/?prod_code=0402B473K500NT):
  exact manufacturer tables all give L=1.00±0.05, W=0.50±0.05 mm. The 1 nF
  page was directly retrieved; the 47 nF English page is available as indexed
  manufacturer content although direct access times out. This resolves the
  earlier missing evidence without assuming the 22 nF sibling's dimensions.

## Gauge and branch fuse

### Littelfuse 0451003.MRL — `blind-carrier:FUSE-SMD_L6.1-W2.7`

The indexed [manufacturer 451/453 datasheet](https://www.littelfuse.com/~/media/electronics/datasheets/fuses/littelfuse_fuse_451_453_datasheet.pdf.pdf)
gives body length 6.10±0.20 and width/height 2.69±0.25 mm, i.e. a **6.30 ×
2.94 mm** maximum XY projection. Local X runs between the two terminals.
Current copper bounds are ±3.435 X and ±1.575 Y. Copper governs both axes,
so the proposed courtyard is **±3.70 X, ±1.85 Y**.

The original body-only courtyard ±3.05 X / ±1.35 Y omits both termination
pads. The direct manufacturer download currently returns 403; its indexed
manufacturer content is available, but the dimensional page should still be
visually recovered before source replacement. This is no new fuse-current,
clearing-time, holder-heating or safety qualification.

### MAX17320G22+ — `blind-core:QFN-24_L4.0-W4.0-P0.50-BL-EP2.6`

The current [MAX17320 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)
identifies package **T2444+4C**, outline **21-0139**, and land pattern
**90-0022**. The primary Rev12 copy is already in
`work/datasheets/max17320-rev12.pdf`. The [manufacturer land-pattern drawing](https://mds.analog.com/api/public/content/tqfn_90-0022.pdf)
lists T2444-4C and gives a 2.60 mm exposed pad, 0.50 mm pitch and peripheral
pad positioning. This proves package association; it is not itself a maximum
body tolerance table.

The exact [manufacturer outline 21-0139](https://mds.analog.com/api/public/content/tqfn_21-0139.pdf)
was subsequently recovered as **Rev V, three pages**, saved to
`work/datasheets/max-outline-courtyard.pdf`. Visual inspection of page 2 gives
D/E=3.90/4.00/**4.10 mm** for the 24-lead package. Page 3 explicitly includes
T2444-4C (2.45/2.60/2.63 mm exposed pad), and page 2 note 14 says dimensional
values are the same for leaded and RoHS “+” package codes. There is no excluded
mold-flash allowance in these notes. The package maximum body bounds are
therefore **[-2.05,-2.05,2.05,2.05] mm**.

Current copper extends to **±2.2425 mm on both axes**, whereas the imported
courtyard is only ±2.0 mm. Copper governs, giving the now source-backed
candidate **[-2.50,-2.50,2.50,2.50] mm**. Renders of all three primary pages
are under `work/courtyard-research/max-outline-courtyard-*.png`.

Placement implication: enlarging the gauge courtyard will likely conflict with
nearby `c_supply` and other lower-strip parts even though the current DRC has
no reported courtyard collision. Preserve the just-frozen placement checkpoint
and move these parts only in the next coordinated repair batch.

## One reusable IC package conclusion

`blind-regen:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR` contains TPS70933DBVR.
It uses the same TI DBV0005A package as TPS70950DBVR already researched in
`work/electronics-courtyard-research.md`. Source pad bounds are ±1.85 X /
±1.25 Y. TI drawing 4214839/K 08/2024, datasheet p33, allows 0.25 mm body
flash per side: maximum terminal projection X=3.00 and body projection
Y=3.55 mm. The candidate courtyard is **±2.10 X / ±2.05 Y**.
Do not copy that envelope to DBV six-pin or unrelated SOT-23 parts without
their own dimensional review.

## Remaining package envelopes — completed research

The machine-readable `hw/placement/footprint-clearances.json` records
all 30 aliases, explicit source/mirror paths, exact MPNs, sources/pages, body
bounds, pad bounds and independently calculated candidate courtyards. Bounds are local XY; pin/pad fingerprints prevent silent substitution during regeneration.
The following table completes the 14 aliases not covered above. Manufacturer
sources are linked per row; detailed axis and molding notes follow.

| Alias | Manufacturer maximum/allowance basis | Candidate courtyard bounds [xmin,ymin,xmax,ymax], mm |
|---|---|---|
| `blind-carrier:PDFN-8_L3.3-W3.3-P0.65-BL` | [AON7400A](https://www.aosmd.com/sites/default/files/res/packaging_information/DFN3x3A_8L_EP1_P.pdf): PO-00047 version I, single page; source terminal rows along Y; D along X, E/E1 along Y. | [-1.95, -1.95, 1.95, 1.95] |
| `blind-carrier:R2512` | [WSL2512R0100FEA](https://www.vishay.com/docs/30100/wsl.pdf): Document30100 revision23-Nov-2023 p2 WSL2512 L6.35+/-.254 W3.18+/-.254; terminal axis X. | [-3.95, -2.1, 3.95, 2.1] |
| `blind-carrier:SOD-123_L2.8-W1.8-LS3.7-RD` | [BZT52C4V7](https://datasheet.lcsc.com/datasheet/pdf/748504625e418aa84c5305d597e87d6d.pdf): JSCJ BZT52C Rev2.1 p4; terminal E1=3.85 max along X; body D=1.70 max along Y. | [-2.45, -1.1, 2.45, 1.1] |
| `blind-control-io:SOT-363_L2.0-W1.3-P0.65-LS2.1-BR` | [SN74LVC2G17DCKR](https://www.ti.com/lit/ds/symlink/sn74lvc2g17.pdf): PDF p20 DCK0006A 4214835/D 11/2024; two pad columns X; body long axis Y. | [-1.6, -1.5, 1.6, 1.5] |
| `blind-control-io:SOT-553-5_L1.6-W1.2-P0.50-LS1.6-TL-1` | [TPD2E2U06DRLR](https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf): PDF p17 DRL0005A 4220753/E11/2024; pad columns X; body length Y. | [-1.2, -1.25, 1.2, 1.25] |
| `blind-core:CAP-SMD_BD6.3-L6.6-W6.6-LS7.3-FD` | [UCM1E221MCL1GS](https://www.nichicon.com/getmedia/f527b3ab-1197-491e-9b2c-7ca4b61e1e20/e-ucm5-11.pdf): CAT.8100O p1 standard6.3x7.7; exact part UCM1E221MCL1GS p2. Local nichicon-ucm-courtyard.pdf. | [-4.7, -3.65, 4.7, 3.65] |
| `blind-core:VQFN-HR-9_L2.0-W1.5-P0.50-TL` | [TPS62902RPJR](https://www.ti.com/lit/ds/symlink/tps62902.pdf): PDF p44 RPJ0009A4224505/A10/2018; body1.6X x2.1Y; source body centre(0,+.09). | [-1.25, -1.4, 1.25, 1.4] |
| `blind-power:IND-SMD_L7.2-W6.6_GPSR07X0` | [CYA0630-2.2UH](https://datasheet.lcsc.com/datasheet/pdf/e3a633cb354465e60aea5c2a2be3f1c0.pdf?productCode=C5189746): SHOUHAN exact CYA0630-2.2UH PDF p2; A7.0+/-.3 terminal axis X, B6.6+/-.3 along Y. Local shouhan-cya0630.pdf. | [-4.3, -3.7, 4.3, 3.7] |
| `blind-power:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR` | [AO3400A, MMBT3906LT1G](https://www.aosmd.com/sites/default/files/res/package/SOT23.pdf): AOS PO-00001 N p1 and onsemi MMBT3906 case318 AU14-Aug-2024 p9; local terminal columns run X, body D runs Y. | [-1.75, -1.95, 1.75, 1.95] |
| `blind-regen:SOT-5X3-6_W1.6-L1.2-P0.50-LS1.6-BL` | [TMP302ADRLR](https://www.ti.com/lit/ds/symlink/tmp302.pdf): PDF p17 DRL0006A4223266/F11/2024. Source terminal rows run Y, 90 degrees to drawing; local body long X. | [-1.25, -1.2, 1.25, 1.2] |
| `blind-regen:TSOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR` | [TLV6710DDCR](https://www.ti.com/lit/ds/symlink/tlv6710.pdf): PDF p25 DDC0006A4214841/E08/2024; lead X/bodylongY3.05 max. | [-1.85, -1.8, 1.85, 1.8] |
| `blind-supervisor:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BR` | [SN74AUP1G97DCKR](https://www.ti.com/lit/ds/symlink/sn74aup1g97.pdf): PDF p27 DCK0006A4214835/D11/2024; padcolumns X, bodylongY. | [-1.5, -1.5, 1.5, 1.5] |
| `blind-supervisor:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR` | [TPS3808G33DBVR](https://www.ti.com/lit/ds/symlink/tps3808.pdf): PDF p36 DBV0006A4214840/G08/2024; terminalspanX3.0/bodylengthY3.05. | [-2.15, -2.05, 2.15, 2.05] |
| `blind-supervisor:VSON-10_L3.0-W3.0-P0.50-TL-EP` | [TPS3430WDRCR](https://www.ti.com/lit/ds/symlink/tps3430.pdf): PDF p34 DRC0010J4218878/B07/2018; square body max3.1. | [-2.15, -2.05, 2.15, 2.05] |

Axis and tolerance decisions:

- AON7400A: PO-00047 version I explicitly excludes mold gate burr, flash and
  cutting burr, without a numeric maximum. D/E body maxima are 3.10 mm;
  terminal projection D4 is 3.20 X and E1 is 3.30 Y. The proposed 3.40 mm
  square includes an **engineering allowance of 0.15 mm per body side**.
  This is conditional, not a manufacturer guarantee. The resulting 3.90 mm
  square courtyard still requires supplier/physical envelope confirmation.
- AO3400A/MMBT3906 share one footprint. AOS PO-00001 N gives terminal span
  3.00 mm along local X and body length 3.10 along Y; its stated non-lead
  flash limit is 5 mil (0.127 mm) per side, giving Y=3.354. The onsemi case
  318 issue AU (14 Aug 2024) gives D=3.04 but excludes flash/gate burr without
  a numeric bound. Allowing 0.15 mm per body side gives 3.34, inside the AOS
  bound. **That onsemi allowance is conditional**, and the combined envelope
  is not claimed to bound arbitrary burrs. Both primary pages were viewed.
- DCK: the two TI logic parts share DCK0006A drawing 4214835/D, 11/2024.
  Lead span X=2.40; body long Y=2.15 plus specified 0.15-per-side flash gives
  2.45. Their pads differ, so LVC2G17 needs ±1.60 X but AUP1G97 needs ±1.50 X.
- DRL: TPD2E2U06 has pad columns in X and long body in Y; TMP302 is rotated
  90 degrees in its source footprint. The specified 0.15-per-side flash
  applies to the drawing's 1.70 maximum body length, giving 2.00. Therefore
  the TMP302 body bound is 2.00 X ×1.70 Y, opposite TPD's 1.70 X ×2.00 Y.
- DBV: TPS70933 and TPS3808 drawings allow 0.25 mm flash per body side,
  making body long Y=3.55; lead X stays 3.00. Their copper differs, so the
  final X courtyards also differ. TLV6710's DDC drawing has no such excluded
  molding allowance and gives 3.05 maximum in both planar axes; do not copy
  DBV's allowance into a different package without evidence.
- TPS62902 RPJ: source body centre is (0,+0.09), proven by the nominal
  outline Y[-0.91,1.09] and pad row positions relative to the primary package
  centre. Maximum body is 1.60 X ×2.10 Y, hence Y[-0.96,1.14]. Recentring at
  the origin would lose the positive edge. The final rounded courtyard is
  nevertheless ±1.25 X / ±1.40 Y because copper controls its negative Y edge.
- TPS3430 DRC: body is 3.10 mm square. Its imported custom exposed pad has
  asymmetric copper bounds; the conservative union includes every custom
  primitive and stroke. The initial compiled-only audit omitted 0.05 mm of
  custom stroke on each Y side. The source check recovered exact bounds
  [-1.9,-1.755186,1.9,1.764823]; use **±2.05 Y**, correcting the initial
  ±2.00 estimate. The JSON above is corrected. Preserve the actual polygon.
- UCM1E221MCL1GS: the current Nichicon standard CL 6.3×7.7 drawing gives
  6.80 mm maximum base/can width. Conservatively add both 0.50 mm terminal
  projections along local X, giving 7.80 X ×6.80 Y; actual copper spans 8.84 X
  and governs. The standard part's height maximum is 8.00 mm. The separate
  vibration-resistant CS outline is not substituted.
- CYA0630: exact SHOUHAN source gives A7.0±0.3 along the terminals and
  B6.6±0.3 perpendicular, so max projection is 7.30 X ×6.90 Y. Copper X
  extends farther; final courtyard is ±4.30 X / ±3.70 Y. This is not the
  alternate Sunlord part's drawing.

## Two existing courtyards that already include their full envelopes

These two additional checks matter because simple pad containment
alone does not prove maximum body clearance. Both pass the proposed rule, with
no size change required. They do not need source-outline replacement and are separate from the 30 repaired aliases.

| Alias | Maximum body/terminal XY, mm | Copper bounds ±X/±Y, mm | Existing courtyard ±X/±Y, mm |
|---|---:|---:|---:|
| `blind-regen:R2512` / CRM2512-FX-10R0ELF | 6.50 ×3.30 | 3.80 /1.85 | 4.05 /2.10 |
| `blind-regulator:IND-SMD_L4.4-W4.2` / MWSA0402S-1R0MT | 4.75 ×4.45 | 2.60 /1.25 | 2.85 /2.50 |

[Bourns CRM2512 drawing](https://www.bourns.com/docs/Product-Datasheets/CRM.pdf)
p2 gives L=6.3±0.2 and W=3.1±0.2. Terminal axis is X. Its courtyard exactly
matches copper plus 0.25 mm; heat-spreading copper is a separate requirement.
[Sunlord MWSA-S catalogue](https://www.sunlordinc.com/uploads/files/20230303/MWSA-S%C2%A0series%C2%A0of%C2%A0SMD%C2%A0Power%C2%A0Inductor.pdf)
p130 (2022-10-12) gives B=4.4±0.35 along terminal axis X and A=4.2±0.25 along
Y. Copper controls X and the package controls Y; the existing rounded
courtyard contains both with the 0.25 mm margin. Both pages were visually read.

This report does not repeat the previous Micro-Fit/PicoBlade/holder/USB/core
DRV/BQ/C6 land-pattern and corridor reviews. Their established mechanical
reservations remain independent constraints; a correct source courtyard alone
does not prove whole-board packing or assembled cable fit. The source repair preserves canonical pads and connectivity; placement and DRC
checks are recorded separately after compilation.

## Library consistency

The replacement tool accepts only the fingerprinted original courtyard and pins
the reviewed source pad geometry. It refuses a divergent mirror or an unexpected
outline rather than overwriting it. Three carrier mirrors still had the old
imported fuse, AON7400A and WSL2512 lands; these were synchronized to the already
reviewed canonical pads. The side-switch mirror's two locating holes were likewise
corrected to the canonical nonplated type. Canonical copper and all circuit pin
identities are unchanged by these mirror repairs.

The compiled checker normalizes each pad angle relative to its parent footprint,
then requires every pad extent to lie inside its courtyard, including aliases
outside the replacement list. Filled custom polygons include their stroke.
Source and compiled checks are backed by fault-injection tests; they do not
resolve the four explicitly conditional package families or physical tolerances.
