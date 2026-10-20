# Controller harness interfaces

**UNVERIFIED, unrouted checkpoint.** `MotorSolderTails`, `EncoderConnector`
and `HomeConnector` are selected for main-controller integration. `MotorConnector`
is the unselected PCB Micro-Fit study and is not instantiated by `HarnessTest`.

| Interface | Contact assignment |
|---|---|
| Motor solder tails | landing1 = motor1, landing2 = motor2 |
| Four-way encoder | 1 ground, 2 switched encoder supply, 3 channelA, 4 channelB |
| Three-way optional home | 1 ground, 2 sensor supply, 3 sense |

Motor leads and encoder pins must be identified independently on the purchased
motor; do not trust cable colours or the low-resolution seller photograph.
Controller signal protection and rail limits belong to the parent circuitry.
The connector does not itself make an unknown encoder electrically compatible.

The selected test contains two purchased headers plus two non-BOM solder
landings, nine physical pins in total. Atopile0.15.9 normal and frozen builds
pass. `python3 hw/sim/blind-harness/checks.py --check` verifies the pin map,
current supplier IDs, primary-drawing pad geometry and negative controls.
No mechanical corridor, powered function or current-temperature test is implied.

Mechanical candidate positions remain provisional: encoder row at local
(u40,v47.3..47.5), mating+u; optional home near(u29.5,v52), mating−v.
With KiCad X=100+u,Y=175−v these correspond to footprint rotations90° and0°.
The motor landings move below v40 to avoid the encoder corridor. Check actual
component, cable and RF reservations before accepting any of these positions.
