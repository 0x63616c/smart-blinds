#!/usr/bin/env python3
"""Check explicit main-board placement and RF exceptions, without routing claims."""
import json
import math
from pathlib import Path

from kicad_sexpr import children, one, parse

ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb'


def check(path=BOARD):
    board=parse(path.read_text())
    plan=json.loads((ROOT/'hw/placement/blind-main/placement.json').read_text())
    mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['controller']
    assert mechanical['board_size_xyz'][1:]==[68.5,54]
    anchors={'pack_connector.header':mechanical['header_reservation']['footprint_origin_local_uv'],
             'encoder_port.header':mechanical['encoder_connector']['footprint_origin_local_uv'],
             'home_port.header':mechanical['home_connector']['footprint_origin_local_uv'],
             'controller.up':mechanical['switch_centres_local_uv'][0],
             'controller.down':mechanical['switch_centres_local_uv'][1],
             'motor_output.landing1':mechanical['motor_solder_pads_local_uv'][0],
             'motor_output.landing2':mechanical['motor_solder_pads_local_uv'][1]}
    for name,uv in anchors.items():
        assert plan['placements'][name]['uv']==uv,name+' differs from mechanical anchor'
    assert dict(plan['reserved'])['encoder-cable']==mechanical['encoder_connector']['cable_transition']['board_corridor_local_uv']
    assert not any(children(board,k) for k in ('segment','arc','via')), 'Study must still be labelled unrouted'
    actual={}
    for fp in children(board,'footprint'):
        props={p[1]:p[2] for p in children(fp,'property')};name=props['atopile_address']
        at=list(map(float,one(fp,'at')[1:])); angle=at[2] if len(at)>2 else 0
        pos=plan['placements'][name]
        assert math.dist([at[0]-100,175-at[1]],pos['uv'])<.00001,name+' position'
        assert abs((angle-pos['rotation']+180)%360-180)<.00001,name+' orientation'
        actual[name]=fp
        if name=='controller.mcu':continue
        # The MCU body is the sole exception inside this RF reservation. Board
        # rule areas cover the remaining antenna/sides; unrelated copper cannot
        # hide inside the allowed module-body rectangle.
        a=math.radians(angle);c,s=math.cos(a),math.sin(a)
        for pad in children(fp,'pad'):
            layers=one(pad,'layers')[1:]
            if not any(str(l).endswith('.Cu') for l in layers):continue
            p=list(map(float,one(pad,'at')[1:]));w,h=map(float,one(pad,'size')[1:])
            pa=math.radians(p[2] if len(p)>2 else 0)
            dx=(abs(w*math.cos(pa))+abs(h*math.sin(pa)))/2
            dy=(abs(w*math.sin(pa))+abs(h*math.cos(pa)))/2
            u=at[0]+c*p[0]+s*p[1]-100;v=175-(at[1]-s*p[0]+c*p[1])
            assert not (u+dx>4.75 and u-dx<24.25 and v+dy>53.5 and v-dy<68.5),name+' copper in MCU exception'
    assert actual.keys()==plan['placements'].keys()
    zones={one(z,'name')[1]:z for z in children(board,'zone')}
    assert len(zones)==13, 'Three RF, two clamp and eight connector-foot rule areas expected'
    for name in ['RF_LEFT_NO_METAL','RF_RIGHT_NO_METAL','RF_ANTENNA_NO_METAL','CLAMP_BARE_LAND_0','CLAMP_BARE_LAND_1']:
        zone=zones[name];keepout=one(zone,'keepout')
        for feature in ['tracks','vias','pads','copperpour']:
            assert one(keepout,feature)[1]=='not_allowed',name+' incomplete rule'
    for index,box in enumerate(mechanical['edge_notches']['bare_land_local_uv']):
        points=children(one(one(zones['CLAMP_BARE_LAND_'+str(index)],'polygon'),'pts'),'xy')
        uv=[(float(p[1])-100,175-float(p[2])) for p in points]
        bounds=[min(u for u,v in uv),min(v for u,v in uv),max(u for u,v in uv),max(v for u,v in uv)]
        assert max(abs(a-b) for a,b in zip(bounds,box))<.00001,'Clamp source differs'
    print(f'PASS: {len(actual)} explicit placements, RF copper exception and 13 rule areas; no routing/thermal acceptance')


if __name__=='__main__':check()
