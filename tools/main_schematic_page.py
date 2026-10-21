"""Draw a hierarchical controller page with explicitly reviewed symbols and pin types.

Shares the primitive drawing conventions of the independently verified block renderer.
All connectivity comes from the compiled PCB, then a separate KiCad netlist is checked.
"""
import copy
import math
from generate_schematics import ROOT, fx, prop, uid, xy
from kicad_sexpr import Atom, children, node as n, one, parse, walk


def draw_page(spec, graph, read_source, project, root_id, instance_path, global_names):
    lib = n("lib_symbols")
    paper = spec.get("paper", "A4")
    if paper not in ("A4", "A3", "A2"):
        raise ValueError("Use a reviewed A4, A3 or A2 sheet layout")
    result = n("kicad_sch", n("version", 20250114), n("generator", "smart_blinds_schematic"),
               n("uuid", root_id), n("paper", paper),
               n("title_block", n("title", spec["title"]), n("rev", "STUDY"),
                 n("comment", 1, "Unrouted integrated circuit; not for fabrication")), lib)
    symbols = {}
    for key, cfg in spec["symbols"].items():
        source = ROOT / cfg["source"]
        container = parse(read_source(source))
        symbol = copy.deepcopy(next(s for s in children(container, "symbol") if s[1] == cfg["name"]))
        original = symbol[1]
        lib_id = "SmartBlinds:" + key
        symbol[1] = lib_id
        # Old imported libraries use obsolete property IDs. They add no semantics.
        for p in children(symbol, "property"):
            p[:] = [v for v in p if not (isinstance(v, list) and v[0] == "id")]
        pins = {}
        for sub in children(symbol, "symbol"):
            sub[1] = key + sub[1][len(original):]
        for pin in walk(symbol, "pin"):
            number = one(pin, "number")[1]
            pin_name = one(pin, "name")[1]
            if "pins" in cfg:
                reviewed = cfg["pins"][number]
                if pin_name != reviewed["name"]:
                    raise ValueError(f"Imported pin changed: {key}.{number} {pin_name}")
                pin[1] = Atom(reviewed["type"])
            else:
                if set(cfg) - {"source", "name", "type"} or cfg["type"] != "passive":
                    raise ValueError(f"Missing reviewed pin types for {key}")
                pin[1] = Atom("passive")
            pins[number] = pin
        if "pins" in cfg and set(cfg["pins"]) != set(pins):
            raise ValueError(f"Pin-type map differs from symbol {key}")
        if cfg.get("type") == "passive" and len(pins) == 2:
            symbol.extend([n("pin_names", n("offset", 0), Atom("hide")), n("pin_numbers", Atom("hide"))])
        lib.append(symbol)
        symbols[key] = (lib_id, pins)

    def wire(a, b, key):
        result.append(n("wire", n("pts", n("xy", *a), n("xy", *b)),
                        n("stroke", n("width", 0), n("type", Atom("default"))), n("uuid", uid(key))))

    def label(name, at, key, right=False):
        if name in global_names:
            result.append(n("global_label", name, n("shape", Atom("bidirectional")),
                n("at", *at, 180 if right else 0), fx(1.0, n("justify", Atom("right" if right else "left"))),
                n("uuid", uid(key))))
        else:
            result.append(n("label", name, n("at", *at, 0),
                fx(1.0, n("justify", Atom("right" if right else "left"), Atom("bottom"))),
                n("uuid", uid(key))))

    for ref, component in sorted(graph.items()):
        cfg = spec["components"][ref]
        if component["properties"].get("Partnumber", "") != cfg["mpn"]:
            raise ValueError(f"Part changed at {ref}: value/placement review required")
        lib_id, pins = symbols[cfg["symbol"]]
        if set(pins) != set(component["pads"]):
            raise ValueError(f"Symbol/PCB pad numbers differ for {ref}")
        x, y, angle = cfg["at"]
        tx, ty = cfg.get("text_offset", [0, -cfg.get("label_offset", 7.62)])
        inst = n("symbol", n("lib_id", lib_id), n("at", x, y, angle), n("unit", 1),
                 n("in_bom", Atom("no" if "exclude_from_bom" in component["attributes"] else "yes")), n("on_board", Atom("yes")), n("dnp", Atom("no")),
                 n("uuid", uid(project + "." + ref)),
                 prop("Reference", ref, x + tx, y + ty, angle=angle),
                 prop("Value", cfg["value"], x + tx, y + ty + 2.54, angle=angle),
                 prop("Footprint", component["footprint"], x, y, True),
                 prop("MPN", cfg["mpn"], x, y, True),
                 prop("LCSC", component["properties"].get("LCSC", ""), x, y, True),
                 prop("atopile_address", component["properties"]["atopile_address"], x, y, True))
        inst.append(n("instances", n("project", project, n("path", instance_path, n("reference", ref), n("unit", 1)))))
        theta = math.radians(angle)
        for number, pin in pins.items():
            inst.append(n("pin", number, n("uuid", uid(project + "." + ref + ".pin." + number))))
            px, py, pa = map(float, one(pin, "at")[1:])
            point = (round(x + px * math.cos(theta) - py * math.sin(theta), 4),
                     round(y - px * math.sin(theta) - py * math.cos(theta), 4))
            key = project + "." + ref + ".wire." + number
            if number in cfg.get("no_connect", []):
                result.append(n("no_connect", n("at", *point), n("uuid", uid(key))))
                continue
            # Extend outward from the pin and place the shared net label at the end.
            outward = math.radians(pa + angle + 180)
            end = (round(point[0] + 7.62 * math.cos(outward), 4),
                   round(point[1] - 7.62 * math.sin(outward), 4))
            wire(point, end, key)
            net_name = spec["net_names"][component["pads"][number]]
            label(net_name, end, key + ".label", end[0] < point[0] - 0.01)
        result.append(inst)

    for i, text in enumerate(spec["notes"]):
        result.append(n("text", text["text"], xy(*text["at"]),
                        fx(text.get("size", 1.27), n("justify", Atom("left"))), n("uuid", uid(root_id + f".note{i}"))))
    return result, lib
