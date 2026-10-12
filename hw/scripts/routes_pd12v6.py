# Routes for pd12v6 (exec'd by layout_pd12v6.py; uses track/via/zone/P/label/dot/bar helpers; mm, +y down).
#
# Layer plan (4 layers)
#   F.Cu  : everything that carries current (VBUS bus, buck SW node, VOUT), all buck small-signal
#           parts, PD controller pins, CC1, LED circuits.
#   In1.Cu: unbroken GND plane (every GND pad gets a via or is a THT pad).
#   In2.Cu: VBUS pour (left half) and VOUT pour (right half) - parallel paths to the F.Cu tracks.
#   B.Cu  : USB D+/D- pair (USB-C -> Micro-Fit), CC2 (crosses the data pads), FB (crosses COMP),
#           GND fill everywhere else.
# Widths: VOUT 1.5 mm, VBUS 0.5-0.8 mm, SW 0.8 mm, signals 0.2 mm.  Vias 0.6/0.3 (0.8/0.4 power,
# 0.45/0.25 only for the three vias squeezed between the 0.5 mm USB-C pad rows).

SIG, PWR = (VIA_D, VIA_DRILL), (PWR_VIA_D, PWR_VIA_DRILL)
TINY = (0.45, 0.25)

def gv(xy, dd=SIG):            # GND via
    via("GND", xy, *dd)
def gpad(ref, num, xy, width=0.3, dd=SIG):   # GND pad -> stub -> via
    track("GND", [P(ref, num), xy], width=width); gv(xy, dd)

# ================================================================== zones (always, also in --place-only)
zone("GND",  "In1.Cu", ((0, 0), (W, H)), priority=0, thermal=True)
zone("GND",  "F.Cu",   ((0, 0), (W, H)), priority=0)
zone("GND",  "B.Cu",   ((0, 0), (W, H)), priority=0)
zone("VBUS", "In2.Cu", ((7.0, 2.0), (19.9, 24.0)), priority=1)
zone("VOUT", "In2.Cu", ((20.5, 2.0), (38.5, 30.0)), priority=1)

# ================================================================== USB-C
# GND pads tie straight into the shell's THT legs (which are the vias)
track("GND", [P("USBC1", "A1B12"), P("USBC1", "4")], width=0.3)
track("GND", [P("USBC1", "B1A12"), P("USBC1", "1")], width=0.3)
# VBUS: both pads -> short stubs -> power vias into the In2 VBUS pour
track("VBUS", [P("USBC1", "A4B9"), (8.0, 15.1), (8.6, 14.4)], width=0.5); via("VBUS", (8.6, 14.4), *PWR)
track("VBUS", [P("USBC1", "B4A9"), (7.9, 19.9), (8.0, 21.6)], width=0.5); via("VBUS", (8.0, 21.6), *PWR)
# CC1 straight across to U2.7
track("CC1", [P("USBC1", "A5"), P("U2", "7")], width=0.2)
# CC2 has to cross the data pads: down to B.Cu, up to pin 6's row, back up
track("CC2", [P("USBC1", "B5"), (7.95, 19.25)], width=0.2); via("CC2", (7.95, 19.25), *TINY)
track("CC2", [(7.95, 19.25), (7.95, 15.25), (10.0, 15.25)], layer="B.Cu", width=0.2); via("CC2", (10.0, 15.25), *SIG)
track("CC2", [(10.0, 15.25), P("U2", "6")], width=0.2)
# USB data: the two D- pads (B7, A7) sandwich D+ (A6).  D- drops to B.Cu at each pad; D+ pads are
# joined on F.Cu around them, then drop to B.Cu.  Pair runs on B.Cu at y 19.8 / 20.3 to the header.
track("USB_DN", [P("USBC1", "B7"), (8.5, 16.75)], width=0.2); via("USB_DN", (8.5, 16.75), *TINY)
track("USB_DN", [P("USBC1", "A7"), (8.5, 17.75)], width=0.2); via("USB_DN", (8.5, 17.75), *TINY)
track("USB_DN", [(8.5, 16.75), (8.5, 20.3), (27.6, 20.3), P("CN1", "4")], layer="B.Cu", width=0.2)
track("USB_DP", [P("USBC1", "A6"), (9.3, 17.25), (9.3, 18.25), P("USBC1", "B6")], width=0.2)
track("USB_DP", [(9.3, 18.25), (9.3, 19.8)], width=0.2); via("USB_DP", (9.3, 19.8), *TINY)
track("USB_DP", [(9.3, 19.8), (26.4, 19.8), (26.4, 16.0), P("CN1", "3")], layer="B.Cu", width=0.2)

