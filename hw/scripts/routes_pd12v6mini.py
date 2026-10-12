# Routes for pd12v6mini (exec'd by layout_pd12v6mini.py; `b` is the pcbkit.Board, `P` = pad centre).
#
# Layer plan (4 layers)
#   F.Cu  : power stage (VBUS island, SW, VOUT), all small-signal parts, CC1, PD controller pins,
#           GND pour everywhere else (solid connection, it carries the buck's ground return).
#   In1.Cu: unbroken GND plane.
#   In2.Cu: VBUS pour (left + bottom-middle) and VOUT pour (right) - feeds every far pin by a via.
#   B.Cu  : USB D+/D- (USB-C -> Micro-Fit), CC2 crossing, GND pour.
# Vias are all 0.5/0.3 mm (no small-drill surcharge at JLCPCB) and tented.
P, T, V, G = b.P, b.track, b.via, (lambda xy: b.via("GND", xy))

# ================================================================== zones
b.zone("GND",  "F.Cu",   ((0, 0), (W, H)), priority=0, thermal=False)
b.zone("GND",  "In1.Cu", ((0, 0), (W, H)), priority=0)
b.zone("GND",  "B.Cu",   ((0, 0), (W, H)), priority=0)
b.zone("VBUS", "F.Cu",   ((6.4, 0.55), (14.05, 2.75)), priority=2, thermal=False)      # input cap / VIN island
b.zone("VBUS", "In2.Cu", [(5.8, 0.6), (15.8, 0.6), (15.8, 13.4), (19.2, 13.4), (19.2, 19.4), (5.8, 19.4)], priority=1)
b.zone("VOUT", "In2.Cu", [(16.1, 0.6), (32.4, 0.6), (32.4, 19.4), (19.5, 19.4), (19.5, 13.1), (16.1, 13.1)], priority=1)

# ================================================================== USB-C
T("GND", [P("USBC1", "A1B12"), P("USBC1", "4")], width=0.3)            # GND pads -> shell legs
T("GND", [P("USBC1", "B1A12"), P("USBC1", "1")], width=0.3)
T("VBUS", [P("USBC1", "A4B9"), (7.5, 7.6), (7.9, 7.3)], width=0.4); V("VBUS", (7.9, 7.3))
T("VBUS", [P("USBC1", "B4A9"), (8.0, 12.4)], width=0.4)
T("VBUS", [(8.0, 12.4), (8.0, 16.4), P("D1", "1")], width=0.5)
V("VBUS", (8.0, 13.9))
# CC1 straight to U2.7
T("CC1", [P("USBC1", "A5"), (10.0, 8.75), (10.75, 9.5), P("U2", "7")], width=0.2)
# CC2 crosses the data pads on B.Cu and comes up next to U2.6
T("CC2", [P("USBC1", "B5"), (7.9, 11.75)], width=0.2); V("CC2", (7.9, 11.75))
T("CC2", [(7.9, 11.75), (7.9, 8.0), (10.2, 8.0)], layer="B.Cu", width=0.2); V("CC2", (10.2, 8.0))
T("CC2", [(10.2, 8.0), (10.7, 8.5), P("U2", "6")], width=0.2)
# USB data: D- pads (B7, A7) sandwich D+ (A6). D- drops to B.Cu at each pad, D+ pads join on F.Cu.
T("USB_DN", [P("USBC1", "B7"), (8.5, 9.25)], width=0.2); V("USB_DN", (8.5, 9.25))
T("USB_DN", [P("USBC1", "A7"), (8.5, 10.25)], width=0.2); V("USB_DN", (8.5, 10.25))
T("USB_DP", [P("USBC1", "A6"), (9.3, 9.75), (9.3, 10.75), P("USBC1", "B6")], width=0.2)
V("USB_DP", (9.3, 10.25))
# pair on B.Cu under U2 to the Micro-Fit: D+ (pin 3, upper), D- (pin 4, lower)
T("USB_DN", [(8.5, 9.25), (8.5, 11.6), (19.9, 11.6), P("CN1", "4")], layer="B.Cu", width=0.2)
T("USB_DP", [(9.3, 10.25), (19.3, 10.25), (20.6, 8.95), P("CN1", "3")], layer="B.Cu", width=0.2)

