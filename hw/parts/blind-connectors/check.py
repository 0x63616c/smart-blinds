#!/usr/bin/env python3
"""Independent physical contact/hole contract from SD-43045-001 Rev H."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,children,one
HERE=Path(__file__).resolve().parent
fp=parse((HERE/'CONN-TH_43045-0600.kicad_mod').read_text())
pads=children(fp,'pad');signal={str(p[1]):p for p in pads if p[1]}
assert set(signal)==set('123456')
# Component-side view, mating direction +Y; sequential rows, not alternating.
expected={'1':(3.,1.5),'2':(0.,1.5),'3':(-3.,1.5),'4':(3.,-1.5),'5':(0.,-1.5),'6':(-3.,-1.5)}
for n,xy in expected.items():
 p=signal[n]
 assert tuple(map(float,one(p,'at')[1:3]))==xy
 assert float(one(p,'drill')[1])==1.02
 assert str(p[2])=='thru_hole'
 assert list(map(float,one(p,'size')[1:]))==[1.8,1.8]
assert str(signal['1'][3])=='rect'
pegs=[p for p in pads if not p[1]]
assert len(pegs)==1
assert tuple(map(float,one(pegs[0],'at')[1:3]))==(0.,5.82)
assert str(pegs[0][2])=='np_thru_hole' and float(one(pegs[0],'drill')[1])==3
sym=parse((HERE/'430450600.kicad_sym').read_text());nums=[]
for main in children(sym,'symbol'):
 for unit in children(main,'symbol'):
  nums += [str(one(p,'number')[1]) for p in children(unit,'pin')]
assert sorted(nums)==list('123456')
print('PASS: six contacts, 3 mm row/column pitch, 1.02 mm signal holes, one nonplated 3 mm peg; physical fit remains unverified')
