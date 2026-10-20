#!/usr/bin/env python3
"""Audit source/BOM/physical pins and conditional USB input arithmetic.

This is not a PD controller, semiconductor transient or USB compliance model.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BOARD = ROOT / 'hw/boards/blind-usb'
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph


def groups(pins):
    return {frozenset(k for k, v in pins.items() if v == net) for net in set(pins.values())}


def verify(actual, expected):
    assert actual.keys() == expected.keys(), 'Physical terminal set mismatch'
    assert groups(actual) == groups(expected), 'Physical net mismatch'


def trip_range(top, bottom, thresholds, error, drop=(0, 0), leakage=1e-7):
    values = [v * (1 + rt / rb) + i * rt + d
              for rt, rb, v, i, d in itertools.product(
                  [top * (1-error), top * (1+error)],
                  [bottom * (1-error), bottom * (1+error)],
                  thresholds, [-leakage, leakage], drop)]
    return [min(values), max(values)]


def calculate():
    manifest = json.loads((BOARD / 'usb-ratings.json').read_text())
    contract = json.loads((BOARD / 'usb-connectivity.json').read_text())['components']
    curves = json.loads((HERE / 'capacitor-bias.json').read_text())
    parts, lim = manifest['parts'], manifest['limits']
    source = (BOARD / 'usb.ato').read_text()
    imports = {cls: path for path, cls in re.findall(r'from "([^"]+)" import (\w+)', source)}
    instances = dict(re.findall(r'^    (\w+) = new (\w+)', source, re.M))
    selected = {}
    for mpn, part in parts.items():
        path = (BOARD / part['wrapper']).resolve()
        wrapper = path.read_text()
        assert f'partno="{mpn}"' in wrapper and f'supplier_partno="{part["lcsc"]}"' in wrapper
        for name in part['instances']:
            assert (BOARD / imports[instances[name]]).resolve() == path, name
            selected[name] = mpn
    assert set(selected) == {n for n, c in instances.items() if c in imports}, 'Unrated part'
    assert 'raw.voltage = 4.75V to 21V' in source
    assert 'factory_bus.address = 40' in source
    bom = BOARD / 'build/builds/usb-test/usb-test.bom.json'
    if bom.exists():
        actual_parts = {}
        for part in json.loads(bom.read_text())['components']:
            for use in part['usages']:
                name = re.search(r'UsbPdInput\.(\w+)\|', use['address'])[1]
                actual_parts[name] = part['mpn']
        assert actual_parts == selected, 'Local BOM is stale or changed'

    graph = board_graph(ROOT / 'hw/layouts/blind-usb/usb-test/usb-test.kicad_pcb')
    actual = {}
    for component in graph.values():
        name = component['properties']['atopile_address'].removeprefix('usb.')
        for pin, net in component['pads'].items():
            actual[name + '.' + pin] = net
    expected = {name + '.' + pin: net for name, pins in contract.items() for pin, net in pins.items()}
    verify(actual, expected)
    mutations = {}
    mutations['load_switch_bypassed'] = {p: actual['efuse.5'] if n == actual['efuse.6'] else n for p, n in actual.items()}
    wrong = actual.copy(); wrong['tvs_cc.2'] = actual['tvs_cc.1']; mutations['cc_protection_shorts_channels'] = wrong
    wrong = actual.copy(); wrong['pd.16'] = actual['pd.14']; mutations['enable_uses_sticky_power_ok'] = wrong
    wrong = actual.copy(); wrong['efuse.3'] = actual['efuse.8']; mutations['auxoff_output_grounded'] = wrong
    wrong = actual.copy(); wrong['d_vdd.1'], wrong['d_vdd.2'] = wrong['d_vdd.2'], wrong['d_vdd.1']; mutations['vdd_diode_reversed'] = wrong
    for label, changed in mutations.items():
        try:
            verify(changed, expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('Undetected fault: ' + label)

    efuse = parts['TPS259470LRPWR']; pd = parts['STUSB4500QTR']
    error = .01 + .0001 * lim['resistor_temperature_excursion_c']
    r = lambda name: parts[name]['resistance_ohm']
    assert r('0402WGF1651TCE') == 1650  # The TI min/max specification is for this exact nominal value.
    ilim = [efuse['ilim_at_1650_min_a'] / (1+error), efuse['ilim_at_1650_max_a'] / (1-error)]
    charger_max = lim['nominal_charger_input_a'] * (1+lim['charger_error_allowance'])
    assert charger_max < ilim[0]
    assert ilim[1] + lim['aux_reserve_a'] < lim['contract_a']
    uvlo = trip_range(r('0402WGF3903TCE') + r('0402WGF1003TCE'), r('0402WGF1003TCE'),
                      efuse['uvlo_rising_v'], error, [0, parts['MMBT3906LT1G']['vce_sat_allowance_v']])
    ovlo = trip_range(r('0402WGF3903TCE') + r('0402WGF2612TCE'), r('0402WGF3012TCE'),
                      efuse['ovlo_rising_v'], error)
    assert uvlo[0] > 5.5 and uvlo[1] < 8.1
    assert ovlo[0] > 15.75 and ovlo[1] < 19
    assert lim['raw_max_v'] < pd['vdd_op_max_v'] and lim['raw_max_v'] < efuse['input_op_max_v']
    assert parts['CL31A475KBHNNNE']['rated_voltage_v'] >= 2 * lim['raw_max_v']
    cap_factor = .9 * lim['cap_temperature_factor'] * lim['cap_aging_planning_factor']
    effective = {
        'raw_21v': curves['CL31A475KBHNNNE']['samples']['21']['typical_capacitance_uf'] * cap_factor,
        'vreg_2v7': curves['CL10A105KB8NNNC']['samples']['2.7']['typical_capacitance_uf'] * cap_factor,
        'vreg_1v2': curves['CL10A105KB8NNNC']['samples']['1.2']['typical_capacitance_uf'] * cap_factor,
        'vdd_21v': curves['CL10A105KB8NNNC']['samples']['21']['typical_capacitance_uf'] * cap_factor,
    }
    assert effective['raw_21v'] >= 1
    assert effective['vreg_2v7'] >= pd['internal_reg_cap_min_uf']
    assert effective['vreg_1v2'] >= pd['internal_reg_cap_min_uf']
    # Deliberately charge both low-voltage regulator caps as though directly
    # on VBUS. This is a conservative nominal-capacitance planning sum only.
    uncontrolled_uf = (4.7 + 3) * 1.1 * 1.15
    assert uncontrolled_uf < lim['uncontrolled_cap_planning_ceiling_uf']
    # Each series resistor can be high while the other two are low.
    rhi, rlo = 1000*(1+error), 1000*(1-error)
    discharge_power = lim['raw_max_v']**2 * rhi / (rhi + 2*rlo)**2
    assert discharge_power < parts['0603WAF1001T5E']['rated_power_w']
    discharge_current = lim['raw_max_v'] / (3*rlo)
    assert discharge_current < pd['monitor_discharge_max_a']
    sink_base_current = lim['raw_max_v'] / (2*10000*(1-error))
    assert sink_base_current < .003
    canonical = {}
    for pin, net in sorted(expected.items()):
        canonical.setdefault(net, []).append(pin)
    return {
        'status': 'PASS of source, selected parts, physical pins and conditional arithmetic only',
        'components': len(graph), 'physical_pins': len(actual),
        'negative_controls_detected': sorted(mutations),
        'semantic_graph_sha256': hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest(),
        'local_bom_policy': 'Validate ignored local BOM if present; absence is not a build claim',
        'ilim_planning_a': ilim, 'charger_input_ceiling_with_provisional_allowance_a': charger_max,
        'uvlo_rising_planning_v': uvlo, 'ovlo_rising_planning_v': ovlo,
        'effective_capacitance_estimates_uf': effective,
        'uncontrolled_capacitance_planning_upper_uf': uncontrolled_uf,
        'discharge_resistor_max_initial_power_w': discharge_power,
        'discharge_current_upper_a': discharge_current,
        'pd_enable_sink_current_upper_a': sink_base_current,
        'vdd_start_margin_using_25c_diode_spec_v': 4.75 - parts['RB521S30T1G']['vf_max_at_200ma_25c_v'] - pd['vdd_op_min_v'],
        'surge_qualified': False, 'pd_nvm_programmed': False, 'hardware_tested': False,
        'limits': 'Typical capacitor curves and conditional resistor/PNP/current allowances do not establish worst-case silicon behavior, USB timing, startup or immunity.',
        'release_gates': manifest['unresolved'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    result = json.dumps(calculate(), indent=2) + '\n'; output = HERE / 'results.json'
    if args.check:
        assert output.read_text() == result, 'Stale USB input results'
    else:
        output.write_text(result)
    print(result, end='')
