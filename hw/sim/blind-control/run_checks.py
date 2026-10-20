#!/usr/bin/env python3
"""Run ngspice energy-envelope checks and a battery-life sensitivity calculation.

No vendor IC or actual motor is modeled by these checks. A passing bound applies
only to the stated stimulus and behavioural clamp. Do not relabel as board proof.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ROOT = HERE.parents[2]


def simulate(case):
    template = (HERE / "regen.cir.in").read_text()
    end = 0.01 + case["duration_s"]
    values = {"CAP_F": case["cap_f"], "ESR_OHM": case["esr_ohm"],
              "CURRENT_A": case["return_current_a"], "CLAMP_V": 13.6,
              "CLAMP_S": case["clamp_conductance_s"], "END_S": end,
              "END_RAMP_S": end + 0.00001, "STOP_S": end + 0.02}
    for key, value in values.items():
        template = template.replace("@" + key + "@", str(value))
    with tempfile.TemporaryDirectory(prefix="blind-regen-") as directory:
        folder = Path(directory)
        (folder / "test.cir").write_text(template)
        run = subprocess.run(["ngspice", "-n", "-b", "test.cir"], cwd=folder,
                             text=True, capture_output=True, timeout=60)
        log = run.stdout + run.stderr
        if run.returncode or "aborted" in log.lower() or "failed" in log.lower():
            raise RuntimeError(f"{case['name']}: simulation failed\n{log[-3000:]}")
        measures = {}
        for name in ("peak_bus", "clamp_energy"):
            match = re.search(r"^" + name + r"\s*=\s*([-+\deE.]+)", log, re.M)
            if not match:
                raise RuntimeError(f"{case['name']}: missing measure {name}")
            measures[name] = float(match.group(1))
        rows = (folder / "wave.txt").read_text().splitlines()
        with (RESULTS / (case["name"] + ".csv")).open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["time_s", "bus_v", "capacitor_v", "dump_current_a", "dump_power_w"])
            writer.writerows(line.split() for line in rows[1:])
        final_time = float(rows[-1].split()[0])
        if abs(final_time - values["STOP_S"]) > 1e-6:
            raise RuntimeError(f"{case['name']}: transient ended early")
    return dict(case, **measures, simulated_through_s=final_time)


def split_load_scenario(*, usable_wh, pack_v, motion_s, preflight_s, motor_a,
                        logic_v, awake_ma, efficiency, idle_ma,
                        service_period_s=3, service_duration_ms=0):
    """Partition one day; service awake time replaces, rather than adds to, idle."""
    values = (usable_wh, pack_v, motion_s, preflight_s, motor_a, logic_v,
              awake_ma, efficiency, idle_ma, service_period_s, service_duration_ms)
    if not all(math.isfinite(v) and v >= 0 for v in values):
        raise ValueError("Energy assumptions must be finite and nonnegative")
    if usable_wh == 0 or pack_v == 0 or not 0 < efficiency <= 1 or service_period_s == 0:
        raise ValueError("Positive capacity, voltage, period and valid efficiency required")
    if motion_s + preflight_s > 86400 or service_duration_ms > service_period_s * 1000:
        raise ValueError("Energy phases cannot exceed a day or a service period")
    stationary_s = 86400 - motion_s - preflight_s
    # Long-run duty fraction, not a prediction of the task's precise daily schedule.
    service_s = stationary_s * service_duration_ms / (1000 * service_period_s)
    awake_s = motion_s + preflight_s + service_s
    idle_s = stationary_s - service_s
    motor_wh = pack_v * motor_a * motion_s / 3600
    awake_wh = logic_v * awake_ma / 1000 / efficiency * awake_s / 3600
    idle_wh = pack_v * idle_ma / 1000 * idle_s / 3600
    daily_wh = motor_wh + awake_wh + idle_wh
    limits = []
    for target_days in (60, 90):
        available_wh = usable_wh / target_days - awake_wh - idle_wh
        limits.append({
            "target_days": target_days,
            "nonmotor_loads_fit_budget": available_wh >= 0,
            # None means there is no motion in this scenario, so no current limit.
            "maximum_motor_branch_average_a": (
                round(max(0, available_wh) / (pack_v * motion_s / 3600), 6)
                if motion_s else None),
        })
    return {
        "motor_branch_average_a": motor_a, "awake_logic_rail_ma": awake_ma,
        "awake_conversion_efficiency": efficiency, "idle_total_pack_ma": idle_ma,
        "additional_service_period_s": service_period_s,
        "additional_service_duration_ms": service_duration_ms,
        "motion_seconds_per_day": motion_s, "preflight_seconds_per_day": preflight_s,
        "additional_service_seconds_per_day": service_s,
        "awake_seconds_per_day": awake_s, "idle_seconds_per_day": idle_s,
        "motor_wh_per_day": motor_wh, "awake_logic_wh_per_day": awake_wh,
        "idle_wh_per_day": idle_wh, "daily_wh": daily_wh,
        "estimated_days": usable_wh / daily_wh if daily_wh else None,
        "motor_budget": limits,
    }


def energy_budget():
    # Deliberately separate arithmetic assumptions from measured energy.
    nominal_wh = 3 * 2 * 5.0 * 3.6
    usable_wh = nominal_wh * 0.80
    profile = json.loads((ROOT / "docs/electrical/planning-profile.json").read_text())
    measurements = json.loads((ROOT / "docs/measurements.json").read_text())
    distance = measurements["blind"]["max_travel_approx_mm"]
    speed = profile["fabric_speed_mm_s"]
    accel = profile["fabric_acceleration_mm_s2"]
    # Rest-to-rest trapezoid, or triangle when there is no cruise interval.
    one_way_s = (distance / speed + speed / accel if distance >= speed * speed / accel
                 else 2 * math.sqrt(distance / accel))
    nominal_motion_s = 2 * one_way_s * profile["full_open_close_cycles_per_day"]
    durations = sorted(set(profile["motion_duration_sensitivity_seconds_per_day"] + [nominal_motion_s]))
    rows = []
    for duration_s in durations:
        for idle_ma in (0.1, 0.5, 1, 3, 5):
            for motor_a in (0.5, 1, 1.5, 2, 3):
                moving_wh = 10.8 * motor_a * duration_s / 3600
                idle_wh = 10.8 * idle_ma / 1000 * (24 - duration_s / 3600)
                daily_wh = moving_wh + idle_wh
                rows.append({"pack_idle_ma": idle_ma, "mean_pack_current_while_moving_a": motor_a,
                             "total_moving_seconds_per_day": duration_s, "daily_wh": round(daily_wh, 4),
                             "estimated_days": round(usable_wh / daily_wh, 1)})
    speed_sweep = [{"fabric_speed_mm_s": value,
                    "total_moving_seconds_per_day": round(2 * (distance/value + value/accel), 2)}
                   for value in (10, 20, 30, 50)]
    max_motion_current = []
    for days in (60, 90):
        for idle_ma in (0.1, 0.5, 1, 3, 5):
            idle_wh = 10.8 * idle_ma / 1000 * (24 - nominal_motion_s / 3600)
            available_wh = usable_wh / days - idle_wh
            max_motion_current.append({"target_days": days, "pack_idle_ma": idle_ma,
                "mean_motion_pack_current_limit_a": round(max(0, available_wh) / (10.8 * nominal_motion_s / 3600), 3)})
    split = profile["split_load_energy"]
    split_args = dict(
        usable_wh=usable_wh, pack_v=10.8, motion_s=nominal_motion_s,
        preflight_s=split["preflight_seconds_per_day"],
        motor_a=split["motor_branch_average_a"], logic_v=split["awake_logic_rail_v"],
        awake_ma=split["awake_logic_rail_ma"],
        efficiency=split["awake_conversion_efficiency"], idle_ma=split["idle_total_pack_ma"],
        service_period_s=split["additional_service_period_s"],
    )
    return {"nominal_pack_wh": nominal_wh, "usable_wh_assumption": usable_wh,
            "nominal_cell_ah_assumption": 5, "usable_fraction_assumption": 0.8,
            "mean_pack_voltage_assumption": 10.8,
            "planning_profile": dict(profile, reported_travel_mm=distance,
                total_moving_seconds_per_day=nominal_motion_s),
            "speed_sensitivity_at_reported_travel": speed_sweep,
            "allowable_mean_motion_current_at_planning_duration": max_motion_current,
            "current_definition": "Whole-device pack current while moving; do not add active MCU/radio energy to these scenarios",
            "split_load_planning": {
                "current_definition": "Motor-branch battery-side current plus separate awake logic and whole-device idle; winding current is not pack current",
                "baseline": split_load_scenario(**split_args),
                "active_logic_sensitivity": [
                    split_load_scenario(**dict(split_args, awake_ma=ma))
                    for ma in split["awake_logic_rail_ma_sensitivity"]],
                "conversion_sensitivity": [
                    split_load_scenario(**dict(split_args, efficiency=efficiency))
                    for efficiency in split["awake_conversion_efficiency_sensitivity"]],
                "additional_service_sensitivity": [
                    split_load_scenario(**split_args, service_duration_ms=ms)
                    for ms in split["additional_service_duration_ms_sensitivity"]],
                "continuous_awake_stress": split_load_scenario(
                    **dict(split_args, service_period_s=0.1), service_duration_ms=100),
                "limits": [
                    "All state currents, wake durations and efficiencies are illustrative",
                    "Additional wakes displace idle; set them to zero when already included in measured idle",
                    "Awake logic figure includes its rail loads; do not add individual component current twice",
                    "No battery-only lifetime penalty is inferred from fast polling while externally powered",
                    "Actual board quiescent and leakage loads must be included in measured state averages",
                ],
            },
            "excluded_or_unmeasured": ["actual cell capacity/aging", "standby radio profile", "self-discharge", "motor load profile and its dependence on speed/PWM", "temperature", "extra adjustment/commissioning moves"],
            "scenarios": rows}


def main():
    if not shutil.which("ngspice"):
        raise SystemExit("ngspice is required")
    RESULTS.mkdir(exist_ok=True)
    cases = [
        {"name": "no_clamp", "cap_f": 220e-6, "esr_ohm": 0.05,
         "return_current_a": 0.5, "duration_s": 0.02, "clamp_conductance_s": 0},
        {"name": "clamp_nominal", "cap_f": 220e-6, "esr_ohm": 0.05,
         "return_current_a": 0.5, "duration_s": 0.02, "clamp_conductance_s": 2},
        {"name": "clamp_stress", "cap_f": 176e-6, "esr_ohm": 0.2,
         "return_current_a": 2, "duration_s": 0.1, "clamp_conductance_s": 2},
    ]
    result = [simulate(case) for case in cases]
    checks = {
        "bulk_cap_alone_exceeds_17v_logic_buck_limit": result[0]["peak_bus"] > 17,
        "ideal_clamp_nominal_under_15v": result[1]["peak_bus"] < 15,
        "ideal_clamp_stress_under_15v": result[2]["peak_bus"] < 15,
        "stress_energy_requires_real_pulse_rating": result[2]["clamp_energy"] > 1,
    }
    version = subprocess.run(["ngspice", "--version"], text=True, capture_output=True).stdout
    summary = {"status": "architecture-envelope-only", "ngspice_version": next(line.strip() for line in version.splitlines() if "ngspice-" in line),
               "template_sha256": hashlib.sha256((HERE / "regen.cir.in").read_bytes()).hexdigest(),
               "checks": checks, "regeneration": result, "battery_energy": energy_budget()}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"checks": checks, "regeneration": result}, indent=2))
    if not all(checks.values()):
        raise SystemExit("An architecture envelope assertion failed")


if __name__ == "__main__":
    main()
