#!/usr/bin/env python3
"""Check/export the reusable paired-loading workshop fixture; stdlib + OpenSCAD.

This checks geometry and source consistency, not battery assembly qualification.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

from build import inspect_stl
from build_retained import check_shared_interfaces

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source/holder_pair_fixture.scad"
PARTS = ("base", "lower_comb", "upper_comb", "lower_clamp", "upper_clamp", "cradle", "lower_pad", "upper_pad")
PAIRED_CHECKS = ("clear_base", "clear_catches", "load_retracted", "comb_contents", "parked_fixture", "parked_combs")
SINGLE_CHECKS = ("clamps_contents", "clamps_fixture", "clamps_parking", "cradle_contents", "primary_loading",
                 "paths_contents", "paths_fixture", "pad_travel", "rear_shell_fixture", "turn_bound")
CONTROLS = ("pad_hook_control", "pad_seat_control", "pad_head_control")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_contract():
    shared = check_shared_interfaces()
    data = json.loads((ROOT / "parameters/retained-interfaces.json").read_text())["paired_loading"]
    source = SOURCE.read_text()
    def declaration(name):
        found = re.search(r"\b" + re.escape(name) + r"=(\[[^;]+\]|-?[0-9.]+);", source)
        assert found, f"Missing fixture declaration: {name}"
        return json.loads(found.group(1))
    for name,key in (("fixture_base_size","workshop_base_size"), ("fixture_translation","fixture_translation_xyz"),
                     ("fixture_turn_axis","turn_axis_global_xyz"), ("fixture_turn_bounds","turn_bounds_global_xyz"),
                     ("fixture_turn_lift","turn_lift_before_rotation"), ("fixture_maximum_height","maximum_fixture_height"),
                     ("fixture_upper_approach_offset","upper_clamp_approach_x_offset"), ("fixture_pad_release","pressure_pad_release")):
        assert declaration(name) == data[key], name
    parking = data["protected_pigtail_parking"]
    assert declaration("fixture_parking_min") == parking["minimum_global_xyz"]
    assert declaration("fixture_parking_size") == parking["size_xyz"]
    assert data["workshop_printed_pieces"] == len(PARTS)
    # Conservative full X-Z box: a dedicated Boolean check confirms its contents.
    low,high = data["turn_bounds_global_xyz"]
    axis = data["turn_axis_global_xyz"]
    radius = max(math.hypot(x-axis[0],z-axis[2]) for x in (low[0],high[0]) for z in (low[2],high[2]))
    minimum = data["fixture_translation_xyz"][2]+axis[2]+data["turn_lift_before_rotation"]-radius
    gap = minimum-data["maximum_fixture_height"]
    assert gap > 10, f"Turn clearance lost: {gap}"
    return {"shared_interfaces":shared, "workshop_declarations_match":True}, {
        "scope":"Full-box rotation after straight lift; combs removed, rear tray clamped, primary row empty",
        "box_global_xyz":data["turn_bounds_global_xyz"], "axis_global_xyz":axis,
        "lift_before_turn_mm":data["turn_lift_before_rotation"], "radius_xz_mm":round(radius,4),
        "minimum_height_above_bench_mm":round(minimum,4), "maximum_fixture_height_mm":data["maximum_fixture_height"],
        "minimum_fixture_clearance_mm":round(gap,4),
        "limit":"Requires actual pigtail restraint inside this box; no loaded-handling or clamp-force qualification"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--intersections", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be 1..4")
    inputs = [SOURCE, ROOT / "source/compact_retained.scad", ROOT / "source/holder_pair_handling.scad",
              ROOT / "source/compact_direct.scad", ROOT / "source/compact_buttons.scad", ROOT / "source/retained_buttons.scad",
              ROOT / "parameters/retained-interfaces.json", Path(__file__).resolve(), ROOT / "build.py", ROOT / "build_retained.py"]
    snapshot = {p.relative_to(ROOT).as_posix():sha(p) for p in inputs}
    output = ROOT / "exports/holder-pair-fixture"
    generated = ROOT / "generated"
    output.mkdir(parents=True,exist_ok=True)
    generated.mkdir(parents=True,exist_ok=True)
    started = time.monotonic()
    contract,turn = check_contract()
    report = {"status":"Reusable workshop geometric candidate; not a released cell-loading procedure",
              "source_sha256":snapshot, "shared_interface_check":contract, "installed_parts_added":0,
              "workshop_printed_parts":8, "workshop_hardware":"Four M3x16 + two M3x10 socket screws; six M3 nuts",
              "scope":"One set shared across eight builds; not eight installed sets",
              "turn_envelope":turn, "nominal_intersections":[], "positive_controls":[], "meshes":[], "renders":[],
              "limits":["Protected pigtail parking is space-only; trim, installed fan and strain-free handling restraint are unfinished.",
                        "Cell insertion uses an assumed 3 mm axial movement / 20 degree tilt and 40 mm normal approach, not a manufacturer-specified path.",
                        "Four temporary catches require a practical retained or sequential release method; modeled simultaneous displacement is not an assembly demonstration.",
                        "Holder current/polarity/retention, solder load path, clamp pressure, print strength/creep and insulation require qualification.",
                        "Broad captive pads prevent modeled screw-tip contact with the tray; their head stops do not establish safe force or torque.",
                        "Wire and inspect both carriers empty; fixed raw links never open or unfold. Qualify sequence with surrogates before a separately reviewed cell-loading procedure."]}

    def run(part, flip=False, empty=False, preview=False):
        suffix = "-companion" if flip else ""
        path = generated / f"holder-pair-{part}.png" if preview else output / f"{part}{suffix}.stl"
        cmd = ["openscad", "-o", str(path), "-D", f'part="{part}"', "-D", f'flip={str(flip).lower()}']
        if preview:
            cmd += ["--preview", "--imgsize=1400,1200", "--projection=o", "--colorscheme=Tomorrow"]
            if part == "pad_detail":
                cmd += ["--camera=44.5,7,16,65,0,40,220"]
            else:
                cmd += ["--camera=0,0,0,30,0,25,400", "--autocenter", "--viewall"]
        else:
            cmd += ["--export-format=binstl"]
        begin = time.monotonic()
        result = subprocess.run(cmd+[str(SOURCE)],capture_output=True,text=True)
        if "ERROR:" in result.stderr or "WARNING:" in result.stderr:
            raise RuntimeError(f"{part}{suffix}: {result.stderr}")
        if empty:
            if not result.returncode or "Current top level object is empty" not in result.stderr:
                raise RuntimeError(f"Unexpected intersection: {part}{suffix}: {result.stderr}")
            path.unlink(missing_ok=True)
        elif result.returncode:
            raise RuntimeError(f"{part}{suffix}: {result.stderr}")
        seconds = round(time.monotonic()-begin,2)
        print(f"{part}{suffix}: {'empty' if empty else 'generated'} ({seconds}s)",flush=True)
        return path,seconds

    if args.intersections:
        tasks = [(p,flip) for p in PAIRED_CHECKS for flip in (False,True)]+[(p,False) for p in SINGLE_CHECKS]
        def check(task):
            name,flip = task
            _,seconds = run("collision_"+name,flip,empty=True)
            return {"pair":name,"companion_up":flip,"intersection":"empty","seconds":seconds}
        outcomes={};failures=[]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures={pool.submit(check,t):t for t in tasks}
            for f in as_completed(futures):
                task=futures[f]
                try:outcomes[task]=f.result()
                except Exception as error:
                    failures.append(str(error));print(f"FAILED {task}: {error}",flush=True)
        if failures:raise RuntimeError("Named workshop checks failed:\n"+"\n".join(failures))
        report["nominal_intersections"]=[outcomes[t] for t in tasks]
        for name in CONTROLS:
            path,seconds=run(name)
            mesh=inspect_stl(path)
            # Head-stop witness is only 0.01 mm thick; rounded cm3 can be zero.
            bounds=mesh["bounds_mm"]
            if not mesh["closed_edge_mesh"] or any(b<=a for a,b in zip(bounds[0],bounds[1])):
                raise RuntimeError(f"Positive pad control failed: {mesh}")
            report["positive_controls"].append({"name":name,"mesh":mesh,"seconds":seconds,
                "limit":"Geometric retention/contact witness only; no load capacity"})
    if args.export:
        def export(name):
            path,seconds=run(name)
            mesh=inspect_stl(path);mesh["seconds"]=seconds
            if not mesh["closed_edge_mesh"] or mesh["connected_shells"]!=1 or mesh["bounds_mm"][0][2]<-.01:
                raise RuntimeError(f"Invalid single print mesh: {mesh}")
            return mesh
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            report["meshes"]=list(pool.map(export,PARTS))
    if args.render:
        for name in ("open","assembly","tray_stage","pad_detail"):
            path,seconds=run(name,preview=True)
            report["renders"].append({"file":path.relative_to(ROOT).as_posix(),"sha256":sha(path),"bytes":path.stat().st_size,"seconds":seconds})
    if snapshot!={p.relative_to(ROOT).as_posix():sha(p) for p in inputs}:
        raise RuntimeError("Workshop inputs changed; evidence not published")
    report["source_snapshot_verified_unchanged"]=True
    report["build_elapsed_seconds"]=round(time.monotonic()-started,2)
    temporary=generated/"holder-pair-fixture-verification.json.tmp"
    temporary.write_text(json.dumps(report,indent=2)+'\n')
    temporary.replace(generated/"holder-pair-fixture-verification.json")
    print("Paired workshop geometry evidence published; physical assembly remains unqualified.")


if __name__ == "__main__":
    main()
