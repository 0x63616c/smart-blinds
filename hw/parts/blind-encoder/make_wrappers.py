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
PARTS = {"TPS70950DBVR": ("Texas Instruments", "C96028", "U")}
PIN_NAMES = {}


def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

if __name__ == "__main__":
    lib = sx.loads((ROOT / "blind-encoder.kicad_sym").read_text())
    for sym in children(lib, "symbol"):
        name = sym[1]
        maker, code, prefix = PARTS[name]
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        classname = "Part_" + stem
        props = {p[1]: p[2] for p in children(sym, "property")}
        footprint = props["Footprint"].split(":", 1)[1]
        # atopile0.15 expects atomic footprint files beside their .ato source.
        footprint_source = ROOT / "blind-encoder.pretty" / (footprint + ".kicad_mod")
        footprint_text = footprint_source.read_text()
        if footprint_text.lstrip().startswith('(module '):
            raise ValueError('Upgrade blind-encoder.pretty with kicad-cli fp upgrade before generating wrappers')
        # Imports have emitted both relative and malformed KIPRJMOD prefixes.
        # Every board using this block lives three directories below hw/.
        footprint_text = re.sub(r'(\(model ")[^"]*/([^/"]+)(")',
                                r'\1${KIPRJMOD}/../../../parts/blind-encoder/blind-encoder.3dshapes/\2\3',
                                footprint_text)
        # Generic geometry is shared by multiple exact parts. Keep identity in
        # the atomic wrapper, not an EasyEDA supplier tag overwritten by import.
        footprint_text = re.sub(r'\t\(property "LCSC Part".*?\n\t\)\n', '', footprint_text, flags=re.S)
        (ROOT / (footprint + ".kicad_mod")).write_text(footprint_text)
        pins = []
        for unit in children(sym, "symbol"):
            for pin in children(unit, "pin"):
                label = children(pin, "name")[0][1]
                number = children(pin, "number")[0][1]
                label = PIN_NAMES.get(name, {}).get(number, re.sub(r"[^a-zA-Z0-9_]", "_", label))
                children(pin, "name")[0][1] = label
                pins.append((label, number))
        (ROOT / (stem + ".kicad_sym")).write_text(sx.dumps([lib[0], *lib[1:3], sym]) + "\n")
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
