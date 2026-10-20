# Motor and signal harness

**Provisional arrangement, 2026-10-20.** A two-wire inline motor disconnect
in the upper bay avoids the large mating corridor of a PCB Micro-Fit. The
encoder has its own small four-way PicoBlade PCB port; an optional three-way
PicoBlade port serves a reference sensor. Factory programming uses pads.

## Motor pair

Use a [Molex2147561021](https://www.molex.com/en-us/products/part-detail/2147561021)
150 mm female pigtail on the controller and one half of a
[2147571021](https://www.molex.com/en-us/products/part-detail/2147571021)
150 mm male-to-male cable on the motor. Cutting the latter produces two roughly
75 mm male tails before stripping allowances. Both are 18 AWG UL1061; no owner
crimp tool is required. The motor end may need insulated splices to the existing
motor lead rather than soldering directly onto its unknown encoder assembly.
Keep the two motor wires together and retain them independently of solder joints.

The manufacturer's current product information lists 8.5 A maximum per contact.
This is not a hot-enclosure continuous-current guarantee. Our 4 A pack-path and
approximately 3.4 A motor-current planning envelopes still require contact,
wire and solder-temperature tests. Motor peak/stall current is not measured.

The [43025 housing drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/430/43025/430250600_sd.pdf)
shows **24.77 mm inline mated axial length**. The current product-specification
recommendation of 12.7 mm relaxed wire at each end gives about 50.17 mm straight
space before bends. Do not reuse the 17.56 mm PCB-header dimension here. An
initial 25.5 × 8.5 × 11.2 mm housing reservation is conservative planning, pending
exact cable male-housing/ear variant confirmation and latch access; it is not
a qualified fit. The preterminated male cable is documented as mating with
43025 receptacles in the [manufacturer-authored cable sheet](https://www.ic-components.cz/files/2d/2147571021.pdf).

Number both mating contacts and continuity-check each complete harness. Motor1
and motor2 are reversible H-bridge outputs; neither is logic ground. Connectors
are unplugged with motor drive disabled and external power disconnected.
Different circuit counts reduce accidental full mating with the six-way pack
plug but do not prove every partial or forced engagement impossible. Labels,
retention and an assembly continuity fixture remain necessary.

## Encoder and optional home

The encoder PCB header is 532610471, JLC **C696092**. Contacts are 1 ground,
2 switched encoder supply, 3 channel A, 4 channel B. The three-way 532610371 home
header uses 1 ground, 2 NC/reserved, 3 dry-contact sense. The present controller does not supply a powered home sensor. Actual supply/logic compatibility
and the motor's pin identity remain bench gates. The controller currently
plans a separately switched 5 V encoder rail limited by a 30 mA planning budget.

A stocked [151340402](https://www.digikey.com/en/products/detail/molex/0151340402/6198148)
150 mm female-to-female four-way cable is 28 AWG. Cutting at the middle yields
two short pigtails; if the route needs more than roughly 75 mm, retain one end
and remove only the far plug instead. The 300 mm 151340403 would yield longer
paired pigtails but is currently out of stock, so it is not the purchasing
baseline. The manufacturer's 15134 drawing maps contacts in reverse order
between its two ends. **All wires are black: identify each cut tail by
continuity, never by left-to-right appearance.**

The exact [Molex cable drawing, Rev B1](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/151/15134/151340402_sd.pdf)
specifies UL1061 wire and contact 500588000 but does not dimension the wire OD.
That [contact's current manufacturer specification](https://www.molex.com/en-us/products/part-detail/500588000)
accepts 0.50–1.00 mm insulation. A 1.00 mm per-wire allowance is therefore a
conservative compatibility-based planning bound, not a measured cable OD.
Actual bundle, strain-relief and bend fit still need checking.

Optional home cabling can use a 151340302 150 mm three-way cable with the same
controlled cutting/continuity process. Sensor selection and whether it is
needed in each unit remain open. PicoBlade is polarized and friction-latched;
it has no alternate key code distinguishing the optional home and encoder
families. Keep their three-/four-way assignments and labels distinct.

## Dated parts budget

Prices below are observed US catalogue prices, not an order or allocated stock.
JLC observations are recorded in `bom/electronics-harness-sourcing.json`.
Overseas stock does not mean in-house inventory; final assembly quotation,
feeder and loss quantities still apply.

| Item | Observed availability | Small quantity price |
|---|---|---:|
| 532610471 / C696092 encoder header |37,635 JLC overseas, Economic/Standard SMT |$0.1497 |
| 532610371 / C293630 home header |26,065 JLC overseas, Economic/Standard SMT |$0.1476 |
| [2147561021](https://www.digikey.com/en/products/detail/molex/2147561021/12180584) female motor pigtail |799 DigiKey |$2.38 |
| [2147571021](https://www.digikey.com/en/products/detail/molex/2147571021/12180297) male-to-male motor cable |3,567 DigiKey; two cut tails |$2.02 |
| [151340402](https://www.digikey.com/en/products/detail/molex/0151340402/6198148) encoder cable |5,153 DigiKey |$4.26 |

For eight units, eight female motor pigtails plus four male-to-male cables cost
$27.12 before shipping/tax, and yield eight inline pairs. Encoder cable cost is
$17.04 if each 150 mm cable can make two usable tails, or $34.08 if each unit
needs a nearly full-length tail. Soldering, splices, sleeves, strain relief,
optional home cables, setup fees and wastage are additional.
