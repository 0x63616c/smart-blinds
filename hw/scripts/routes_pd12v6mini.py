# Routes for pd12v6mini rev B (exec'd by layout_pd12v6mini.py; `b` = pcbkit.Board).
#
# Routing rules (so the copper looks deliberate):
#   * one width per job: SIG 0.2 mm (every signal), TAP 0.3 mm (power into 0402 pads),
#     PWR 0.6 mm (power into big pads). Heavy current runs in shaped copper areas, not traces.
#   * every track leaves its pad straight along the pad axis; corners are 45 deg chamfers of
#     the same size (path() below does it), never right angles or odd angles.
#   * top layer = pads + short pad-to-pad links. USB data runs on B.Cu, CC2 hops on In2,
#     VBUS/VOUT reach far pins through the In2 power pours.
#   * one via size (0.5/0.3), tented. GND vias only where a pad needs one.
# Layers: F.Cu parts + GND pour | In1 GND | In2 VBUS (left) / VOUT (right) | B.Cu USB data + GND.
import math

SIG, TAP, PWR = 0.2, 0.3, 0.6
P, V = b.P, b.via
def G(xy): b.via("GND", xy)

def path(net, pts, w=SIG, layer="F.Cu", c=0.3):
    """Track through orthogonal/45-degree waypoints; each right-angle corner becomes a 45-degree chamfer."""
    out = [pts[0]]
    for a, p, q in zip(pts, pts[1:], pts[2:]):
        d1, d2 = (p[0] - a[0], p[1] - a[1]), (q[0] - p[0], q[1] - p[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        u1, u2 = (d1[0] / l1, d1[1] / l1), (d2[0] / l2, d2[1] / l2)
        if abs(u1[0] * u2[0] + u1[1] * u2[1]) < 1e-6:          # right angle -> chamfer
            k = min(c, l1 / 2, l2 / 2)
            out += [(round(p[0] - u1[0] * k, 3), round(p[1] - u1[1] * k, 3)),
                    (round(p[0] + u2[0] * k, 3), round(p[1] + u2[1] * k, 3))]
        else:
            out.append(p)
    out.append(pts[-1])
    b.track(net, out, layer=layer, width=w)

# ================================================================== copper areas (pours)
b.zone("GND", "F.Cu",   ((0, 0), (W, H)), priority=0, thermal=False)
b.zone("GND", "In1.Cu", ((0, 0), (W, H)), priority=0)
b.zone("GND", "B.Cu",   ((0, 0), (W, H)), priority=0)
# input: C3/C4/C5 VBUS pads and U1 VIN on one copper island
b.zone("VBUS", "F.Cu", ((6.6, 1.9), (15.25, 3.95)), priority=2, thermal=False)
# switch node: U1 SW strip -> C1 -> L1 pad 1
b.zone("SW", "F.Cu", ((16.15, 3.98), (18.45, 5.3)), priority=3, thermal=False, clearance=0.15)
# output: L1 pad 2 -> C6 -> straight down onto Micro-Fit pin 1, with a tab for the feed-forward cap
b.zone("VOUT", "F.Cu", [(21.47, 5.25), (26.95, 5.25), (26.95, 6.95), (26.35, 7.55), (26.35, 12.0),
                        (24.85, 12.0), (24.85, 7.55), (24.25, 6.95), (22.55, 6.95), (22.55, 8.35),
                        (21.45, 8.35)], priority=2, thermal=False)
# In2: VBUS on the left, VOUT on the right
b.zone("VBUS", "In2.Cu", [(5.8, 0.6), (16.2, 0.6), (16.2, 10.0), (17.5, 10.0), (17.5, 17.2),
                          (13.6, 17.2), (13.6, 23.9), (5.8, 23.9)], priority=1)
b.zone("VOUT", "In2.Cu", [(16.5, 0.6), (34.4, 0.6), (34.4, 23.9), (13.9, 23.9), (13.9, 17.5),
                          (17.8, 17.5), (17.8, 9.7), (16.5, 9.7)], priority=1)

# ================================================================== INPUT: USB-C
path("GND", [P("USBC1", "A1B12"), P("USBC1", "4")], PWR)              # GND pads -> shell legs
path("GND", [P("USBC1", "B1A12"), P("USBC1", "1")], PWR)
path("VBUS", [P("USBC1", "A4B9"), (8.75, 11.1)], PWR)                 # VBUS -> In2 (2 vias each side)
V("VBUS", (7.95, 11.1)); V("VBUS", (8.75, 11.1))
path("VBUS", [P("USBC1", "B4A9"), (7.6, 15.9), (8.1, 16.4), (8.9, 16.4)], PWR)
V("VBUS", (8.1, 16.4)); V("VBUS", (8.9, 16.4))
path("CC1", [P("USBC1", "A5"), P("U2", "7")])                         # straight across to U2.7
# D- pads (B7, A7) sandwich D+ (A6): D- drops to B.Cu at each pad, D+ pads join on top
path("USB_DN", [P("USBC1", "B7"), (8.4, 12.75)]); V("USB_DN", (8.4, 12.75))
path("USB_DN", [P("USBC1", "A7"), (8.4, 13.75)]); V("USB_DN", (8.4, 13.75))
path("USB_DP", [P("USBC1", "A6"), (9.2, 13.25), (9.2, 14.25), P("USBC1", "B6")]); V("USB_DP", (9.2, 13.75))
# CC2 hops over the data pads on In2 and comes up beside U2.6
path("CC2", [P("USBC1", "B5"), (8.0, 15.25)]); V("CC2", (8.0, 15.25))
path("CC2", [(8.0, 15.25), (10.0, 15.25), (10.0, 11.25), (10.6, 11.25)], layer="In2.Cu"); V("CC2", (10.6, 11.25))
path("CC2", [(10.6, 11.25), P("U2", "6")])
# USB 2.0 pair on B.Cu, under U2, to Micro-Fit pins 3 (D+) and 4 (D-)
path("USB_DN", [(8.4, 12.75), (8.4, 14.6), (22.2, 14.6), P("CN1", "4")], layer="B.Cu")
path("USB_DP", [(9.2, 13.75), (20.85, 13.75), P("CN1", "3")], layer="B.Cu")
# TVS: VBUS / GND each by a via straight below its pad
path("VBUS", [P("D1", "1"), (6.16, 22.0)], PWR); V("VBUS", (6.16, 22.0))
path("GND", [P("D1", "2"), (10.54, 22.0)], PWR); G((10.54, 22.0))

# ================================================================== BUCK
for xy in ((7.05, 2.5), (7.05, 3.5), (11.8, 2.6), (14.45, 2.3)):     # VBUS island <- In2
    V("VBUS", xy)
G((8.4, 7.6)); G((10.6, 7.6))                                          # input-cap GND
path("GND", [P("U1", "10"), (12.45, 5.49)]); G((12.45, 5.49))         # MODE -> GND (Eco-mode)
path("GND", [P("U1", "3"), (14.95, 4.97)])                             # AGND -> PGND, one point
path("BOOT", [P("U1", "7"), P("C1", "1")])                             # straight boot link
path("SW", [P("C1", "2"), (17.92, 4.4)], TAP)                          # C1 into the SW area
# EN: pin straight down to R8, R7 beside it
path("EN", [P("U1", "1"), P("R8", "1")])
path("EN", [P("R7", "2"), P("R8", "1")])
path("VBUS", [P("R7", "1"), (11.05, 8.83)], TAP); V("VBUS", (11.05, 8.83))
# FB: pin -> R3, then one straight bus along the tops of R3 / R2 / R4
path("FB", [P("U1", "2"), (14.45, 7.1), (15.95, 7.1), P("R3", "1")])
path("FB", [P("R3", "1"), P("R4", "2")])
path("FF", [P("R4", "1"), P("C2", "2")])                              # along the bottoms
# C2 top pad (VOUT) sits inside the VOUT copper tab
path("VOUT", [P("R2", "1"), (18.85, 8.83)], TAP); V("VOUT", (18.85, 8.83))

# ================================================================== OUTPUT
V("VOUT", (25.6, 8.6)); V("VOUT", (25.6, 9.6))                        # output strip -> In2
G((27.45, 2.6)); G((27.45, 3.6))                                       # C6 GND
path("VOUT", [(23.75, 22.52), P("C7", "1"), (27.45, 22.52)], PWR)      # C7 VOUT -> In2 both sides
V("VOUT", (23.75, 22.52)); V("VOUT", (27.45, 22.52))
G((23.75, 19.48)); G((27.45, 19.48))                                   # C7 GND

# ================================================================== PD + status columns
path("VBUS", [P("U2", "8"), (10.6, 13.25)], PWR); V("VBUS", (10.6, 13.25))
path("CFG1", [P("U2", "9"), (10.4, 14.25), P("R1", "1")])
path("PG_n", [P("U2", "10"), P("R6", "2")])                            # left column, one straight line:
path("LED_PD_K", [P("R6", "1"), P("LED2", "1")])                       #   PG -> R6 -> LED2 -> VBUS
path("VBUS", [P("LED2", "2"), (12.0, 21.0)], TAP); V("VBUS", (12.0, 21.0))
path("VBUS", [P("U2", "1"), P("C8", "1")], TAP)                        # right column: VHV -> C8
path("VBUS", [P("C8", "1"), (17.1, 16.48)], TAP); V("VBUS", (17.1, 16.48))
V("VOUT", (18.0, 18.25)); path("VOUT", [(18.0, 18.25), P("LED1", "2")], TAP)   # VOUT -> LED1 -> R5 -> GND
path("LED_OUT_K", [P("LED1", "1"), P("R5", "1")])

# ================================================================== silkscreen
b.dot(12.95, 6.35, 0.3)                       # U1 pin 1 (EN corner)
b.dot(19.25, 15.9, 0.3)                       # U2 pin 1 (VHV corner)
b.bar(5.0, 20.4, 1.0, True)                  # D1 cathode
b.label("PD", 12.0, 22.9, 1.0, bold=True)     # what each LED means, under its column
b.label("ON", 18.0, 22.9, 1.0, bold=True)
# back: product, rating, Micro-Fit pin names, warning
b.label("e8s  pd12v6 mini", 15.0, 3.0, 1.0, "B.SilkS", bold=True)
b.label("USB-C PD in   12.6V 5A out", 15.0, 4.8, 0.8, "B.SilkS")
b.label("12V6", 25.6, 10.4, 0.8, "B.SilkS"); b.label("D+", 22.6, 10.4, 0.8, "B.SilkS")
b.label("GND", 25.6, 16.6, 0.8, "B.SilkS");  b.label("D-", 22.6, 16.6, 0.8, "B.SilkS")
b.label("output not current limited", 15.5, 20.2, 0.8, "B.SilkS")
b.label(REV, 15.5, 21.8, 0.8, "B.SilkS")
