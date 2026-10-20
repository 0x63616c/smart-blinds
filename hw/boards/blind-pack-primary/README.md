# Primary retained carrier

**UNVERIFIED, unrouted circuit checkpoint.** This is the primary of two
86×104 mm planning boards inside one screwed, insulated pack cassette. It has
three MYOUNG holders, one 3 A positive-branch fuse per holder, the MAX17320
gauge/protection circuit, and solder landings for the retained wiring.

`protection.ato` preserves the checked 27-component core of the earlier
`blind-carrier` study. The independent pack check compares every physical pin
against that earlier contract and checks the new holder/fuse partition.
The primary BOM contains 33 purchased components; its 17 solder features are
not purchased components. The compiled board has 50 electrical footprints and 120 pins, plus four
board-only NPTH mounting holes. The [placement study](../../placement/blind-pack/README.md)
puts the holder-facing components on the outward front face of the cassette.

The four `link_*` pads permanently join the identically named companion pads:
raw ground, series junction1, junction2 and raw top. They carry cell current,
not merely sense current. Use retained, insulated wire, with a controlled
continuity check before inserting any cells. **An open middle-node link can
leave companion cell voltages unmonitored. This topology is not tolerant of
an arbitrary single open interconnect.**

The only user-accessible pack cable is protected and follows the six-way
[battery harness](../../../docs/electrical/battery-connector.md):

| Cable contact | Primary solder landing |
|---|---|
| 1 | `harness_pack_positive` |
| 2 | `harness_pack_ground` |
| 3 | `harness_gauge_sda` |
| 4 | `harness_gauge_scl` |
| 5 | `harness_charger_ntc_sense` |
| 6 | `harness_charger_ntc_return` |

Gauge NTC1/2 use separate sense/return pad pairs and reference raw ground.
The charger thermistor has two separate local landings wired only to cable
contacts5/6. Its return is deliberately not tied to raw ground. The gauge alert
is a factory test landing; it is not added to the six-way cable.

Normal compilation and isolated circuit-only frozen checks passed with atopile
0.15.9. The four board-only holes are checked separately; the pinned compiler
removes them during a direct build. Follow the placement README workflow. Run
`python3 hw/sim/blind-pack/checks.py --check` from the repository for the
136-pin combined graph, holder geometry and six fault regressions. Solder
landings, holder holes and parts are placed within the mechanical allocation;
routing, thermal and assembly qualification remain open. No release or physical battery-safety claim follows
from compilation. Complete NVM settings, thermistor selection/attachment,
fuse clearing, cell matching, reverse insertion and failed-short protection
remain open.
