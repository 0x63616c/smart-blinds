# Regulator checks

`python3 hw/sim/blind-regulator/checks.py --check` verifies the selected source,
exact MPN/LCSC wrappers, local generated BOM if present, all12parts/31physicalpins,
corrected inductor land geometry and the published rating arithmetic.
`results.json` records conditional current/ramp estimates and unresolved gates.
This is not a TPS62902 silicon simulation or a physical transient test.

The source uses AEE, so the current-ripple estimate uses TI's varying-frequency
Equation5 rather than incorrectly assuming constant2.5MHz. Fault peak uses a
**typical**, not maximum, propagation delay. There is no claim of proven fault
current, loop stability or Wi-Fi-burst performance.
