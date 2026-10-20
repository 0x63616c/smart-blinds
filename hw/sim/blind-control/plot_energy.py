#!/usr/bin/env python3
"""Render fresh energy arithmetic, independent of cached SPICE results."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_checks import energy_budget


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    data = energy_budget()
    split = data["split_load_planning"]
    rows = split["additional_service_sensitivity"]
    assumptions = data["planning_profile"]["split_load_energy"]
    period = assumptions["additional_service_period_s"]
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "smart-blinds-energy",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    })
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    labels = [f'{r["additional_service_duration_ms"]:g} ms' for r in rows]
    lower = [0.0] * len(rows)
    for key, label, color in (
        ("motor_wh_per_day", "Motor branch", "#156d63"),
        ("idle_wh_per_day", "Whole-device idle", "#b8c5bd"),
        ("awake_logic_wh_per_day", "Awake logic, including service", "#c3853e"),
    ):
        values = [r[key] for r in rows]
        left.bar(labels, values, bottom=lower, label=label, color=color, width=0.65)
        lower = [a + b for a, b in zip(lower, values)]
    left.axhline(data["usable_wh_assumption"] / 60, color="#476a9e", linestyle="--", label="60-day energy allowance")
    left.set(title="Daily energy", ylabel="Wh per day", xlabel=f"Extra awake service in each {period:g}-second idle period")
    left.legend(fontsize=8, loc="upper left")
    left.set_ylim(0, max(lower) * 1.42)
    right.plot([r["additional_service_duration_ms"] for r in rows],
               [r["estimated_days"] for r in rows], color="#156d63", marker="o")
    right.axhline(60, color="#476a9e", linestyle="--", label="60-day target")
    right.set(title="Estimated battery life", xlabel=f"Extra awake service per {period:g}-second idle period (ms)",
              ylabel="Days", ylim=(0, 68))
    for row in (rows[0], rows[-2], rows[-1]):
        ms = row["additional_service_duration_ms"]
        right.annotate(f'{row["estimated_days"]:.1f}', (ms, row["estimated_days"]),
                       xytext=(6 if row is not rows[-1] else -30, -17), textcoords="offset points")
    right.legend(fontsize=8, loc="lower left")
    for axis in (left, right):
        axis.grid(axis="y", alpha=0.15)
        axis.set_axisbelow(True)
    fig.suptitle("Frequent wake-ups consume the battery budget", fontsize=17, fontweight="bold")
    baseline = split["baseline"]
    fig.supxlabel(
        f"Planning scenarios only: {data['usable_wh_assumption']:g} Wh usable; "
        f"{baseline['motion_seconds_per_day']:g} s/day moving at {baseline['motor_branch_average_a']:g} A motor branch.\n"
        f"{baseline['awake_logic_rail_ma']:g} mA awake logic at {assumptions['awake_logic_rail_v']:g} V / "
        f"{baseline['awake_conversion_efficiency']:.0%} conversion; "
        f"{baseline['preflight_seconds_per_day']:g} s/day preflight; "
        f"{baseline['idle_total_pack_ma']:g} mA total pack idle. Extra wakes replace idle time.\n"
        "Set extra service time to zero when already included in measured idle. Actual currents and wake times are unmeasured.",
        fontsize=9,
    )
    fig.savefig(destination / "energy.png", dpi=160)
    fig.savefig(destination / "energy.svg", metadata={"Date": None})
    plt.close(fig)
    (destination / "energy.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    render(parser.parse_args().output_dir)
