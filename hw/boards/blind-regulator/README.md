# 3.3 V logic supply — circuit capture

Fresh TPS62902RPJR buck from charger SYS (8.8–13.2 V steady planning envelope),
with a 1 A load design envelope. This is an unrouted 12-part / 31-pin subcircuit,
not a fabrication release. The motor remains on protected PACK.

VSET intentionally floats to select the internal 3.3 V divider; 26.1 kΩ MODE/S-CONF
selects automatic PFM/PWM, AEE and output discharge. TI specifies ±1.25% static
regulation across its full temperature range, giving 3.25875–3.34125 V. The minimum
is about 65 mV above the selected supervisor's worst release threshold. This is
static margin only; assembled-board Wi-Fi bursts and regulator transients must be
measured. The source's ±2% output declaration is a total design target, not proof.

The shared 47 nF soft-start capacitor gives about 15.1 ms nominal ramp using TI
Equation14. Two shared 10 µF/50 V input capacitors replace the inadequate single
nominal 10 µF choice. Two local active 22 µF/25 V output capacitors supplement the
MCU-local capacitor. Primary DC-bias curves and explicit tolerance/temperature/aging
assumptions are checked in `hw/sim/blind-power`; those estimates are not guaranteed
production minima.

The 1 µH Sunlord MWSA0402S-1R0MT is 4.4×4.2×1.8 mm nominal, 2.0 mm maximum high.
Its 27 mΩ maximum DCR and published 5.6/7 A currents at approximately 20/30%
inductance drop provide useful margin over the rejected tiny Murata candidate.
Those columns use different criteria; they are not min/typ limits. TI's typical
50 ns current-limit propagation delay gives a conditional 4.93 A fault peak in the
chosen model. No maximum delay is specified, so fault current remains a bench gate.

Public imported inductor lands were smaller and farther apart than Sunlord's
recommendation. The wrapper generator now produces 1.5×2.5 mm pads, 2.2 mm inner
gap, with a courtyard enclosing the maximum body and pads. The footprint and 3D
model still require assembly review. The imported smaller Murata part is retained
as a rejected candidate, not present in the circuit.

Run `ato build -v` and `ato build --frozen -v` in this directory using atopile0.15.9.
Run `python3 hw/sim/blind-regulator/checks.py --check` from the repository. It checks
exact wrapper identities, source rail values, local generated BOM when present,
all compiled physical pin connections, corrected pad dimensions, and the rating
arithmetic. Open VSET is explicitly isolated. Layout, thermal performance, routed
DRC, power integrity and physical behavior remain unverified.

Sources: [TI TPS62902](https://www.ti.com/lit/ds/symlink/tps62902.pdf),
[Sunlord MWSA-S](https://www.sunlordinc.com/uploads/files/20230303/MWSA-S%C2%A0series%C2%A0of%C2%A0SMD%C2%A0Power%C2%A0Inductor.pdf),
[Samsung 22 µF](https://product.samsungsem.com/mlcc/CL21A226MAYNNN.do),
[Samsung 10 µF](https://product.samsungsem.com/mlcc/CL31A106KBHNNN.do).
