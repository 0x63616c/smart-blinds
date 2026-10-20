# Protected-pack pigtail

**Provisional selection:** one Molex **430450600** dual-row right-angle header
on the controller, with the ready-made **2147561061** six-way, 150 mm, 18 AWG
female-to-pigtail cable. The other end is soldered to the protected carrier
and retained by a screwed cable clamp. This needs one plug to assemble the
unit and no user crimp tool. There is no purchase or manufacture release.

The pack protection stays inside the screwed cassette. No raw cell taps leave
it. A motor connector must be mechanically incompatible with this battery
connector. The supplied wires are black: identify each by contact continuity,
then label it before soldering. The current physical contact assignment is:

| Header contact | Circuit |
| --- | --- |
| 1 | Protected PACK+ |
| 2 | Protected PACK− / controller ground |
| 3 | Gauge SDA |
| 4 | Gauge SCL |
| 5 | Separate charger thermistor |
| 6 | Separate charger thermistor return |

This is the project's assignment, not a manufacturer cable signal standard.
The independent charger thermistor remains separate from the gauge's sensors.
Do not connect the carrier's raw return to this harness. Controller pull-ups,
absent-pack handling and sensor wiring must agree with the integrated design.

## Fit and service

The [header drawing](https://store.comet.bg/download-file.php?id=29300) and
[housing drawing](https://static.maritex.eu/file/display/byVFWC0B1L2j0n10Z6Yv_MBP6mNQYIro/43025-0600.pdf)
were visually checked. The header is 12.65 mm wide; the receptacle is nominal
9.85 mm wide. Mated height is **10.81 mm**, with **11.0 mm required for latch
operation**. General drawing tolerances increase these to conservative
11.06/11.35 mm envelopes, before PCB and print variation. The initial 1.5 mm
controller shift therefore needs a tolerance-aware fit check. Full mated axial
length is 17.56 mm from the header body rear, not an extra 17.56 mm beyond its
front. The header needs a nearby board edge/notch for the overhanging plug.

[PS-43045 Rev R, 2025-11-14](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf?inline=)
requires 12.70 mm of relaxed wire after a two-to-eight-circuit housing before
an imposed bend or tie. It lists 30 mating cycles, making this a service
connection rather than the daily charging interface. Preserve this straight
fan, a bend corridor, finger/latch access and the unplug travel in the CAD.
Never pull on wires or mate/unmate under charging or motor load.

[Molex's cable data](https://www.molex.com/en-us/products/part-detail/2147561061)
confirms UL1061, 18 AWG, six loaded contacts and 150 mm length. The
[manufacturer's older product sheet](https://docs.rs-online.com/86e4/A700000006949960.pdf)
adds a 1.85 mm maximum insulation diameter; it is a maximum envelope, not a
minimum diameter for clamping. Actual wire OD, clamp compression, insulation
damage and pull retention need sample checks. The pigtail strip/tin length is
not yet verified from its assembly drawing, so pack manufacture includes a
controlled strip/tin operation if required. No hand crimping is required.

## Current and price

The PS-43045 reference table gives 6.5 A for six-circuit wire-to-board,
18 AWG, all circuits powered at 30°C rise. Our **4 A pack planning envelope**
remains conditional on ambient, copper, housing heat and contact tests.
The cable headline 8.5 A is not the assembled six-way system rating.

The [JLC header snapshot](https://jlcpcb.com/partdetail/430450600/C127367)
shows 34,749 overseas units, Economic/Standard manual assembly and $0.5556
at one / $0.451 at ten. This is not in-house SMT inventory or a final THT
quote. [DigiKey US](https://www.digikey.com/en/products/detail/molex/2147561061/12180656)
shows 3,794 cables at $4.40 each / $3.741 at ten. Eight sets cost **$39.64**
in parts; ten sets cost **$41.92**, giving two spares for $2.28 extra.
Sourcing is recorded in `bom/electronics-connectors-sourcing.json`.
Assembly labour, procurement minimums/loss, shipping, tariff and tax are extra.
The pack clamp, solder joints and inspection are also assembly operations.

The earlier single-row pair of headers with a complete cable was $53.42 for
eight and needed wider mating space. The selected pigtail removes the pack
header and its insulating-barrier conflict. Surface-mount 436500612 and WAGO
2060 alternatives were not selected; their assembly cost or process needs
were less attractive. Final quotes can still change this decision.
