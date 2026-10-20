#!/usr/bin/env python3
"""Check physical circuit contract, selected-part identity and scoped bounds.

The delay, returned current and bulk capacitance are explicit assumptions. This
does not establish a maximum transient voltage for the manufactured assembly.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / 'hw/boards/blind-regen'
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children, one, parse


def groups(pins):
    return {frozenset(k for k, v in pins.items() if v == net)
            for net in set(pins.values())}


def verify(actual, expected):
    assert actual.keys() == expected.keys(), 'Physical pin set mismatch'
    assert groups(actual) == groups(expected), 'Physical net mismatch'


def calculate():
    manifest = json.loads((BOARD / 'regen-ratings.json').read_text())
    contract = json.loads((BOARD / 'regen-connectivity.json').read_text())
    parts, lim = manifest['parts'], manifest['limits']
    source = (BOARD / 'regen.ato').read_text()
    imports = dict((name, path) for path, name in re.findall(
        r'from "([^"]+)" import (\w+)', source))
    instances = dict(re.findall(r'^    (\w+) = new (\w+)', source, re.M))
    expected_parts = {}
    for mpn, part in parts.items():
        path = (BOARD / part['wrapper']).resolve()
        wrapper = path.read_text()
        assert f'partno="{mpn}"' in wrapper
        assert f'supplier_partno="{part["lcsc"]}"' in wrapper
        for instance in part['instances']:
            assert (BOARD / imports[instances[instance]]).resolve() == path
            expected_parts[instance] = mpn
    assert {n for n, c in instances.items() if c in imports} == set(expected_parts)
    bom = BOARD / 'build/builds/regen-test/regen-test.bom.json'
    if bom.exists():
        built = {}
        for part in json.loads(bom.read_text())['components']:
            for use in part['usages']:
                instance = re.search(r'RegenerationClamp\.(\w+)\|', use['address'])[1]
                built[instance] = part['mpn']
        assert built == expected_parts, 'Build BOM differs; rebuild the circuit'
    graph = board_graph(ROOT / 'hw/layouts/blind-regen/regen-test/regen-test.kicad_pcb')
    actual = {}
    for comp in graph.values():
        name = comp['properties']['atopile_address'].removeprefix('regen.')
        for number, net in comp['pads'].items():
            actual[name + '.' + number] = net
    expected = {name + '.' + pin: net for name, pins in contract['components'].items()
                for pin, net in pins.items()}
    verify(actual, expected)
    mutations = {}
    wrong = actual.copy(); wrong['detector.4'] = actual['detector.3']
    mutations['sense_input_grounded'] = wrong
    wrong = actual.copy(); wrong['q_hold.3'] = actual['q_hold.2']
    mutations['thermal_latch_feedback_missing'] = wrong
    wrong = actual.copy(); wrong['thermal_supply.1'] = 'WRONG_SYS_SUPPLY'
    mutations['independent_supply_lost'] = wrong
    wrong = {pin: actual['q_thermal.1'] if net == actual['q_thermal.5'] else net
             for pin, net in actual.items()}
    mutations['thermal_series_fet_bypassed'] = wrong
    wrong = actual.copy(); wrong['r_dump1b.1'] = actual['r_dump1b.2']
    mutations['one_bank_resistor_bypassed'] = wrong
    for label, wrong in mutations.items():
        try:
            verify(wrong, expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('Undetected fault injection: ' + label)

    fp = parse((ROOT / 'hw/parts/blind-regen/R2512.kicad_mod').read_text())
    assert sorted(float(one(p, 'at')[1]) for p in children(fp, 'pad')) == [-2.575, 2.575]
    assert all(list(map(float, one(p, 'size')[1:])) == [2.45, 3.7]
               for p in children(fp, 'pad'))
    # Full resistor tolerance plus an independent +/-TCR allowance at100C delta.
    def bounds(mpn):
        p = parts[mpn]
        tolerance = p['tolerance'] + p['tcr_abs_ppm_per_c'] * 1e-6 * lim['resistor_temperature_delta_c']
        return [p['resistance_ohm'] * (1 - tolerance),
                p['resistance_ohm'] * (1 + tolerance)]
    top = [a + b for a, b in itertools.product(bounds('0402WGF3303TCE'), bounds('0402WGF1002TCE'))]
    feedback = [2 * r for r in bounds('0603WAF1005T5E')]
    det = parts['TLV6710DDCR']
    thresholds = {}
    for edge in ('rising', 'falling'):
        values = []
        for rt, rb, rf, vth, ib, drop in itertools.product(
                top, bounds('0402WGF1002TCE'), feedback,
                [det[edge + '_threshold_min_v'], det[edge + '_threshold_max_v']],
                [-det['input_bias_planning_a'], det['input_bias_planning_a']],
                [0.05, lim['assumed_gate_high_drop_max_v']]):
            # KCL at the sense node. On-state gate is PACK minus assumed PNP drop.
            high = edge == 'falling'
            values.append((vth * (1/rt + 1/rb + 1/rf) + ib + (drop/rf if high else 0))
                          / (1/rt + (1/rf if high else 0)))
        thresholds[edge + '_min_v'], thresholds[edge + '_max_v'] = min(values), max(values)
    assert thresholds['falling_min_v'] > lim['pack_normal_max_v']
    assert thresholds['rising_max_v'] < lim['rail_design_ceiling_v']
    current, cap, esr = (lim['assumed_return_max_a'], lim['assumed_bulk_min_f'],
                         lim['assumed_bulk_esr_ohm'])
    delay = lim['assumed_control_delay_s']
    peak = thresholds['rising_max_v'] + current * (delay / cap + esr)
    delayed_peak = thresholds['rising_max_v'] + current * (lim['stress_delay_s'] / cap + esr)
    assert peak < lim['rail_design_ceiling_v'] < lim['charger_bat_abs_max_v']
    assert delayed_peak > lim['charger_bat_abs_max_v'], 'Delay stress must expose the limit'
    gate_min = lim['pack_normal_min_v'] * bounds('0402WGF1003TCE')[0] / (
        bounds('0402WGF1003TCE')[0] + bounds('0402WGF8202TCE')[1])
    gate_max = lim['rail_design_ceiling_v'] * bounds('0402WGF1003TCE')[1] / (
        bounds('0402WGF1003TCE')[1] + bounds('0402WGF8202TCE')[0])
    assert gate_min > 4.5 and gate_max < parts['AON7400A']['vgs_abs_v']
    assert lim['rail_design_ceiling_v'] < parts['AON7400A']['vgs_abs_v']
    bank = parts['CRM2512-FX-10R0ELF']
    bank_min = 2 * bank['resistance_ohm'] * (1-bank['tolerance']) / 4
    bank_max = 2 * bank['resistance_ohm'] * (1+bank['tolerance']) / 4
    sink_min = thresholds['falling_min_v'] / (bank_max + 2*parts['AON7400A']['rds_4v5_max_25c_ohm'])
    assert sink_min > current
    # Worst pulse power of one element at modeled ceiling: opposing1% tolerances
    # yield almost equal branch sharing, bounded here by the minimum resistance.
    part_pulse = peak**2 / (4 * bank['resistance_ohm'] * (1-bank['tolerance']))
    assert part_pulse < bank['pulse_curve_read_100ms_w']
    assert part_pulse > bank['power_w_at70c_on_specified_board']
    bias = json.loads((Path(__file__).with_name('capacitor-bias.json')).read_text())
    effective_cap = bias['typical_capacitance_uf'] * .9 * .85 * .9
    ldo = parts['TPS70933DBVR']
    assert ldo['output_effective_min_uf'] < effective_cap < ldo['output_effective_max_uf']
    local_max = ldo['output_v'] * (1 + ldo['output_planning_tolerance'])
    assert local_max < parts['TMP302ADRLR']['supply_max_v']
    # TMP sinks its pull-up and the PNP base path; no transistor gain guarantee.
    hot_sink_upper = local_max / bounds('0402WGF1002TCE')[0] * 2
    assert hot_sink_upper < parts['TMP302ADRLR']['output_test_current_a']
    idle_estimate = (lim['pack_normal_max_v'] / (min(top) + bounds('0402WGF1002TCE')[0])
                     + lim['pack_normal_max_v'] / (bounds('0402WGF8202TCE')[0] + bounds('0402WGF1003TCE')[0])
                     + det['iq_max_a'] + parts['TMP302ADRLR']['iq_max_a']
                     + ldo['iq_no_load_max_a'] + local_max/bounds('0402WGF1003TCE')[0])
    canonical = {}
    for pin, net in sorted(expected.items()): canonical.setdefault(net, []).append(pin)
    return {'status': 'PASS of physical pin contract, part identity and conditional arithmetic',
            'components': len(graph), 'physical_pins': len(actual),
            'negative_controls_detected': sorted(mutations),
            'semantic_graph_sha256': hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest(),
            'threshold_bounds_with_tolerance_and_TCR': thresholds,
            'conditional_peak_with_assumed_100us_delay_v': peak,
            'failure_example_with_assumed_1ms_delay_v': delayed_peak,
            'maximum_total_delay_to18v_s': (lim['rail_design_ceiling_v']-thresholds['rising_max_v']-current*esr)*cap/current,
            'thermal_series_gate_min_v': gate_min, 'thermal_series_gate_max_v': gate_max,
            'minimum_dump_current_at_release_a': sink_min,
            'individual_resistor_power_at_conditional_peak_w': part_pulse,
            'stuck_dump_at12p6_total_w': lim['pack_normal_max_v']**2/bank_min,
            'stuck_dump_at12p6_each_w': lim['pack_normal_max_v']**2/(8*bank_min),
            'output_cap_effective_estimate_uf': effective_cap,
            'thermostat_sink_upper_a': hot_sink_upper,
            'idle_current_partial_bound_a': idle_estimate,
            'idle_exclusions': 'LDO loaded ground current, transistor/PCB/cap leakage, host gate input load; not a guaranteed total idle specification',
            'thermal_open_2a_time_from18v_to20v_s': (lim['charger_bat_abs_max_v']-lim['rail_design_ceiling_v'])*cap/current,
            'scope': 'Transient values depend on assumed delay/current/C/ESR and PNP saturation. Pulse graph is single-pulse, no assembly thermal proof.',
            'release_gates': manifest['unresolved']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = json.dumps(calculate(), indent=2) + '\n'
    target = Path(__file__).with_name('results.json')
    if args.check: assert target.read_text() == text, 'Stale clamp check results'
    else: target.write_text(text)
    print(text, end='')
