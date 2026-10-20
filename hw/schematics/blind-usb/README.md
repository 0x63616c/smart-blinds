# Native USB-C input schematic

This A3 drawing contains 33 parts and 113 physical pins, independently exported
by KiCad and compared with the compiled circuit. Three explicit external-power
ERC findings remain: PD VDD, eFuse IN and ground. There are no exclusions or
artificial power flags. Factory I2C, USB data, the charger input capacitor bank
and integrated-board qualification remain outside this drawing.

See `hw/boards/blind-usb/README.md` for the profile requirements and unresolved
startup, discharge, source entitlement and surge limits. This is an unrouted
circuit study, not a fabrication or charging release.
