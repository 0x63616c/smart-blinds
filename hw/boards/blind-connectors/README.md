# Protected pack connector

One provisional Molex 430450600 six-way header with an explicit harness pin
assignment. `connector.ato:ProtectedPackConnector` is ready for parent circuit
composition; the standalone test is one part / six physical contacts and has
no routed board or source of power.

Build using atopile 0.15.9: `ato build -b connector-test`, then
`ato build -b connector-test --frozen`. The first frozen comparison exposed
zero-angle serialization (0.0 versus omitted); a normal re-save stabilizes the
format. The independent source/hole and compiled pin checks are
`python3 hw/sim/blind-connectors/checks.py --check` from the repository root.

Mating direction is local +Y. Body limits are x=±6.325, y=0.51..10.42 mm;
plastic locator is (0,5.82). Mating board edge must be at y≤15.98 mm to clear
the plug. The whole plug, latch, insertion stroke and 12.7 mm relaxed wire
corridor are separate placement constraints. See the part README for drawing
revisions and tolerances; the illustration model is not dimensional evidence.

[Harness diagram](../../../docs/electrical/protected-pack-harness.svg) and
[selection/cost](../../../docs/electrical/battery-connector.md).
