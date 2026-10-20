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
    "TPS3430WDRCR": ("Texas Instruments", "C2870545", "U"),
    "TPS3808G33DBVR": ("Texas Instruments", "C43698", "U"),
    "SN74LVC1G97DCKR": ("Texas Instruments", "C30743", "U"),
    "SN74AUP1G97DCKR": ("Texas Instruments", "C2682139", "U"),
    "CL05C121JB5NNNC": ("SAMSUNG", "C307442", "C"),
}
PIN_NAMES = {
    "TPS3430WDRCR": {"1":"VDD1", "2":"CWD", "3":"SET0", "4":"CRST", "5":"GND", "6":"SET1", "7":"WDI", "8":"WDO", "9":"NC", "10":"VDD2", "11":"EP"},
    "TPS3808G33DBVR": {"1":"RESET", "2":"GND", "3":"MR", "4":"CT", "5":"SENSE", "6":"VDD"},
    "SN74AUP1G97DCKR": {"1":"IN1", "2":"GND", "3":"IN0", "4":"Y", "5":"VCC", "6":"IN2"},
    "SN74LVC1G97DCKR": {"1":"IN1", "2":"GND", "3":"IN0", "4":"Y", "5":"VCC", "6":"IN2"},
}

def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

if __name__ == "__main__":
    lib = sx.loads((ROOT / "blind-supervisor.kicad_sym").read_text())
    for sym in children(lib, "symbol"):
        name = sym[1]
        maker, code, prefix = PARTS[name]
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        classname = "Part_" + stem
        props = {p[1]: p[2] for p in children(sym, "property")}
        footprint = props["Footprint"].split(":", 1)[1]
        # atopile0.15 expects atomic footprint files beside their .ato source.
        footprint_source = ROOT / "blind-supervisor.pretty" / (footprint + ".kicad_mod")
        footprint_text = footprint_source.read_text().replace('${KIPRJMOD}/hw/parts/', '${KIPRJMOD}/../../../parts/')
        # The AUP import references a nonexistent model filename. Reuse the
        # downloaded nominal DCK/SC70-6 body as visual geometry only.
        footprint_text = footprint_text.replace("SC-70-6_L2.0-W1.3-H1.0-P0.65.wrl", "SC-70-6_L2.1-W1.3-H1.0-LS2.1-P0.65.wrl")
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
