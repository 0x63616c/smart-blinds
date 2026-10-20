#!/usr/bin/env python3
"""Independent dimension/identity checks of manufacturer land transcriptions.

Not a solder/process qualification. KiCad DRC separately checks custom polygons.
"""
from pathlib import Path
from kicad_sexpr import children,one,parse
ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'hw/parts/blind-core'


def close(values,expected):
    assert len(values)==len(expected) and all(abs(float(x)-y)<1e-5 for x,y in zip(values,expected)),(values,expected)

def named(fp):
    return {p[1]:p for p in children(fp,'pad') if p[1] and p[2]=='smd'}

def check(fp):
    name=str(fp[1]).split(':')[-1];p=named(fp)
    if name.startswith('QFN-29_'):
        assert set(p)=={str(i) for i in range(1,30)}
        for number in (1,9,16,24):
            q=p[str(number)];assert q[3]=='custom';close(one(q,'size')[1:],[.1,.1])
            vertices=children(one(one(q,'primitives'),'gr_poly'),'pts')[0][1:]
            ax,ay=map(float,one(q,'at')[1:3]);xs=[ax+float(v[1]) for v in vertices];ys=[ay+float(v[2]) for v in vertices]
            top=number in (1,24);right=number in (16,24)
            close([min(xs),min(ys),max(xs),max(ys)],
                  [1.25 if top else 1.3,-2.2 if top else 1.5,2.2,-1.5 if top else 2.2] if right else
                  [-2.2,-2.2 if top else 1.5,-1.25 if top else -1.3,-1.5 if top else 2.2])
        dims={**{str(i):(-1.9,round(-1.2+(i-2)*.4,6),.6,.2) for i in range(2,9)},
              **{str(i):(round(-1+(i-10)*.4,6),1.9,.2,.6) for i in range(10,16)},
              '17':(1.85,1.2,.7,.2),'18':(1.875,.8,.65,.2),'19':(1.8625,.4,.675,.2),
              '20':(1.9,0,.6,.2),'21':(1.9,-.4,.6,.2),'22':(1.9,-.8,.6,.2),'23':(1.9,-1.2,.6,.2),
              '25':(.9,-1.725,.2,.95),'26':(.45,-1.7,.2,1),'27':(0,-1.7,.2,1),'28':(-.45,-1.7,.2,1),'29':(-.9,-1.725,.2,.95)}
        for number,values in dims.items():
            close(one(p[number],'at')[1:3]+one(p[number],'size')[1:],values)
        assert not any(q[2]=='thru_hole' for q in children(fp,'pad'))
    elif name.startswith('HTSSOP-16_'):
        assert set(p)=={str(i) for i in range(1,18)}
        for number in range(1,17):
            x=(-2.275+(number-1)*.65) if number<=8 else (2.275-(number-9)*.65)
            close(one(p[str(number)],'at')[1:3],[x,2.9 if number<=8 else -2.9]);close(one(p[str(number)],'size')[1:],[.45,1.5])
        close(one(p['17'],'size')[1:],[5,3.4]);assert one(p['17'],'layers')[1:]==['F.Cu']
        rect=next(q for q in children(fp,'fp_rect') if one(q,'layer')[1]=='F.Paste')
        close(one(rect,'start')[1:],[-1.775,-1.23]);close(one(rect,'end')[1:],[1.775,1.23])
        mask=next(q for q in children(fp,'fp_poly') if one(q,'layer')[1]=='F.Mask')
        assert [tuple(map(float,q[1:])) for q in children(one(mask,'pts'),'xy')]==[(-1.775,-1.23),(1.775,-1.23),(1.775,1.23),(-1.775,1.23)]
        expected={(x,y) for x in (-1.8,-.6,.6,1.8) for y in (-1.2,0,1.2)}
        vias=[q for q in children(fp,'pad') if q[2]=='thru_hole'];assert len(vias)==12
        assert {tuple(map(float,one(q,'at')[1:3])) for q in vias}==expected
        for q in vias:
            assert q[1]=='17' and one(q,'layers')[1:]==['*.Cu'];close(one(q,'drill')[1:],[.2]);close(one(q,'size')[1:],[.45,.45])
    elif name.startswith('WIRELM-SMD_ESP32-C6'):
        assert set(p)=={str(i) for i in range(1,38)}
        left=[tuple(map(float,one(p[str(i)],'at')[1:3])) for i in range(1,15)]
        right=[tuple(map(float,one(p[str(i)],'at')[1:3])) for i in range(15,29)]
        close(left[0],[-8.75,-8.26]);close(left[-1],[-8.75,8.25]);close(right[0],[8.75,8.25]);close(right[-1],[8.75,-8.26])
        for i in range(13):close([left[i+1][1]-left[i][1]],[1.27])
        for number in range(1,29):close(one(p[str(number)],'size')[1:],[1.5,.9])
        close(one(p['33'],'at')[1:3],[-1.505,-2.54])
        for number in range(29,38):close(one(p[str(number)],'size')[1:],[.8,.8])
        vias=[q for q in children(fp,'pad') if q[2]=='thru_hole'];assert len(vias)==12
        for q in vias:
            assert q[1]=='29' and one(q,'layers')[1:]==['*.Cu'];close(one(q,'drill')[1:],[.3]);close(one(q,'size')[1:],[.5,.5])
    else:return False
    # Every repeated pad in compiled boards must have the SAME explicit net.
    groups={}
    for q in children(fp,'pad'):
        if not q[1]:continue
        if children(q,'net'):groups.setdefault(q[1],set()).add(one(q,'net')[2])
        elif any(v[1]=='atopile_address' for v in children(fp,'property')):raise AssertionError('Compiled electrical pad has no net')
    assert all(len(nets)==1 for nets in groups.values())
    return True

if __name__=='__main__':
    count=0
    for path in LIB.glob('*.kicad_mod'):
        fp=parse(path.read_text())
        if check(fp):
            assert path.read_bytes()==(LIB/'blind-core.pretty'/path.name).read_bytes();count+=1
    assert count==3
    boards=0
    for folder,target in [('blind-controller','motor-test'),('blind-io','controller-test'),('blind-charger','charger-test'),('blind-assembly','controller-test'),('blind-main','main-test')]:
        b=parse((ROOT/f'hw/layouts/{folder}/{target}/{target}.kicad_pcb').read_text())
        boards+=sum(check(fp) for fp in children(b,'footprint'))
    assert boards==8,boards
    print('PASS: three manufacturer land patterns, eight compiled instances, repeated thermal-pad net identity')
