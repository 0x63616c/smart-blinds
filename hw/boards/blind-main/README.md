# Integrated controller study

The main circuit contains **196 footprints and 609 independently checked logical
pin identities**: 194 purchased parts and two bare motor-wire solder landings.
Repeated ground/thermal pads are checked for consistent net identity and counted
once per physical pad number. Eight separately reviewed circuit blocks are preserved.

The current **54 × 68.5 mm**, four-layer placement has an underside USB-C tab,
a keyed protected-pack header, retained motor solder tails, encoder connector,
optional dry-contact input and two side switches. Its black mask is a design
preference; the final assembly service, panel and price remain unquoted.

Independent boundary checks keep protected PACK separate from charger SYS,
raw USB separate from the eFuse output, and the factory PD bus separate from
the host/gauge bus. The reset-gated encoder rail feeds the encoder port.
Home pin 2 is isolated/reserved; only pins 1 (ground) and 3 (contact) are used.
BQ25798 pin 29 is an elongated perimeter PMID lead, not an exposed ground pad.

Normal and frozen builds, twenty integration tests, manufacturer land-pattern
checks, explicit placement and RF-rule checks pass locally. Injected wrong rails,
swapped ports and shorted signals are rejected. The actual KiCad placement check
has no reported courtyard overlap or keepout infringement, but 98 inherited
footprints lack courtyards; full clearance coverage is still being completed.
It remains **entirely unrouted**;
manufacturing rules, silkscreen cleanup, power/thermal layout, RF/EMI and
prototype qualification remain unfinished. Passing these checks does
not establish physical function or fabrication readiness.

The [complete native KiCad hierarchy](../../schematics/blind-main/README.md) now
contains eleven sheets. Its independently exported netlist matches all 609 pin
identities and all 142 nets. Nine fault-injection tests pass; seven exact ERC
findings remain documented.

The thermal latch independently gates motor permission and pulls the shared driver
fault line low; firmware cannot distinguish those two faults on that pin alone.
The regenerative clamp remains a conditional pulse design, with sustained
backdrive and actual thermal performance unresolved.

```sh
ato build hw/boards/blind-main -b main-test --frozen -v
python3 hw/boards/blind-main/check_main.py
python3 tools/check_main_placement.py
python3 -m unittest discover -s hw/boards/blind-main -p 'test_*.py' -v
```

[Placement evidence](../../../docs/electrical/main-placement.md) ·
[Motor and signal harness](../../../docs/electrical/motor-signal-harness.md) ·
[Protected-pack connection](../../../docs/electrical/battery-connector.md).
