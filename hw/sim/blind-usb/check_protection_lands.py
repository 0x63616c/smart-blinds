#!/usr/bin/env python3
"""Primary TI land transcription in source and compiled USB/main captures.
No assembly-process acceptance: thermal vias/RTN copper still need actual routing.
"""
import copy,json,math,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'tools'))
from kicad_sexpr import parse,children,one

def test(fp,kind):
 assert 'smd' in one(fp,'attr')[1:]
 pads={str(p[1]):p for p in children(fp,'pad')}
 expected={}
 if kind=='cutoff':
  for i in range(8):
   expected[str(i+1)]=(-2.275+.65*i,2.9,.45,1.5)
   expected[str(16-i)]=(-2.275+.65*i,-2.9,.45,1.5)
  expected['17']=(0,0,5,3.4)
 else:
  expected={str(n):(x,y,.45,.3) for n,x,y in [(1,-.975,-.65),(2,-.975,0),(3,-.975,.65),(4,.975,.65),(5,.975,0),(6,.975,-.65)]};expected['7']=(0,0,1,1.6)
 assert set(pads)==set(expected)
 for n,(x,y,w,h) in expected.items():
  p=pads[n];a=one(p,'at');s=one(p,'size');assert p[2:4]==['smd','rect'];assert all(abs(float(v)-e)<1e-6 for v,e in zip(a[1:3]+s[1:3],[x,y,w,h]))
  assert ('F.Cu' in one(p,'layers')[1:]) and not children(p,'drill')
 if kind=='cutoff':
  assert one(pads['17'],'layers')[1:]==['F.Cu']
  mask=[p for p in children(fp,'fp_poly') if one(p,'layer')[1]=='F.Mask'];assert len(mask)==1
  pts=one(mask[0],'pts');assert [(float(x[1]),float(x[2]))for x in children(pts,'xy')]==[(-1.65,-1.65),(1.65,-1.65),(1.65,1.65),(-1.65,1.65)]
  paste=[p for p in children(fp,'fp_rect') if one(p,'layer')[1]=='F.Paste'];assert len(paste)==1
  assert one(paste[0],'start')[1:]==['-1.65','-1.65'] and one(paste[0],'end')[1:]==['1.65','1.65']
  assert one(mask[0],'fill')[1]=='solid' and one(paste[0],'fill')[1]=='solid'
 courts=[p for p in children(fp,'fp_rect') if one(p,'layer')[1]=='F.CrtYd'];assert len(courts)==1
 a,b=one(courts[0],'start')[1:3],one(courts[0],'end')[1:3]
 expect=(-2.95,-3.9,2.95,3.9) if kind=='cutoff' else(-1.45,-1.3,1.45,1.3)
 assert all(abs(float(v)-e)<1e-6 for v,e in zip(a+b,expect))
 return float(b[0])-float(a[0]),float(b[1])-float(a[1])

def main():
 p=R/'hw/parts/blind-usb-protection';checked=[]
 for kind,fn in [('cutoff','TPS26600_PWP16.kicad_mod'),('tvs_guarded','TVS1800_DRV6.kicad_mod')]:
  f=parse((p/fn).read_text());test(f,kind);assert (p/fn).read_bytes()==(p/'blind-usb-protection.pretty'/fn).read_bytes();checked.append(fn)
  for block in ['blind-usb/usb-test/usb-test.kicad_pcb','blind-main/main-test/main-test.kicad_pcb']:
   board=parse((R/'hw/layouts'/block).read_text());fps=[x for x in children(board,'footprint') if any(v[1]=='atopile_address' and v[2]=='usb.'+kind for v in children(x,'property'))];assert len(fps)==1;test(fps[0],kind);checked.append(block+':'+kind)
 f=parse((p/'TPS26600_PWP16.kicad_mod').read_text());faults={}
 q=copy.deepcopy(f);one(children(q,'pad')[0],'at')[1]='0';faults['wrong_pin1_land']=q
 q=copy.deepcopy(f);q.remove(next(x for x in children(q,'fp_poly') if one(x,'layer')[1]=='F.Mask'));faults['lost_thermal_mask']=q
 q=copy.deepcopy(f);q.remove(next(x for x in children(q,'fp_rect') if one(x,'layer')[1]=='F.Paste'));faults['lost_thermal_paste']=q
 q=copy.deepcopy(f);one(q,'attr')[1]='through_hole';faults['wrong_SMT_metadata']=q
 q=copy.deepcopy(f);one(children(q,'pad')[-1],'size')[1]='2.3';faults['undersized_imported_thermal_land']=q
 for name,q in faults.items():
  try:test(q,'cutoff')
  except (AssertionError,ValueError):pass
  else:raise AssertionError('Undetected '+name)
 print(json.dumps({'status':'PASS primary source and compiled geometry; thermal routing still pending','checked':checked,'negative_controls':list(faults)},indent=2))
if __name__=='__main__':main()
