#!/usr/bin/env python3
"""Audited MYOUNG A5 through-hole holder; current/reverse-insertion unqualified."""
from pathlib import Path
import sexpdata as sx
ROOT=Path(__file__).resolve().parent

def children(n,k):return [v for v in n if isinstance(v,list) and v and str(v[0])==k]
def rounded(n):return [rounded(v) for v in n] if isinstance(n,list) else round(n,3) if isinstance(n,float) else n
if __name__=='__main__':
 lib=sx.loads((ROOT/'blind-holders.kicad_sym').read_text());sym=next(s for s in children(lib,'symbol') if s[1]=='BH-21700-A5BJ001')
 for u in children(sym,'symbol'):
  for p in children(u,'pin'):p[1]=sx.Symbol('passive')
 (ROOT/'BH-21700-A5BJ001.kicad_sym').write_text(sx.dumps([lib[0],*lib[1:3],sym])+'\n')
 fp=sx.loads((ROOT/'blind-holders.pretty/BAT-TH_BH-21700-A5BJ001.kicad_mod').read_text())
 for m in children(fp,'model'):m[1]=m[1].replace('${KIPRJMOD}/hw/parts/','${KIPRJMOD}/../../../parts/')
 for p in children(fp,'pad'):
  if p[1]=='':p[2]=sx.Symbol('np_thru_hole')
  else:children(p,'drill')[0][1:]=[sx.Symbol('oval'),1.,3.7]
 fp=[v for v in fp if not(isinstance(v,list) and v and str(v[0]) in ('fp_line','fp_rect') and children(v,'layer') and children(v,'layer')[0][1]=='F.CrtYd')]
 fp.append(sx.loads('(fp_rect (start -42.15 -13) (end 42.15 13) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))'))
 fp.append(sx.loads('(fp_rect (start -41.5 -12.5) (end 41.5 12.5) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))'))
 (ROOT/'BAT-TH_BH-21700-A5BJ001.kicad_mod').write_text(sx.dumps(rounded(fp))+'\n')
 (ROOT/'BH_21700_A5BJ001.ato').write_text('''import has_designator_prefix
import has_part_picked
import is_atomic_part

component Part_BH_21700_A5BJ001:
    """UNVERIFIED holder: drawing has no current rating or reverse-cell protection claim."""
    trait is_atomic_part<manufacturer="MYOUNG", partnumber="BH-21700-A5BJ001", footprint="BAT-TH_BH-21700-A5BJ001.kicad_mod", symbol="BH-21700-A5BJ001.kicad_sym">
    trait has_part_picked::by_supplier<supplier_id="lcsc", supplier_partno="C20606809", manufacturer="MYOUNG", partno="BH-21700-A5BJ001">
    trait has_designator_prefix<prefix="BT">
    signal positive
    signal negative
    positive ~ pin 1
    negative ~ pin 2
''')
