#!/usr/bin/env python3
"""Restore the board-level PicoBlade plastic-foot areas omitted by atopile.

Run after build/placement. This only replaces named rule areas; it preserves
all electrical pads and the original KiCad serialization/version.
"""
import argparse
import copy
import math
from pathlib import Path
import uuid
from kicad_sexpr import children, one, parse, dumps, node

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'PICOBLADE_FOOT_'
NAMES = {'CONN-SMD_4P-P1.25_53261-0471', 'CONN-TH_532610371'}
NS = uuid.UUID('9128d03d-7d40-55cd-a64c-ecf68c7712e8')


def restore(board):
    for zone in list(children(board, 'zone')):
        if children(zone,'name') and one(zone,'name')[1].startswith(PREFIX):
            assert children(zone,'keepout'), 'Never remove copper zones'
            board.remove(zone)
    count = 0
    for fp in children(board,'footprint'):
        name = str(fp[1]).split(':')[-1]
        if name not in NAMES: continue
        assert one(fp,'layer')[1]=='F.Cu', 'Back-side transform is not implemented'
        props = {p[1]:p[2] for p in children(fp,'property')}
        at = list(map(float,one(fp,'at')[1:]))
        angle = math.radians(at[2] if len(at)>2 else 0)
        c,s = math.cos(angle),math.sin(angle)
        source = parse((ROOT/'hw/parts/blind-harness'/(name+'.kicad_mod')).read_text())
        for i, original in enumerate(children(source,'zone')):
            zone=copy.deepcopy(original)
            tag=PREFIX+props['atopile_address']+'_'+str(i)
            zone += [node('name',tag),node('uuid',str(uuid.uuid5(NS,tag)))]
            for p in children(one(one(zone,'polygon'),'pts'),'xy'):
                a,b=map(float,p[1:]);p[1:]=[round(at[0]+c*a+s*b,6),round(at[1]-s*a+c*b,6)]
            board.append(zone); count += 1
    return count


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('board',type=Path);args=p.parse_args()
    board=parse(args.board.read_text());count=restore(board)
    args.board.write_text(dumps(board)+'\n')
    print(f'Restored {count} front-copper plastic-foot rule areas')
