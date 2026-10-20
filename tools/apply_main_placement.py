#!/usr/bin/env python3
"""Apply the explicit unrouted placement study with KiCad's Python runtime.

Never run on a routed board. Component placement is preliminary, not a routing,
thermal, manufacturing or installed-fit acceptance. Coordinates use the shared
mechanical u/v axes, with KiCad x=100+u and y=175-v.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import uuid

import pcbnew
import wx
from normalize_placement_pcb import normalize
from apply_harness_keepouts import restore
from kicad_sexpr import parse, dumps

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'hw/layouts/blind-main/main-test/main-test.kicad_pcb'
PLAN = ROOT / 'hw/placement/blind-main/placement.json'
MECHANICAL = ROOT / 'cad/parameters/retained-interfaces.json'
NAMESPACE = uuid.UUID('ad7b678f-3919-5a1b-828d-cf42a1360ea2')
UUID_REPLACEMENTS = {}


def point(uv):
    return pcbnew.VECTOR2I(pcbnew.FromMM(100+uv[0]), pcbnew.FromMM(175-uv[1]))


def stable_id(item, name):
    UUID_REPLACEMENTS[str(item.m_Uuid.AsString())] = str(uuid.uuid5(NAMESPACE, name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BOARD)
    args = parser.parse_args()
    app = wx.App(False)
    quiet = wx.LogNull()
    reference_text=BOARD.read_text()
    board = pcbnew.LoadBoard(str(BOARD))
    if any(board.GetTracks()):
        raise ValueError('Refusing placement replay over existing routed tracks/vias')
    plan = json.loads(PLAN.read_text())
    mechanical = json.loads(MECHANICAL.read_text())['controller']
    if mechanical['board_size_xyz'][1:] != [68.5,54]:
        raise ValueError('Mechanical board dimensions changed; review outline first')
    fprints = {f.GetFieldText('atopile_address'):f for f in board.GetFootprints()}
    if set(fprints) != set(plan['placements']):
        raise ValueError('Component set changed; update the placement study explicitly')
    for name, pos in plan['placements'].items():
        f = fprints[name]
        f.SetPosition(point(pos['uv']))
        f.SetOrientationDegrees(pos['rotation'])
        f.Reference().SetVisible(False)
        f.Value().SetVisible(False)

    # Source-generated board drawings and rule areas only; no electrical nets
    # or library geometry are modified here. Current study has no routed copper.
    drawings=list(board.GetDrawings());zones=list(board.Zones())
    for zone in zones:
        if not zone.GetIsRuleArea():
            raise ValueError('Refusing to discard a copper zone')
    for item in drawings:
        board.Remove(item)
    for zone in zones:
        board.Remove(zone)
    board.GetDesignSettings().SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))

    serial = 0
    def segment(a,b):
        nonlocal serial
        s=pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(point(a)); s.SetEnd(point(b)); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(.05)); stable_id(s,f'edge-{serial}');serial+=1;board.Add(s)
    def arc(a,m,b):
        nonlocal serial
        s=pcbnew.PCB_SHAPE(board);s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(point(a),point(m),point(b));s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(.05));stable_id(s,f'edge-{serial}');serial+=1;board.Add(s)

    # Straight shortened top: no substrate beneath module antenna, no fragile
    # connector-side fingers. Rounded edge notches match removable CAD clamps.
    outline=mechanical['board_outline_local_uv']
    notch=mechanical['edge_notches'];r=notch['inside_corner_radius']
    for a,b in zip(outline,outline[1:]+outline[:1]):
        if a==[54,0] and b==[54,68.5]:
            previous=a
            for centre in notch['centres_local_v']:
                low=centre-notch['width_along_v']/2
                high=centre+notch['width_along_v']/2
                back=54-notch['depth_along_u'];cx=back+r
                segment(previous,[54,low]);segment([54,low],[cx,low])
                arc([cx,low],[cx-r/math.sqrt(2),low+r-r/math.sqrt(2)],[back,low+r])
                segment([back,low+r],[back,high-r])
                arc([back,high-r],[cx-r/math.sqrt(2),high-r+r/math.sqrt(2)],[cx,high])
                segment([cx,high],[54,high]);previous=[54,high]
            segment(previous,b)
        else:segment(a,b)

    def keepout(name, box, footprints=False):
        z=pcbnew.ZONE(board);z.SetIsRuleArea(True);z.SetZoneName(name)
        z.SetLayerSet(pcbnew.LSET.AllCuMask(4))
        z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowFootprints(footprints)
        poly=z.Outline();poly.NewOutline()
        x0,y0,x1,y1=box
        for uv in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:poly.Append(point(uv))
        stable_id(z,'keepout-'+name);board.Add(z)

    # The module's own required body lands/ground are the explicit exception.
    # Its full body is allowed, but unrelated parts cannot use that exception.
    keepout('RF_LEFT_NO_METAL',[-9.5,53.5,4.75,90])
    keepout('RF_RIGHT_NO_METAL',[24.25,53.5,38.5,90])
    keepout('RF_ANTENNA_NO_METAL',[4.75,68.5,24.25,90])
    for i,box in enumerate(notch['bare_land_local_uv']):
        keepout('CLAMP_BARE_LAND_'+str(i),box,True)

    title=pcbnew.PCB_TEXT(board);title.SetText('SB-C1 R0');title.SetPosition(point([27,1]))
    title.SetLayer(pcbnew.B_SilkS);title.SetMirrored(True)
    title.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(.8),pcbnew.FromMM(.8)))
    title.SetTextThickness(pcbnew.FromMM(.12));stable_id(title,'board-id');board.Add(title)
    pcbnew.SaveBoard(str(args.output),board)
    # KiCad's stackup C++ object is not exposed in this Python build. Replace
    # the inherited two-layer descriptor with a coherent four-layer study.
    # Values follow JLC's published 1.6mm JLC3313 table, not a selected quote;
    # final stackup and USB field-solver geometry remain manufacturing gates.
    text=args.output.read_text()
    for old,new in UUID_REPLACEMENTS.items():
        text=text.replace(old,new)
    stack='''\t\t(stackup
            (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
            (layer "F.Paste" (type "Top Solder Paste"))
            (layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))
            (layer "F.Cu" (type "copper") (thickness 0.035))
            (layer "dielectric 1" (type "prepreg") (thickness 0.0994) (material "FR4 3313") (epsilon_r 4.05) (loss_tangent 0.02))
            (layer "In1.Cu" (type "copper") (thickness 0.0152))
            (layer "dielectric 2" (type "core") (thickness 1.265) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
            (layer "In2.Cu" (type "copper") (thickness 0.0152))
            (layer "dielectric 3" (type "prepreg") (thickness 0.0994) (material "FR4 3313") (epsilon_r 4.05) (loss_tangent 0.02))
            (layer "B.Cu" (type "copper") (thickness 0.035))
            (layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))
            (layer "B.Paste" (type "Bottom Solder Paste"))
            (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
            (copper_finish "ENIG") (dielectric_constraints no)
        )'''
    text,count=re.subn(r'\t\t\(stackup\n.*?\n\t\t\)',lambda _:stack,text,count=1,flags=re.S)
    if count!=1:raise ValueError('Expected the inherited stackup descriptor')
    # Inherited reference boards have a different folder depth. Resolve only
    # verified local model files, without substituting another component model.
    def model_path(m):
        path=m[1]
        if path.startswith('${KIPRJMOD}/') and not (BOARD.parent/path.replace('${KIPRJMOD}/','')).resolve().exists():
            marker='/parts/'
            if marker not in path:raise ValueError('Missing local 3D model: '+path)
            suffix=path.split(marker,1)[1]
            if not (ROOT/'hw/parts'/suffix).exists():raise ValueError('Missing local 3D model: '+path)
            path='${KIPRJMOD}/../../../parts/'+suffix
        return '(model "'+path+'"'
    text=re.sub(r'\(model "([^"]+)"',model_path,text)
    with tempfile.TemporaryDirectory() as folder:
        reference=Path(folder)/'reference.kicad_pcb';reference.write_text(reference_text)
        text=normalize(text,reference)
    data=parse(text);restored=restore(data)
    if restored!=8:raise ValueError('Expected eight PicoBlade plastic-foot areas')
    args.output.write_text(dumps(data)+'\n')
    print(json.dumps({'status':'UNROUTED placement study; not manufacture-ready',
       'placed_components':len(fprints),'copper_layers':4,
       'mechanical_source_sha256':hashlib.sha256(MECHANICAL.read_bytes()).hexdigest(),
       'output':str(args.output)},indent=2))


if __name__=='__main__':main()
