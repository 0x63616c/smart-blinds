# USB input part library

These public EasyEDA imports are geometry starting points. KiCad 10 upgrades
are retained in `blind-usb.pretty`; `make_wrappers.py` creates atomic imports
and normalizes model paths. Run `kicad-cli fp upgrade --force` on that library
before regenerating after a fresh legacy import.

The STUSB4500 QFN exposed pad is numbered 25 in this library. TPS259470L
variant-specific labels replace imported aliases. The ESDA25W has two
independent cathodes K1/K2 and one common anode; the repeated imported K name
must never short both configuration channels. Atomic symbol labels and Ato
pin aliases agree. Physical pins are independently audited by the USB block
contract and native schematic export.

Land patterns, paste apertures and model alignment are not yet fully qualified.
In particular the generic 1206 capacitor model is marked H1.3 while Samsung
specifies 1.6 mm nominal / 1.8 mm maximum for CL31A475KBHNNNE; use the primary
maximum envelope for enclosure/layout clearance, not the generic STEP shape.

The connected study and primary-source/rating record now live under
`../../boards/blind-usb`. Its tests do not validate PD NVM, surge immunity or
complete charging behavior.

The new HRO TYPE-C-31-M-12 footprint uses the manufacturer's RevA drawing dated
2020-12-08. Its datum is the centre between locator holes; the mouth faces+Y.
The imported pads and shell slots differed, so this separate wrapper preserves
the inherited e8s library while matching the published lands. The body mouth
is6.25mm from the locator line, versus5.79mm to the recommended board edge.
The enclosure therefore reserves a flush-mouth PCB tongue. Dimensions/source
hash are in `usb-connector-geometry.json`; `hw/sim/blind-usb/check_footprint.py`
checks the source and both compiled uses. The retained STEP is approximate,
not authority for enclosure fit or mating clearance.