# ================================================================== PD controller U2
track("VBUS", [P("U2", "8"), (10.3, 17.25)], width=0.3); via("VBUS", (10.0, 17.25), *SIG)
track("VBUS", [(10.3, 17.25), (10.0, 17.25)], width=0.3)
track("VBUS", [P("U2", "1"), (18.6, 19.25), (18.6, 18.6), (19.5, 18.6), P("C9", "1")], width=0.3)
track("VBUS", [(19.5, 18.6), (19.5, 19.2)], width=0.3); via("VBUS", (19.5, 19.2), *SIG)
track("GND", [P("C9", "2"), (19.5, 15.3)], width=0.3); gv((19.5, 15.3))
for xy in ((14.0, 16.6), (15.0, 16.6), (14.0, 17.9), (15.0, 17.9)): gv(xy)      # exposed pad
track("CFG1", [P("U2", "9"), (10.5, 18.25), (10.0, 18.75), P("R1", "1")], width=0.2)
gpad("R1", "2", (10.0, 24.3))
track("PG_n", [P("U2", "10"), (11.5, 20.3), (12.5, 21.3), P("R6", "2")], width=0.2)
track("LED_PD_K", [P("R6", "1"), P("LED2", "2")], width=0.2)
track("VBUS", [P("LED2", "1"), (16.0, 21.75)], width=0.3); via("VBUS", (16.0, 21.75), *SIG)

# ================================================================== input: TVS, bulk caps, VIN
# VBUS bus runs ABOVE the caps (their VBUS pads face up) and drops into VIN from the top-left,
# because the 1210 pads leave no room between the caps and U1's pin row.
track("VBUS", [P("D2", "1"), (8.25, 5.3), (17.1, 5.3), (17.1, 7.5), (17.4, 7.87), P("U1", "2")], width=0.6)
track("VBUS", [P("C4", "1"), (11.8, 5.3)], width=0.8); track("VBUS", [P("C5", "1"), (15.4, 5.3)], width=0.8)
for xy in ((10.0, 5.3), (13.6, 5.3), (16.5, 5.3)): via("VBUS", xy, *PWR)
track("VBUS", [P("C6", "1"), (13.0, 14.8), (15.5, 14.8), P("R8", "1")], width=0.3)
via("VBUS", (14.25, 14.8), *SIG)
track("GND", [P("D2", "2"), (8.25, 12.6)], width=0.6); gv((8.25, 12.6))
gv((9.9, 10.4)); track("GND", [P("D2", "2"), (9.9, 10.4)], width=0.6)
track("GND", [P("C4", "2"), (14.1, 10.3), P("C5", "2")], width=0.5); gv((14.1, 10.3))
gpad("C4", "2", (11.8, 11.45)); gpad("C5", "2", (15.4, 11.45))
gpad("C6", "2", (12.0, 12.8))

