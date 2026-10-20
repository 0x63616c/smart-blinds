# Trade Study: Compact supported drive and holder-tail clearance

**Date:** 2026-10-19
**Status:** OPEN

## 1. Context

The first holder study allocated 170 × 158 × 64 mm for a broad carrier and 150 × 158 × 74 mm for two stacked carriers. Those were packaging envelopes. Once a separately supported shaft gained real collars, coupling, retainers and the seller's 6 mm front boss, its 180 mm axial envelope became a poor fit for a small wall product. The user values a compact, clean white case and PCB-mounted holders that reduce pack assembly work. We therefore compare a directly supported motor shaft with the independent shaft and revisit the supposedly fixed 12 mm gap behind opposing through-hole holders.

The new `cad/source/compact_direct.scad` shows a **115 × 174 × 71 mm** candidate with two single-sided three-holder PCBs, a side-mounted 35 × 75 mm controller, underside USB-C and two vertically spaced front buttons. Untrimmed holder pins increase depth to 78 mm. The wheel, outboard bearing pod/retainer, guard, plunger and button guide are separate print-fit candidates. The pack bars, controller support, shell attachment and wiring are still allocations, not a complete fastened enclosure. No board outline or manufacturing release is frozen by this study.

## 2. Options

### A: Motor shaft with an outboard bearing, trimmed TH carriers

An 8 mm wheel fits between the motor's front boss and a 6 × 10 × 3 mm outboard bearing. Nominal X positions are: boss 76–82, exposed shaft 82–97.5, wheel 82.7–90.7, bearing 93.5–96.5 and retainer 96.5–99.5 mm. The wheel uses the seller's 5.4 mm motor flat; it is a different bore from the independent shaft's 5.5 mm flat. A removable screwed guard and the boss/pod constrain axial escape; a radial grub screw holds the wheel's nominal axial position. The exact motor geometry, D-bore fit, alignment and clamp friction require testing.

The compact fit checks use a **7 mm eccentric shaft offset clocked into Z**. A zero-offset substitution is not supported by this snapshot: its lower guard screw would cross the vertical pod-foot screw. It needs a revised small guard/pod hole pair before export, not just a change to the offset variable. The independent cartridge separately explores 0/7 mm offsets. No measured offset is claimed for the owned motors.

