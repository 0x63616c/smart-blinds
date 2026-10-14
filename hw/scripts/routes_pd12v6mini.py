# Routes for pd12v6mini rev E (exec'd by layout_pd12v6mini.py; `b` = pcbkit.Board).
#
# Routing rules (so the copper looks deliberate):
#   * one width per job: SIG 0.2 mm (every signal), TAP 0.3 mm (power into 0402 pads),
#     PWR 0.6 mm (power into big pads). Heavy current runs in shaped copper areas, not traces.
#   * every track leaves its pad straight along the pad axis and enters the far pad the same way;
#     corners are 45 deg chamfers of one size (path() below), never right angles or odd angles.
#   * a via sits in line with the pad it serves, never hung off the side of a track.
#   * no top copper passes under a part body except into that part's own pad (check_layout.py).
#   * top layer = pads, short pad-to-pad links and the power path drawn as copper
#     (USB-C -> TVS -> input caps -> TPS56637 -> inductor -> output cap -> Micro-Fit).
#     USB data and CC2 run on B.Cu, CC1 hops on In2, far power pins reach In2 by one via.
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

def x(ref, pad): return P(ref, pad)[0]
def y(ref, pad): return P(ref, pad)[1]

# ================================================================== copper areas (pours)
b.zone("GND", "F.Cu",   ((0, 0), (W, H)), priority=0, thermal=False)
b.zone("GND", "In1.Cu", ((0, 0), (W, H)), priority=0)
b.zone("GND", "B.Cu",   ((0, 0), (W, H)), priority=0)
# input power path on top: USB-C VBUS -> corner over the TVS cathode -> up the TVS column ->
# along the input caps -> U1 VIN
TOP = 3.75                                                            # top edge of the VBUS strip
b.zone("VBUS", "F.Cu", [(D1X - 0.85, 10.4), (D1X - 0.85, TOP), (UX + 0.55, TOP), (UX + 0.55, PY - 0.6),
                        (D1X + 0.85, PY - 0.6), (D1X + 0.85, 10.4)], priority=2, thermal=False)
# switch node: U1 SW strip -> L1 pad 1, notched up to take C1's SW pad
L1P1 = x("L1", "1")
b.zone("SW", "F.Cu", [(UX + 1.45, PY - 0.62), (x("C1", "2") - 0.3, PY - 0.62), (x("C1", "2") - 0.3, PY - 1.25),
                      (L1P1, PY - 1.25), (L1P1, PY + 0.7), (UX + 1.45, PY + 0.7)], priority=3, thermal=False,
       clearance=0.15)
# output: L1 pad 2 -> C6 VOUT pad -> straight down onto Micro-Fit pin 1 (bottom edge clear of the CN1 label)
C6X = x("C6", "1")
b.zone("VOUT", "F.Cu", [(x("L1", "2") - 0.55, PY - 2.25), (C6X + 0.8, PY - 2.25), (C6X + 0.8, y("CN1", "1")),
                        (C6X - 0.8, y("CN1", "1")), (C6X - 0.8, PY + 1.1), (x("L1", "2") - 0.55, PY + 1.1)],
       priority=2, thermal=False)
# In2: VBUS on the left and along the bottom of the PD cell, VOUT top right and the OUTPUT cell
b.zone("VBUS", "In2.Cu", [(0.6, 0.6), (UX + 1.85, 0.6), (UX + 1.85, YM - 0.15), (XB, YM - 0.15), (XB, H - 0.6),
                          (0.6, H - 0.6)], priority=1)
b.zone("VOUT", "In2.Cu", [(UX + 2.15, 0.6), (W - 0.6, 0.6), (W - 0.6, H - 0.6), (XB + 0.3, H - 0.6),
                          (XB + 0.3, YM - 0.45), (UX + 2.15, YM - 0.45)], priority=1)

