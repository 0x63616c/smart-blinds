#!/usr/bin/env python3
"""Export/check the retained enclosure candidate; stdlib plus OpenSCAD."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
from pathlib import Path
import subprocess
import time

from build import inspect_stl

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source/compact_retained.scad"
PARTS = ["backplate", "cover", "cassette_rear", "cassette_front", "cassette_spacer",
         "controller_frame", "controller_clip", "button_plunger", "button_face", "button_guide"]
CHECKS = ["cassette_contents", "cassette_controller", "cassette_drive", "cassette_cover",
          "case_pillars_drive", "controller_cover", "controller_buttons", "controller_keys", "connector_frame", "connector_pcb", "rf_metal", "wiring_drive",
          "wiring_cover", "wiring_cassette", "wiring_pillars", "cassette_backplate",
          "mount_tool", "button_guides", "button_adjuster", "signal_header_buttons", "wiring_controller", "mount_head", "cleat_engagement", "service_drive", "service_controller", "connector_buttons", "signal_wires_switches"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output, part, preview=False, empty=False):
    command = ["openscad", "-o", str(output), "-D", f'part="{part}"']
    if preview:
        command += ["--preview", "--imgsize=1400,1200", "--projection=o", "--colorscheme=Tomorrow"]
        if part == "buttons":
            command += ["--camera=101.9,40,65,90,0,90,95"]
        elif part == "cleat_section":
            command += ["--camera=29.4,11.5,7.5,65,0,50,70"]
        else:
            command += ["--camera=0,0,0,22,0,25,500", "--autocenter", "--viewall"]
    elif output.suffix == ".stl":
        command += ["--export-format=binstl"]
    start = time.monotonic()
    result = subprocess.run(command + [str(SOURCE)], capture_output=True, text=True)
    if "ERROR:" in result.stderr or "WARNING:" in result.stderr:
        raise RuntimeError(f"{part}: {result.stderr}")
    if empty:
        if result.returncode and "Current top level object is empty" in result.stderr:
            output.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"Unexpected intersection or failed check {part}: {result.stderr}")
    elif result.returncode:
        raise RuntimeError(f"{part}: {result.stderr}")
    elapsed = round(time.monotonic() - start, 2)
    print(f"{part}: {'empty intersection' if empty else 'generated'} ({elapsed}s)", flush=True)
    return elapsed


def check_shared_interfaces():
    """Cross-check the PCB placement contract against the actual CAD declarations."""
    data = json.loads((ROOT / "parameters/retained-interfaces.json").read_text())
    prelude = SOURCE.read_text().split("case_screws=")[0]
    values = {k: float(v) for k,v in re.findall(r"(W|H|D|pcb_x|pcb_y|pcb_z|pcb_t|pcb_h|pcb_depth)=([0-9.]+);", prelude)}
    controller = data["controller"]
    assert [values[k] for k in ("W","H","D")] == [data["case"][k] for k in ("width","height","depth")]
    assert [values[k] for k in ("pcb_x","pcb_y","pcb_z")] == controller["global_pcb_origin_xyz"]
    assert [values[k] for k in ("pcb_t","pcb_h","pcb_depth")] == controller["board_size_xyz"]
    buttons = (ROOT / "source/retained_buttons.scad").read_text()
    setback = float(re.search(r"switch_setback=([0-9.]+);",buttons).group(1))
    tip = values["pcb_z"] + values["pcb_depth"] + .75 - setback
    assert abs(tip - controller["switch_tip_global_z"]) < 1e-9
    adjustment = controller["button_adjustment"]
    stroke_min, stroke_max = adjustment["switch_travel_manufacturer_range"]
    travel = adjustment["positive_stop_travel"]
    required = [round(tip + travel - stroke_max,6), round(tip + travel - stroke_min,6)]
    assert required == adjustment["expected_first_closure_setting_global_z"]
    low,high = adjustment["screw_tip_adjustment_global_z"]
    assert low <= required[0] <= required[1] <= high
    # Attachment declarations drive the geometry, rather than merely documenting it.
    source = SOURCE.read_text()
    def declaration(name):
        match = re.search(r"\b" + re.escape(name) + r"=(\[[^;]+\]|[0-9.]+);", source)
        assert match, f"Missing CAD attachment declaration: {name}"
        return json.loads(match.group(1))
    mount = data["cassette_attachment"]
    assert declaration("pack_cleats") == mount["cleat_centres_global_xy"]
    assert declaration("pack_mounts") == [mount["screw_global_xy"]]
    assert declaration("cleat_stem") == mount["cleat_stem_xyz"]
    head = declaration("cleat_head")
    assert head == mount["cleat_head_xyz"]
    head_z = declaration("cleat_head_z")
    assert head_z == mount["cleat_head_global_z"]
    assert abs(head_z[1] - head_z[0] - head[2]) < 1e-9
    assert declaration("catch_floor_z") == mount["catch_floor_global_z"]
    assert declaration("pocket_roof_z") == mount["pocket_roof_global_z"]
    assert declaration("mount_tool_d") == mount["driver_corridor_diameter"]
    assert [0,declaration("service_slide"),0] == mount["disengage_translation_xyz"]
    assert [0,0,declaration("service_forward")] == mount["withdraw_translation_xyz"]
    overlap = round((head[0] - declaration("pocket_slot_width"))/2,6)
    capture = round(declaration("pack_cleats")[0][1] + head[1]/2 - declaration("pocket_entry_y")[1],6)
    assert overlap == mount["capture_per_side_x"]
    assert capture == mount["capture_length_y"]
    header = controller["header_reservation"]
    assert declaration("pack_header_origin") == header["footprint_origin_global_xyz"]
    assert [round(header["footprint_origin_global_xyz"][2]-values["pcb_z"],6),
            round(header["footprint_origin_global_xyz"][1]-values["pcb_y"],6)] == header["footprint_origin_local_uv"]
    wire = controller["protected_harness"]
    assert declaration("pack_free_y") == wire["wire_free_interval_global_y"]
    assert abs(wire["wire_free_interval_global_y"][0]-header["wire_exit_global_y"]) < 1e-9
    assert abs(wire["wire_free_interval_global_y"][1]-wire["wire_free_interval_global_y"][0]-wire["free_wire_length_after_housing"]) < 1e-9
    assert declaration("pack_bend_centre") == wire["bend_centre_global_xy"]
    assert declaration("pack_bend_r") == wire["bend_radius_nominal"]
    assert abs(wire["bend_centre_global_xy"][1]+wire["bend_radius_nominal"]-wire["cassette_port_global_y"]) < 1e-9
    encoder = controller["encoder_connector"]["cable_transition"]
    assert declaration("encoder_transition_y") == encoder["global_y"]
    assert declaration("encoder_bundle") == encoder["bundle_square_side"]
    assert declaration("encoder_board_corridor") == encoder["board_corridor_local_uv"]
    extent = round(encoder["global_y"] - values["pcb_y"] + encoder["bundle_square_side"]/2,6)
    assert extent == encoder["upper_v_extent_actual"]
    assert abs(extent+encoder["upper_v_allowance"]-encoder["board_corridor_local_uv"][3]) < 1e-9
    overboard = controller["encoder_connector"]["over_board_wire_constraint"]
    assert abs(overboard["nearest_wire_x"]-overboard["component_face_x"]-overboard["clearance"]-overboard["maximum_mounted_component_height"]) < 1e-9
    assert overboard["local_uv"] == [51,42.4,54,extent]
    assert overboard["global_wire_box_min"][0] == overboard["nearest_wire_x"]
    return {"cad_and_pcb_contract_match": True,
            "attachment_geometry_declarations_match": True,
            "header_and_encoder_route_declarations_match": True,
            "cleat_nominal_capture_mm": {"per_side_x": overlap, "length_y": capture},
            "button_first_closure_setting_z_mm": required,
            "limit": "Dimensional contract only; actuation, tolerance, retention loads, creep and print qualification are separate."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--intersections", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if args.jobs < 1 or args.jobs > 4:
        parser.error("--jobs must be 1..4")
    started = time.monotonic()
    inputs = [SOURCE, ROOT / "source/compact_direct.scad", ROOT / "source/compact_buttons.scad", ROOT / "source/retained_buttons.scad",
              Path(__file__).resolve(), ROOT / "build.py", ROOT / "parameters/retained-interfaces.json"]
    snapshot = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    output = ROOT / "exports/retained-compact-fit"
    generated = ROOT / "generated"
    output.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    evidence = {
        "status": "Retained enclosure fit candidate; no physical qualification or fabrication release",
        "shared_interface_check": check_shared_interfaces(),
        "source_sha256": snapshot,
        "case_mm": [115, 174, 71],
        "maximum_projection_at_buttons_mm": 72.2,
        "carrier_outline_mm": [86, 104, 1.6],
        "carrier_holes_local_mm": [[4, 4], [82, 4], [4, 100], [82, 100]],
        "cassette_closure": "Four M3x60 closure screws; two integral cleats and one separate M3x6 mounting screw",
        "cassette_mount_driver_corridor_diameter_mm": 8,
        "cassette_disengagement_slide_mm": 2.5,
        "cassette_forward_service_sweep_mm": 72,
        "controller_component_height_reservation_mm": 9,
        "controller_outline_mm": [54, 68.5, 1.6],
        "controller_local_mapping": "u=global Z-8; v=global Y-3",
        "protected_harness": {
            "controller_header": "Molex430450600 with430250600 housing",
            "cassette_pigtail": "Molex2147561061,150mm,18AWGUL1061",
            "wire_diameter_maximum_mm": 1.85,
            "relaxed_wire_length_mm": 12.7,
            "mated_latch_height_reservation_mm": 11.35,
            "pcb_component_face_global_x_mm": 100.6,
            "remaining_straight_wall_clearance_mm": .65,
            "retention": "Two cable ties on integral cassette lid bars; qualification pending",
            "internal_termination": "Actual carrier pads now placed; final internal wire fan and strain retention remain qualification/design work"
        },
        "adjustable_buttons": {
            "screw": "M2x6 socket head, captive M2 nut plus separate M2 jam nut",
            "switch_tip_z_mm": 62.45,
            "positive_stop_travel_mm": .4,
            "screw_tip_adjustment_z_mm": [62.5,62.9],
            "expected_first_closure_setting_z_mm": [62.55,62.75],
            "setting": "First electrical closure at positive stop; verify release, jam locking and repeated operation. No maximum overtravel is assumed.",
            "released_state": "No intended preload; switch return must overcome guide friction. Cap can float within positive free gap."
        },
        "motor_inline": {"family_envelope_mm":[25.5,8.5,11.2],"primary_mated_length_mm":24.77,
                         "relaxed_wire_each_end_mm":12.7,"retention":"Two ties to raised cassette tray; cable male ear variant and pull/bend qualification open"},
        "nominal_intersections": [], "meshes": [], "artifacts": [],
    }
    if args.intersections:
        def check(name):
            seconds = run(output / f"collision-{name}.stl", "collision_" + name, empty=True)
            return {"pair": name, "intersection": "empty", "seconds": seconds}
        outcomes = {}
        failures = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(check, name): name for name in CHECKS}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    outcomes[name] = future.result()
                except Exception as error:
                    failures.append(f"{name}: {error}")
                    print(f"FAILED {name}: {error}", flush=True)
        if failures:
            raise RuntimeError("Named intersection failures:\n" + "\n".join(failures))
        evidence["nominal_intersections"] = [outcomes[name] for name in CHECKS]
        checks_dir = output / "checks"
        checks_dir.mkdir(exist_ok=True)
        capture_file = checks_dir / "capture-engaged.stl"
        run(capture_file, "capture_engaged")
        capture = inspect_stl(capture_file)
        if not capture["closed_edge_mesh"] or capture["volume_cm3"] < .009:
            raise RuntimeError(f"Cleat positive capture control failed: {capture}")
        evidence["cleat_positive_capture"] = {
            "condition": "Cassette lifted 1 mm forwards without the 2.5 mm release slide",
            "result": "Geometric interference with the two cleat heads, as intended",
            "mesh": capture,
            "limit": "Shows geometric capture only, not load capacity, creep or print tolerance."
        }
    if args.export:
        def export(name):
            path = output / f"{name}.stl"
            seconds = run(path, name)
            mesh = inspect_stl(path)
            mesh["seconds"] = seconds
            if not mesh["closed_edge_mesh"] or mesh["connected_shells"] != 1 or mesh["bounds_mm"][0][2] < -.01:
                raise RuntimeError(f"Invalid single print mesh: {mesh}")
            return mesh
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            evidence["meshes"] = list(pool.map(export, PARTS))
        barrier = output / "barrier-outline.dxf"
        run(barrier, "barrier_outline")
        evidence["artifacts"].append({"file": barrier.relative_to(ROOT).as_posix(),
                                      "sha256": sha(barrier), "bytes": barrier.stat().st_size,
                                      "purpose": "Cutting outline for separately specified 1 mm insulating sheet"})
    if args.render:
        for name in ["assembly", "closed", "exploded", "cassette", "buttons", "cleat_section"]:
            run(generated / f"retained-compact-{name}.png", name, preview=True)
    if snapshot != {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}:
        raise RuntimeError("Sources changed during build; evidence not published")
    evidence["source_snapshot_verified_unchanged"] = True
    evidence["build_elapsed_seconds"] = round(time.monotonic() - started,2)
    evidence["limits"] = [
        "Named nominal static intersections plus conservative continuous service envelopes are checked; no tolerance or structural analysis.",
        "Service drive/controller tests expand closed-cassette bounds through the 2.5 mm rise and 72 mm forward removal, including boards/cells, lid and inline tray/housing. Cable manipulation is excluded.",
        "Cleat/backplate engagement uses 12 sampled actual rear-tray positions, not a continuous pocket sweep. The central washer pocket is elongated for the 2.5 mm rise.",
        "The motor rear cable allocation is excluded from the wire/drive test because the wire intentionally enters it.",
        "The cassette/contents test excludes intended PCB face seating planes with 0.02 mm contact bands.",
        "The cassette/backplate test excludes the intended Z3 seating plane with a 0.02 mm contact band.",
        "Controller-key interference checks the PCB interior, excluding its intended face-contact planes by 0.01 mm each.",
        "The motor still carries radial load; its +7 mm shaft-offset fit and guard are provisional.",
        "The 71 mm version requires inspected holder tail-and-fillet protrusion <=1.5 mm; untrimmed retained case not implemented.",
        "Carrier and controller volumes are allocations, not actual routed board geometry.",
        "Controller connector envelope and relaxed pigtail route are modeled; actual harness, latch/finger access and cable manipulation remain unqualified.",
        "Protected carrier pads and controller ports are placed; internal pack wire fan, exact inline motor cable variant, signal retention and home-sensor mount are unfinished.",
        "Button test samples nominal near-stop geometry, not a continuous tolerance sweep; actuation margin, return friction and locking require qualification.",
        "Wall anchors, electrical insulation, cell-holder polarity/current/fastening, switch actuation, thermal and printed strength need qualification.",
    ]
    temporary = generated / "retained-compact-verification.json.tmp"
    temporary.write_text(json.dumps(evidence, indent=2) + "\n")
    temporary.replace(generated / "retained-compact-verification.json")
    print("Retained enclosure source evidence published; no physical validation claimed.")


if __name__ == "__main__":
    main()
