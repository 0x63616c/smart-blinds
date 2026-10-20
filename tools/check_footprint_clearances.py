#!/usr/bin/env python3
"""Check actual courtyard coverage and the main connector service reservations.

The added source envelopes include two explicit provisional package allowances.
This is an assembly-clearance check, not full footprint, routing or fit approval.
"""
import argparse
import collections
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from kicad_sexpr import children, one, parse
from complete_courtyards import courtyard_items, bounds
ROOT=Path(__file__).resolve().parents[1]
BOARDS={
    'main':'hw/layouts/blind-main/main-test/main-test.kicad_pcb',
    'primary':'hw/layouts/blind-pack-primary/primary-test/primary-test.kicad_pcb',
    'companion':'hw/layouts/blind-pack-companion/companion-test/companion-test.kicad_pcb',
}
COUNTS={'main':196,'primary':50,'companion':10}
ASSEMBLY_FAILURES={'courtyards_overlap','missing_courtyard','malformed_courtyard','items_not_allowed'}

def check_drc_report(report):
    """Only the named assembly checks are accepted here; other DRC stays open."""
    if not isinstance(report.get('violations'),list) or not isinstance(report.get('unconnected_items'),list):
        raise ValueError('Incomplete KiCad DRC report')
    if set(report.get('included_severities',[]))!={'error','warning','exclusion'}:
        raise ValueError('DRC must include every severity and excluded finding')
    ignored={item['key'] for item in report.get('ignored_checks',[])}
    # KiCad defaults missing_courtyard to ignored. Complete footprint coverage
    # above checks every electrical footprint independently; mechanical support
    # features have separate carrier checks.
    if ignored & (ASSEMBLY_FAILURES-{'missing_courtyard'}):
        raise ValueError('Assembly clearance DRC category is disabled')
    counts=collections.Counter(item['type'] for item in report['violations'])
    failed={name:count for name,count in counts.items() if name in ASSEMBLY_FAILURES}
    if failed:raise ValueError('Assembly clearance DRC failed: '+json.dumps(failed,sort_keys=True))
    return {'assembly_clearance_findings':0,'remaining_violations':dict(sorted(counts.items())),
            'ignored_checks':sorted(ignored),
            'unconnected_items':len(report['unconnected_items'])}

def run_drc(path):
    cli=shutil.which('kicad-cli') or '/Applications/KiCad.app/Contents/MacOS/kicad-cli'
    version=subprocess.run([cli,'version'],check=True,text=True,capture_output=True).stdout.strip()
    if not version.startswith('10.'):raise ValueError('KiCad 10 required for clearance DRC')
    before=path.read_bytes()
    with tempfile.TemporaryDirectory(prefix='blinds-clearance-') as directory:
        output=Path(directory)/'drc.json'
        result=subprocess.run([cli,'pcb','drc','--format','json','--severity-all','--all-track-errors',
                               '-o',str(output),str(path)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        if path.read_bytes()!=before:raise ValueError('DRC unexpectedly modified source board')
        return {'kicad_version':version,**check_drc_report(json.loads(output.read_text()))}

def local_bounds(items):
    points=[]
    for item in items:
        if item[0] in ('fp_rect','fp_line'):
            points.extend(tuple(map(float,one(item,key)[1:])) for key in ('start','end'))
        elif item[0]=='fp_circle':
            x,y=map(float,one(item,'center')[1:]);end=list(map(float,one(item,'end')[1:]));r=math.dist((x,y),end)
            points.extend([(x-r,y-r),(x+r,y+r)])
        else:raise ValueError('Unsupported courtyard geometry requires review: '+item[0])
    if not points:raise ValueError('Missing courtyard')
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError('Non-finite courtyard geometry')
    return [min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)]

def placed_bounds(fp,box):
    at=list(map(float,one(fp,'at')[1:]))
    if len(at) not in (2,3) or not all(math.isfinite(v) for v in at+box):
        raise ValueError('Non-finite or malformed placement geometry')
    angle=math.radians(at[2] if len(at)>2 else 0)
    c,s=math.cos(angle),math.sin(angle);pts=[]
    for x in (box[0],box[2]):
        for y in (box[1],box[3]):pts.append((at[0]-100+c*x+s*y,175-at[1]+s*x-c*y))
    return [min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]

def intersects(a,b):
    return min(a[2],b[2])-max(a[0],b[0])>1e-5 and min(a[3],b[3])-max(a[1],b[1])>1e-5

def check_wire_source(source,controller):
    """Tie the restricted component-height box to the actual straight CAD run."""
    encoder=controller['encoder_connector'];transition=encoder['cable_transition']
    contract=encoder['over_board_wire_constraint']
    module=re.search(r'module encoder_cables\(\)\{(.*?)\n\}',source,re.S)
    route=re.search(r'path_box\((\[.*?\]),encoder_bundle\);',module.group(1) if module else '',re.S)
    if not route:raise ValueError('Encoder CAD route requires renewed height review')
    points=json.loads(route.group(1).replace('encoder_transition_y',str(transition['global_y'])))
    radius=transition['bundle_square_side']/2
    origin=controller['global_pcb_origin_xyz'];uv=contract['local_uv']
    low,high=points[1:3]
    if (low[:2]!=high[:2] or low[1]!=transition['global_y'] or low[2]+radius>origin[2]+uv[0]
        or high[2]-radius<origin[2]+uv[2] or points[0][2]+radius>origin[2]+uv[0]):
        raise ValueError('Encoder CAD vertical route no longer covers reviewed box')
    minimum=[low[0]-radius,low[1]-radius,origin[2]+uv[0]]
    maximum=[low[0]+radius,low[1]+radius,origin[2]+uv[2]]
    expected_uv=[uv[0],minimum[1]-origin[1],uv[2],maximum[1]-origin[1]]
    pairs=[(minimum,contract['global_wire_box_min']),(maximum,contract['global_wire_box_max']),
           (expected_uv,uv),([origin[0]+controller['board_size_xyz'][0]],[contract['component_face_x']])]
    if any(len(a)!=len(b) or any(not math.isfinite(x) or not math.isfinite(y) or abs(x-y)>1e-6 for x,y in zip(a,b)) for a,b in pairs):
        raise ValueError('Encoder CAD route and component-height contract disagree')

def check_overboard_wire(path,contract):
    box=contract['local_uv']
    face,wire,clearance,height=[contract[k] for k in ('component_face_x','nearest_wire_x','clearance','maximum_mounted_component_height')]
    if (len(box)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in box+[face,wire,clearance,height])
        or box[0]>=box[2] or box[1]>=box[3] or min(clearance,height)<=0
        or abs(wire-face-clearance-height)>1e-6):
        raise ValueError('Invalid over-board wire height contract')
    # Exact currently reviewed resistors only: Royalohm max body 0.40 mm plus
    # a provisional 0.15 mm assembled standoff. This is not a generic 0402 rule.
    allowed={'controller.r_down','controller.r_charge'}
    parts=[]
    for fp in children(parse(path.read_text()),'footprint'):
        props={v[1]:v[2] for v in children(fp,'property')}
        if not intersects(placed_bounds(fp,local_bounds(courtyard_items(fp))),box):continue
        if (props.get('atopile_address') not in allowed or fp[1]!='UNI_ROYAL_0402WGF1002TCE:R0402'
            or props.get('LCSC')!='C25744' or height<.55):
            raise ValueError('Unreviewed or too-tall part under encoder wire: '+props.get('atopile_address','unknown'))
        parts.append(props['atopile_address'])
    return {'reviewed_parts_under_route':sorted(parts),'maximum_mounted_height_mm':height,
            'reviewed_resistor_height_with_solder_allowance_mm':.55}

