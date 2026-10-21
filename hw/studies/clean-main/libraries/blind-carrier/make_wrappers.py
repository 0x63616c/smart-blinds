#!/usr/bin/env python3
"""Split the public EasyEDA import into atomic local library wrappers.

Run with the project's atopile Python (sexpdata). This does not call a parts
service or assign electrical ratings. Review pin maps against primary documents
before using a wrapper in a circuit. Existing source-derived symbols are retained.
"""
from pathlib import Path
import re
import sexpdata as sx

ROOT = Path(__file__).resolve().parent
PARTS = {
    "0451003.MRL": ("Littelfuse", "C13982", "F"),
    "AON7400A": ("Alpha & Omega Semiconductor", "C85734", "Q"),
    "WSL2512R0100FEA": ("Vishay", "C844901", "R"),
    "CL21B474KBFNNNE": ("Samsung", "C13967", "C"),
    "0402WGF100JTCE": ("UNI-ROYAL", "C25077", "R"),
    "1206W4F1000T5E": ("UNI-ROYAL", "C17901", "R"),
    "0402WGF1500TCE": ("UNI-ROYAL", "C25082", "R"),
    "BZT52C4V7": ("JSCJ", "C2116", "D"),
}
PIN_NAMES = {}


def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

if __name__ == "__main__":
    lib = sx.loads((ROOT / "blind-carrier.kicad_sym").read_text())
    for sym in children(lib, "symbol"):
        name = sym[1]
        maker, code, prefix = PARTS[name]
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        classname = "Part_" + stem
        props = {p[1]: p[2] for p in children(sym, "property")}
        footprint = props["Footprint"].split(":", 1)[1]
        # atopile0.15 expects atomic footprint files beside their .ato source.
        footprint_source = ROOT / "blind-carrier.pretty" / (footprint + ".kicad_mod")
        footprint_text = footprint_source.read_text().replace('${KIPRJMOD}/hw/parts/', '${KIPRJMOD}/../../../parts/')
        # Generic geometry is shared by multiple exact parts. Keep identity in
        # the atomic wrapper, not an EasyEDA supplier tag overwritten by import.
        footprint_text = re.sub(r'\t\(property "LCSC Part".*?\n\t\)\n', '', footprint_text, flags=re.S)
        if name in {"0451003.MRL", "WSL2512R0100FEA"}:
            # Manufacturer land patterns, not the generic imported pads.
            fp = sx.loads(footprint_text)
            centre, size = (2.455, [1.96, 3.15]) if name == "0451003.MRL" else (2.855, [1.65, 3.68])
            for pad in children(fp, "pad"):
                children(pad, "at")[0][1:3] = [-centre if pad[1] == "1" else centre, 0]
                children(pad, "size")[0][1:3] = size
            footprint_text = sx.dumps(fp) + "\n"
        if name == "AON7400A":
            # AOS PO-00047I manufacturer land pattern, top view. Number9 is
            # the exposed drain; its three overlapping copper regions are one pad.
            fp = sx.loads(footprint_text)
            old9 = None
            for pad in children(fp, "pad"):
                n = int(pad[1])
                if n <= 4:
                    children(pad, "at")[0][1:3] = [round(-0.975 + (n-1)*0.65, 3), 1.4]
                    children(pad, "size")[0][1:3] = [0.35, 0.5]
                elif n <= 8:
                    children(pad, "at")[0][1:3] = [round(0.975 - (n-5)*0.65, 3), -1.5]
                    children(pad, "size")[0][1:3] = [0.4, 0.3]
                else:
                    old9 = pad
            fp.remove(old9)
            for x,y,w,h in [(0,-0.36,2.45,1.98),(-1.415,0,0.38,0.43),(1.415,0,0.38,0.43)]:
                fp.append(sx.loads(f'(pad "9" smd rect (at {x} {y}) (size {w} {h}) (layers "F.Cu" "F.Mask"))'))
            # Divided paste is provisional; final assembler stencil review required.
            for x in [-0.6,0.6]:
                for y in [-0.9,0.1]:
                    fp.append(sx.loads(f'(pad "" smd rect (at {x} {y}) (size 0.9 0.7) (layers "F.Paste"))'))
            footprint_text = sx.dumps(fp) + "\n"
        (ROOT / (footprint + ".kicad_mod")).write_text(footprint_text)
        (ROOT / (stem + ".kicad_sym")).write_text(sx.dumps([lib[0], *lib[1:3], sym]) + "\n")
        pins = []
        for unit in children(sym, "symbol"):
            for pin in children(unit, "pin"):
                label = children(pin, "name")[0][1]
                number = children(pin, "number")[0][1]
                label = PIN_NAMES.get(name, {}).get(number, re.sub(r"[^a-zA-Z0-9_]", "_", label))
                pins.append((label, number))
        # Repeated names are one net, with all duplicate physical pads connected.
        lines = ["import has_designator_prefix", "import has_part_picked", "import is_atomic_part", "", f"component {classname}:",
                 '    """Atomic imported geometry; see README for pin-review status."""',
                 f'    trait is_atomic_part<manufacturer="{maker}", partnumber="{name}", footprint="{footprint}.kicad_mod", symbol="{stem}.kicad_sym">',
                 f'    trait has_part_picked::by_supplier<supplier_id="lcsc", supplier_partno="{code}", manufacturer="{maker}", partno="{name}">',
                 f'    trait has_designator_prefix<prefix="{prefix}">', ""]
        seen = set()
        for label, number in pins:
            if label and label not in seen and not label[0].isdigit():
                lines.append(f"    signal {label}")
                seen.add(label)
            if label in seen:
                lines.append(f"    {label} ~ pin {number}")
            else:
                lines.append(f"    pin {number}")
        (ROOT / (stem + ".ato")).write_text("\n".join(lines) + "\n")
        print(name, len(pins), "pins")
