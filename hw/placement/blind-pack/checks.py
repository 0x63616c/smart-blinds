#!/usr/bin/env python3
"""Check actual retained-carrier geometry against its assembly coordinates.

This checks an unrouted placement, not current capacity, solderability or safety.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children, one, parse, dumps
import check_footprint_clearances as CLEARANCES

PACK_SPEC=importlib.util.spec_from_file_location('pack_contract',ROOT/'hw/sim/blind-pack/checks.py')
PACK=importlib.util.module_from_spec(PACK_SPEC);PACK_SPEC.loader.exec_module(PACK)


def near(actual, expected):
    assert len(actual)==len(expected) and all(abs(float(a)-b)<1e-5 for a,b in zip(actual,expected)), (actual,expected)


def assembly_point(xy,which):
    x,y=map(float,xy)
    return [x-100 if which=='primary' else 186-x,204-y]


def outline_check(board,which,plan):
    # Expected straight spans and circular midpoints are mechanical constraints,
    # independent of the serialized drawing order or UUIDs.
    w,h=plan['outline_mm'];r=plan['corner_radius_mm'];k=r/math.sqrt(2)
    lines=children(board,'gr_line');arcs=children(board,'gr_arc')
    assert len(lines)==len(arcs)==4, 'Rounded carrier outline requires four lines and four arcs'
    def key(points):return tuple(sorted(tuple(round(v,5) for v in p) for p in points))
    actual_lines=[];actual_arcs=[]
    for item in lines+arcs:
        assert one(item,'layer')[1]=='Edge.Cuts'
        points=[assembly_point(one(item,t)[1:3],which) for t in (('start','end') if item[0]=='gr_line' else ('start','mid','end'))]
        (actual_lines if item[0]=='gr_line' else actual_arcs).append(key(points))
    expected_lines=[[[r,0],[w-r,0]],[[w,r],[w,h-r]],[[w-r,h],[r,h]],[[0,h-r],[0,r]]]
    expected_arcs=[[[w-r,0],[w-r+k,r-k],[w,r]],[[w,h-r],[w-r+k,h-r+k],[w-r,h]],
                   [[r,h],[r-k,h-r+k],[0,h-r]],[[0,r],[r-k,r-k],[r,0]]]
    assert sorted(actual_lines)==sorted(map(key,expected_lines)), 'Board straight edges changed'
    assert sorted(actual_arcs)==sorted(map(key,expected_arcs)), 'Board corner arcs changed'


def keepout_check(zones,which,mechanical):
    byname={one(z,'name')[1]:z for z in zones}
    assert len(byname)==len(zones), 'Duplicate rule-area name'
    support=mechanical['outward_supports']['front_primary' if which=='primary' else 'rear_companion']
    spans=support['local_x_intervals'] if which=='primary' else support['lower_local_x_intervals']
    bridges=support['lower_bridge_bare_rectangles_local_xy'] if which=='companion' else []
    expected_names={
        *[f'RF_NO_METAL_{i}' for i in range(len(mechanical['copper_keepout_local_xy']))],
        *[f'BARE_CORNER_SUPPORT_{i}_{q}' for i in range(len(mechanical['mounting_holes_local'])) for q in range(4)],
        *[f'LOWER_SUPPORT_{i}' for i in range(len(spans))],
        *[f'LOWER_BRIDGE_SUPPORT_{i}' for i in range(len(bridges))],
    }
    if which=='companion':expected_names.add('UPPER_SUPPORT')
    assert set(byname)==expected_names, ('Missing or unexpected support/RF area',set(byname)^expected_names)
    def polygons(z):
        return [[assembly_point(p[1:3],which) for p in one(poly,'pts')[1:]] for poly in children(z,'polygon')]
    def bbox(points):return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
    for name,z in byname.items():
        assert set(one(z,'layers')[1:])=={'F.Cu','B.Cu'}, 'Support/RF area must cover both copper layers'
        assert not children(z,'filled_polygon')
        limits={n[0]:n[1] for n in one(z,'keepout')[1:]}
        assert limits=={'tracks':'not_allowed','vias':'not_allowed','pads':'not_allowed','copperpour':'not_allowed',
                        'footprints':'allowed' if name.startswith('BARE_CORNER_SUPPORT_') else 'not_allowed'}, name
    for i,box in enumerate(mechanical['copper_keepout_local_xy']):
        points=polygons(byname[f'RF_NO_METAL_{i}'])
        assert len(points)==1 and len(points[0])==4
        x0,y0,x1,y1=box
        assert sorted(tuple(round(v,5) for v in p) for p in points[0])==sorted(((x0,y0),(x1,y0),(x1,y1),(x0,y1)))
    for i,centre in enumerate(mechanical['mounting_holes_local']):
        for quadrant in range(4):
            rings=polygons(byname[f'BARE_CORNER_SUPPORT_{i}_{quadrant}'])
            assert len(rings)==1 and len(rings[0])==26
            outer,inner=rings[0][:13],rings[0][13:]
            for ring,radius in [(outer,mechanical['bare_support_land_diameter']/2),(inner,mechanical['mounting_hole_diameter']/2+.1)]:
                assert all(abs(math.dist(p,centre)-radius)<2e-6 for p in ring), 'Bare support annulus changed'
            # Each quadrant must reach both of its radial boundaries.
            for end,angle in [(outer[0],quadrant*math.pi/2),(outer[-1],(quadrant+1)*math.pi/2)]:
                radius=mechanical['bare_support_land_diameter']/2
                near(end,[centre[0]+radius*math.cos(angle),centre[1]+radius*math.sin(angle)])
    y0,y1=support['local_y'] if which=='primary' else support['lower_local_y']
    for i,(x0,x1) in enumerate(spans):
        points=polygons(byname[f'LOWER_SUPPORT_{i}']);assert len(points)==1
        near(bbox(points[0]),[x0,y0,x1,y1])
        if x0==4 or x1==82:
            # The mounting-hole cut-out is the only permitted interruption.
            centre=[4 if x0==4 else 82,4]
            assert len(points[0])==36
            assert all(math.dist(p,centre)>=1.8-2e-6 for p in points[0])
        else:assert len(points[0])==4
    if which=='companion':
        points=polygons(byname['UPPER_SUPPORT']);assert len(points)==1 and len(points[0])==4
        x0,x1=support['upper_local_x'];y0,y1=support['upper_local_y'];near(bbox(points[0]),[x0,y0,x1,y1])
    for i,(x0,y0,x1,y1) in enumerate(bridges):
        points=polygons(byname[f'LOWER_BRIDGE_SUPPORT_{i}'])
        assert len(points)==1 and len(points[0])==4, 'Bridge support must be one rectangle'
        corners=points[0]
        assert sorted(tuple(round(v,5) for v in p) for p in corners)==sorted(((x0,y0),(x1,y0),(x1,y1),(x0,y1))), 'Bridge support extent changed'
        # Corner membership alone would admit a self-crossed bow-tie polygon.
        assert all((abs(a[0]-b[0])<1e-6) != (abs(a[1]-b[1])<1e-6)
                   for a,b in zip(corners,corners[1:]+corners[:1])), 'Bridge support edges must follow its perimeter'


def check_board(which, path, plan, mechanical):
    board=parse(path.read_text())
    assert not any(children(board,k) for k in ('segment','arc','via')), 'Placement study must remain unrouted'
    near(one(one(board,'general'),'thickness')[1:], [mechanical['thickness']])
    outline_check(board,which,plan)
    fps=children(board,'footprint'); electrical={}; holes=[]
    for fp in fps:
        props={p[1]:p[2] for p in children(fp,'property')}
        if 'atopile_address' in props:
            assert props['atopile_address'] not in electrical, 'Duplicate electrical address'
            electrical[props['atopile_address']]=fp
        else:
            assert set(one(fp,'attr')[1:])=={'board_only','exclude_from_pos_files','exclude_from_bom'}
            pads=children(fp,'pad');assert len(pads)==1
            pad=pads[0];assert pad[1]=='' and pad[2]=='np_thru_hole' and not children(pad,'net')
            near(one(pad,'drill')[1:],[3.4]);near(one(pad,'size')[1:],[3.4,3.4]);near(one(pad,'at')[1:3],[0,0])
            x,y=map(float,one(fp,'at')[1:3]);holes.append([x-100 if which=='primary' else 186-x,204-y])
    assert len(holes)==4 and sorted(holes)==sorted(mechanical['mounting_holes_local'])
    assert set(electrical)==set(plan['boards'][which]['placements'])
    for name, pos in plan['boards'][which]['placements'].items():
        fp=electrical[name];assert one(fp,'layer')[1]=='F.Cu', 'Components must face outwards'
        x,y=pos['xy'];expected=[100+x if which=='primary' else 186-x,204-y]
        at=one(fp,'at')[1:];near(at[:2],expected)
        angle=float(at[2]) if len(at)>2 else 0;assert (angle-pos['rotation'])%360==0
    for i,x in enumerate(mechanical['holder_centres_local_x'],1):
        fp=electrical[f'carrier.holder{i}'];at=list(map(float,one(fp,'at')[1:]));angle=math.radians(at[2]);c,s=math.cos(angle),math.sin(angle)
        for pad in children(fp,'pad'):
            if pad[1] not in ('1','2'):continue
            a,b=map(float,one(pad,'at')[1:3]);px,py=at[0]+c*a+s*b,at[1]-s*a+c*b
            assembly=[px-100 if which=='primary' else 186-px,204-py]
            near(assembly,[x,9.9 if pad[1]=='1' else 89.9])
    missing_courtyards=sorted(name for name,fp in electrical.items() if not any(
        children(item,'layer') and one(item,'layer')[1]=='F.CrtYd' for item in fp if isinstance(item,list)))
    assert not missing_courtyards, ('Missing carrier courtyards',missing_courtyards)
    envelope_plan=json.loads((ROOT/'hw/placement/footprint-clearances.json').read_text())
    expected_envelopes={e['compiled_alias']:CLEARANCES.bounds(parse((ROOT/e['source']).read_text()),e)
                        for e in envelope_plan['footprints']}
    envelope_check=CLEARANCES.check_board(which,path,expected_envelopes)
    graph=board_graph(path)
    pins={f"{which}.{c['properties']['atopile_address'].removeprefix('carrier.')}.{pin}":net
          for c in graph.values() for pin,net in c['pads'].items()}
    expected={pin:net for pin,net in PACK.expected_graph().items() if pin.startswith(which+'.')}
    PACK.verify(pins,expected)
    reference=board_graph(ROOT/f'hw/layouts/blind-pack-{which}/{which}-test/{which}-test.kicad_pcb')
    assert set(graph)==set(reference)
    for ref, actual in graph.items():
        expected=reference[ref]
        for field in ('pads','footprint','attributes'):
            assert actual[field]==expected[field], ('Placement changed '+field,ref)
        # KiCad adds empty default Datasheet/Description fields on save.
        assert {k:v for k,v in actual['properties'].items() if v}=={k:v for k,v in expected['properties'].items() if v}
    zones=children(board,'zone');assert zones and all(children(z,'keepout') for z in zones)
    names={one(z,'name')[1] for z in zones}
    assert {'RF_NO_METAL_0',*[f'BARE_CORNER_SUPPORT_{i}_{q}' for i in range(4) for q in range(4)]}.issubset(names)
    assert len([n for n in names if n.startswith('LOWER_SUPPORT_')])==(2 if which=='primary' else 4)
    assert ('UPPER_SUPPORT' in names)==(which=='companion')
    keepout_check(zones,which,mechanical)
    # Raw current links must line up with the retained internal wire channels.
    for address, global_xy in zip(('link_raw_ground','link_junction1','link_junction2','link_raw_top'),mechanical['raw_group_channels_global_xy']):
        at=one(electrical['carrier.'+address],'at')[1:3]
        local=assembly_point(at,which)
        near([local[i]+mechanical['global_origin_xy'][i] for i in range(2)],global_xy)
    return {'electrical_footprints':len(graph),'board_only_mounting_holes':4,
            'physical_electrical_pins':sum(len(f['pads']) for f in graph.values()),
            'courtyard_coverage':{'present':len(graph)-len(missing_courtyards),'missing_addresses':missing_courtyards},
            'reviewed_envelopes_and_pad_containment':envelope_check,
            'side':'all front/component-side; primary faces +Z, companion faces -Z',
            'board_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def physical_margins(plan,mechanical):
    width,length,_=mechanical['holder_envelope']
    holders=[plan['boards']['primary']['placements'][f'carrier.holder{i}']['xy'] for i in (1,2,3)]
    rectangles=[(x-width/2,y-length/2,x+width/2,y+length/2) for x,y in holders]
    boss_radius=mechanical['bare_support_land_diameter']/2
    distances=[]
    for cx,cy in mechanical['mounting_holes_local']:
        for x0,y0,x1,y1 in rectangles:
            distances.append(math.hypot(max(x0-cx,0,cx-x1),max(y0-cy,0,cy-y1))-boss_radius)
    return {'minimum_holder_to_corner_support_mm':round(min(distances),5),
            'minimum_maximum_body_gap_between_holders_mm':round(min(b[0]-a[2] for a,b in zip(rectangles,rectangles[1:])),5)}


def negative_controls(path,plan,mechanical,companion_path):
    original=parse(path.read_text())
    def electrical(d):return next(f for f in children(d,'footprint') if any(p[1]=='atopile_address' for p in children(f,'property')))
    def holder(d):return next(f for f in children(d,'footprint') if any(p[1:3]==['atopile_address','carrier.holder1'] for p in children(f,'property')))
    def hole(d):return next(f for f in children(d,'footprint') if 'board_only' in one(f,'attr')[1:])
    def rf(d):return next(z for z in children(d,'zone') if one(z,'name')[1]=='RF_NO_METAL_0')
    def remove_courtyard(d):
        fp=electrical(d)
        fp[:]=[item for item in fp if not (isinstance(item,list) and children(item,'layer') and one(item,'layer')[1]=='F.CrtYd')]
    def shrink_reviewed_courtyard(d):
        fp=next(f for f in children(d,'footprint') if any(p[1:3]==['atopile_address','carrier.protection.gauge'] for p in children(f,'property')))
        court=next(i for i in fp if isinstance(i,list) and i[0]=='fp_rect' and children(i,'layer') and one(i,'layer')[1]=='F.CrtYd')
        one(court,'end')[1]=str(float(one(court,'end')[1])-.05)
    def courtyard_omits_pad(d):
        fp=next(f for f in children(d,'footprint') if any(p[1:3]==['atopile_address','carrier.fuse1'] for p in children(f,'property')))
        court=next(i for i in fp if isinstance(i,list) and i[0]=='fp_rect' and children(i,'layer') and one(i,'layer')[1]=='F.CrtYd')
        one(court,'end')[1]='3.0'
    def add_primary_bridge(d):
        zone=deepcopy(rf(d));one(zone,'name')[1]='LOWER_BRIDGE_SUPPORT_0';d.append(zone)
    def short_rails(d):
        def pad(name):
            fp=next(f for f in children(d,'footprint') if any(p[1:3]==['atopile_address','carrier.'+name] for p in children(f,'property')))
            return children(fp,'pad')[0]
        source=one(pad('link_raw_top'),'net')[:];target=one(pad('harness_pack_positive'),'net')[:]
        assert source!=target
        for fp in children(d,'footprint'):
            for pin in children(fp,'pad'):
                for net in children(pin,'net'):
                    if net==source:net[:]=target[:]
    cases={
        'whole_raw_to_protected_positive_short':short_rails,
        'reversed_holder':lambda d:one(holder(d),'at').__setitem__(3,'-90'),
        'plated_mounting_hole':lambda d:children(hole(d),'pad')[0].__setitem__(2,'thru_hole'),
        'duplicate_electrical_address':lambda d:d.append(deepcopy(electrical(d))),
        'moved_outline_corner':lambda d:one(children(d,'gr_arc')[0],'mid').__setitem__(1,'99'),
        'missing_RF_keepout':lambda d:d.remove(rf(d)),
        'RF_copper_allowed':lambda d:one(one(rf(d),'keepout'),'copperpour').__setitem__(1,'allowed'),
        'shrunk_RF_keepout':lambda d:one(one(rf(d),'polygon'),'pts')[1].__setitem__(1,'182'),
        'missing_carrier_courtyard':remove_courtyard,
        'shrunken_reviewed_courtyard':shrink_reviewed_courtyard,
        'courtyard_omits_pad':courtyard_omits_pad,
        'companion_bridge_on_primary':add_primary_bridge,
    }
    passed=[]
    with tempfile.TemporaryDirectory() as folder:
        for name,mutate in cases.items():
            data=deepcopy(original);mutate(data)
            candidate=Path(folder)/f'{name}.kicad_pcb';candidate.write_text(dumps(data)+'\n')
            try:check_board('primary',candidate,plan,mechanical)
            except (AssertionError,ValueError):passed.append(name)
            else:raise AssertionError('Corrupted placement was accepted: '+name)
        companion=parse(companion_path.read_text())
        def bridge(d):return next(z for z in children(d,'zone') if one(z,'name')[1]=='LOWER_BRIDGE_SUPPORT_0')
        def shrink_bridge(d):
            pts=one(one(bridge(d),'polygon'),'pts')
            # Companion PCB X runs opposite to assembly X.
            old=float(pts[1][1]);pts[1][1]=str(old-.1)
        companion_cases={
            'missing_companion_bridge':lambda d:d.remove(bridge(d)),
            'shrunk_companion_bridge':shrink_bridge,
            'companion_bridge_copper_allowed':lambda d:one(one(bridge(d),'keepout'),'copperpour').__setitem__(1,'allowed'),
            'companion_bridge_wrong_layers':lambda d:one(bridge(d),'layers').__setitem__(slice(1,None),['F.Cu']),
        }
        for name,mutate in companion_cases.items():
            data=deepcopy(companion);mutate(data)
            candidate=Path(folder)/f'{name}.kicad_pcb';candidate.write_text(dumps(data)+'\n')
            try:check_board('companion',candidate,plan,mechanical)
            except (AssertionError,ValueError):passed.append(name)
            else:raise AssertionError('Corrupted placement was accepted: '+name)
    return passed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir',type=Path,help='Check primary-normalized.kicad_pcb and companion-normalized.kicad_pcb here')
    p.add_argument('--output',type=Path);args=p.parse_args()
    plan=json.loads((Path(__file__).with_name('placement.json')).read_text())
    mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['carrier']
    assert plan['outline_mm']==mechanical['outline']==[86,104]
    results={}
    for which in ('primary','companion'):
        path=args.work_dir/f'{which}-normalized.kicad_pcb' if args.work_dir else ROOT/f'hw/layouts/blind-pack-{which}/{which}-test/{which}-test.kicad_pcb'
        results[which]=check_board(which,path,plan,mechanical)
    primary=args.work_dir/'primary-normalized.kicad_pcb' if args.work_dir else ROOT/'hw/layouts/blind-pack-primary/primary-test/primary-test.kicad_pcb'
    companion=args.work_dir/'companion-normalized.kicad_pcb' if args.work_dir else ROOT/'hw/layouts/blind-pack-companion/companion-test/companion-test.kicad_pcb'
    regressions=negative_controls(primary,plan,mechanical,companion)
    result={'status':'PASS: actual unrouted placement geometry, component sides, mounting holes, holder polarity and independent pin contract',
            'boards':results,**physical_margins(plan,mechanical),'rejected_faults':regressions,
            'limits':['Every electrical footprint courtyard contains its actual pad envelope; manifest-covered outlines match reviewed source maxima/allowances. AON7400A molding allowance remains conditional.',
                      'KiCad DRC is separate; passing dimensional checks does not qualify solderability, thermal performance or actual manufactured fit.',
                      '0.2 mm holder-to-boss margin is not a tolerance-qualified fit.',
                      'Holder fasteners and insertion backing fixture remain unresolved.',
                      'Solder tails must be trimmed/insulated to the 1.5 mm inner protrusion budget.']}
    text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='')


if __name__=='__main__':main()
