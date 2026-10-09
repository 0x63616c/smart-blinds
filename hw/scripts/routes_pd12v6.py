# Routes for pd12v6 (exec'd by layout_pd12v6.py; uses track/via/zone/P helpers, mm, +y down).
#
# Layer plan
#   F.Cu : all power (VBUS bus, buck SW node, VOUT), the buck's small-signal parts, PD controller
#   B.Cu : USB data to the header, CC lines to the PD controller, VBUS feed to the PD/op-amp side,
#          the current-limit injection line, and the OUT_RTN return to the shunt + header.
#   Both layers are flooded with GND; every GND pad gets a via next to it (two for the big caps).
#
# Widths: 5 A paths 1.5–2.5 mm, VBUS (≤5 A @ 20 V) 0.8–1.0 mm, signals 0.25 mm.

def gnd_via(xy, d=VIA_D, drill=VIA_DRILL):
    via("GND", xy, d, drill)

def gnd_pad_via(ref, num, xy, width=0.3, d=VIA_D, drill=VIA_DRILL):
    """GND pad -> short track -> via."""
    track("GND", [P(ref, num), xy], width=width)
    gnd_via(xy, d, drill)

# =============================================================================== USB-C -> VBUS
# upper VBUS pad -> stub -> trunk up to the input-cap bus at y 7.2
track("VBUS", [P("USBC1", "A4B9"), (7.9, 12.6)], width=0.3)
track("VBUS", [(7.9, 12.6), (8.6, 12.6), (8.6, 7.2)], width=0.8)
track("VBUS", [(7.7, 7.2), (12.6, 7.2)], width=0.8)              # C5 pad1 -> C4 pad1 -> U1 VIN
track("VBUS", [(12.6, 7.2), (13.2, 7.37)], width=0.6)            # into VIN pad
track("VBUS", [P("C6", "1"), (10.2, 7.84)], width=0.5)           # 100 nF off the bus
track("VBUS", [P("R14", "1"), (10.3, 12.2), (10.3, 15.2)], width=0.5)   # UVLO divider + TVS feed
track("VBUS", [P("LED2", "1"), (11.85, 15.2)], width=0.4)        # PD LED anode from the TVS pad

# lower VBUS pad -> via -> B.Cu feed for the PD controller / op-amp side
track("VBUS", [P("USBC1", "B4A9"), (7.6, 17.4)], width=0.3)
track("VBUS", [(7.6, 17.4), (8.3, 17.9)], width=0.5)
via("VBUS", (8.3, 17.9), PWR_VIA_D, PWR_VIA_DRILL)
track("VBUS", [(8.3, 17.9), (9.6, 17.9), (10.3, 17.1)], width=0.5)          # ties lower VBUS pad to the TVS / upper trunk
track("GND", [P("USBC1", "A1B12"), (6.4, 11.27)], width=0.4)               # shell GND pads -> shield pegs
track("GND", [P("USBC1", "B1A12"), (6.4, 18.73)], width=0.4)
track("VBUS", [(8.3, 17.9), (8.3, 19.8), (10.3, 21.8), (10.3, 23.5), (11.2, 24.4), (11.5, 24.4)], layer="B.Cu", width=0.6)
via("VBUS", (11.5, 24.4), PWR_VIA_D, PWR_VIA_DRILL)
track("VBUS", [(11.5, 24.4), P("C12", "1"), P("U3", "1")], width=0.4)      # VHV + its 1 uF
track("VBUS", [(11.5, 24.4), (17.5, 24.4), (17.9, 24.0)], layer="B.Cu", width=0.6)
via("VBUS", (17.9, 24.0))
track("VBUS", [(17.9, 24.0), P("R9", "1")], width=0.3)                   # reference divider
track("VBUS", [(15.0, 24.4), (15.0, 17.95), (15.35, 17.6)], layer="B.Cu", width=0.3)     # U3 VBUS pin (jog clears R1)
via("VBUS", (15.35, 17.6))
track("VBUS", [(15.35, 17.6), P("U3", "8")], width=0.3)
track("VBUS", [(16.6, 24.4), (16.6, 32.2), (25.3, 32.2), (25.5, 32.4)], layer="B.Cu", width=0.5)   # op-amp supply
via("VBUS", (25.5, 32.4))
track("VBUS", [(25.5, 32.4), P("C8", "1")], width=0.3)
track("VBUS", [(25.5, 32.9), (24.7, 33.3), P("U2", "8")], width=0.25)

