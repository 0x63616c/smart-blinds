# Design brief

Updated 2026-10-19 from the owner's current instructions. These requirements supersede archived
six-unit, modular-board, 2S3P, holder and controller decisions.

The owner authorized this GitHub repository to be public on 2026-10-19.

## Scope and acceptance target

Design a complete, costed package for two prototype units, followed by a budget for eight complete
units: seven installed and one spare. Include original CAD, print exports, schematic/PCB,
firmware, Home Assistant integration, build/calibration instructions and a reproducible validation
record. Do not buy parts or release fabrication without an explicit instruction to do so.

| Requirement | Target / evidence needed |
|---|---|
| Appearance | Clean white printed enclosure, low on wall, screw mounting, accessible USB-C, two physical buttons |
| Size | Compare at least three complete arrangements; report width, height, depth, volume and service clearances |
| Cost | Minimize complete eight-unit cost within reason, including assembly setup/feeder costs, hardware and pack construction |
| PCB | Controller/charger/motor drive with JLCPCB-supplied and assembled common components where practical; minimal silkscreen; a separate battery-holder/protection carrier is permitted if it reduces assembly work or size |
| Finish | Black PCB solder mask preferred; quantify any assembly-cost effect before selection |
| Battery | Six Samsung INR21700-50E cells, 3S2P per device; owner prefers PCB-mounted holders to simplify assembly; compare main-board holders, a separate keyed carrier and welded construction |
| Motor | Purchased Recfountik JGB37-520 12 V, 111 RPM, encoder; exact electrical and dimensional data pending |
| Charging | USB-C; correct 3S CC/CV charging, protection, temperature sensing and cell-balance strategy |
| Runtime | 60 days target, 90 days stretch; provisional one full open-close cycle/day; include standby and conversion losses |
| Controls | Immediate local buttons; Home Assistant; a few seconds' preparation delay accepted to favour battery life |
| Telemetry | Meaningful charge estimate, charging/fault state, freshness and calibration status |
| Coordination | Shared physical bottom-edge height, coordinated starts and movement across different-height blinds |
| Alignment | Proposed prototype target: final bottom edges within 5 mm in the common reachable range; prove physically |
| Delivery | Source-generated previews in README/CI; clear source revision and validation status; buildable/printable outputs |

## Group movement semantics

A group command of 50% means a shared physical height. It does **not** mean 50% of each blind's
individual travel. Calibrate each blind against a common fixed height datum, including its headrail
position, actual reachable endpoints and fabric displacement versus encoder position.

Only positions reachable by every group member can be promised as aligned. Define the group
slider against that shared range and explain endpoint behaviour in Home Assistant. Individual
fully-open/fully-closed commands must remain distinguishable from a shared group level.
If blinds begin at different heights, document the rejoining movement; equal speed, simultaneous
arrival and immediate alignment cannot all be assumed from arbitrary starting positions.

Use a readiness/scheduled-start protocol with an explicit missing-device policy. Never just send
seven independent commands and describe them as synchronized. Handle stale commands, lost
connectivity, clock error, low battery, local override and a jam during a group move.

## Required hardware provisions

Encoder inputs with verified supply/logic compatibility; variable-speed bidirectional motor drive;
current feedback and a safe motor-off default; temperature-aware charging/protection; programming
and test access; buttons that can wake the controller; and provision for a home/limit sensor.
The actual reference method remains a design decision. Incremental motor encoders alone cannot
prove fabric position after chain slip, manual movement or lost power.

## Design selection

Compare whole-unit packaging before freezing a PCB outline. Evaluate wall footprint and projection,
chain wrap/tension, mounting loads, acoustics, wiring bend radii, battery insulation, USB cable access,
antenna clearance, printing/supports, assembly time and repair. Keep uncertain dimensions parametric.

Choose radio/MCU, charger, protection, gauge and driver from documented alternatives. Wi-Fi is a
preference, not a locked architecture. Any hub requirement must be explicit. Model the total power
cost of command latency and synchronized operation, not only a chip's deep-sleep headline.

## Open facts

See [measurements](measurements.json). A seven-blind inventory, exact motor geometry and electrical
limits, cell condition/count, desired noise and daily usage remain unverified. Proceed with labelled
assumptions for design studies; do not promote them into manufacturing dimensions or verified life.

The owner is away for several weeks and cannot measure the motors. Use documented JGB37-520
family dimensions with a stated variant allowance; keep the motor bracket and shaft adapter
replaceable. Continue the design now, with physical fit qualification before fabrication.
The exact purchased 111 RPM listing is [Amazon B0H4Y1BQ8Y](https://www.amazon.com/dp/B0H4Y1BQ8Y).

On 20 October the owner confirmed the existing blinds stay in place when the
chain is released. Plan for motor-off holding through that existing mechanism;
qualify that the added chain path and preload preserve it on each installation.