def check_board(which,path,expected):
    board=parse(path.read_text());parts={};repaired=0
    for fp in children(board,'footprint'):
        props={v[1]:v[2] for v in children(fp,'property')}
        if 'atopile_address' not in props:
            if which!='main' and 'board_only' in one(fp,'attr')[1:]:continue
            raise ValueError('Unexpected component without an electrical address')
        if one(fp,'layer')[1]!='F.Cu':raise ValueError('Expected front-side electrical footprint')
        name=props['atopile_address']
        if name in parts:raise ValueError('Duplicate electrical address: '+name)
        items=courtyard_items(fp);box=local_bounds(items)
        placed_bounds(fp,box)  # Validate finite placement even on carrier boards.
        if fp[1] in expected:
            target=expected[fp[1]]
            if len(items)!=1 or items[0][0]!='fp_rect' or any(abs(a-b)>1e-6 for a,b in zip(box,target)):
                raise ValueError('Compiled courtyard differs from reviewed envelope: '+name)
            repaired+=1
        parts[name]=(fp,box)
    if len(parts)!=COUNTS[which]:raise ValueError('Unexpected component count')
    if which=='main':
        reserved=json.loads((ROOT/'hw/placement/blind-main/placement.json').read_text())['reserved']
        allowed={'antenna':{'controller.mcu'},'battery-plug':{'pack_connector.header'},
                 'encoder-cable':{'encoder_port.header'},'home-cable':{'home_port.header'}}
        for label,reservation in reserved:
            for name,(fp,box) in parts.items():
                if name in allowed.get(label,set()):continue
                if intersects(placed_bounds(fp,box),reservation):
                    raise ValueError('Courtyard enters reserved '+label+': '+name)
    return {'electrical_footprints':len(parts),'with_courtyards':len(parts),'new_envelopes_checked':repaired}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drc',action='store_true',help='Also run actual KiCad 10 assembly clearance checks on all three boards')
    args=parser.parse_args()
    plan=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
    expected={e['compiled_alias']:bounds(parse((ROOT/e['source']).read_text()),e) for e in plan['footprints']}
    result={which:check_board(which,ROOT/path,expected) for which,path in BOARDS.items()}
    if result['main']['new_envelopes_checked']!=sum(e['main_instances'] for e in plan['footprints']):
        raise ValueError('Main-board repaired instance count changed')
    mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['controller']
    check_wire_source((ROOT/'cad/source/compact_retained.scad').read_text(),mechanical)
    result['main']['encoder_wire_height']=check_overboard_wire(ROOT/BOARDS['main'],
        mechanical['encoder_connector']['over_board_wire_constraint'])
    if args.drc:
        for which,path in BOARDS.items():result[which]['drc']=run_drc(ROOT/path)
    print(json.dumps({'status':'Outline presence complete; inherited pad/body envelope audit incomplete; no physical-clearance or fabrication acceptance',
                      'boards':result},indent=2))
if __name__=='__main__':main()
