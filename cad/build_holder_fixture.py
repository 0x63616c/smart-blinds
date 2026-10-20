#!/usr/bin/env python3
"""Export a reusable holder-service fixture candidate, with source-bound checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from build import inspect_stl

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source/holder_service_fixture.scad"
PARTS = ("base", "lower_comb", "upper_comb")
CHECKS = ("holders", "pcb", "tails")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    inputs = [SOURCE, ROOT / "source/compact_direct.scad", ROOT / "source/compact_buttons.scad", ROOT / "parameters/retained-interfaces.json",
              Path(__file__).resolve(), ROOT / "build.py"]
    snapshot = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    interfaces = json.loads((ROOT / "parameters/retained-interfaces.json").read_text())
    source_text = SOURCE.read_text()
    def declaration(name):
        match = re.search(r"\b" + re.escape(name) + r"=(\[[^;]+\]|[0-9.]+);", source_text)
        assert match, f"Missing fixture declaration: {name}"
        return json.loads(match.group(1))
    lands = interfaces["carrier"]["service_fixture_backing"]["local_rectangles_xy"]
    assert declaration("backing_lands") == lands
    assert declaration("pcb_size")[:2] == interfaces["carrier"]["outline"]
    assert declaration("pcb_size")[2] == interfaces["carrier"]["thickness"]
    assert declaration("holder_rim_height") == interfaces["holder_body_capture"]["modeled_rim_upper_height"]
    assert declaration("contact_gap") == interfaces["holder_body_capture"]["independent_contact_gap"]
    output = ROOT / "exports/holder-service-fixture"
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "Reusable workshop fixture candidate; no fit/load/insertion qualification",
              "source_sha256": snapshot, "shared_interface_check": "Backing lands, board size and rim/gap declarations match the shared JSON", "installed_parts_added": 0,
              "workshop_printed_parts": 3, "workshop_hardware": "Four M3x30 socket screws and four M3 nuts",
              "backing_lands_local_xy": lands,
              "default_contact_gap_over_upper_rim_envelope_mm": .2,
              "default_maximum_gap_over_lower_drawing_rim_mm": 1.2,
              "nominal_intersections": [], "meshes": [],
              "limits": ["The default gap gives capture, not preload or verified solder unloading.",
                         "Actual holder rim/seat, cell insertion trajectory, force and fixture stiffness require qualification.",
                         "Backing lands require electrical reservation against exposed pads, vias and tails before routing.",
                         "Future fixture use requires a fitted contact setting and depowered pack service procedure."]}

    def run(part, empty=False, preview=False):
        path = ROOT / "generated/holder-service-fixture.png" if preview else output / (part + ".stl")
        cmd = ["openscad", "-o", str(path), "-D", f'part="{part}"']
        if preview:
            cmd += ["--preview", "--imgsize=1400,1000", "--projection=o", "--colorscheme=Tomorrow",
                    "--camera=0,0,0,30,0,20,350", "--autocenter", "--viewall"]
        else:
            cmd += ["--export-format=binstl"]
        started = time.monotonic()
        result = subprocess.run(cmd + [str(SOURCE)], capture_output=True, text=True)
        if "ERROR:" in result.stderr or "WARNING:" in result.stderr:
            raise RuntimeError(f"{part}: {result.stderr}")
        if empty:
            if not result.returncode or "Current top level object is empty" not in result.stderr:
                raise RuntimeError(f"Unexpected intersection: {part}: {result.stderr}")
            path.unlink(missing_ok=True)
        elif result.returncode:
            raise RuntimeError(f"{part}: {result.stderr}")
        print(f"{part}: {'empty' if empty else 'generated'} ({time.monotonic()-started:.2f}s)", flush=True)
        return path

    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(lambda p: run("collision_" + p, empty=True), CHECKS))
    report["nominal_intersections"] = [{"pair": p, "intersection": "empty"} for p in CHECKS]
    if args.export:
        with ThreadPoolExecutor(max_workers=3) as executor:
            paths = list(executor.map(run, PARTS))
        for path in paths:
            mesh = inspect_stl(path)
            if not mesh["closed_edge_mesh"] or mesh["connected_shells"] != 1 or mesh["bounds_mm"][0][2] < -.01:
                raise RuntimeError(f"Invalid print mesh: {mesh}")
            report["meshes"].append(mesh)
    if args.render:
        run("assembly", preview=True)
    if snapshot != {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}:
        raise RuntimeError("Fixture inputs changed during export; evidence not published")
    report["source_snapshot_verified_unchanged"] = True
    (ROOT / "generated/holder-service-fixture-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Fixture geometry checked; no physical qualification claimed.")


if __name__ == "__main__":
    main()
