#!/usr/bin/env python3
"""Audit the actual compiled pin graph and fixed-part arithmetic, not hardware behavior."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from generate_schematics import board_graph


EXPECTED_PARTS = {
    "watchdog": ("TPS3430WDRCR", "C2870545"),
    "supervisor": ("TPS3808G33DBVR", "C43698"),
    "inputs": ("SN74LVC2G17DCKR", "C50714"),
    "gate": ("SN74AUP1G97DCKR", "C2682139"),
    "c_timing": ("CL05C121JB5NNNC", "C307442"),
    **{n: ("0402WGF1002TCE", "C25744") for n in ("r_request", "r_wdi", "r_wdo", "r_reset")},
    "r_sleep": ("0402WGF1001TCE", "C11702"),
    **{n: ("CL05B104KB54PNC", "C307331") for n in ("c_wd", "c_sup", "c_inputs", "c_gate")},
}

# Independent pin-level specification from primary pin tables, not .ato aliases.
# Each complete group must form exactly one distinct PCB net.
NETS = [
    ["watchdog.1", "watchdog.10", "supervisor.5", "supervisor.6", "inputs.5", "gate.5",
     "r_request.1", "r_wdi.1", "r_wdo.1", "r_reset.1", "c_wd.1", "c_sup.1", "c_inputs.1", "c_gate.1"],
    ["watchdog.5", "watchdog.6", "watchdog.11", "supervisor.2", "inputs.2", "gate.2", "gate.3",
     "r_sleep.2", "c_timing.2", "c_wd.2", "c_sup.2", "c_inputs.2", "c_gate.2"],
    ["watchdog.2", "c_timing.1"],
    ["watchdog.3", "inputs.6", "gate.6"],
    ["watchdog.7", "inputs.4"],
    ["watchdog.8", "supervisor.3", "r_wdo.2"],
    ["supervisor.1", "gate.1", "r_reset.2"],
    ["inputs.1", "r_request.2"],
    ["inputs.3", "r_wdi.2"],
    ["gate.4", "r_sleep.1"],
    ["watchdog.4"], ["watchdog.9"], ["supervisor.4"],
]


def verify_graph(graph):
    actual = {}
    names = {}
    for component in graph.values():
        props = component["properties"]
        name = props["atopile_address"].rsplit(".", 1)[-1]
        assert name not in names, f"Duplicate address {name}"
        names[name] = (props["Partnumber"], props["LCSC"])
        for pin, net in component["pads"].items():
            actual.setdefault(net, set()).add(f"{name}.{pin}")
    assert names == EXPECTED_PARTS, "Changed, missing or additional component; redo pin/rating review"
    assert {frozenset(v) for v in actual.values()} == {frozenset(v) for v in NETS}, "Supervisor pin graph differs from reviewed circuit"
    return sum(map(len, actual.values()))


def check():
    pcb = ROOT / "hw/layouts/blind-supervisor/supervisor-test/supervisor-test.kicad_pcb"
    pins = verify_graph(board_graph(pcb))
    source = (HERE / "supervisor.ato").read_text()
    assert "rail.voltage = 3.3V +/- 2%" in source, "Update rail calculations"
    bom = json.loads((HERE / "build/builds/supervisor-test/supervisor-test.bom.json").read_text())
    built = {}
    for component in bom["components"]:
        for use in component["usages"]:
            match = re.search(r"MotorSupervisor\.(\w+)\|", use["address"])
            assert match, use
            built[match[1]] = component["mpn"]
    assert built == {n: p[0] for n, p in EXPECTED_PARTS.items()}, "Generated BOM mismatch"

    # Samsung C0G: 120pF +/-5%, +/-30ppm/K. 5pF extra is a layout budget,
    # not measured parasitic capacitance. -40..85C logic range, worst delta65K.
    cmin_pf = 120 * .95 * (1 - 30e-6 * 65)
    cmax_pf = 120 * 1.05 * (1 + 30e-6 * 65) + 5
    assert cmin_pf >= 100
    upper_min_ms = (77.4 * cmin_pf / 1000 + 55) * .905
    upper_max_ms = (77.4 * cmax_pf / 1000 + 55) * 1.095
    lower_max_ms = upper_max_ms / 8
    assert lower_max_ms < 10 < 20 < 45 < upper_min_ms < upper_max_ms < 100

    rail_min, rail_max = 3.3 * .98, 3.3 * 1.02
    # Conservative full-temperature supervisor accuracy, despite AUP's 85C limit.
    trip_min = 3.07 * .985
    release_max = 3.07 * 1.015 * 1.025
    assert trip_min > 3.0 and release_max < rail_min
    assert .8 < 1.5  # AUP logic minimum is below DRV sleep-input HIGH threshold.
    sleep_load_max_a = rail_max / 990 + 75e-6
    assert sleep_load_max_a < .004  # AUP VOH min2.55V at3V/4mA, >DRV VIH1.5V.
    assert 2.55 > 1.5 and .45 < .8
    assert 2 * rail_max**2 / 990 < .0625
    off_voltage_v = (.6e-6 + 5e-6) * 1010
    assert off_voltage_v < .8
    return {
        "status": "PASS: compiled graph, BOM and static arithmetic; not physical cutoff proof",
        "components": len(EXPECTED_PARTS), "pins": pins,
        "assumed_timing_stray_budget_pf": 5, "timing_cap_min_pf": cmin_pf,
        "timing_cap_max_pf": cmax_pf, "watchdog_lower_max_ms": lower_max_ms,
        "watchdog_upper_min_ms": upper_min_ms, "watchdog_upper_max_ms": upper_max_ms,
        "proposed_falling_edge_interval_ms": 20, "firmware_feed_interval_limits_ms": [10, 45],
        "reset_release_delay_ms": [12, 28], "supervisor_trip_min_v": trip_min,
        "supervisor_release_max_v": release_max, "rail_min_v": rail_min,
        "static_release_margin_v": rail_min-release_max,
        "sleep_high_load_max_a": sleep_load_max_a, "sleep_poweroff_voltage_bound_v": off_voltage_v,
        "unresolved": [
            "Full controller integration must remove/replace the 1uF EN RC load; supervisor output maximum 5mA is not a capacitor discharge rating.",
            "Reset must physically return GPIO20 HIGH before release; scope-test frozen control task, IRQ lockout, debug halt, boot, repeated faults and no automatic motion restart.",
            "Watchdog SET/WDI input leakage lacks a bound in the primary table; buffered logic-drive assumption needs physical qualification.",
            "MR assertion latency has a typical, not maximum, datasheet value; entire last-heartbeat-to-motor-terminal cutoff must be measured against 100ms target.",
            "Capacitor stray allowance, 3V3 ripple/load transients, rail collapse and motor coasting are not proven by these calculations.",
            "SN74AUP1G97 rating limits this block to -40..85C. Pack operating temperatures are more restrictive.",
            "Native schematic separately checks 49 pins with two explicit external-power ERC findings. Placement/routing, DRC, fabrication and physical cutoff tests remain open.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    result = check()
    if args.record:
        (HERE / "supervisor-verification.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
