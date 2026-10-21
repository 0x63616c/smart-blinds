#!/usr/bin/env python3
"""Add explicit sourced body/pad clearance outlines to imported footprints."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import children,one,parse,dumps,node,Atom
PLAN=ROOT/'hw/placement/footprint-clearances.json'
NS=uuid.UUID('af628b4b-9955-5031-9a01-58eb28521ed7')

def courtyard_items(fp):
    return [v for v in fp if isinstance(v,list) and children(v,'layer') and one(v,'layer')[1]=='F.CrtYd']

def geometry_hash(items):
    """Hash parsed geometry, including pad types, drill sizes and pin numbers."""
    return hashlib.sha256(dumps(node('geometry',*items)).encode()).hexdigest()

def update_outline(fp,expected,entry,path,check):
    existing=courtyard_items(fp)
    if existing==[expected]:return False
    if check:raise ValueError('Missing or unreviewed courtyard: '+path)
    if existing:
        originals=entry.get('replace_courtyard_sha256',{})
        if geometry_hash(existing)!=originals.get(path):
            raise ValueError('Existing courtyard differs from reviewed original: '+path)
    fp[:]=[item for item in fp if item not in existing]
    fp.append(expected)
    return True

def pad_bounds(fp):
    points=[]
    for pad in children(fp,'pad'):
        at=list(map(float,one(pad,'at')[1:]));x,y=at[:2]
        angle=math.radians(at[2] if len(at)>2 else 0)
        w,h=map(float,one(pad,'size')[1:])
        if not all(math.isfinite(v) for v in at+[w,h]) or min(w,h)<=0:
            raise ValueError('Invalid pad geometry')
        dx=(abs(w*math.cos(angle))+abs(h*math.sin(angle)))/2
        dy=(abs(w*math.sin(angle))+abs(h*math.cos(angle)))/2
        points.extend([(x-dx,y-dy),(x+dx,y+dy)])
        for primitives in children(pad,'primitives'):
            for primitive in primitives[1:]:
                if primitive[0]!='gr_poly' or one(primitive,'fill')[1]!='yes':
                    raise ValueError('Unsupported custom-pad geometry')
                stroke=float(one(primitive,'width')[1])/2
                if not math.isfinite(stroke) or stroke<0:raise ValueError('Invalid custom-pad stroke')
                for vertex in children(one(primitive,'pts'),'xy'):
                    px,py=map(float,vertex[1:])
                    if not math.isfinite(px) or not math.isfinite(py):raise ValueError('Non-finite custom-pad vertex')
                    c,s=math.cos(angle),math.sin(angle)
                    vx=x+c*px+s*py;vy=y-s*px+c*py
                    points.extend([(vx-stroke,vy-stroke),(vx+stroke,vy+stroke)])
    if not points:raise ValueError('No pads')
    return [min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)]

def bounds(fp,entry):
    pads=pad_bounds(fp);body=entry['body_lead_bounds_mm']
    if len(body)!=4 or not all(math.isfinite(v) for v in body) or body[0]>=body[2] or body[1]>=body[3]:
        raise ValueError('Invalid body envelope')
    margin=entry['clearance_margin_mm'];grid=.05
    if margin!=.25:raise ValueError('Expected explicitly reviewed 0.25mm clearance')
    union=[min(pads[i],body[i])-margin for i in (0,1)]+[max(pads[i],body[i])+margin for i in (2,3)]
    minimum=[round(math.floor((v+1e-8)/grid)*grid,4) if i<2 else round(math.ceil((v-1e-8)/grid)*grid,4) for i,v in enumerate(union)]
    retained=entry.get('retained_courtyard_bounds_mm')
    if retained is None:return minimum
    # A corrected land pattern may become smaller without forcing a reviewed
    # assembly envelope to shrink. Never let an override reduce the minimum.
    if (len(retained)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in retained)
        or any(retained[i]>minimum[i]+1e-8 for i in (0,1))
        or any(retained[i]<minimum[i]-1e-8 for i in (2,3))
        or any(abs(v/grid-round(v/grid))>1e-6 for v in retained)):
        raise ValueError('Retained courtyard must enclose the full minimum on the 0.05mm grid')
    return retained

def drawing(box,key):
    return node('fp_rect',node('start',*box[:2]),node('end',*box[2:]),
        node('stroke',node('width',.05),node('type',Atom('default'))),
        node('fill',Atom('none')),node('layer','F.CrtYd'),node('uuid',str(uuid.uuid5(NS,key))))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    plan=json.loads(PLAN.read_text());results=[];pending=[]
    for entry in plan['footprints']:
        path=ROOT/entry['source'];fp=parse(path.read_text());box=bounds(fp,entry)
        pads=children(fp,'pad')
        if 'reviewed_pad_sha256' in entry and geometry_hash(pads)!=entry['reviewed_pad_sha256']:
            raise ValueError('Pad geometry differs from reviewed source: '+entry['source'])
        expected=parse(dumps(drawing(box,entry['source'])))
        if update_outline(fp,expected,entry,entry['source'],a.check):
            pending.append((path,dumps(fp)+'\n'))
        # Table-specific mirror libraries are explicit, never found by a broad glob.
        for mirror in entry.get('mirrors',[]):
            mp=ROOT/mirror;mf=parse(mp.read_text())
            if children(mf,'pad')!=pads:raise ValueError('Mirror pad geometry differs: '+mirror)
            # Preserve the mirror's own library identity/model path.
            if update_outline(mf,expected,entry,mirror,a.check):
                pending.append((mp,dumps(mf)+'\n'))
        results.append({'source':entry['source'],'body_lead_bounds_mm':entry['body_lead_bounds_mm'],
            'pad_bounds_mm':pad_bounds(fp),'courtyard_bounds_mm':box,'envelope_status':entry['envelope_status']})
    # Validate all entries before making any source change.
    for path,text in pending:path.write_text(text)
    print(json.dumps({'status':'SOURCE GEOMETRY ONLY; rebuild and DRC required','footprints':results},indent=2))
if __name__=='__main__':main()