# =============================================================================== buck: TPS54560
# BOOT / SW to the bootstrap cap above the IC
track("BOOT", [(13.3, 6.09), (13.3, 5.1), (14.5, 4.3), P("C1", "1")], width=0.25)
track("SW",   [(19.7, 6.09), (19.7, 5.1), (18.5, 4.3), P("C1", "2")], width=0.4)
# SW -> catch diode cathode -> inductor
track("SW", [(20.3, 6.09), (21.9, 7.3)], width=1.0)
track("SW", [P("D1", "1"), (25.0, 7.5)], width=1.5)
# GND pin + exposed pad
track("GND", [(18.3, 7.37), (17.5, 7.37)], width=0.4)
track("GND", [(20.2, 7.37), (20.9, 7.9)], width=0.4); gnd_via((20.9, 7.9))
# EN (UVLO divider)
track("EN", [P("R14", "2"), P("R15", "1")], width=0.25)
track("EN", [(12.35, 10.75), (12.35, 8.63), (12.8, 8.63)], width=0.25)
# RT
track("RT", [(13.6, 10.1), P("R11", "1")], width=0.25)
# COMP network
track("COMP", [(20.2, 8.63), (21.0, 9.4), P("C2", "1")], width=0.25)
track("COMP", [(21.95, 9.85), P("R2", "1")], width=0.25)
track("COMP_Z", [P("R2", "2"), (23.45, 11.55), (23.0, 12.0), P("C3", "1")], width=0.25)
# FB: pin -> R4 (bottom) -> R3 (top), plus the current-limit clamp diode
track("FB", [(19.5, 10.2), P("R4", "1"), P("R3", "2")], width=0.25)
track("FB", [(19.07, 11.25), (15.5, 11.25), P("D2", "1")], width=0.25)
# buck-side GND vias
for x in (7.0, 8.4):   gnd_pad_via("C5", "2", (x, 2.5), 0.5, PWR_VIA_D, PWR_VIA_DRILL)
for x in (10.1, 11.5): gnd_pad_via("C4", "2", (x, 2.5), 0.5, PWR_VIA_D, PWR_VIA_DRILL)
for y in (2.6, 3.6):   gnd_pad_via("D1", "2", (24.5, y), 0.6, PWR_VIA_D, PWR_VIA_DRILL)
gnd_pad_via("C6", "2", (11.6, 8.5))
gnd_pad_via("R15", "2", (11.05, 12.75))
track("GND", [P("R11", "2"), (13.9, 13.6), (14.3, 13.6)], width=0.25); gnd_via((14.6, 13.6))
gnd_pad_via("C2", "2", (23.4, 10.35))
gnd_pad_via("C3", "2", (24.5, 11.4))
gnd_pad_via("R4", "2", (19.6, 13.65))

# =============================================================================== VOUT (12.6 V, 5 A)
track("VOUT", [P("L1", "2"), (35.3, 12.3), (36.8, 13.8), (36.8, 21.5), P("CN1", "2")], width=1.8)
track("VOUT", [(35.3, 12.3), (26.6, 12.3), (24.6, 15.6)], width=1.6)    # to the output caps
track("VOUT", [P("C9", "1"), P("C10", "1")], width=1.5)
track("VOUT", [P("R3", "1"), (20.8, 15.2)], width=0.5)                  # feedback divider top
track("VOUT", [(36.9, 7.8), (38.4, 7.2), P("LED1", "2")], width=0.4)    # output LED
track("LED_OUT_K", [P("LED1", "1"), P("R7", "1")], width=0.25)
gnd_pad_via("R7", "2", (38.8, 12.7))
for x in (19.5, 20.9): gnd_pad_via("C9", "2", (x, 20.5), 0.5, PWR_VIA_D, PWR_VIA_DRILL)
for x in (22.6, 24.0): gnd_pad_via("C10", "2", (x, 20.5), 0.5, PWR_VIA_D, PWR_VIA_DRILL)

# =============================================================================== OUT_RTN (return, 5 A)
# XT30 pin 1 -> B.Cu (passes beside pin 2) -> two vias -> shunt pad 1
track("OUT_RTN", [P("CN1", "1"), (37.1, 20.7), (37.1, 27.0), (35.6, 28.4), (34.6, 28.4)], layer="B.Cu", width=1.0)
for x in (34.6, 35.6):
    via("OUT_RTN", (x, 28.4), PWR_VIA_D, PWR_VIA_DRILL)
    track("OUT_RTN", [(x, 28.4), (x, 30.0)], width=0.8)
# shunt pad 1 -> B.Cu run along the bottom edge -> R12 sense tap -> header pin 3
track("OUT_RTN", [(35.07, 33.2), (35.07, 34.4)], width=1.0)
via("OUT_RTN", (35.07, 34.4), PWR_VIA_D, PWR_VIA_DRILL)
track("OUT_RTN", [(35.07, 34.4), (34.3, 35.2), (18.2, 35.2), (11.5, 35.2), (8.2, 31.9), (8.2, 24.0), P("J1", "3")], layer="B.Cu", width=0.8)
via("OUT_RTN", (18.2, 35.2))
track("OUT_RTN", [(18.2, 35.2), P("R12", "1")], width=0.25)
# shunt GND side
for y in (30.2, 31.5, 32.8): gnd_pad_via("R13", "2", (27.7, y), 0.6, PWR_VIA_D, PWR_VIA_DRILL)

