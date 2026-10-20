# Native USB-C input schematic

This A3 drawing contains 32 parts and 111 physical pins, independently exported
by KiCad and compared with the compiled circuit. Eight explicit findings remain:
four external supplies (VDD, VSYS, eFuse IN and ground), undriven external SCL,
and three isolated external labels (SDA, SCL, ALERT). There are no exclusions or
artificial power flags. The integrated main schematic connects the host bus,
VSYS and shared interrupt pull-up and retains its seven reviewed findings.

VSYS uses always-on 3.3 V with a local 1 µF capacitor. The old factory 100 kΩ bus pulls
are removed. RESET remains active HIGH for service; the runtime bus has one owner.
See `hw/boards/blind-usb/README.md` for profile/fixture requirements and unresolved
power handover, discharge, source entitlement, leakage and surge limits.
