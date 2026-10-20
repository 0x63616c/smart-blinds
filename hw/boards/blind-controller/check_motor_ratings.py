#!/usr/bin/env python3
"""Fixed selected-part checks, tied to source instances, rail expressions and build BOM.

This complements the unit-literal Ato checks; imported atomic wrappers do not
expose rated parameters to the solver. No result is a motor/thermal safety proof.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def check():
    manifest = json.loads((ROOT / "motor-ratings.json").read_text())
    parts, limits = manifest["parts"], manifest["limits"]
    source = (ROOT / "motor.ato").read_text()
    imports = dict((name, path) for path, name in re.findall(r'from "([^"]+)" import (\w+)', source))
    instances = dict(re.findall(r'^    (\w+) = new (\w+)', source, re.M))
    expected = {}
    for mpn, part in parts.items():
        wrapper = (ROOT / part["wrapper"]).resolve()
        text = wrapper.read_text()
        assert re.search(r'partno="' + re.escape(mpn) + r'"', text), f"MPN mismatch: {wrapper}"
        assert f'supplier_partno="{part["lcsc"]}"' in text, f"LCSC mismatch: {wrapper}"
        for instance in part["instances"]:
            assert (ROOT / imports[instances[instance]]).resolve() == wrapper, f"Changed part for {instance}"
            expected[instance] = mpn
    physical = {name for name, cls in instances.items() if cls in imports}
    assert physical == set(expected), f"Unrated or missing physical parts: {physical ^ set(expected)}"
    rail = re.search(r'pack.voltage = ([\d.]+)V to ([\d.]+)V', source)
    logic = re.search(r'logic.voltage = ([\d.]+)V \+/- ([\d.]+)%', source)
    assert rail and tuple(map(float, rail.groups())) == (limits["pack_min_v"], limits["pack_max_v"]), "Update rated rail envelope"
    assert logic and tuple(map(float, logic.groups())) == (limits["logic_nominal_v"], limits["logic_tolerance"] * 100), "Update logic envelope"
    bom_path = ROOT / "build/builds/motor-test/motor-test.bom.json"
    if bom_path.exists():
        actual = {}
        for part in json.loads(bom_path.read_text())["components"]:
            for usage in part["usages"]:
                match = re.search(r'MotorBridge\.(\w+)\|', usage["address"])
                assert match, usage
                actual[match[1]] = part["mpn"]
        assert actual == expected, "Build BOM disagrees with source rating records; rebuild/review"
    ic = parts["DRV8874PWPR"]
    resistor = parts["0402WGF1002TCE"]
    sense = parts["0402WGF1201TCE"]
    c100 = parts["CL05B104KB54PNC"]
    fly = parts["0402B223K500NT"]
    bulk = parts["UCM1E221MCL1GS"]
    vmin = limits["logic_nominal_v"] * (1 - limits["logic_tolerance"])
    vmax = limits["logic_nominal_v"] * (1 + limits["logic_tolerance"])
    rmin = resistor["resistance_ohm"] * (1 - resistor["tolerance"])
    rmax = resistor["resistance_ohm"] * (1 + resistor["tolerance"])
    vref_min, vref_max = vmin*rmin/(rmin+rmax), vmax*rmax/(rmin+rmax)
    gain = ic["ipropr_gain_a_per_a"]
    trip_min = vref_min / (sense["resistance_ohm"] * (1+sense["tolerance"]) * gain * (1+ic["gain_tolerance_2_to_4_a"]))
    trip_max = vref_max / (sense["resistance_ohm"] * (1-sense["tolerance"]) * gain * (1-ic["gain_tolerance_2_to_4_a"]))
    assert ic["vm_min_v"] <= limits["pack_min_v"] < limits["pack_max_v"] <= ic["vm_max_v"]
    assert limits["trip_min_a"] <= trip_min <= trip_max <= limits["trip_max_a"]
    assert 2 <= trip_min <= trip_max <= 4, "Selected gain-error range no longer applicable"
    assert vref_max <= ic["vref_max_v"]
    pull_power = vmax**2 / rmin
    ipropi_power = ic["ipropi_max_a"]**2 * sense["resistance_ohm"] * (1+sense["tolerance"])
    assert limits["resistor_power_derating"] * pull_power <= resistor["max_power_w_at_70c"]
    assert limits["resistor_power_derating"] * ipropi_power <= sense["max_power_w_at_70c"]
    assert vmax <= resistor["max_voltage_v"]
    assert ic["ipropi_max_a"] * sense["resistance_ohm"] * (1+sense["tolerance"]) <= sense["max_voltage_v"]
    pmode_min = vmin - ic["pmode_high_input_max_a"] * rmax
    assert pmode_min >= ic["pmode_high_min_v"]
    assert fly["max_voltage_v"] >= limits["ceramic_voltage_derating"] * limits["pack_max_v"]
    assert c100["max_voltage_v"] >= limits["ceramic_voltage_derating"] * max(limits["pack_max_v"], ic["pump_differential_max_v"], vref_max)
    assert bulk["max_voltage_v"] >= limits["pack_max_v"]
    assert bulk["capacitance_f"]*(1-bulk["tolerance"]) >= limits["minimum_bulk_f"]
    assert fly["capacitance_f"] == 22e-9 and c100["capacitance_f"] == 100e-9
    return {"status": "PASS: fixed-part steady-state arithmetic only", "physical_components": len(expected),
            "build_bom_checked": bom_path.exists(), "trip_min_a": trip_min, "trip_max_a": trip_max,
            "vref_min_v": vref_min, "vref_max_v": vref_max,
            "divider_nominal_total_ohm": 2*resistor["resistance_ohm"],
            "pull_resistor_worst_power_w": pull_power, "ipropi_resistor_power_at_3ma_w": ipropi_power,
            "pmode_high_min_v": pmode_min, "unresolved": manifest["unresolved"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Refresh the tracked calculation report")
    args = parser.parse_args()
    result = json.dumps(check(), indent=2) + "\n"
    if args.write:
        (ROOT / "motor-rating-report.json").write_text(result)
    print(result, end="")
