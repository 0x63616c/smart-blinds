#!/usr/bin/env python3
"""Independent split-harness pin/land-pattern contract; no mechanical fit claim."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import parse,children,one

def geometry(node,count,compiled=False):
    assert one(node,'attr')[1:] == ['smd'], 'Both selected PicoBlade headers require SMT assembly metadata'
    pads=children(node,'pad'); electrical={p[1]:p for p in pads if p[1]}
    assert set(electrical)==set(map(str,range(1,count+1)))
    for number,pad in electrical.items():
        x=-(count-1)*.625+(int(number)-1)*1.25
        assert list(map(float,one(pad,'at')[1:3]))==[x,0.]
        assert list(map(float,one(pad,'size')[1:]))==[.8,1.6]
        assert pad[2]=='smd'
    mounts=[p for p in pads if not p[1]]
    assert len(mounts)==2
    assert sorted(float(one(p,'at')[1]) for p in mounts)==[-((count-1)*.625+2.55),(count-1)*.625+2.55]
    assert all(float(one(p,'at')[2])==2.9 for p in mounts)
    assert all(list(map(float,one(p,'size')[1:]))==[2.1,3.] for p in mounts)
    zones=children(node,'zone'); assert len(zones)==(0 if compiled else 4)
    for zone in zones:
        assert one(zone,'layer')[1]=='F.Cu'
        for feature in ('tracks','vias','pads','copperpour'):
            assert one(one(zone,'keepout'),feature)[1]=='not_allowed'
    return {'signal_pitch_mm':1.25,'signal_land_mm':[.8,1.6], 'mount_land_mm':[2.1,3.],
            'mount_centres_mm':[[-((count-1)*.625+2.55),2.9],[(count-1)*.625+2.55,2.9]],
            'pad_bounds_mm':[-((count-1)*.625+3.6),-.8,(count-1)*.625+3.6,4.4],
            'body_y_mm':[.8,5.], 'body_nominal_width_mm':1.25*count+5.15,
            'mated_wire_exit_y_mm':6., 'mating_direction':'+Y', 'height_mm':3.4}

def calculate():
    graph=board_graph(ROOT/'hw/layouts/blind-harness/harness-test/harness-test.kicad_pcb')
    components={c['properties']['atopile_address']:c for c in graph.values()}
    expected={'encoder.header':{'1':'ground','2':'supply','3':'channel_a','4':'channel_b'},
              'home.header':{'1':'home-ground','2':'home-supply','3':'sense'},
              'motor.landing1':{'1':'contact'},'motor.landing2':{'1':'motor-contact'}}
    assert {k:c['pads'] for k,c in components.items()}==expected,'Compiled contact assignment differs'
    source=(ROOT/'hw/boards/blind-harness/harness.ato').read_text()
    assert 'landing1.contact ~ motor1' in source and 'landing2.contact ~ motor2' in source
    assert components['encoder.header']['properties']['lcsc_id']=='C696092'
    assert components['home.header']['properties']['lcsc_id']=='C293630'
    partdir=ROOT/'hw/parts/blind-harness'; shapes={}; negatives=[]
    for name,count in [('CONN-SMD_4P-P1.25_53261-0471',4),('CONN-TH_532610371',3)]:
        fp=parse((partdir/(name+'.kicad_mod')).read_text());shapes[name]=geometry(fp,count)
        assert (partdir/(name+'.kicad_mod')).read_bytes()==(partdir/'blind-harness.pretty'/(name+'.kicad_mod')).read_bytes()
        board=parse((ROOT/'hw/layouts/blind-harness/harness-test/harness-test.kicad_pcb').read_text())
        compiled=next(f for f in children(board,'footprint') if str(f[1]).split(':')[-1]==name)
        geometry(compiled,count,True)
        props={q[1]:q[2] for q in children(compiled,'property')}
        address=props['atopile_address']
        at=list(map(float,one(compiled,'at')[1:]))
        angle=math.radians(at[2] if len(at)>2 else 0)
        c,s=math.cos(angle),math.sin(angle)
        for zone in children(fp,'zone'):
            expected_points=[(round(at[0]+c*float(p[1])+s*float(p[2]),5),round(at[1]-s*float(p[1])+c*float(p[2]),5)) for p in children(one(one(zone,'polygon'),'pts'),'xy')]
            matches=[]
            for q in children(board,'zone'):
                if not children(q,'name') or not str(one(q,'name')[1]).startswith('PICOBLADE_FOOT_'+address+'_'): continue
                points=[tuple(round(float(v),5) for v in p[1:]) for p in children(one(one(q,'polygon'),'pts'),'xy')]
                if points==expected_points:matches.append(q)
            assert len(matches)==1,'Compiled connector plastic-foot rule area missing or misplaced'
            for feature in ('tracks','vias','pads','copperpour'):
                assert one(one(matches[0],'keepout'),feature)[1]=='not_allowed'
        wrong=parse((partdir/(name+'.kicad_mod')).read_text())
        first=next(p for p in children(wrong,'pad') if p[1]=='1')
        one(first,'at')[1]=str(-float(one(first,'at')[1]))
        try:geometry(wrong,count)
        except AssertionError:negatives.append(f'{count}way_mirrored_pin1')
        else:raise AssertionError('Mirrored pad escaped detection')
    swapped={k:dict(v) for k,v in expected.items()}
    swapped['encoder.header']['1'],swapped['encoder.header']['2']=swapped['encoder.header']['2'],swapped['encoder.header']['1']
    assert swapped != expected;negatives.append('encoder_power_ground_swap')
    paths=sorted([*partdir.glob('*.ato'),*partdir.glob('*.kicad_mod'),*partdir.glob('*.kicad_sym'),ROOT/'hw/boards/blind-harness/harness.ato'])
    return {'status':'PASS: selected two signal headers and two solder landings; no powered or mechanical qualification',
            'footprints':len(graph),'physical_pins':sum(len(c['pads']) for c in graph.values()),
            'selected_pcba_parts':2,'geometry':shapes,'negative_controls_detected':negatives,
            'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'limits':['Current motor pinout and encoder supply still need bench identification.',
                      'Imported 3D models are visual aids; manufacturer drawing controls geometry.',
                      'PicoBlade plastic-foot rule areas prohibit front copper/pads; full footprint courtyard also reserves component space.',
                      'Mating access, cable bend radii, inline motor pair geometry and actual enclosure placement are separate checks.',
                      'The two-way and eight-way PCB Micro-Fit studies are not selected.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    result=json.dumps(calculate(),indent=2)+'\n';path=Path(__file__).with_name('results.json')
    if args.check:assert path.read_text()==result,'Stale harness results'
    else:path.write_text(result)
    print(result,end='')
