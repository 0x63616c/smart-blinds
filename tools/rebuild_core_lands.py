#!/usr/bin/env python3
"""Transcribe three manufacturer land patterns; keep symbol/net identities intact.

Sources/revisions and remaining assembly gates: docs/electrical/land-pattern-review.md.
Run before normal atopile rebuilds. This does not modify placement or routed copper.
"""
import math
from pathlib import Path
import uuid
from kicad_sexpr import Atom as A, children, dumps, node as n, one, parse

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'hw/parts/blind-core'
NS=uuid.UUID('d3b09a45-7660-54a7-8dce-58f4bc2a03d6')


def identity(fp,tag): return n('uuid',str(uuid.uuid5(NS,fp[1]+'/'+tag)))
def pad(fp,number,x,y,w,h,shape='roundrect',layers=('F.Cu','F.Paste','F.Mask'),tag=None):
    p=n('pad',str(number),A('smd'),A(shape),n('at',round(x,6),round(y,6),0),n('size',w,h),n('layers',*layers))
    if shape=='roundrect':p.append(n('roundrect_rratio',round(.05/min(w,h),6)))
    p.append(identity(fp,tag or 'pad-'+str(number)));fp.append(p);return p

def via(fp,number,x,y,drill=.2,diameter=.45):
    fp.append(n('pad',str(number),A('thru_hole'),A('circle'),n('at',round(x,6),round(y,6)),n('size',diameter,diameter),
                n('drill',drill),n('layers','*.Cu'),n('remove_unused_layers',A('no')),identity(fp,f'via-{x}-{y}')))

def rect(fp,a,b,layer,tag):
    fp.append(n('fp_rect',n('start',*a),n('end',*b),n('stroke',n('width',.05 if layer=='F.CrtYd' else .1),n('type',A('default'))),
                n('fill',A('none')),n('layer',layer),identity(fp,tag)))

def base(name):
    fp=parse((LIB/(name+'.kicad_mod')).read_text())
    fp[:]=[v for v in fp if not(isinstance(v,list) and v and (v[0]=='pad' or v[0].startswith('fp_')))]
    return fp

def save(fp):
    text=dumps(fp)+'\n';(LIB/(fp[1]+'.kicad_mod')).write_text(text)
    (LIB/'blind-core.pretty'/(fp[1]+'.kicad_mod')).write_text(text)

def rounded_outline(vertices,r=.05):
    result=[]
    for i,p in enumerate(vertices):
        before,after=vertices[i-1],vertices[(i+1)%len(vertices)]
        def unit(q):
            length=math.dist(p,q);return ((q[0]-p[0])/length,(q[1]-p[1])/length)
        u,v=unit(before),unit(after)
        centre=(p[0]+r*(u[0]+v[0]),p[1]+r*(u[1]+v[1]))
        a=math.atan2(p[1]+r*u[1]-centre[1],p[0]+r*u[0]-centre[0])
        b=math.atan2(p[1]+r*v[1]-centre[1],p[0]+r*v[0]-centre[0])
        delta=(b-a+math.pi)%(2*math.pi)-math.pi
        for j in range(7):
            angle=a+delta*j/6;result.append((centre[0]+r*math.cos(angle),centre[1]+r*math.sin(angle)))
    return result

def corner(fp,number,anchor,vertices):
    p=pad(fp,number,*anchor,.1,.1,'custom')
    pts=[n('xy',round(x-anchor[0],6),round(y-anchor[1],6)) for x,y in rounded_outline(vertices)]
    p.extend([n('options',n('clearance',A('outline')),n('anchor',A('circle'))),
              n('primitives',n('gr_poly',n('pts',*pts),n('width',0),n('fill',A('yes'))))])


def charger():
    fp=base('QFN-29_L4.0-W4.0-P0.40-TL-BQ25792RQMR')
    # TI RQM0029A top-view land example. There is no central exposed pad:
    # PMID is the elongated perimeter lead 29, independent of ground lead 27.
    top=[(-2.2,-1.7),(-1.45,-1.7),(-1.45,-2.2),(-1.25,-2.2),(-1.25,-1.5),(-2.2,-1.5)]
    bottom=[(-2.2,1.5),(-1.3,1.5),(-1.3,2.2),(-1.5,2.2),(-1.5,1.7),(-2.2,1.7)]
    corner(fp,1,(-1.725,-1.6),top);corner(fp,24,(1.725,-1.6),[(-x,y) for x,y in top])
    corner(fp,9,(-1.75,1.6),bottom);corner(fp,16,(1.75,1.6),[(-x,y) for x,y in bottom])
    for pin in range(2,9):pad(fp,pin,-1.9,-1.2+(pin-2)*.4,.6,.2)
    for pin in range(10,16):pad(fp,pin,-1+(pin-10)*.4,1.9,.2,.6)
    # Unequal three lower-right leads are dimensioned separately by TI.
    pad(fp,17,1.85,1.2,.7,.2);pad(fp,18,1.875,.8,.65,.2);pad(fp,19,1.8625,.4,.675,.2)
    for pin in range(20,24):pad(fp,pin,1.9,-(pin-20)*.4,.6,.2)
    for pin in range(25,30):
        outer=pin in (25,29);pad(fp,pin,.9-(pin-25)*.45,-1.725 if outer else -1.7,.2,.95 if outer else 1)
    rect(fp,(-2,-2),(2,2),'F.Fab','body');rect(fp,(-2.45,-2.45),(2.45,2.45),'F.CrtYd','courtyard');save(fp)