# ================================================================== INPUT: USB-C + TVS
# GND pads A1B12 / B1A12 join the shell legs through the solid top GND pour (no odd-angle stubs)
path("VBUS", [P("USBC1", "A4B9"), (D1X, y("USBC1", "A4B9"))], PWR)    # straight across onto the TVS cathode end
# USB-C fan-out vias sit on three columns 0.75 mm apart: X1 CC1 / VBUS, X2 D- / VBUS, X3 D+ loop / CC2
X1, X2, X3 = 7.9, 8.65, 9.4
b4 = P("USBC1", "B4A9")                                               # other VBUS pad -> In2, two vias in line
path("VBUS", [b4, (X2, b4[1])], PWR); V("VBUS", (X1, b4[1])); V("VBUS", (X2, b4[1]))
for yy in (y("D1", "2") + 1.45, y("D1", "2") + 2.25):                 # TVS GND -> In1, in line below it
    G((D1X, yy))
# The pins alternate D-, D+, D-, D+ (B7, A6, A7, B6), so one pair must loop: each D- pad drops to B.Cu
# at X2, and the D+ pads join on top in a rectangle around them, dropping once at its corner on X3
dn1, dn2, dp1, dp2 = P("USBC1", "B7"), P("USBC1", "A7"), P("USBC1", "A6"), P("USBC1", "B6")
path("USB_DN", [dn1, (X2, dn1[1])]); V("USB_DN", (X2, dn1[1]))
path("USB_DN", [dn2, (X2, dn2[1])]); V("USB_DN", (X2, dn2[1]))
path("USB_DP", [dp1, (X3, dp1[1]), (X3, dp2[1]), dp2]); V("USB_DP", (X3, dp1[1]))
# CC: CC1 hops on In2, CC2 runs on B.Cu, both come up in the via column beside the CH224A
cc1, cc2 = P("USBC1", "A5"), P("USBC1", "B5")
path("CC1", [cc1, (X1, cc1[1])]); V("CC1", (X1, cc1[1]))
path("CC2", [cc2, (X3, cc2[1])]); V("CC2", (X3, cc2[1]))            # clear of the B4A9 vias
VCOL = x("U2", "6") - 1.25                                            # via column left of U2
XC = 14.5                                                             # CC1 drops down here on In2
path("CC1", [(X1, cc1[1]), (XC, cc1[1]), (XC, y("U2", "7") - (VCOL - XC)), (VCOL, y("U2", "7"))], layer="In2.Cu")
path("CC2", [(X3, cc2[1]), (X3, y("U2", "6")), (VCOL, y("U2", "6"))], layer="B.Cu")   # down, then across under the back text
# USB 2.0 pair on B.Cu along the centre line, fanned out symmetrically into Micro-Fit pins 3 / 4
p3, p4 = P("CN1", "3"), P("CN1", "4")
XF = p3[0] - 3.0                                                      # start of the 45-degree fan-out
path("USB_DP", [(X3, dp1[1]), (XF, dp1[1]), (XF + (dp1[1] - p3[1]), p3[1]), p3], layer="B.Cu")
path("USB_DN", [(X2, dn1[1]), (X2, dn2[1]), (XF, dn2[1]), (XF + (p4[1] - dn2[1]), p4[1]), p4], layer="B.Cu")

# ================================================================== BUCK
for ref in ("C3", "C4", "C9"):                                        # each input cap: In2 VBUS via above,
    V("VBUS", (x(ref, "1"), TOP + 0.35))                              # In1 GND via below, both in line
    G((x(ref, "2"), PY + 3.0))
path("GND", [P("U1", "10"), (UX - 2.25, y("U1", "10"))]); G((UX - 2.25, y("U1", "10")))   # MODE -> GND
path("GND", [P("U1", "3"), (x("U1", "3"), PY + 2.3)]); G((x("U1", "3"), PY + 2.3))       # AGND -> GND plane
path("BOOT", [P("U1", "7"), P("C1", "1")])                             # straight boot link
path("EN", [P("U1", "1"), P("R8", "1")])                               # EN straight down to R8 ...
path("EN", [P("R7", "2"), P("R8", "1")])                               # ... R7 beside it
path("FB", [P("U1", "2"), (x("U1", "2"), RY - 1.0), (x("R3", "1"), RY - 1.0), P("R3", "1")])
path("FB", [P("R3", "1"), P("R4", "2")])                               # FB bus along the tops
path("FF", [P("R4", "1"), P("C2", "2")])                               # FF along the bottoms
path("VOUT", [(x("C2", "1"), PY + 3.7), P("C2", "1")], TAP)             # C2 straight off L1 pad 2's end
VIA_ROW = RY + 1.2                                                     # power vias in line under the row
path("VBUS", [P("R7", "1"), (x("R7", "1"), VIA_ROW)], TAP); V("VBUS", (x("R7", "1"), VIA_ROW))
path("VOUT", [P("R2", "1"), (x("R2", "1"), VIA_ROW)], TAP); V("VOUT", (x("R2", "1"), VIA_ROW))

