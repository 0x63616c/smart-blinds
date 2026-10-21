#!/usr/bin/env python3
"""Create selected C127367 atomic part from import; audited SD-43045-001 Rev H."""
from pathlib import Path
import sexpdata as sx
ROOT = Path(__file__).resolve().parent

def children(node, key):
    return [v for v in node if isinstance(v,list) and v and str(v[0])==key]

def rounded(node):
    return [rounded(v) for v in node] if isinstance(node,list) else round(node,3) if isinstance(node,float) else node

if __name__=='__main__':
    lib=sx.loads((ROOT/'blind-connectors.kicad_sym').read_text())
    sym=next(s for s in children(lib,'symbol') if s[1]=='430450600')
    for unit in children(sym,'symbol'):
        for pin in children(unit,'pin'): pin[1]=sx.Symbol('passive')
    (ROOT/'430450600.kicad_sym').write_text(sx.dumps([lib[0],*lib[1:3],sym])+'\n')
    fp=sx.loads((ROOT/'blind-connectors.pretty/CONN-TH_43045-0600.kicad_mod').read_text())
    for model in children(fp,'model'):
        model[1]=model[1].replace('${KIPRJMOD}/hw/parts/','${KIPRJMOD}/../../../parts/')
    for pad in children(fp,'pad'):
        if pad[1]=='':
            pad[2]=sx.Symbol('np_thru_hole')
            children(pad,'size')[0][1:]=[3.,3.]
            children(pad,'drill')[0][1:]=[3.]
        else:
            children(pad,'drill')[0][1:]=[1.02]
            if pad[1]=='1': pad[3]=sx.Symbol('rect')
    # Existing courtyard excludes rear solder tails. Include all six pads and
    # full header; plug, cable, latch operation and removal need separate space.
    fp=[v for v in fp if not (isinstance(v,list) and v and str(v[0]) in ('fp_line','fp_rect') and children(v,'layer') and children(v,'layer')[0][1]=='F.CrtYd')]
    fp.append(sx.loads('(fp_rect (start -6.825 -2.9) (end 6.825 10.92) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))'))
    fp.append(sx.loads('(fp_rect (start -6.325 0.51) (end 6.325 10.42) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))'))
    (ROOT/'CONN-TH_43045-0600.kicad_mod').write_text(sx.dumps(rounded(fp))+'\n')
    lines=['import has_designator_prefix','import has_part_picked','import is_atomic_part','',
           'component Part_430450600:',
           '    """UNVERIFIED manufacturing; six pins and one locator audited against SD-43045-001 Rev H."""',
           '    trait is_atomic_part<manufacturer="Molex", partnumber="430450600", footprint="CONN-TH_43045-0600.kicad_mod", symbol="430450600.kicad_sym">',
           '    trait has_part_picked::by_supplier<supplier_id="lcsc", supplier_partno="C127367", manufacturer="Molex", partno="430450600">',
           '    trait has_designator_prefix<prefix="J">','']
    for i in range(1,7): lines += [f'    signal contact{i}',f'    contact{i} ~ pin {i}']
    (ROOT/'430450600.ato').write_text('\n'.join(lines)+'\n')