def module():
    fp=base('WIRELM-SMD_ESP32-C6-WROOM-1')
    for pin in range(1,15):pad(fp,pin,-8.75,8.25-(14-pin)*1.27,1.5,.9,'rect')
    for pin in range(15,29):pad(fp,pin,8.75,8.25-(pin-15)*1.27,1.5,.9,'rect')
    grid={29:(0,0),30:(1,0),31:(2,0),32:(2,1),33:(1,1),34:(0,1),35:(0,2),36:(1,2),37:(2,2)}
    for number,(x,y) in grid.items():pad(fp,number,-2.755+1.25*x,-3.79+1.25*y,.8,.8,'rect')
    # Imported thermal holes were unnumbered/no-net and shorted the GND islands.
    # Repeated physical pad 29 assigns every thermal barrel to the same GND net.
    # No paste/mask opening on these holes; no filled-via process is implied.
    for x in range(3):
        for y in range(2):via(fp,29,-2.755+1.25*x,-3.165+1.25*y,.3,.5)
    for x in range(2):
        for y in range(3):via(fp,29,-2.13+1.25*x,-3.79+1.25*y,.3,.5)
    rect(fp,(-9,-15.75),(9,9.75),'F.Fab','body')
    rect(fp,(-9,-15.75),(9,-9.75),'F.Fab','antenna')
    rect(fp,(-9.75,-16),(9.75,10),'F.CrtYd','courtyard')
    fp[:]=[q for q in fp if not(isinstance(q,list) and q and q[0]=='model')]
    fp.append(n('model','${KIPRJMOD}/../../../parts/blind-core/blind-core.3dshapes/ESP32-C6-WROOM-1.STEP',
                n('offset',n('xyz',-9,-9.75,0)),n('scale',n('xyz',1,1,1)),n('rotate',n('xyz',0,0,0))))
    save(fp)


def motor():
    fp=base('HTSSOP-16_L5.0-W4.4-P0.65-LS6.4-BL-EP')
    # Rotate TI PWP0016J example 90 degrees to preserve existing pin orientation.
    for pin in range(1,9):pad(fp,pin,-2.275+(pin-1)*.65,2.9,.45,1.5)
    for pin in range(9,17):pad(fp,pin,2.275-(pin-9)*.65,-2.9,.45,1.5)
    # Mask-defined thermal land: TI 5 x 3.4 copper, 3.55 x 2.46 exposed opening.
    pad(fp,17,0,0,5,3.4,'rect',('F.Cu',))
    # Distinct primitive kinds avoid atopile 0.15.9 deduplicating identical
    # rectangles across layers and silently dropping the mask opening.
    fp.append(n('fp_poly',n('pts',n('xy',-1.775,-1.23),n('xy',1.775,-1.23),n('xy',1.775,1.23),n('xy',-1.775,1.23)),
                n('stroke',n('width',0),n('type',A('default'))),n('fill',A('solid')),n('layer','F.Mask'),identity(fp,'F.Mask')))
    fp.append(n('fp_rect',n('start',-1.775,-1.23),n('end',1.775,1.23),
                n('stroke',n('width',0),n('type',A('default'))),n('fill',A('solid')),n('layer','F.Paste'),identity(fp,'F.Paste')))
    for x in (-1.8,-.6,.6,1.8):
        for y in (-1.2,0,1.2):via(fp,17,x,y)
    rect(fp,(-2.5,-2.2),(2.5,2.2),'F.Fab','body')
    rect(fp,(-2.75,-3.9),(2.75,3.9),'F.CrtYd','courtyard');save(fp)

if __name__=='__main__':
    charger();module();motor();print('Rebuilt BQ25798, ESP32-C6-WROOM-1 and DRV8874 manufacturer land patterns')
