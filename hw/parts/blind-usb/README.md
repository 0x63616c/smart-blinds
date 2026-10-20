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
