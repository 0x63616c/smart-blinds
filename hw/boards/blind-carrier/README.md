# Protected 3S2P battery carrier study

**UNVERIFIED.** This is an original, unrouted pack circuit with external holder and
thermistor terminals. It is not a manufacturing release or a drop-in battery holder.
The two physical carriers form one screwed-closed, insulated pack. Their four raw
series-group rails are retained internal connections; only protected power and
telemetry may leave the cassette.

The circuit captures a MAX17320G22+ gauge/protector, two opposing high-side
AON7400A N-FETs, a Kelvin-connected 10 mΩ shunt, three 100 Ω balancing resistors,
differential 100 nF cell filters, internal regulator/charge-pump bypass, two pack
NTC inputs, and six individual 3 A cell-positive fuses. Gauge telemetry has 150 Ω
series resistors and 4.7 V Zeners; the clamps are on the external connector
side and return to PACK−, following ADI UG7177 Figure 3. See the
[review and remaining electrical limits](../../../docs/electrical/pack-communication-clamps.md).
The controller supplies the pullups. ZVC is open
and zero-volt recharge must remain disabled. PFAIL is terminated as the manufacturer
instructs for an unused output; **no independent secondary protector or thermal
fuse heater is implemented yet**.

The [Rev12 MAX17320 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)
Figure24 on page73 is explicit for 3S: CELL2 connects directly to CELL1, RBAL2 is
omitted, CELL3 senses the second junction, and BATTS senses the top of the stack.
The corrected July2025 drawing was inspected directly. Older diagrams must not
silently replace it. The [implementation guide](https://www.analog.com/media/en/technical-documentation/user-guides/max17320-battery-pack-implementation-guide.pdf)
p4 item5 connects the exposed pad directly to the gauge GND pin. This design follows
that choice with RAW_GND, while CSN separately senses the load side of the shunt.
ADI's [EP grounding clarification](https://ez.analog.com/power/battery-management-system/a/documents/DO6991/i-m-using-max17320-in-my-design-can-i-connect-the-exposed-pad-to-gnd-power-plane-to-dissipate-more-power)
warns against accidentally joining the two ground paths through the pad. Electrical
net equality does not enforce the required Kelvin layout.

`carrier-connectivity.json` is an independent physical-pin contract; its checks
cover every compiled physical terminal and deliberate short/open negative controls.
`carrier-ratings.json` binds the exact fixed parts, source declarations and scoped
calculations. The manufacturer land patterns replace the generic imported fuse,
shunt and AON7400A pad geometry. FET paste subdivision is provisional.

## Fault boundaries

The pack path is provisionally sized at 4 A, including motor and logic. This is a
calculation envelope, not an accepted continuous holder rating. At equal division,
each branch carries2 A; a missing or high-resistance parallel cell can push nearly
all current into its partner. A 3 A branch fuse cannot guarantee uninterrupted
operation in that condition. Pack voltage alone cannot detect every missing cell.

The MAX protector cannot stop current flowing locally between two parallel cells.
Each positive branch therefore has a Littelfuse0451003.MRL before the parallel
junction. Its primary series data gives300 A interruption at32 VDC, nominal22.7 mΩ
cold resistance and1.65 A²s melting I²t. Those figures do **not** establish actual
short-circuit current, total clearing energy, wire/holder protection or reversal
acceptance. Fuse coordination needs a contained, instrumented test and the actual
cell/contact/path resistance. Nominal melting I²t must not be treated as guaranteed
clearing time.

Cells are a matched six-cell set with verified condition and close open-circuit
voltages before pairing. Service is depowered and controlled. Recessed/retained
positive-contact geometry must reject reversal with the actual flat-top50E cells;
that geometry is not accepted yet. Raw rails and cell can contacts must be insulated.
A pack FET failed short cannot be assumed safe merely because the gauge reports it;
a separate secondary overvoltage/fuse path remains an explicit design decision.

## Verification and remaining work

Run `ato build --build carrier-test` then its `--frozen` form from this directory
using the pinned0.15.9 runtime. Run `python3 hw/sim/blind-carrier/checks.py --check`
from the repository root. These are circuit/source checks, not hardware simulation.

The protected connector, exact holders, NTC harnesses, secondary protection choice,
NVM profile, cell-insertion sequence, electrical fault tests, placement, routing and
thermal verification are still outstanding. The six-way connector candidate is
Molex430450600 with PACK+/PACK−/SDA/SCL plus a separate charger NTC pair; it is not
captured in this circuit yet. Gauge ALERT would stay internal if that option wins.