[NSK's miniature-bearing catalog](https://www.nsk.com/common/data/ctrgPdf/bearings/e126h.pdf) gives the 6 × 10 × 3 mm shielded MR106ZZ1 family. The current [open MR106 page](https://www.nsk.com/engineering/products/bearings/ball-bearings/deep-groove-ball-bearings/extra-small-ball-bearings-and-miniature-ball-bearings-metric-series/mr106-esm-md.html?___store=default) describes a 2.5 mm wide part, so the suffix must be checked when sourcing. A load rating for a particular NSK bearing does not establish the gearbox, shaft fit or printed bracket's capacity.

This arrangement **shares radial load with the gearbox**. In a simple two-support calculation, placing the original front support somewhere from X=76 to 82 mm, the new bearing at X=95 and the chain load at X=86.7 leaves approximately 44–64% of the chain radial force at the motor support. For the unverified 42.24 N example, that is about 18–27 N. Actual gearbox-bearing position, stiffness, runout and internal bearing loads are unknown; this is a sensitivity calculation, not a rating. A no-binding alignment check and force/temperature/endurance test are required before selecting it.

The two carrier boards are 86 × 104 mm allocations. Loaded holder height is reserved at 25 mm per side. Trimmed pins and solder fillets must project no more than **1.5 mm** from each facing board; a 1 mm rigid insulating barrier plus 0.5 mm clearance each side then permits a **5 mm board gap**. The resulting stack is 25 + 1.6 + 5 + 1.6 + 25 = 58.2 mm before case, supports and retaining bars. This is a controlled manufacturing operation, not a presumed free JLC service. There are 12 holder leads per device, or 96 for eight; manual clipping needs inspection, debris removal and time in the assembly budget.

The dimension budget is explicit rather than scaling the old case around a new motor. The boards have 4 mm corner radii and edge notches for the retaining-bar feet; the exact routed outlines still belong to the PCB/cassette integration.

| Direction | Occupied interval / allowance | Consequence |
|---|---|---|
| Height: holder | Y=14–97.8 mm, 83.8 mm long | The holder adds about 13 mm over a bare 70.8 mm cell |
| Height: carrier | Y=6–110 mm, 104 mm long | End support, interconnect/protection allocation and edge clearance add 20.2 mm beyond holder length |
| Height: motor clamps | Y=112.3–167.7 mm | 2.3 mm nominal gap from carrier; 3.9 mm to the inner top wall |
| Width: carrier | X=3–89 mm | 86 mm board, three holder positions at X=18/44/70 |
| Width: controller | PCB X=101.5–103.1; component allowance to111.1 mm | 12.5 mm from carrier FR4 to PCB; 1.5 mm from component allowance to the inner side wall |
| Depth: trimmed | 3 backplate + 2 rear clearance + 25 holder + 1.6 PCB + 5 gap + 1.6 PCB + 25 holder + 0.7 bar clearance + 2 bar + 2.7 front clearance + 2.4 wall | 71 mm total; no full-width 15 mm radio gap |
| Depth: untrimmed | Same stack with 12 mm board gap | 78 mm total |

The controller's front buttons and radio clearance fit in the allocated side space, but actual large charger capacitors, connector insertion, cassette fasteners and PCB ground layout can still change it. Retaining-bar feet and standoffs remain allocations whose strength and attachment are unfinished.

The protection capture now includes six 3 A Littelfuse 0451003.MRL branch fuses, each allocated at 6.10 × 2.69 × 2.69 mm. Their exact placement belongs to the retained carrier layout and must avoid cell-insertion load paths. The current CAD strip is only an electronics reservation. Mechanical rejection of a reversed flat-top Samsung 50E is not established by the selected holder or printed case; terminal geometry and actual holder behaviour need qualification. A closed, protected cassette does not by itself make arbitrary cell insertion safe.

The controller is edge-on in the Y–Z plane at X=101.5 mm, rather than using a 15 mm empty slab in front of every cell. Its local antenna band is reserved at the upper end (Y=71.5–78 mm), away from the underside USB metal. The former bottom-end reservation overlapped USB and was rejected. Carrier copper and other metal must remain at X≤86 mm in the local band, including screw heads; the FR4 edge can extend to X=89. Incoming wires route above Z=55.5 mm to clear the antenna’s front edge at Z=38 mm. Exact module keepout, PCB ground, connector locations and RF performance still require electrical placement and tests. Two right-angle SMT switches on that same board face the cover, allowing straight captive front plungers. The [button interface](front-button-interface.md) records the sourced switch, rear guide/positive stop and the remaining sub-millimetre tolerance qualification. The earlier side-button arrangement remains selectable in CAD.

### B: The same direct support with untrimmed TH carriers

Keep the holder's maximum 4.5 mm tails. A 12 mm gap accommodates both tails, the 1 mm barrier and 1 mm clearance each side. All other principal positions remain comparable, with the front board, retaining bars and cover moved 7 mm outward. The case becomes **115 × 174 × 78 mm**. It is a fallback when the trimming quote, process or inspection is unattractive.

Interdigitating the full-length tails could nominally reduce the gap to about 5–6 mm, but a flat middle barrier would intersect them. It would require a staggered contact layout, a shaped insulation barrier and explicit clearance to the opposite board's solder/copper under insertion loads. A 2–3 mm lateral stagger can also grow the carrier width or conflict with holder screws. This is not accepted as a shortcut before a PCB contact layout and mechanical tolerance study exist. Controlled trimming is the simpler first process candidate.

### C: Independent shaft and flexible coupling

The separately retained [drive cartridge](retained-drive-prototype.md) allocates **180 × 160 × 58 mm** with documented commercial coupling, shaft, bearings and collars. Chain radial load goes primarily into its own two bearings; the coupling still needs alignment and qualification. The purchased reference shaft stack costs roughly $25 per device before screws and prints. Smaller commodity couplings/collars could reduce axial width toward approximately 145–155 mm, but no exact qualified low-cost stack is selected. It cannot be represented as a 100 mm wide unit with the current motor body and an inline independent shaft.

### D: Overlapping shafts with a timing belt

A parallel shaft above the motor overlaps their X envelopes and avoids the long inline coupling. A sourced [110 mm, 55-tooth, 6 mm wide GT2 belt](https://shop.sdp-si.com/a-6r51m055060.html) with equal 20-tooth pulleys gives a nominal 35 mm centre distance: L=2C+40 mm. Retaining the current pack and motor positions therefore moves the narrow case toward **115 × 209 × 71 mm** before a tension adjuster/guard is resolved. That is an analytical budget, not a rendered retained belt assembly. A 170–190 mm height would require a substantive change to the pack/protection/motor overlap.

The [SDP/SI reference catalog](https://sdp-si.com/products/best-sellers.php) lists 6 mm bore, 20-tooth metal pulleys around $16 each, while the belt product page lists $7.60. These are research prices, not a best-price quote. At 1:1 ratio a 0.258 N·m shaft torque implies about 40.5 N belt tension difference at a 6.37 mm pulley pitch radius, **before** preload. A belt does not eliminate radial load on the motor and can increase it. Larger pulleys/reduction can change that balance but add size or alter speed. Tooth-load, tension, backlash, noise, life and efficiency must be checked before choosing this fallback.

### E: SMT holders

Two single-sided SMT carrier boards could avoid protruding TH pins and approach a 3 mm back gap, about 2 mm less than the trimmed TH option. A double-sided single board may save more depth, but opposing peg footprints and the 92.6 mm terminal envelope need a real layout; the previous 12 mm stagger/height allowance was not a qualified design. The sourced MYOUNG SMT holder currently requires JLC Standard assembly, while the TH part supports Economic/Standard. This can only be decided using whole-order assembly quotes, not the holder unit-price saving alone. Both candidates still lack a qualified current/retention result.

## 3. Comparison Table

Case figures are allocations, not physical measurements. A/B use the source model; C uses its retained drive and an assumed integrated allocation; D/E are explicitly analytical alternatives.

| Criterion | A: trimmed TH, direct support | B: untrimmed TH, direct support | C: independent inline shaft | D: overlapping belt shafts | E: SMT holders |
|---|---|---|---|---|---|
| Case W × H × D | 115 × 174 × 71 mm | 115 × 174 × 78 mm | 180 × 160 × 58 mm | About 115 × 209 × 71 mm | Depth potentially 2–4 mm below A; height/outline unresolved |
| Wall footprint | 200.1 cm² | 200.1 cm² | 288 cm² | About 240.4 cm² | Depends on peg/terminal layout |
| Envelope volume | 1420.7 cm³ | 1560.8 cm³ | 1670.4 cm³ | About 1706.5 cm³ | Not claimed without layout |
| Pack assembly | 96 trimmed leads across eight; two joined PCBs per unit | No pin trim; deeper case | Broad carrier possible | Same carrier work plus belt setting | Assembly tier quote needed |
| Motor radial load | Reduced but remains; actual rating unknown | Same as A | Chain carried by separate bearings | Belt preload remains on motor | Independent of holder method |
| Cost/parts | One extra bearing; price/fastener quote open | Similar parts to A | ~$25 sourced shaft stack before screws/prints | Reference pulleys + belt roughly $40 before shaft/bearings | Lower holder unit price may lose to Standard setup |
| Qualification burden | Motor-shaft support, narrow wheel, trimming, RF | Motor support, wheel, RF | Coupling alignment, shaft stack, thermal/creep | Tension, extra bearing loads, guards, wear/noise | Contact current, retention, peg layout, assembly quote |

## 4. Recommendation

**Rationale:** Develop option A as the compact prototype candidate, retain B as the manufacturing fallback and keep C as a load-path comparison. A reduces wall footprint by about 25.5% versus the first 170 × 158 mm broad study and saves 7 mm projection versus untrimmed twins. It also removes the costly external coupling/shaft/collars. The motor's own shaft is the reason the smaller outline is possible; that trade must remain visible.

**What we're giving up:** A depends on controlled lead trimming, a protected fixed interconnect between two carrier boards and successful qualification of a shared gearbox/outboard-bearing load path. It is not an independently supported drive. Front buttons need actual travel/force and tolerance qualification; the carrier/cover/controller attachment is still design work. Model intersections, mesh closure and illustrative load calculations are not physical proof.

**When to revisit:** Change the drive if the motor shaft length/fit, radial load, noise, runout or endurance test fails. Revisit B or SMT if the trimming quote/process is poor. Revisit the belt only if a qualified lower-cost stack materially improves the enclosure or a reduction ratio is required. Final PCB population, battery protection/connector placement, real RF keepouts and the thermal tests can still change the case.