# ================================================================== PD
path("CC2", [(VCOL, y("U2", "6")), P("U2", "6")]); V("CC2", (VCOL, y("U2", "6")))
path("CC1", [(VCOL, y("U2", "7")), P("U2", "7")]); V("CC1", (VCOL, y("U2", "7")))
path("VBUS", [P("U2", "8"), (VCOL, y("U2", "8"))], TAP); V("VBUS", (VCOL, y("U2", "8")))
path("CFG1", [P("U2", "9"), P("R1", "1")])
path("PG_n", [P("U2", "10"), P("R6", "2")])                            # PD LED on pin 10's line
path("LED_PD_K", [P("R6", "1"), P("LED2", "1")])
led2v = (x("LED2", "2") - 0.8, SY)
path("VBUS", [P("LED2", "2"), led2v], TAP); V("VBUS", led2v)
vhv = (x("U2", "1") + 1.25, y("U2", "1"))
path("VBUS", [P("U2", "1"), vhv, P("C8", "1")], TAP); V("VBUS", vhv)  # pin 1 -> via -> C8, one line

# ================================================================== OUTPUT
# the output strip reaches In2 through Micro-Fit pin 1 itself (plated through), so no extra vias
path("GND", [P("C7", "2"), P("CN1", "2")], PWR)                        # C7 GND pad straight up to pin 2
c7v = P("C7", "1")                                                     # C7 VOUT -> In2, in line to its right
c7a, c7b = (c7v[0] + 1.35, c7v[1]), (c7v[0] + 2.15, c7v[1])
path("VOUT", [c7v, c7b], PWR); V("VOUT", c7a); V("VOUT", c7b)
# ON status LED (bottom of OUTPUT): VOUT via -> LED1 -> R5 -> GND
led1v = (x("LED1", "2") + 0.8, SY)
path("VOUT", [P("LED1", "2"), led1v], TAP); V("VOUT", led1v)
path("LED_OUT_K", [P("LED1", "1"), P("R5", "1")])

# ================================================================== silkscreen
b.dot(x("U1", "1") - 0.5, y("U1", "1") + 0.6, 0.3)                    # U1 pin 1 (EN), just off its corner
b.dot(x("U2", "1") + 0.15, y("U2", "1") + 0.75, 0.3)                  # U2 pin 1 (VHV), just below the pin
b.bar(D1X, y("D1", "1") - 1.5, 1.6, False)                             # D1 cathode (VBUS) end
b.label("PD", x("LED2", "1") - 0.42, SY - 1.0, 0.8, bold=True)          # what each LED means
b.label("ON", x("LED1", "1") + 0.42, SY - 1.0, 0.8, bold=True)
# back: product, rating, Micro-Fit pin names, warning
BX = UX + 3.85                                                         # clear of the cap vias on the left
b.label("e8s  pd12v6 mini", BX, 2.9, 1.0, "B.SilkS", bold=True)
b.label("USB-C PD in   12.6V 5A out", BX, 5.2, 0.8, "B.SilkS")
b.label("12V6", x("CN1", "1"), y("CN1", "1") - 1.6, 0.8, "B.SilkS"); b.label("D+", x("CN1", "3"), y("CN1", "3") - 1.6, 0.8, "B.SilkS")
b.label("GND", x("CN1", "2"), y("CN1", "2") + 1.6, 0.8, "B.SilkS");  b.label("D-", x("CN1", "4"), y("CN1", "4") + 1.6, 0.8, "B.SilkS")
b.label("output not current limited", W / 2 - 1.0, 15.1, 0.8, "B.SilkS")
b.label(REV, W / 2 - 1.0, 16.7, 0.8, "B.SilkS")
