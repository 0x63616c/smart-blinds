#!/usr/bin/env python3
"""Plot measured simulation outputs and explicitly assumed battery scenarios."""
import csv
import json
from pathlib import Path
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent / "results"
summary = json.loads((HERE / "summary.json").read_text())
motion_s = summary["battery_energy"]["planning_profile"]["total_moving_seconds_per_day"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8"})
fig, grid = plt.subplots(2, 2, figsize=(12, 8.6), layout="constrained")
axes = grid.ravel()
for name, label, color in [("no_clamp", "220 µF only", "#b83f36"),
                           ("clamp_nominal", "Ideal clamp, 0.5 A / 20 ms", "#156d63"),
                           ("clamp_stress", "Ideal clamp, 2 A / 100 ms", "#476a9e")]:
    with (HERE / (name + ".csv")).open() as source:
        rows = list(csv.DictReader(source))
    axes[0].plot([float(r["time_s"]) * 1000 for r in rows], [float(r["bus_v"]) for r in rows],
                 label=label, color=color, linewidth=1.7)
axes[0].axhline(17, color="#555555", linewidth=0.8, linestyle="--", label="Logic buck 17 V operating limit")
axes[0].set(xlabel="Time (ms)", ylabel="Motor supply (V)", title="Battery disconnected during energy return")
axes[0].legend(fontsize=8, loc="upper right")
axes[0].grid(alpha=0.15)
for current, color in [(1, "#156d63"), (1.5, "#476a9e"), (2, "#b37b2d"), (3, "#b83f36")]:
    rows = [r for r in summary["battery_energy"]["scenarios"] if r["mean_pack_current_while_moving_a"] == current
            and r["total_moving_seconds_per_day"] == motion_s]
    axes[1].plot([r["pack_idle_ma"] for r in rows], [r["estimated_days"] for r in rows],
                 marker="o", markersize=3, color=color, label=f"{current:g} A while moving")
axes[1].axhspan(60, 90, color="#bbbb99", alpha=0.22, label="60–90 day goal")
axes[1].set(xlabel="Whole-device standby at battery (mA)", ylabel="Estimated days", title=f"Reported tallest blind, {motion_s:g} s motion/day")
axes[1].set_ylim(0, 105)
axes[1].legend(fontsize=8)
axes[1].grid(alpha=0.15)
for current, color in [(0.5, "#156d63"), (1, "#476a9e"), (1.5, "#b37b2d"), (3, "#b83f36")]:
    rows = [r for r in summary["battery_energy"]["scenarios"] if r["mean_pack_current_while_moving_a"] == current
            and r["pack_idle_ma"] == 0.5]
    axes[2].plot([r["total_moving_seconds_per_day"] for r in rows], [r["estimated_days"] for r in rows],
                 marker="o", markersize=3, color=color, label=f"{current:g} A while moving")
axes[2].axhspan(60, 90, color="#bbbb99", alpha=0.22)
axes[2].axvline(motion_s, color="#555555", linewidth=0.8, linestyle="--")
axes[2].set(xlabel="Total motion per day (s)", ylabel="Estimated days", title="Motion-duration sweep; assumed standby 0.5 mA", ylim=(0, 300))
axes[2].legend(fontsize=8)
axes[2].grid(alpha=0.15)
for days, color in [(60, "#156d63"), (90, "#476a9e")]:
    rows = [r for r in summary["battery_energy"]["allowable_mean_motion_current_at_planning_duration"] if r["target_days"] == days]
    axes[3].plot([r["pack_idle_ma"] for r in rows], [r["mean_motion_pack_current_limit_a"] for r in rows],
                 color=color, label=f"{days} days", marker="o", markersize=3)
axes[3].set(xlabel="Whole-device standby at battery (mA)", ylabel="Maximum mean motion current (A)",
            title=f"Current budget at {motion_s:g} s/day", ylim=(0, 1.7))
axes[3].legend(fontsize=8)
axes[3].grid(alpha=0.15)
fig.suptitle("Architecture calculations — not a tested controller", fontsize=15, fontweight=700)
fig.supxlabel("Assumptions: 108 Wh nominal, 80% usable, 10.8 V mean, 3048 mm travel at 20 mm/s and 40 mm/s².\nCurrent varies with speed/PWM; sweeps are scenarios, not measured motor performance. Clamp is ideal.", fontsize=9)
fig.savefig(HERE / "electrical-envelope.png", dpi=180)
fig.savefig(HERE / "electrical-envelope.svg")
svg_path = HERE / "electrical-envelope.svg"
svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n")
plt.close(fig)
