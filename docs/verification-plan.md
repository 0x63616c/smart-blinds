# Verification and prototype release gates

A render, simulation or clean rule check is evidence of that specific check only. It does not prove
that a PCB will charge a real pack safely, fit purchased parts or move a blind reliably.

## 1. Design evidence

- Compare at least three whole-product layouts with the same motor/cell/interface assumptions.
- Trace critical dimensions and ratings to owner measurements or the exact manufacturer's data.
- Confirm each populated part's JLCPCB identity, footprint, assembly eligibility, stock date and fees.
- Review battery interconnect insulation, cell protection/balancing, fusing, connector polarity,
  charging temperature limits and failure behaviour before prototype assembly.
- Define position reference/recovery and group target semantics before selecting MCU pins.

## 2. Electrical checks

Run schematic connectivity/ERC and PCB DRC, with any justified exceptions recorded. Check netlist
agreement, connector pinouts, footprint/pin mapping, creepage/clearance appropriate to rails, copper
current/thermal limits, decoupling, antenna keepouts and manufacturing constraints.

Simulate critical circuits where usable vendor models exist: charger/power-path transients, input
and battery limits, motor startup/stall/regeneration, current feedback, rail droop and reset behaviour.
Record model/vendor/version, input assumptions, parameter sweeps, results and omitted effects.
Behavioural estimates must be labelled; do not call an ideal-switch model proof of the real IC.
Model motor current across the pack operating range and calibrate the model against measurements.

## 3. Firmware and group tests

Test non-linear fabric calibration, shared reachable height limits, different initial positions,
encoder direction/resolution, speed ramps, current/encoder jam detection and recovery. Exercise
clock uncertainty, late/missing acknowledgements, duplicate/stale commands, network loss, reboot,
power loss, manual movement, local override, low battery and firmware-update interruption.
Never permit a retained/replayed command to cause unexpected motion after reconnection.

## 4. Mechanical checks

Check source CAD dimensions, unintended intersections and assembly access. Inspect mesh validity,
print orientation/supports, fastener engagement, drive retention, chain loading and clearances.
Print small motor/shaft/chain/fastener fit coupons before a whole enclosure. Test chain retention
and tension over the entire stroke, accessible loops/pinch points, wall fixing and removal/service.
Six cells and the motor must fit with insulation, wiring, tolerances and ventilation—not only nominal solids.

## 5. Physical prototype gate

Use two different-height blinds, including the heaviest. Verify measured pull, motor running/start
current and a controlled current-limited stall characterization, encoder pinout and actual geometry.
Check charging with the actual USB supplies/cables and protected pack, imbalance/temperature/fault
responses, loaded motor starts at low battery, regeneration, RF range and reset safety.

Measure group start skew and final bottom-edge error against the proposed 5 mm target, plus
visible alignment during motion and drift over repeated cycles. Test interrupted calibration,
power removal and chain slip; document when re-referencing is required.

Measure idle energy over representative network conditions, movement energy, charging losses and
usable pack energy. Publish a 60/90-day projection with usage assumptions and reserve; confirm it
with subsequent endurance testing. Report acoustics and user acceptance rather than inventing a
quietness claim. Only then evaluate an eight-unit build.

## Release evidence

Every release should contain sources, CAD assembly and exploded previews, print files, schematic,
PCB/3D preview, BOM and placement/manufacturing exports as appropriate, firmware/build identifiers,
assembly/calibration guide, validation results and outstanding limitations. No physical acceptance
is implied by CI passing. Neither parts ordering nor fabrication is authorized by this plan.