# =============================================================================== current limit (LM358)
track("I_SENSE", [P("R12", "2"), P("C11", "1"), (19.0, 30.2), (19.0, 27.3), (22.07, 27.3), P("U2", "3")], width=0.25)
gnd_pad_via("C11", "2", (17.4, 28.8))
gnd_pad_via("U2", "4", (19.9, 28.8))
gnd_pad_via("U2", "5", (19.9, 34.0))
gnd_pad_via("C8", "2", (27.7, 34.0))
track("P2INneg", [P("U2", "6"), P("U2", "7")], width=0.25)
track("I_REF", [P("R9", "2"), P("R10", "1"), P("R6", "1")], width=0.25)
gnd_pad_via("R10", "2", (18.4, 26.5))
track("I_INT", [P("R6", "2"), (23.5, 26.2), P("C7", "2"), (23.33, 27.4), P("U2", "2")], width=0.25)
track("I_OUT", [P("U2", "1"), (24.61, 27.5), P("C7", "1"), P("R5", "1")], width=0.25)
# injection into FB: R5 -> via -> B.Cu -> via -> D2 anode
track("I_INJ", [P("R5", "2"), (27.75, 24.9)], width=0.25)
via("I_INJ", (27.75, 24.9))
track("I_INJ", [(27.75, 24.9), (27.75, 15.4), (19.4, 15.4), (18.6, 14.6), (18.6, 14.2)], layer="B.Cu", width=0.25)
via("I_INJ", (18.6, 14.2))
track("I_INJ", [(18.6, 14.2), (18.19, 13.3), P("D2", "2")], width=0.25)

# =============================================================================== PD controller (CH224A)
track("CFG1", [P("R1", "1"), P("U3", "9")], width=0.25)
track("PG_n", [P("R8", "2"), P("U3", "10")], width=0.25)
track("LED_PD_K", [P("LED2", "2"), (13.0, 15.5), P("R8", "1")], width=0.25)
gnd_pad_via("R1", "2", (14.9, 16.1))
gnd_pad_via("D3", "2", (11.1, 22.6), 0.5)
gnd_pad_via("C12", "2", (9.2, 25.5))
for xy in ((14.2, 22.0), (14.2, 23.0), (15.8, 22.0), (15.8, 23.0)): gnd_via(xy)   # U3 exposed pad
# CC lines: USB-C pads -> via -> B.Cu -> via -> U3 pins 7/6
track("CC1", [P("USBC1", "A5"), (8.3, 13.75)], width=0.25); via("CC1", (8.3, 13.75))
track("CC1", [(8.3, 13.75), (8.3, 14.4), (16.0, 14.4), (16.0, 16.0)], layer="B.Cu", width=0.25)
via("CC1", (16.0, 16.0)); track("CC1", [(16.0, 16.0), P("U3", "7")], width=0.25)   # via above CC2's B.Cu run
track("CC2", [P("USBC1", "B5"), (9.0, 16.75)], width=0.25); via("CC2", (9.0, 16.75))
track("CC2", [(9.0, 16.75), (17.0, 16.75), (17.0, 17.6)], layer="B.Cu", width=0.25)
via("CC2", (17.0, 17.6)); track("CC2", [(17.0, 17.6), P("U3", "6")], width=0.25)

# =============================================================================== USB 2.0 data pass-through
# D+ : both pads joined on top, then B.Cu to header pin 2
track("USB_DP", [P("USBC1", "A6"), (7.8, 14.75), (7.8, 15.75), P("USBC1", "B6")], width=0.25)
track("USB_DP", [(7.8, 15.25), (8.9, 15.25)], width=0.25); via("USB_DP", (8.9, 15.25))
track("USB_DP", [(8.9, 15.25), (8.9, 16.1), (7.4, 16.1), (7.25, 16.3), (7.25, 21.3), P("J1", "2")], layer="B.Cu", width=0.25)
# D- : both pads to vias under the connector, B.Cu between the shell pegs to header pin 1
track("USB_DN", [P("USBC1", "B7"), (5.4, 14.25)], width=0.25); via("USB_DN", (5.4, 14.25))
track("USB_DN", [P("USBC1", "A7"), (5.4, 15.25)], width=0.25); via("USB_DN", (5.4, 15.25))
track("USB_DN", [(5.4, 14.25), (5.4, 15.25), (4.0, 16.65), (4.0, 21.5), P("J1", "1")], layer="B.Cu", width=0.25)

# =============================================================================== GND pours (both layers)
zone("GND", "F.Cu", ((0, 0), (W, H)))
zone("GND", "B.Cu", ((0, 0), (W, H)))
