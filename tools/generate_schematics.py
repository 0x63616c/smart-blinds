#!/usr/bin/env python3
"""Render a native schematic from an atopile board graph and reviewed page layout.

The PCB graph owns connectivity; the JSON owns drawing placement and readable names.
KiCad's separately exported netlist must reproduce EVERY physical pad connection.
No electrical connectivity is inferred from component positions or screenshots.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET

from kicad_sexpr import Atom, children, dumps, node as n, one, parse, walk

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.UUID("c325696b-b4f0-4d7d-bc27-ff0d1fa9d1bc")


def uid(key):
    return str(uuid.uuid5(NAMESPACE, key))


def fx(size=1.27, *extra):
    return n("effects", n("font", n("size", size, size)), *extra)


def xy(x, y):
    return n("at", round(x, 4), round(y, 4), 0)


def prop(key, value, x, y, hidden=False, angle=0):
    return n("property", key, value, n("at", x, y, angle), fx(1.27, *([n("hide", Atom("yes"))] if hidden else [])))


def board_graph(path):
    pcb = parse(path.read_text())
    result = {}
    for fp in children(pcb, "footprint"):
        properties = {p[1]: p[2] for p in children(fp, "property")}
        attributes = {str(a) for row in children(fp, "attr") for a in row[1:]}
        if "board_only" in attributes:
            # Only explicitly mechanical, nonconductive mounting holes may be
            # absent from the circuit graph. Reject disguised electrical parts.
            pads = children(fp, "pad")
            if (properties.get("atopile_address") or not pads or
                not {"exclude_from_bom", "exclude_from_pos_files"} <= attributes or
                any(p[1] or p[2] != "np_thru_hole" or children(p, "net") for p in pads)):
                raise ValueError("Board-only feature is not an isolated mechanical hole")
            # NPTH alone is insufficient: a land larger than its drill still
            # flashes copper. Accept only the reviewed circular, copper-free
            # hole geometry, with no hidden copper graphics or local zones.
            for pad in pads:
                drill=one(pad,"drill");size=one(pad,"size")
                if (pad[3]!="circle" or len(drill)!=2 or len(size)!=3 or
                    not math.isfinite(float(drill[1])) or float(drill[1])<=0 or
                    any(float(v)!=float(drill[1]) for v in size[1:]) or
                    children(pad,"primitives") or children(pad,"offset") or
                    one(pad,"layers")[1:]!=["*.Cu","*.Mask"]):
                    raise ValueError("Board-only hole has unsupported or conductive pad geometry")
            for item in fp[2:]:
                if not isinstance(item,list) or not item or item[0]=="pad":continue
                if item[0]=="zone" or any(str(layer[1]).endswith(".Cu") for layer in children(item,"layer")):
                    raise ValueError("Board-only hole contains copper graphics or zones")
            continue
        ref = properties["Reference"]
        if ref in result:
            raise ValueError(f"Duplicate reference {ref}")
        pads = {}
        for pad in children(fp, "pad"):
            if not pad[1]:
                continue
            net = one(pad, "net")[2]
            if pad[1] in pads and pads[pad[1]] != net:
                raise ValueError(f"Inconsistent repeated pad {ref}.{pad[1]}")
            pads[pad[1]] = net
        result[ref] = dict(properties=properties, footprint=fp[1], pads=pads,
                           attributes=sorted(attributes))
    return result


def verify_netlist(graph, spec, path):
    """Check independently exported KiCad XML against every physical PCB pad."""
    nets = ET.parse(path).getroot().find("nets")
    actual = {}
    for net in nets:
        for pin in net.findall("node"):
            key = (pin.attrib["ref"], pin.attrib["pin"])
            if key in actual:
                raise ValueError(f"Duplicate exported pin {key}")
            actual[key] = net.attrib["name"].lstrip("/")
    expected = {(ref, pin): spec["net_names"][name] for ref, comp in graph.items() for pin, name in comp["pads"].items()}
    for ref, component in spec["components"].items():
        for number in component.get("no_connect", []):
            pin = (ref, number)
            # NC names are assigned by KiCad. Verify isolation on BOTH sides.
            pcb_name = graph[ref]["pads"][number]
            if sum(name == pcb_name for c in graph.values() for name in c["pads"].values()) != 1:
                raise ValueError(f"Intentional NC is connected in the PCB: {pin}")
            if pin not in actual or list(actual.values()).count(actual[pin]) != 1:
                raise ValueError(f"Intentional NC is not isolated in the schematic: {pin}")
            expected[pin] = actual[pin]
    if actual != expected:
        wrong = {str(k): {"pcb": expected.get(k), "schematic": actual.get(k)}
                 for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k)}
        raise ValueError(f"Schematic/PCB graph mismatch: {json.dumps(wrong, indent=2)}")
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--check", action="store_true", help="Require committed schematic to match generation")
    args = parser.parse_args()
    layout_path = args.layout.resolve()
    hashes = {}
    def read_source(path):
        data = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        return data.decode()
    spec = json.loads(read_source(layout_path))
    pcb_path = ROOT / spec["pcb"]
    output = ROOT / spec["output"]
    for p in (pcb_path, Path(__file__).resolve(), ROOT / "tools/kicad_sexpr.py"):
        read_source(p)
    graph = board_graph(pcb_path)
    if set(graph) != set(spec["components"]):
        raise ValueError("Page component set differs from PCB; update the drawing deliberately")
    if len(set(spec["net_names"].values())) != len(spec["net_names"]):
        raise ValueError("Readable net names must be unique")
    pcb_nets = {net for c in graph.values() for net in c["pads"].values()}
    if pcb_nets != set(spec["net_names"]):
        raise ValueError("Net-name map must cover exactly the PCB nets")
    root_id = uid(str(output.relative_to(ROOT)))
    project = output.stem
    lib = n("lib_symbols")
    paper = spec.get("paper", "A4")
    if paper not in ("A4", "A3"):
        raise ValueError("Use a reviewed A4 or A3 sheet layout")
    result = n("kicad_sch", n("version", 20250114), n("generator", "smart_blinds_schematic"),
               n("uuid", root_id), n("paper", paper),
               n("title_block", n("title", spec["title"]), n("rev", "BLOCK STUDY"),
                 n("comment", 1, "Not a complete controller; not for fabrication")), lib)
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
        if cfg.get("type") == "passive":
            symbol.extend([n("pin_names", n("offset", 0), Atom("hide")), n("pin_numbers", Atom("hide"))])
        lib.append(symbol)
        symbols[key] = (lib_id, pins)

    def wire(a, b, key):
        result.append(n("wire", n("pts", n("xy", *a), n("xy", *b)),
                        n("stroke", n("width", 0), n("type", Atom("default"))), n("uuid", uid(key))))

    def label(name, at, key, right=False):
        result.append(n("label", name, n("at", *at, 0), fx(1.0, n("justify", Atom("right" if right else "left"), Atom("bottom"))),
                        n("uuid", uid(key))))

    for ref, component in sorted(graph.items()):
        cfg = spec["components"][ref]
        if component["properties"]["Partnumber"] != cfg["mpn"]:
            raise ValueError(f"Part changed at {ref}: value/placement review required")
        lib_id, pins = symbols[cfg["symbol"]]
        if set(pins) != set(component["pads"]):
            raise ValueError(f"Symbol/PCB pad numbers differ for {ref}")
        x, y, angle = cfg["at"]
        tx, ty = cfg.get("text_offset", [0, -cfg.get("label_offset", 7.62)])
        inst = n("symbol", n("lib_id", lib_id), n("at", x, y, angle), n("unit", 1),
                 n("in_bom", Atom("yes")), n("on_board", Atom("yes")), n("dnp", Atom("no")),
                 n("uuid", uid(ref)),
                 prop("Reference", ref, x + tx, y + ty, angle=angle),
                 prop("Value", cfg["value"], x + tx, y + ty + 2.54, angle=angle),
                 prop("Footprint", component["footprint"], x, y, True),
                 prop("MPN", cfg["mpn"], x, y, True),
                 prop("LCSC", component["properties"]["LCSC"], x, y, True),
                 prop("atopile_address", component["properties"]["atopile_address"], x, y, True))
        inst.append(n("instances", n("project", project, n("path", "/" + root_id, n("reference", ref), n("unit", 1)))))
        theta = math.radians(angle)
        for number, pin in pins.items():
            inst.append(n("pin", number, n("uuid", uid(ref + ".pin." + number))))
            px, py, pa = map(float, one(pin, "at")[1:])
            point = (round(x + px * math.cos(theta) - py * math.sin(theta), 4),
                     round(y - px * math.sin(theta) - py * math.cos(theta), 4))
            key = ref + ".wire." + number
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
                        fx(text.get("size", 1.27), n("justify", Atom("left"))), n("uuid", uid(f"note{i}"))))
    result.append(n("sheet_instances", n("path", "/", n("page", "1"))))
    contents = dumps(result) + "\n"
    external_lib = copy.deepcopy(lib)
    external_lib[0] = Atom("kicad_symbol_lib")
    for sym in children(external_lib, "symbol"):
        sym[1] = sym[1].split(":", 1)[1]
    external_lib[1:1] = [n("version", 20241209), n("generator", "smart_blinds_schematic")]
    external_lib_text = dumps(external_lib) + "\n"
    sym_table = dumps(n("sym_lib_table", n("version", 7), n("lib", n("name", "SmartBlinds"),
                     n("type", "KiCad"), n("uri", "${KIPRJMOD}/SmartBlinds.kicad_sym"), n("options", ""), n("descr", "Reviewed electrical pin types")))) + "\n"
    footprint_table_path = pcb_path.parent / "fp-lib-table"
    fp_table = parse(read_source(footprint_table_path))
    used_libraries = {c["footprint"].split(":")[0] for c in graph.values()}
    footprint_dirs = {}
    for item in children(fp_table, "lib"):
        name = one(item, "name")[1]
        if name in used_libraries:
            directory = Path(one(item, "uri")[1].replace("${KIPRJMOD}", str(pcb_path.parent))).resolve()
            footprint_dirs[name] = directory
    if set(footprint_dirs) != used_libraries:
        raise ValueError("Footprint library table is incomplete")
    for c in graph.values():
        library, name = c["footprint"].split(":", 1)
        read_source(footprint_dirs[library] / (name + ".kicad_mod"))
    def footprint_table(base):
        table = n("fp_lib_table", n("version", 7))
        for name, directory in sorted(footprint_dirs.items()):
            table.append(n("lib", n("name", name), n("type", "KiCad"),
                           n("uri", "${KIPRJMOD}/" + os.path.relpath(directory, base)), n("options", ""), n("descr", "Project footprint")))
        return dumps(table) + "\n"
    generated = {output: contents, output.with_suffix(".kicad_pro"): "{}\n", output.parent / "SmartBlinds.kicad_sym": external_lib_text,
                 output.parent / "sym-lib-table": sym_table, output.parent / "fp-lib-table": footprint_table(output.parent)}
    cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"
    if args.check:
        for path, content in generated.items():
            if not path.exists() or path.read_text() != content:
                raise ValueError(f"Committed schematic/library is stale: {path.name}")
    with tempfile.TemporaryDirectory(prefix="smart-blinds-schematic-") as temp:
        tmp = Path(temp)
        schematic = tmp / output.name
        schematic.write_text(contents)
        schematic.with_suffix(".kicad_pro").write_text("{}\n")
        (tmp / "SmartBlinds.kicad_sym").write_text(external_lib_text)
        (tmp / "sym-lib-table").write_text(sym_table)
        (tmp / "fp-lib-table").write_text(footprint_table(tmp))
        def run(*command):
            subprocess.run([cli, *command], check=True, capture_output=True, text=True)
        run("sch", "export", "netlist", "--format", "kicadxml", "-o", str(tmp / "graph.xml"), str(schematic))
        connections = verify_netlist(graph, spec, tmp / "graph.xml")
        run("sch", "erc", "--format", "json", "-o", str(tmp / "erc.json"), str(schematic))
        erc = json.loads((tmp / "erc.json").read_text())
        violations = [v for sheet in erc.get("sheets", []) for v in sheet.get("violations", [])]
        counts = {}
        for item in violations:
            kind = item["type"]
            counts[kind] = counts.get(kind, 0) + 1
        # An isolated block has no external power source; do not add fake power flags
        # to obtain a green check. Record the exact reviewed boundary findings instead.
        if counts != spec["expected_erc_types"]:
            print(json.dumps(violations, indent=2))
            raise ValueError(f"ERC findings changed: {counts}")
        erc_items = {}
        for item in violations:
            erc_items.setdefault(item["type"], []).extend(i["description"] for i in item["items"])
        if {k: sorted(v) for k, v in erc_items.items()} != {k: sorted(v) for k, v in spec["expected_erc_items"].items()}:
            raise ValueError(f"ERC affected items changed: {erc_items}")
        for relative, sha in hashes.items():
            if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != sha:
                raise ValueError(f"Source changed during generation: {relative}")
        verification = {
            "status": "block_graph_verified_not_complete_controller",
            "pin_connections_checked": connections, "physical_components": len(graph),
            "erc_clean": not violations, "erc_findings": counts, "erc_affected_items": erc_items,
            "erc_scope": spec["erc_scope"],
            "source_sha256": dict(sorted(hashes.items())),
        }
        if not args.check:
            output.parent.mkdir(parents=True, exist_ok=True)
            for path, content in generated.items():
                path.write_text(content)
            output.with_suffix(".verification.json").write_text(json.dumps(verification, indent=2) + "\n")
        elif json.loads(output.with_suffix(".verification.json").read_text()) != verification:
            raise ValueError("Verification record is stale; regenerate it")
        print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
