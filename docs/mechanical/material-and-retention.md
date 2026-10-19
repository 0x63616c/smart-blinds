# Material, load paths and the next retained assembly

The initial print-material candidate is **white PETG with a manufacturer technical datasheet**, such as Prusament PETG Signal White. This is a prototype choice, not a claim that any white filament is suitable. The [Prusament PETG datasheet](https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf) reports 68 °C heat deflection temperature under its stated ISO75 loads and notes that print orientation/settings change results. HDT is not a continuous-use temperature or a creep rating.

Use **45 °C maximum measured temperature at structural printed parts as an initial engineering acceptance target**, with a 50 °C stop/review threshold during prototype testing. These are deliberately conservative project targets below the reported HDT, not manufacturer operating ratings. Measure the window-facing case, battery supports, charger region and motor bracket during charging, repeated movement, stalled-current limiting and sun-heated installation conditions. The electrical charge-temperature limit can be stricter and controls the charger independently. Revise material or thermal design if the location cannot meet the target. White PLA is not the default for a sun-facing loaded bracket. PETG is not a certified fire enclosure.

The wall backplate carries the battery, drive and wall-fastener loads. The cosmetic front cover carries only its own weight and button actuation. Use mechanically retained nuts/bolts and washers for load-bearing parts; heat-set inserts may help assembly but need pull-out/creep qualification. Do not ask cosmetic snap clips or solder pads to retain cell mass or motor torque.

The next detailed CAD pass must implement the following interfaces:

| Interface | Required construction | Verification |
|---|---|---|
| Wall | Three separated screw positions in reinforced backplate; anchor type follows actual wall construction | Pull/shear test with installed anchor and load, not a guessed universal screw |
| Battery carrier | Screws/standoffs at board edges plus an insulating backing plate; holder screws where supported by drawing; smooth insulating retention bars/straps | No PCB bending during cell insertion; wraps cannot rub screw ends; removal cannot short contacts |
| Twin carrier | Rigid screwed cassette; two boards never rely on raw-rail solder joints as spacers |4.5 mm maximum tails clear 1 mm barrier; inspect all raw rails before closing |
| Motor | Replaceable split clamps/shims with captive nuts, adjustable slots and explicit torque-reaction path | Clock eccentric output into depth direction; preserve rear cable bend; proof-load against slip |
| Output shaft | Two replaceable bearing blocks on the backplate, independent of cosmetic shell; positive axial shaft retention | Rated shaft/bearings/coupler selected; fit coupons, chain radial load, jam and wear tests |
| Chain | Removable screwed guard and controlled entry/exit clearance; avoid trapping a coupler | Actual chain wrap and separation, slip/jam and enclosure-access tests |
| Controller | Screwed carrier or mounting holes and connectors accessible without pulling cell wires | Connector insertion/removal, USB plug body clearance, antenna separation |
| Controls | Vertically arranged up/down plungers with captive flanges and guides | No preloading switches; tolerance/temperature and repeated actuation tests |
| Cover | Screwed lower retention with captured upper locating features | Cover cannot become the primary motor/battery support |

For first coupons, use a calibrated 0.4 mm nozzle and 0.2 mm layer height as a starting assumption. Load-bearing brackets should use at least five walls with local solid material around fasteners; final slicer settings must follow actual geometry and printer. No strength rating is inferred from wall count. Retention parts should be oriented so critical loads are mostly within layers, then tested at the temperature target. The drive wheel should be a separate replaceable wear item, not printed into the case.

A low-power sensor can be mounted beside a straight chain strand, but an added magnet/collar may not pass the bead pockets. A wheel or chain-loop index repeats and cannot by itself establish absolute fabric height. Keep a sensor/header provision and supervised position recovery until a real reference strategy is selected with firmware.

Current v 2 models show the occupied volumes and cable route. They do not yet implement these retained interfaces; passing their bounding checks does not turn them into production parts.