# ================================================================== buck U1
track("BOOT", [P("C1", "1"), P("U1", "1")], width=0.25)
track("SW", [P("C1", "2"), P("D1", "1")], width=0.4)
track("SW", [(24.27, 3.0), P("U1", "8")], width=0.6)
track("SW", [P("U1", "8"), (25.3, 6.59), (26.5, 7.5), P("L1", "1")], width=0.8)
track("GND", [P("D1", "2"), (28.2, 4.9)], width=0.8); track("GND", [(27.6, 4.9), (28.8, 4.9)], width=0.8)
gv((27.6, 4.9), PWR); gv((28.8, 4.9), PWR)
track("GND", [P("U1", "7"), (22.6, 7.87)], width=0.3)              # pin 7 into the exposed pad
track("EN", [P("R8", "2"), P("R9", "1")], width=0.2)
track("EN", [(17.2, 12.75), (17.2, 9.13), P("U1", "3")], width=0.2)
gpad("R9", "2", (19.0, 14.25))
track("RT", [P("U1", "4"), (19.7, 11.8), P("R7", "1")], width=0.2)
gpad("R7", "2", (20.5, 15.3))
track("COMP", [P("U1", "6"), (25.65, 9.13), (25.65, 12.75), P("R2", "1")], width=0.2)
track("COMP", [P("R2", "1"), (26.4, 12.75), (26.4, 16.3), P("C2", "1")], width=0.2)
track("COMP_Z", [P("R2", "2"), P("C3", "1")], width=0.2)
track("GND", [P("C3", "2"), (22.0, 12.8)], width=0.3); gv((22.0, 12.8))
gpad("C2", "2", (25.5, 18.7))
# FB: pin 5 -> B.Cu (under the COMP network) -> up between R3 and R4
track("FB", [P("U1", "5"), (24.27, 11.2), (24.3, 11.6)], width=0.2); via("FB", (24.3, 11.6), *SIG)
track("FB", [(24.3, 11.6), (22.5, 13.4), (22.5, 15.2)], layer="B.Cu", width=0.2); via("FB", (22.5, 15.2), *SIG)
track("FB", [(22.5, 15.2), (22.5, 16.25)], width=0.2)
track("FB", [P("R3", "2"), P("R4", "1")], width=0.2)
gpad("R4", "2", (23.5, 18.7))
track("VOUT", [P("R3", "1"), (21.5, 18.7)], width=0.3); via("VOUT", (21.5, 18.7), *SIG)

# ================================================================== output
track("VOUT", [P("L1", "2"), (32.91, 9.6), (35.0, 9.6), P("C7", "1")], width=1.5)
track("VOUT", [(32.91, 9.6), (32.91, 13.6), P("CN1", "1")], width=1.5)
via("VOUT", (33.0, 11.4), *PWR); via("VOUT", (36.5, 11.4), *PWR)
track("VOUT", [P("C7", "1"), (36.5, 11.4)], width=0.8)
gpad("C7", "2", (35.0, 6.98), 0.8, PWR)
track("VOUT", [P("LED1", "2"), (29.7, 25.2), (29.7, 27.52), P("C8", "1")], width=0.5)
track("VOUT", [P("C8", "1"), (32.9, 27.52)], width=0.8); via("VOUT", (32.9, 27.52), *PWR)
gpad("C8", "2", (31.5, 23.2), 0.8, PWR)
track("LED_OUT_K", [P("R5", "1"), P("LED1", "1")], width=0.2)
gpad("R5", "2", (26.5, 24.2))

# ================================================================== GND stitching around the edge
for xy in ((10, 1.6), (16, 1.6), (31.5, 1.6), (34, 1.6), (6, 30.4), (20, 30.4), (26, 30.4), (33, 30.4),
           (38.6, 6.5), (38.6, 10.5), (38.6, 26.5), (1.6, 9.5), (1.6, 25.5)):
    gv(xy)

# ================================================================== polarity / pin-1 marks
dot(17.1, 5.9)                      # U1 pin 1
dot(18.6, 20.1, 0.4)                # U2 pin 1 (bottom-right corner, pin 1 = VBUS)
dot(30.6, 11.5)                     # CN1 pin 1 (+12.6 V)
bar(22.4, 3.0, 1.8, True)           # D1 cathode (SW side)
bar(8.25, 4.7, 2.0, False)          # D2 cathode (VBUS side, top)
bar(28.5, 27.7, 1.0, False)         # LED1 cathode
bar(15.0, 24.1, 1.0, False)         # LED2 cathode
for t, x, y in (("+", 30.6, 14.4), ("-", 30.6, 20.6), ("D+", 27.6, 14.4), ("D-", 27.6, 20.6)):
    label(t, x, y, 0.8, "B.SilkS")  # header pins, readable from the back
