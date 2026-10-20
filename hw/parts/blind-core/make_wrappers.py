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
    "DRV8874PWPR": ("Texas Instruments", "C1855818", "U"),
    "BQ25798RQMR": ("Texas Instruments", "C2876593", "U"),
    "MAX17320G22+": ("Analog Devices", "C2914309", "U"),
    "ESP32-C6-WROOM-1-N4": ("Espressif", "C6034714", "U"),
    "TPS62902RPJR": ("Texas Instruments", "C2870154", "U"),
    "0402WGF1201TCE": ("UNI-ROYAL", "C25862", "R"),
    "0402B223K500NT": ("FH", "C1532", "C"),
    "UCM1E221MCL1GS": ("Nichicon", "C340768", "C"),
}
PIN_NAMES = {
    "MAX17320G22+": {"11": "PFAIL"},
    "BQ25798RQMR": {"6": "DP", "7": "DM", "12": "QON_n", "13": "CE_n", "21": "INT_n"},
    "ESP32-C6-WROOM-1-N4": {"2": "VDD3V3"},
}

def children(node, key):
    return [v for v in node if isinstance(v, list) and v and str(v[0]) == key]

if __name__ == "__main__":
    lib = sx.loads((ROOT / "blind-core.kicad_sym").read_text())
    for sym in children(lib, "symbol"):
        name = sym[1]
        maker, code, prefix = PARTS[name]
        stem = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        classname = "Part_" + stem
        props = {p[1]: p[2] for p in children(sym, "property")}
        footprint = props["Footprint"].split(":", 1)[1]
        # atopile0.15 expects atomic footprint files beside their .ato source.
        footprint_source = ROOT / "blind-core.pretty" / (footprint + ".kicad_mod")
        footprint_text = footprint_source.read_text().replace('${KIPRJMOD}/hw/parts/', '${KIPRJMOD}/../../../parts/')
        (ROOT / (footprint + ".kicad_mod")).write_text(footprint_text)
        if name == "UCM1E221MCL1GS":
            # Imported vertical pins face away from the capacitor body. Correct
            # drawing orientation without changing terminal numbers/positions.
            for unit in children(sym, "symbol"):
                for pin in children(unit, "pin"):
                    number = children(pin, "number")[0][1]
                    children(pin, "at")[0][3] = 270 if number == "1" else 90
                    children(pin, "length")[0][1] = 3.81
        (ROOT / (stem + ".kicad_sym")).write_text(sx.dumps([lib[0], *lib[1:3], sym]) + "\n")
        pins = []
        for unit in children(sym, "symbol"):
            for pin in children(unit, "pin"):
                label = children(pin, "name")[0][1]
                number = children(pin, "number")[0][1]
                label = PIN_NAMES.get(name, {}).get(number, re.sub(r"[^a-zA-Z0-9_]", "_", label))
                if name == "MAX17320G22+" and number == "11":
                    children(pin, "name")[0][1] = "PFAIL"
                pins.append((label, number))
        # Store corrected pin labels as well as wrapper aliases.
        if name == "MAX17320G22+":
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
