#!/usr/bin/env python3
"""Restore only the four reviewed board-only carrier holes after atopile builds.

Atopile 0.15.9 drops footprints absent from its electrical source. This helper
preserves the circuit and does not move parts, edges, keepouts or routed copper.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import uuid

from kicad_sexpr import Atom, children, one, parse, dumps, node
from generate_schematics import board_graph

ROOT=Path(__file__).resolve().parents[1]
NS=uuid.UUID('5549cf1f-843d-5355-bdb3-bf3ea0319d53')
LIB='blind-pack-features:MountingHole_M3_3.4mm'
ATTRS={'board_only','exclude_from_pos_files','exclude_from_bom'}


def strip_checked_holes(board,require_four=True):
    holes=[]
    for fp in children(board,'footprint'):
        attrs=set(one(fp,'attr')[1:])
        if 'board_only' not in attrs:continue
        props={p[1]:p[2] for p in children(fp,'property')}
        if fp[1]!=LIB or attrs!=ATTRS or 'atopile_address' in props:
            raise ValueError('Unsupported board-only footprint; refusing to remove it')
        pads=children(fp,'pad')
        if len(pads)!=1 or pads[0][1:4]!=['','np_thru_hole','circle'] or children(pads[0],'net'):
            raise ValueError('Mounting footprint has an electrical or unexpected pad')
        if list(map(float,one(pads[0],'drill')[1:]))!=[3.4] or list(map(float,one(pads[0],'size')[1:]))!=[3.4,3.4]:
            raise ValueError('Mounting-hole geometry changed')
        holes.append(fp)
    if len(holes) not in ((4,) if require_four else (0,4)):
        raise ValueError('Expected exactly four reviewed holes (or none before restoration)')
    if holes and {next(p[2] for p in children(f,'property') if p[1]=='Reference') for f in holes}!={'H1','H2','H3','H4'}:
        raise ValueError('Unexpected mounting-hole references')
    for fp in holes:board.remove(fp)
    return holes


def restore(board,which):
    if any(children(board,t) for t in ('segment','arc','via')):
        raise ValueError('Refusing to restore study features on a routed board')
    if any(not children(z,'keepout') for z in children(board,'zone')):
        raise ValueError('Refusing to restore study features on a board with copper zones')
    strip_checked_holes(board,False)
    mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['carrier']
    source=parse((ROOT/'hw/parts/blind-pack-features/MountingHole_M3_3.4mm.kicad_mod').read_text())
    assert mechanical['mounting_hole_diameter']==3.4
    for i,(x,y) in enumerate(mechanical['mounting_holes_local']):
        fp=deepcopy(source);fp[1]=LIB
        fp[:]=[v for v in fp if not isinstance(v,list) or v[0] not in ('version','generator')]
        fp.append(node('at',100+x if which=='primary' else 186-x,204-y))
        fp.append(node('uuid',str(uuid.uuid5(NS,which+f'/mounting-hole-{i}'))))
        next(p for p in children(fp,'property') if p[1]=='Reference')[2]=f'H{i+1}'
        one(fp,'pad').append(node('uuid',str(uuid.uuid5(NS,which+f'/mounting-hole-pad-{i}'))))
        board.append(fp)
    return board


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('board',choices=['primary','companion'])
    p.add_argument('--path',type=Path);a=p.parse_args()
    path=a.path or ROOT/f'hw/layouts/blind-pack-{a.board}/{a.board}-test/{a.board}-test.kicad_pcb'
    before=board_graph(path);text=dumps(restore(parse(path.read_text()),a.board))+'\n'
    # Check the prospective file before replacing the requested board.
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        candidate=Path(folder)/'restored.kicad_pcb';candidate.write_text(text)
        if board_graph(candidate)!=before:raise ValueError('Mechanical restoration changed circuit')
    path.write_text(text)
    print(f'{a.board}: four local NPTH holes restored; circuit unchanged')


if __name__=='__main__':main()
