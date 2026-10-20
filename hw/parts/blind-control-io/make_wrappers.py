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
    "0402WGF4701TCE": ("UNI-ROYAL", "C25900", "R"),
    "0402WGF1003TCE": ("UNI-ROYAL", "C25741", "R"),
    "0402WGF1001TCE": ("UNI-ROYAL", "C11702", "R"),
    "CL21A226MAQNNNE": ("SAMSUNG", "C45783", "C"),
    "CL05A105KA5NQNC": ("SAMSUNG", "C52923", "C"),
    "SN74LVC2G17DCKR": ("Texas Instruments", "C50714", "U"),
    "TS-1088-AR02016": ("XUNPU", "C720477", "SW"),
    "0402WGF220JTCE": ("UNI-ROYAL", "C25092", "R"),
    "TPD2E2U06DRLR": ("Texas Instruments", "C1972959", "D"),
}
PIN_NAMES = {
    "SN74LVC2G17DCKR": {"1": "A1", "2": "GND", "3": "A2", "4": "Y2", "5": "VCC", "6": "Y1"},
    "TPD2E2U06DRLR": {"1": "NC1", "2": "NC2", "3": "IO1", "4": "GND", "5": "IO2"},
}

def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

if __name__ == "__main__":
    lib = sx.loads((ROOT / "blind-control-io.kicad_sym").read_text())
    for sym in children(lib, "symbol"):
        name = sym[1]
        maker, code, prefix = PARTS[name]
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        classname = "Part_" + stem
        props = {p[1]: p[2] for p in children(sym, "property")}
        footprint = props["Footprint"].split(":", 1)[1]
        # atopile0.15 expects atomic footprint files beside their .ato source.
        footprint_source = ROOT / "blind-control-io.pretty" / (footprint + ".kicad_mod")
        footprint_text = footprint_source.read_text().replace('${KIPRJMOD}/hw/parts/', '${KIPRJMOD}/../../../parts/')
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