# ================================================================== input caps + VIN (VBUS island on F.Cu)
for xy in ((6.8, 1.35), (6.8, 2.3), (12.4, 1.05)): V("VBUS", xy)
T("VBUS", [P("C5", "1"), (11.9, 2.41)], width=0.3)
# GND side: cap GND pads -> PGND strip, vias into the planes
T("GND", [P("C4", "2"), (10.75, 4.4), (11.35, 4.35)], width=0.6)
T("GND", [P("C5", "2"), (11.35, 4.35)], width=0.3)
T("GND", [(11.35, 3.57), (11.9, 3.57)], width=0.4)
T("GND", [P("C3", "2"), P("C4", "2")], width=0.6)
for xy in ((11.35, 4.35), (8.0, 6.4), (9.0, 6.3)): G(xy)
T("GND", [P("C3", "2"), (8.0, 6.4)], width=0.4); T("GND", [P("C4", "2"), (9.0, 6.3)], width=0.4)
T("GND", [P("U1", "10"), (11.9, 4.29), (11.35, 4.35)], width=0.2)           # MODE -> GND (Eco-mode)
T("GND", [P("U1", "3"), (13.85, 3.77)], width=0.2)                         # AGND -> PGND, single point
T("GND", [(14.0, 3.57), (14.5, 3.75)], width=0.4); G((14.5, 3.75))

# ================================================================== buck
T("BOOT", [P("U1", "7"), (15.45, 2.04), P("C1", "1")], width=0.2)
# SW leaves U1 as a 0.25 mm pad strip; a copper area takes it to the inductor at full width
b.zone("SW", "F.Cu", ((15.05, 2.8), (16.8, 3.95)), priority=3, thermal=False, clearance=0.15)
T("SW", [(15.2, 3.0), (16.2, 3.1), P("L1", "1")], width=0.25)
T("SW", [P("C1", "2"), (16.2, 2.7), (16.2, 3.1)], width=0.3)
# EN: R7 (VBUS) / R8 (GND) tap -> EN pin
T("EN", [P("R7", "2"), P("R8", "1"), (12.85, 5.52), P("U1", "1")], width=0.2)
V("VBUS", (11.5, 7.45)); T("VBUS", [P("R7", "1"), (11.5, 7.45)], width=0.25)
G((13.0, 7.45)); T("GND", [P("R8", "2"), (13.0, 7.45), P("R3", "2")], width=0.25)
# FB: R3 / R4 / R2 tops -> FB pin
T("FB", [P("R3", "1"), P("R4", "2"), P("R2", "2")], width=0.2)
T("FB", [P("R3", "1"), (13.35, 5.5), P("U1", "2")], width=0.2)
T("FF", [P("R4", "1"), P("C2", "2")], width=0.2)
T("VOUT", [P("R2", "1"), P("C2", "1")], width=0.25)
T("VOUT", [P("C2", "1"), (16.35, 7.55)], width=0.25); V("VOUT", (16.35, 7.55))

# ================================================================== output
T("VOUT", [P("L1", "2"), (22.48, 3.4)], width=1.5)
T("VOUT", [(22.48, 3.4), (22.48, 7.4), P("CN1", "1")], width=1.2)
for xy in ((22.48, 5.5), (22.48, 6.6)): V("VOUT", xy)
T("GND", [P("C6", "2"), (26.6, 2.6)], width=1.0)
for xy in ((26.7, 1.6), (26.7, 3.6)): G(xy)
T("GND", [(26.6, 2.6), (26.7, 1.6)], width=0.6); T("GND", [(26.6, 2.6), (26.7, 3.6)], width=0.6)
V("VOUT", (22.48, 15.55)); T("VOUT", [(22.48, 15.55), P("C7", "1")], width=0.8)
T("GND", [P("C7", "2"), (26.6, 17.4)], width=1.0); G((26.6, 16.6)); G((26.6, 18.2))
T("GND", [(26.6, 17.4), (26.6, 16.6)], width=0.6); T("GND", [(26.6, 17.4), (26.6, 18.2)], width=0.6)

