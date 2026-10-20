#!/usr/bin/env python3
"""Check the USB socket lands against the transcribed HRO manufacturer drawing."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,children,one

def near(actual,expected):
    assert len(actual)==len(expected) and all(abs(float(a)-b)<1e-6 for a,b in zip(actual,expected)),(actual,expected)

def check(fp):
    pads=children(fp,'pad');named={p[1]:p for p in pads if p[1]};holes=[p for p in pads if not p[1]]
    xs={'A1B12':-3.2,'A4B9':-2.4,'B8':-1.75,'A5':-1.25,'B7':-.75,'A6':-.25,
        'A7':.25,'B6':.75,'A8':1.25,'B5':1.75,'B4A9':2.4,'B1A12':3.2}
    assert set(named)==set(xs)|{'1','2','3','4'} and len(pads)==18
    for pin,x in xs.items():
        p=named[pin];assert p[2]=='smd' and p[3]=='rect';near(one(p,'at')[1:3],[x,-1.07]);near(one(p,'size')[1:],[.6 if len(pin)>2 else .3,1.14])
    for pin in ['1','2','3','4']:
        p=named[pin];front=pin in ['2','3'];assert p[2]=='thru_hole' and p[3]=='oval'
        near(one(p,'at')[1:3],[(1 if pin in ['1','2'] else -1)*4.325,3.68 if front else -.5])
        near(one(p,'size')[1:],[.9,1.7 if front else 2.0]);assert one(p,'drill')[1]=='oval'
        near(one(p,'drill')[2:],[.6,1.4 if front else 1.7])
    assert len(holes)==2
    for p,x in zip(sorted(holes,key=lambda p:float(one(p,'at')[1])),[-2.89,2.89]):
        assert p[2]=='np_thru_hole';near(one(p,'at')[1:3],[x,0]);near(one(p,'drill')[1:],[.6])

if __name__=='__main__':
    part=ROOT/'hw/parts/blind-usb/HRO_TYPE_C_31_M_12.kicad_mod';check(parse(part.read_text()))
    for target in ['blind-usb/usb-test/usb-test','blind-main/main-test/main-test']:
        pcb=parse((ROOT/'hw/layouts'/f'{target}.kicad_pcb').read_text())
        fp=next(f for f in children(pcb,'footprint') if {p[1]:p[2] for p in children(f,'property')}.get('atopile_address')=='usb.connector')
        check(fp)
    print('PASS: exact USB land dimensions and pin positions in source, USB block and main capture; physical fit remains untested')
