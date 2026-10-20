#!/usr/bin/env python3
"""Compute a solid-model PETG mass budget from unchanged, checked CAD reports."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

CAD = Path(__file__).resolve().parent
REPO = CAD.parent
DENSITY = 1.27
DENSITY_SOURCE = "https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf"
PARTS = {
    "compact-direct": {name: 1 for name in (
        "rear_lower", "rear_upper", "front_lower", "front_upper", "bearing_block",
        "retainer", "wheel", "guard")},
    "retained-compact": {"backplate": 1, "cover": 1, "cassette_rear": 1,
        "cassette_front": 1, "cassette_spacer": 1, "controller_frame": 1,
        "controller_clip": 2, "button_plunger": 2, "button_face": 2, "button_guide": 1},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate(verify_stls=False):
    rows, evidence = [], {}
    for family, quantities in PARTS.items():
        report_path = CAD / "generated" / f"{family}-verification.json"
        report = json.loads(report_path.read_text())
        if not report.get("source_snapshot_verified_unchanged"):
            raise ValueError(f"Unverified source snapshot: {report_path}")
        for name, digest in report["source_sha256"].items():
            if sha(CAD / name) != digest:
                raise ValueError(f"CAD report is stale: {name}")
        meshes = {Path(mesh["file"]).stem: mesh for mesh in report["meshes"]}
        for name, quantity in quantities.items():
            mesh = meshes[name]
            if not mesh["closed_edge_mesh"] or mesh["connected_shells"] != 1:
                raise ValueError(f"Not a closed single print mesh: {name}")
            if verify_stls:
                path = CAD / mesh["file"]
                if sha(path) != mesh["sha256"] or path.stat().st_size != mesh["bytes"]:
                    raise ValueError(f"STL differs from checked report: {path}")
            volume = round(mesh["volume_cm3"] * quantity, 3)
            rows.append({"family": family, "part": name, "per_unit": quantity,
                         "for_eight": quantity * 8, "single_model_cm3": mesh["volume_cm3"],
                         "unit_model_cm3": volume, "unit_solid_petg_g": round(volume * DENSITY, 2),
                         "stl_sha256": mesh["sha256"]})
        evidence[report_path.relative_to(REPO).as_posix()] = sha(report_path)
    total_volume = round(sum(row["unit_model_cm3"] for row in rows), 3)
    return {
        "status": "Solid CAD material estimate; not a slicer prediction, purchase quantity or physical mass",
        "parts_per_unit": sum(row["per_unit"] for row in rows),
        "parts_for_eight": sum(row["for_eight"] for row in rows),
        "model_volume_cm3_per_unit": total_volume,
        "solid_petg_grams_per_unit": round(total_volume * DENSITY, 2),
        "solid_petg_kg_for_eight": round(total_volume * DENSITY * 8 / 1000, 3),
        "density_g_cm3": DENSITY,
        "density_source": DENSITY_SOURCE,
        "source_reports_sha256": evidence,
        "calculator_sha256": sha(Path(__file__)),
        "limits": ["Infill, perimeter settings, supports, brims, purge and failed prints change consumption.",
                   "Separate insulating sheets, cells, boards, purchased hardware and cables are excluded.",
                   "No filament price, machine time, print settings or structural qualification is inferred."],
        "parts": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-stls", action="store_true")
    args = parser.parse_args()
    result = calculate(args.verify_stls)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(result["parts"][0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["parts"])
    outputs = {
        REPO / "bom/mechanical-print-estimate.json": json.dumps(result, indent=2) + "\n",
        REPO / "bom/mechanical-print-volume.csv": stream.getvalue(),
    }
    for path, expected in outputs.items():
        if args.check:
            if path.read_bytes() != expected.encode():
                raise SystemExit(f"Stale print estimate: {path}")
        else:
            path.write_bytes(expected.encode())
    print(f"{result['parts_per_unit']} printed pieces per unit; {result['solid_petg_grams_per_unit']} g solid-model PETG; {result['solid_petg_kg_for_eight']} kg for eight, before slicer changes and waste.")


if __name__ == "__main__":
    main()
