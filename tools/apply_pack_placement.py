#!/usr/bin/env python3
"""Replay the unrouted retained-carrier placement with KiCad's Python runtime.

Assembly x/y coordinates are shared with the mechanical model. The companion
component view is mirrored in X because its component face points toward -Z.
Never replay this study over routed copper. This is not a release generator.
"""
import argparse
import json
import math
import tempfile
from pathlib import Path
import uuid

import pcbnew
import wx
from normalize_placement_pcb import normalize

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'hw/placement/blind-pack/placement.json'
MECHANICAL = ROOT / 'cad/parameters/retained-interfaces.json'
NS = uuid.UUID('5549cf1f-843d-5355-bdb3-bf3ea0319d53')


def apply(which, output):
    plan = json.loads(PLAN.read_text())
    mechanical = json.loads(MECHANICAL.read_text())['carrier']
    assert mechanical['outline'] == plan['outline_mm'] == [86, 104]
    path = ROOT / f'hw/layouts/blind-pack-{which}/{which}-test/{which}-test.kicad_pcb'
    reference_text = path.read_text()
    board = pcbnew.LoadBoard(str(path))
    if any(board.GetTracks()):
        raise ValueError('Refusing to replace placement on a routed board')
    old_footprints = list(board.GetFootprints())
    old_drawings = list(board.GetDrawings())
    old_zones = list(board.Zones())
    for fp in old_footprints:
        if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            try:address=fp.GetFieldText('atopile_address')
            except KeyError:address=None
            assert not address
            assert all(p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and not p.GetNumber() for p in fp.Pads())
            board.Remove(fp)
    footprints = {f.GetFieldText('atopile_address'): f for f in board.GetFootprints()}
    assert set(footprints) == set(plan['boards'][which]['placements'])
    replacements = {}

    def point(xy):
        x = 100 + xy[0] if which == 'primary' else 186 - xy[0]
        return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(204 - xy[1]))

    def identity(item, name):
        replacements[item.m_Uuid.AsString()] = str(uuid.uuid5(NS, which + '/' + name))

    for name, placement in plan['boards'][which]['placements'].items():
        fp = footprints[name]
        assert fp.GetLayer() == pcbnew.F_Cu, 'All components must face outward'
        fp.SetPosition(point(placement['xy']))
        fp.SetOrientationDegrees(placement['rotation'])
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
    for item in old_drawings:
        board.Remove(item)
    for item in old_zones:
        if not item.GetIsRuleArea():
            raise ValueError('Refusing to remove a copper zone')
        board.Remove(item)
    board.GetDesignSettings().SetCopperLayerCount(2)
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))

    serial = 0
    def segment(a, b):
        nonlocal serial
        item = pcbnew.PCB_SHAPE(board)
        item.SetShape(pcbnew.SHAPE_T_SEGMENT)
        item.SetStart(point(a)); item.SetEnd(point(b))
        item.SetLayer(pcbnew.Edge_Cuts); item.SetWidth(pcbnew.FromMM(.05))
        identity(item, f'outline-{serial}'); serial += 1; board.Add(item)

    def arc(a, mid, b):
        nonlocal serial
        item = pcbnew.PCB_SHAPE(board)
        item.SetShape(pcbnew.SHAPE_T_ARC)
        item.SetArcGeometry(point(a), point(mid), point(b))
        item.SetLayer(pcbnew.Edge_Cuts); item.SetWidth(pcbnew.FromMM(.05))
        identity(item, f'outline-{serial}'); serial += 1; board.Add(item)

    r = plan['corner_radius_mm']; k = r / math.sqrt(2)
    segment([r, 0], [86-r, 0]); arc([86-r, 0], [86-r+k, r-k], [86, r])
    segment([86, r], [86, 104-r]); arc([86, 104-r], [86-r+k, 104-r+k], [86-r, 104])
    segment([86-r, 104], [r, 104]); arc([r, 104], [r-k, 104-r+k], [0, 104-r])
    segment([0, 104-r], [0, r]); arc([0, r], [r-k, r-k], [r, 0])

    def keepout(name, vertices, footprints=True):
        zone = pcbnew.ZONE(board); zone.SetIsRuleArea(True); zone.SetZoneName(name)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask(2))
        zone.SetDoNotAllowTracks(True); zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowPads(True); zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowFootprints(footprints)
        poly = zone.Outline(); poly.NewOutline()
        for p in vertices: poly.Append(point(p))
        identity(zone, name); board.Add(zone)

    for i, box in enumerate(mechanical['copper_keepout_local_xy']):
        x0, y0, x1, y1 = box
        keepout(f'RF_NO_METAL_{i}', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    for i, centre in enumerate(mechanical['mounting_holes_local']):
        fp = pcbnew.FootprintLoad(str(ROOT/'hw/parts/blind-pack-features'),'MountingHole_M3_3.4mm')
        if fp is None:raise ValueError('Missing local mounting-hole footprint')
        fp.SetFPID(pcbnew.LIB_ID('blind-pack-features', 'MountingHole_M3_3.4mm'))
        fp.SetReference(f'H{i+1}'); fp.SetValue('M3 clearance 3.4 mm')
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        fp.SetPosition(point(centre)); identity(fp, f'mounting-hole-{i}')
        pads=list(fp.Pads());assert len(pads)==1
        pad=pads[0];assert pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH and not pad.GetNumber()
        assert pad.GetDrillSize().x==pcbnew.FromMM(mechanical['mounting_hole_diameter'])
        identity(pad, f'mounting-hole-pad-{i}'); board.Add(fp)
        radius = mechanical['bare_support_land_diameter']/2
        # The pinned compiler retains only one polygon per zone. Four
        # single-polygon quadrants preserve the full annulus and its NPTH void.
        for quadrant in range(4):
            angles=[quadrant*math.pi/2+j*math.pi/24 for j in range(13)]
            vertices=[[centre[0]+radius*math.cos(a),centre[1]+radius*math.sin(a)] for a in angles]
            vertices += [[centre[0]+1.8*math.cos(a),centre[1]+1.8*math.sin(a)] for a in reversed(angles)]
            keepout(f'BARE_CORNER_SUPPORT_{i}_{quadrant}',vertices,False)
    support = mechanical['outward_supports']['front_primary' if which == 'primary' else 'rear_companion']
    spans = support['local_x_intervals'] if which == 'primary' else support['lower_local_x_intervals']
    low_y, high_y = support['local_y'] if which == 'primary' else support['lower_local_y']
    # Clipped mounting-hole geometry below is deliberately restricted to this
    # reviewed support/mounting arrangement; changed mechanics must be reviewed.
    assert (low_y, high_y) == (2, 5)
    assert mechanical['mounting_holes_local'] == [[4, 4], [82, 4], [4, 100], [82, 100]]
    # The end spans meet mounting-hole centres. Cut the physical NPTH void
    # out of each rule polygon instead of waiving pad restrictions globally.
    def lower_support_polygon(x0, x1):
        r = 1.8; upper = math.asin(1/r)
        if x0 == 4:
            angles = [upper + (-math.pi/2-upper)*i/32 for i in range(33)]
            return [(x0,2),(x1,2),(x1,5)] + [(4+r*math.cos(a),4+r*math.sin(a)) for a in angles]
        if x1 == 82:
            angles = [-math.pi/2 + (-math.pi-upper+math.pi/2)*i/32 for i in range(33)]
            return [(x0,2),(x1,2)] + [(82+r*math.cos(a),4+r*math.sin(a)) for a in angles] + [(x0,5)]
        return [(x0,2),(x1,2),(x1,5),(x0,5)]
    for i, (x0,x1) in enumerate(spans):
        keepout(f'LOWER_SUPPORT_{i}', lower_support_polygon(x0,x1))
    if which == 'companion':
        x0, x1 = support['upper_local_x']; y0, y1 = support['upper_local_y']
        keepout('UPPER_SUPPORT', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        for i, (x0,y0,x1,y1) in enumerate(support['lower_bridge_bare_rectangles_local_xy']):
            keepout(f'LOWER_BRIDGE_SUPPORT_{i}', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never leave a KiCad-10 file in the canonical layout if normalization or
    # the independent graph check fails. The pinned compiler reads KiCad 9.
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder)/'placement.kicad_pcb'
        reference = Path(folder)/'reference.kicad_pcb'
        reference.write_text(reference_text)
        pcbnew.SaveBoard(str(raw), board)
        text = raw.read_text()
        for old, new in replacements.items(): text = text.replace(old, new)
        text = normalize(text, reference)
    output.write_text(text)
    print(f'{which}: {len(footprints)} footprints placed; UNROUTED study at {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', choices=['primary', 'companion'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    app = wx.App(False); quiet = wx.LogNull()
    apply(args.board, args.output or ROOT / f'hw/layouts/blind-pack-{args.board}/{args.board}-test/{args.board}-test.kicad_pcb')
