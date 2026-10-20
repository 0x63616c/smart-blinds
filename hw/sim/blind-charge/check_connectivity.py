#!/usr/bin/env python3
"""Compare compiled physical-pad nets with the independently reviewed pin contract.

Does not derive expected connections from Ato or its wrapper pin names. Every pad,
including three intentional NC pins, must occur exactly once. Net names may change
but their full sets of connected physical pins must agree, so opens/shorts fail.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph

MANIFEST = ROOT / 'hw/boards/blind-charger/charger-connectivity.json'
PCB = ROOT / 'hw/layouts/blind-charger/charger-test/charger-test.kicad_pcb'
REPORT = Path(__file__).with_name('connectivity-results.json')


def groups(pins):
    result = {}
    for pin, net in pins.items():
        result.setdefault(net, set()).add(pin)
    return {frozenset(group) for group in result.values()}


def verify(actual, expected):
    if actual.keys() != expected.keys():
        raise ValueError(f'Physical pin set differs: {set(actual) ^ set(expected)}')
    ag, eg = groups(actual), groups(expected)
    if ag != eg:
        raise ValueError('Connectivity mismatch: ' + repr({
            'unexpected': [sorted(x) for x in ag-eg],
            'missing': [sorted(x) for x in eg-ag]}))


def calculate():
    contract = json.loads(MANIFEST.read_text())
    graph = board_graph(PCB)
    actual = {}
    for ref, component in graph.items():
        address = component['properties']['atopile_address']
        prefix = contract['prefix'] + '.'
        assert address.startswith(prefix), (ref, address)
        instance = address[len(prefix):]
        for number, net in component['pads'].items():
            key = f'{instance}.{number}'
            assert key not in actual, key
            actual[key] = net
    expected = {f'{name}.{pin}':net for name,pins in contract['pins'].items() for pin,net in pins.items()}
    verify(actual, expected)
    for pin in contract['intentional_no_connect']:
        assert list(actual.values()).count(actual[pin]) == 1, pin
    # Meaningful negative controls: exchanging BQ PMID/GND, shorting VBUS/BAT,
    # losing the CE transistor connection and wiring a declared NC must all fail.
    mutations = {}
    swapped = actual.copy()
    swapped['ic.29'], swapped['ic.27'] = swapped['ic.27'], swapped['ic.29']
    mutations['pmid_ground_pin_swap'] = swapped
    short = {pin: actual['ic.2'] if net == actual['ic.22'] else net for pin,net in actual.items()}
    mutations['input_battery_short'] = short
    opened = actual.copy(); opened['q_charge.3'] = '__test_open'
    mutations['ce_gate_open'] = opened
    nc = actual.copy(); nc['ic.6'] = actual['ic.27']
    mutations['nc_grounded'] = nc
    for label, mutation in mutations.items():
        try: verify(mutation, expected)
        except ValueError: pass
        else: raise AssertionError(f'Negative control was not detected: {label}')
    canonical = {}
    for pin, net in sorted(expected.items()):
        canonical.setdefault(net, []).append(pin)
    return {
        'status':'PASS: compiled pad equivalence against independent physical-pin contract',
        'component_count':len(graph), 'physical_pin_count':len(actual), 'net_count':len(groups(actual)),
        'intentional_nc_count':len(contract['intentional_no_connect']),
        'negative_controls_detected':sorted(mutations),
        'contract_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'semantic_graph_sha256':hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest(),
        'limits':'Not a fresh Ato build, schematic ERC, routed DRC, transient simulation or physical validation.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = calculate()
    text = json.dumps(result, indent=2) + '\n'
    if args.check:
        assert REPORT.read_text() == text, 'Connectivity report is stale; regenerate after review'
    else: REPORT.write_text(text)
    print(f'Charger: {result["component_count"]} components, {result["physical_pin_count"]} pins; graph and negative controls PASS')
