"""Narrow silkscreen edits for routed carriers; canonical footprints stay intact."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from kicad_sexpr import Atom, children, dumps, node, one, parse

# Preserve the original aliases. Only these routed projects use the derivatives.
LIBRARIES = {
    "blind-carrier": ("C0805", "FUSE-SMD_L6.1-W2.7",
                      "PDFN-8_L3.3-W3.3-P0.65-BL", "R0402", "R1206",
                      "R2512", "SOD-123_L2.8-W1.8-LS3.7-RD"),
    "blind-control-io": ("R0402",),
    "blind-power": ("R0402",),
    "blind-holders": ("BAT-TH_BH-21700-A5BJ001",),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_silk_graphics(value):
    """Retain text, electrical/mechanical geometry, models and all other fields."""
    if not isinstance(value, list):
        return value
    return [without_silk_graphics(v) for v in value
            if not (isinstance(v, list) and v and (
                v[0] == "uuid" or
                (v[0] in {"fp_line", "fp_circle", "fp_arc", "fp_rect", "fp_poly"}
                 and children(v, "layer") and one(v, "layer")[1] == "F.SilkS")))]


def finish_footprint(fp):
    before = without_silk_graphics(fp)
    name = fp[1].split(":")[-1]
    edits = 0
    for item in list(fp):
        if not isinstance(item, list) or not children(item, "layer"):
            continue
        if one(item, "layer")[1] != "F.SilkS":
            continue
        if (name == "FUSE-SMD_L6.1-W2.7" and item[0] == "fp_line"
                and one(item, "start")[1:] == ["4.06", "-1.4"]
                and one(item, "end")[1:] == ["4.06", "1.4"]):
            fp.remove(item)
            edits += 1
        elif (name == "BAT-TH_BH-21700-A5BJ001" and item[0] == "fp_line"
              and one(item, "start")[1:] == ["-41.5", "-12.5"]
              and one(item, "end")[1:] == ["41.5", "-12.5"]):
            one(item, "end")[1] = Atom("-40.25")
            right = copy.deepcopy(item)
            one(right, "start")[1] = Atom("-37.25")
            one(right, "end")[1] = Atom("41.5")
            # Libraries also need a unique ID; board generators re-key it later.
            for uid in children(right, "uuid"):
                right.remove(uid)
            right.append(node("uuid", str(uuid.uuid5(
                uuid.NAMESPACE_URL, "smart-blinds/holder-silk/right"))))
            fp.append(right)
            edits += 1
        elif (name in {"R0402", "R1206"} and item[0] == "fp_circle"
              and (one(item, "center")[1:], one(item, "end")[1:]) in (
                  (["-0.5", "0.25"], ["-0.47", "0.25"]),
                  (["-1.55", "0.79"], ["-1.52", "0.79"]))):
            fp.remove(item)
            edits += 1
        elif (name == "PDFN-8_L3.3-W3.3-P0.65-BL"
              and item[0] == "fp_line"
              and one(item, "start")[1:] in (
                  ["-1.65", "-1.65"], ["1.65", "-1.65"])
              and one(item, "end")[1:] ==
                  [one(item, "start")[1], "1.65"]):
            fp.remove(item)
            edits += 1
    assert without_silk_graphics(fp) == before, "Finish changed more than silk graphics"
    return edits


def finish_board(tree, expected_edits):
    before = without_silk_graphics(tree)
    edits = sum(finish_footprint(fp) for fp in children(tree, "footprint"))
    assert edits == expected_edits, (edits, expected_edits)
    assert without_silk_graphics(tree) == before


def library_contents(alias, name):
    source = ROOT / "hw/parts" / alias / (name + ".kicad_mod")
    # Both consuming routed boards live at the same depth. Models still come
    # from the original parts tree, never duplicated into this finish library.
    tree = parse(source.read_text().replace(
        "${KIPRJMOD}/../../../parts/", "${KIPRJMOD}/../../parts/"))
    finish_footprint(tree)
    return dumps(tree) + "\n"


def dependencies():
    paths = [Path(__file__), ROOT / "tools/kicad_sexpr.py"]
    for alias, names in LIBRARIES.items():
        for name in names:
            paths += [ROOT / "hw/parts" / alias / (name + ".kicad_mod"),
                      HERE / "footprints" / alias / (name + ".kicad_mod")]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def write_libraries():
    for alias, names in LIBRARIES.items():
        folder = HERE / "footprints" / alias
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / (name + ".kicad_mod")).write_text(library_contents(alias, name))


def write_table(source, project):
    table = parse(source.read_text())
    for lib in children(table, "lib"):
        alias = one(lib, "name")[1]
        folder = (HERE / "footprints" / alias if alias in LIBRARIES
                  else ROOT / "hw/parts" / Path(one(lib, "uri")[1]).name)
        one(lib, "uri")[1] = "${KIPRJMOD}/" + os.path.relpath(folder, project)
    (project / "fp-lib-table").write_text(dumps(table) + "\n")


def verify_libraries(project, source_table):
    for alias, names in LIBRARIES.items():
        folder = HERE / "footprints" / alias
        assert {p.stem for p in folder.glob("*.kicad_mod")} == set(names)
        for name in names:
            assert (folder / (name + ".kicad_mod")).read_text() == library_contents(alias, name)
    actual = parse((project / "fp-lib-table").read_text())
    original = parse(source_table.read_text())
    assert {one(x, "name")[1] for x in children(actual, "lib")} == {
        one(x, "name")[1] for x in children(original, "lib")}
    for lib in children(actual, "lib"):
        alias = one(lib, "name")[1]
        old = next(x for x in children(original, "lib") if one(x, "name")[1] == alias)
        expected = (HERE / "footprints" / alias if alias in LIBRARIES
                    else ROOT / "hw/parts" / Path(one(old, "uri")[1]).name)
        assert one(lib, "uri")[1] == "${KIPRJMOD}/" + os.path.relpath(expected, project)
    return dependencies()
