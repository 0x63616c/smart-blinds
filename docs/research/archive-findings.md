# Recovered evidence, not an inherited design

Archive snapshot: `0x63616c/github-archive` at `26769e539743604a34cc46ca228d470a0e8e63a7`.
The owner explicitly requested a fresh design. Old selected chips, controller modules, holder
footprints, enclosure meshes and claims of completion are not accepted requirements.

| Finding | Evidence / confidence |
|---|---|
| Chain beads 4.5 mm; centre pitch 6 mm | Owner-entered measurements, September 2026; not independently checked |
| Linking cord about 1 mm maximum; no separate coupler reported | Owner estimate; verify across all seven blinds |
| Chain strands lie in a plane perpendicular to wall | Archived owner description; verify each installation |
| About 5 lbf peak pull on worst blind | Archived design-decision note; original measurement data not recovered |
| Tallest travel about 10 ft / 3048 mm | Approximate owner report |
| 100 mm chain motion gave 100–120 mm fabric motion | Recorded owner measurement; no complete travel mapping |
| Recfountik 12 V / 111 RPM encoder motor | September 19 purchase record plus current owner screenshot |
| Generic motor CAD was for a 100 RPM variant | Exact fit and redistribution permission unverified; do not reuse as proven geometry |
| Holder drawing 83 × 23.8 mm | Height missing; 75 mm terminal annotation conflicts with 37.85 + 38.15 = 76 mm |

Sources:

- [Entered chain measurements](https://github.com/0x63616c/github-archive/blob/26769e539743604a34cc46ca228d470a0e8e63a7/0x63616c/smart-shades--2026-09-24-145605/docs/entered-measurements.json)
- [Dimensions and their original qualifiers](https://github.com/0x63616c/github-archive/blob/26769e539743604a34cc46ca228d470a0e8e63a7/0x63616c/smart-shades--2026-09-24-145605/docs/dimensions.json)
- [Later motor/gauge handoff](https://github.com/0x63616c/github-archive/blob/26769e539743604a34cc46ca228d470a0e8e63a7/0x63616c/smart-blinds--2026-09-24-142826/docs/handoffs/2026-09-19-gauge-and-motor.md)

The older Amazon listing B0GTN399G7 is not reliable identification of the later Recfountik purchase.
Do not copy its generic pinout, dimensions or stall current onto the owned motor without verification.
No verified encoder voltage/counts, stall current or complete motor mounting dimensions were found.

Packmule's integrated-board approach is an example to reassess, not a circuit to copy. Its reported
deep-sleep current is not evidence of connected Wi-Fi runtime. Older Smart Shades/Benchtop pack
arrangements and part counts have also been superseded by the current eight-unit/3S2P brief.