# ================================================================== PD controller
T("VBUS", [P("U2", "8"), (10.1, 11.0)], width=0.3); V("VBUS", (10.1, 11.0))
T("VBUS", [P("U2", "1"), (17.5, 13.2), P("C8", "1")], width=0.3)
V("VBUS", (17.08, 14.8)); T("VBUS", [P("C8", "1"), (17.08, 14.8)], width=0.3)
T("GND", [P("C8", "2"), (18.6, 14.0)], width=0.3); G((18.6, 14.0))
for xy in ((13.5, 8.7), (15.5, 8.7), (13.5, 12.3), (15.5, 12.3)): G(xy)   # U2 EP / body stitching
T("GND", [(13.5, 8.7), (13.5, 9.6)], width=0.3); T("GND", [(15.5, 8.7), (15.5, 9.6)], width=0.3)
T("GND", [(13.5, 12.3), (13.5, 11.4)], width=0.3); T("GND", [(15.5, 12.3), (15.5, 11.4)], width=0.3)
T("CFG1", [P("U2", "9"), (10.4, 11.85), P("R1", "1")], width=0.2)
G((10.4, 15.4)); T("GND", [P("R1", "2"), (10.4, 15.4)], width=0.25)
T("PG_n", [P("U2", "10"), (12.8, 13.05), (12.8, 16.9), (13.5, 17.6), P("R6", "2")], width=0.2)
T("LED_PD_K", [P("R6", "1"), P("LED2", "1")], width=0.2)
V("VBUS", (16.42, 16.7)); T("VBUS", [P("LED2", "2"), (16.42, 16.7)], width=0.25)
T("GND", [P("D1", "2"), (11.39, 16.0)], width=0.6); G((11.39, 16.0))

# ================================================================== ON LED
T("LED_OUT_K", [P("R5", "1"), P("LED1", "1")], width=0.2)
G((18.57, 16.7)); T("GND", [P("R5", "2"), (18.57, 16.7)], width=0.25)
V("VOUT", (20.92, 16.7)); T("VOUT", [P("LED1", "2"), (20.92, 16.7)], width=0.25)

# ================================================================== GND stitching along the edges
for xy in ((5.2, 0.9), (15.4, 0.9), (28.0, 0.9), (32.1, 6.0), (32.1, 14.0), (28.0, 19.1), (13.0, 19.1),
           (5.2, 19.1), (0.9, 8.0), (0.9, 12.0)):
    G(xy)

# ================================================================== silkscreen: as little as possible
b.dot(11.8, 5.15, 0.3)                                  # U1 pin 1 (EN, bottom-left corner)
b.dot(18.7, 12.9, 0.3)                                  # U2 pin 1 (VHV, bottom-right corner)
b.bar(5.95, 17.6, 1.4, True)                            # D1 cathode bar (VBUS side)
b.label("PD", 16.0, 19.0, 0.8)                          # LED labels under the LEDs
b.label("ON", 20.5, 19.0, 0.8)
# back: everything a user needs to know (front stays clean)
b.label("e8s  pd12v6 mini", 16.0, 2.6, 1.0, "B.SilkS", bold=True)
b.label("USB-C PD in   12.6V 5A out", 16.0, 4.6, 0.8, "B.SilkS")
b.label("12V6", 23.6, 7.0, 0.8, "B.SilkS"); b.label("D+", 20.6, 7.0, 0.8, "B.SilkS")
b.label("GND", 23.6, 13.0, 0.8, "B.SilkS");  b.label("D-", 20.6, 13.0, 0.8, "B.SilkS")
b.label("output not current limited", 15.0, 15.8, 0.8, "B.SilkS")
b.label(REV, 15.0, 17.4, 0.8, "B.SilkS")
