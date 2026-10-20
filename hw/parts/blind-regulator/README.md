# Logic regulator support parts

Public EasyEDA imports are split by `make_wrappers.py` into local atomic parts.
The selected parts are Sunlord MWSA0402S-1R0MT (C408332) and UNI-ROYAL 26.1 kΩ
0402WGF2612TCE (C25875). Murata DFE201610E-1R0M=P2 (C161082) remains an unused
candidate: its 3.6 A saturation figure is below the regulator's 3.9 A maximum
static current limit.

Sunlord's primary MWSA-S catalogue dated2022-10-12, pages130–131, gives 1 µH±20%,
27 mΩ maximum DCR, 5.6 A at approximately20% inductance drop, and 7 A at30% drop.
The lower thermal figure5.4 A corresponds to20°C rise, versus6 A at40°C rise.
These are distinct test criteria, not minimum/typical production bounds. Maximum
body dimensions are4.75×4.45×2.0 mm. The generator corrects imported lands to
1.5×2.5 mm with2.2 mm inner gap, matching the primary drawing. It expands the
courtyard to5.7×5.0 mm. Pad1/2 are passive terminals, orientation is immaterial.

Source: [primary Sunlord catalogue](https://www.sunlordinc.com/uploads/files/20230303/MWSA-S%C2%A0series%C2%A0of%C2%A0SMD%C2%A0Power%C2%A0Inductor.pdf).
Adjacent footprints support atopile0.15.9. Nested relative model paths assume the
same layout depth as the other fresh boards. Assembly qualification remains open.
