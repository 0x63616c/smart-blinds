#!/usr/bin/env python3
"""Rebuild atomic split-harness parts from imports and audited Molex drawings."""
from pathlib import Path
import sexpdata as sx

ROOT = Path(__file__).resolve().parent

def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

def rounded(node):
    return [rounded(v) for v in node] if isinstance(node, list) else round(node, 4) if isinstance(node, float) else node

def rect(x1, y1, x2, y2, layer, width=.1):
    return sx.loads(f'(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {width}) (type default)) (fill none) (layer "{layer}"))')

def generate(mpn, code, symbol, footprint, count, pico=False):
    lib = sx.loads((ROOT/'blind-harness.kicad_sym').read_text())
    sym = next(s for s in children(lib, 'symbol') if s[1] == symbol)
    for prop in children(sym, 'property'):
        if prop[1] == 'LCSC Part':
            prop[2] = code
        elif prop[1] == 'Datasheet':
            prop[2] = f'https://www.molex.com/en-us/products/part-detail/{mpn}'
    for unit in children(sym, 'symbol'):
        # The two solder nails are mechanical attachment, not extra circuits.
        unit[:] = [v for v in unit if not (isinstance(v, list) and v and str(v[0]) == 'pin' and int(children(v, 'number')[0][1]) > count)]
        for pin in children(unit, 'pin'):
            pin[1] = sx.Symbol('passive')
    (ROOT/f'{mpn}.kicad_sym').write_text(sx.dumps([lib[0], *lib[1:3], sym])+'\n')
    fp = sx.loads((ROOT/f'blind-harness.pretty/{footprint}.kicad_mod').read_text())
    for prop in children(fp, 'property'):
        if prop[1] == 'LCSC Part':
            prop[2] = code
    fp[:] = [v for v in fp if not (isinstance(v, list) and v and str(v[0]) in ('fp_line', 'fp_rect', 'fp_circle', 'fp_arc', 'zone'))]
    if pico:
        # Both PicoBlade variants have only surface-mount electrical/retention
        # lands. The imported 3-way filename and attr incorrectly said THT.
        children(fp, 'attr')[0][1:] = [sx.Symbol('smd')]
    for model in children(fp, 'model'):
        model[1] = model[1].replace('${KIPRJMOD}/hw/parts/', '${KIPRJMOD}/../../../parts/')
        if pico:
            # KiCad model Y is opposite footprint Y. Imported models are only
            # visual aids; the drawing and checked pad geometry are authoritative.
            children(children(model, 'offset')[0], 'xyz')[0][2] = -1.45 if count == 4 else -1.55
    for pad in children(fp, 'pad'):
        if pico:
            number = int(pad[1]) if pad[1] else None
            if number is not None and number <= count:
                children(pad, 'at')[0][1:] = [-(count-1)*.625+(number-1)*1.25, 0.]
                children(pad, 'size')[0][1:] = [.8, 1.6]
            else:
                pad[1] = ''
                sign = (1 if number == count+1 else -1) if number else (1 if children(pad, 'at')[0][1] > 0 else -1)
                children(pad, 'at')[0][1:] = [sign*((count-1)*.625+2.55), 2.9]
                children(pad, 'size')[0][1:] = [2.1, 3.]
        elif pad[1] == '':
            pad[2] = sx.Symbol('np_thru_hole')
            children(pad, 'at')[0][1:] = [-1.5, 5.82]
        else:
            children(pad, 'size')[0][1:] = [1.8, 1.8]
            children(pad, 'drill')[0][1:] = [1.02]
            if pad[1] == '1':
                pad[3] = sx.Symbol('rect')
    if pico:
        half_body = (1.25*count+1.75)/2
        half_pad = (count-1)*.625+3.6
        fp += [rect(-half_body, .8, half_body, 5., 'F.Fab'),
               rect(-half_pad-.5, -1.3, half_pad+.5, 5.9, 'F.CrtYd', .05)]
        for sign in (-1, 1):
            a = sign*((count-1)*.625+.5)
            b = sign*((count-1)*.625+1.5)
            for y1, y2 in ((.4, 2.2), (3.6, 5.4)):
                # These four plastic-foot regions must stay clear of copper,
                # solder and other components. Rule areas enforce the former.
                x1, x2 = sorted((a, b))
                fp.append(rect(x1, y1, x2, y2, 'Dwgs.User', .05))
                fp.append(sx.loads(f'''(zone (net 0) (net_name "") (layer "F.Cu") (hatch edge 0.5)
                    (connect_pads (clearance 0)) (min_thickness 0.25)
                    (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))
                    (fill (thermal_gap 0.3) (thermal_bridge_width 0.3))
                    (polygon (pts (xy {x1} {y1}) (xy {x2} {y1}) (xy {x2} {y2}) (xy {x1} {y2}))))'''))
    else:
        fp += [rect(-3.325, .51, 3.325, 10.42, 'F.Fab'), rect(-3.825, -2.9, 3.825, 10.92, 'F.CrtYd', .05)]
    text = sx.dumps(rounded(fp))+'\n'
    (ROOT/f'{footprint}.kicad_mod').write_text(text)
    (ROOT/f'blind-harness.pretty/{footprint}.kicad_mod').write_text(text)
    lines = ['import has_designator_prefix', 'import has_part_picked', 'import is_atomic_part', '', f'component Part_{mpn}:',
             '    """UNVERIFIED manufacturing; Molex drawing-audited contact geometry."""',
             f'    trait is_atomic_part<manufacturer="Molex", partnumber="{mpn}", footprint="{footprint}.kicad_mod", symbol="{mpn}.kicad_sym">',
             f'    trait has_part_picked::by_supplier<supplier_id="lcsc", supplier_partno="{code}", manufacturer="Molex", partno="{mpn}">',
             '    trait has_designator_prefix<prefix="J">']
    for i in range(1, count+1):
        lines += [f'    signal contact{i}', f'    contact{i} ~ pin {i}']
    (ROOT/f'{mpn}.ato').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__':
    generate('430450200', 'C122431', '0430450200', 'CONN-TH_43045-0200', 2)
    generate('532610471', 'C696092', '53261-0471', 'CONN-SMD_4P-P1.25_53261-0471', 4, True)
    generate('532610371', 'C293630', '532610371', 'CONN-TH_532610371', 3, True)
