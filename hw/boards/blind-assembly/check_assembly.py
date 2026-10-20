#!/usr/bin/env python3
"""Verify block preservation and critical cross-block physical-pin connections."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph


def by_address(graph):
    return {c['properties']['atopile_address']: c for c in graph.values()}


def groups(graph):
    nets = {}
    for name, c in graph.items():
        for pin, net in c['pads'].items():
            nets.setdefault(net, set()).add(name + '.' + pin)
    return {frozenset(v) for v in nets.values()}


def verify(graph):
    actual = by_address(graph)
    blocks = [('controller', 'blind-io', 'controller-test', 'controller'),
              ('supervision', 'blind-supervisor', 'supervisor-test', 'block'),
              ('motor', 'blind-controller', 'motor-test', 'bridge')]
    expected_names = set()
    for prefix, folder, target, source_prefix in blocks:
        reference = by_address(board_graph(ROOT / f'hw/layouts/{folder}/{target}/{target}.kicad_pcb'))
        reference = {prefix + k[len(source_prefix):]: v for k, v in reference.items()}
        expected_names.update(reference)
        projected = {k: v for k, v in actual.items() if k.startswith(prefix + '.')}
        assert set(projected) == set(reference), f'{prefix}: component set changed'
        for name in reference:
            for prop in ('Partnumber', 'LCSC'):
                assert projected[name]['properties'][prop] == reference[name]['properties'][prop], name
        assert groups(projected) == groups(reference), f'{prefix}: internal wiring changed'
    assert set(actual) == expected_names
    nets = groups(actual)
    critical = [
        {'controller.mcu.18', 'supervision.inputs.1', 'supervision.r_request.2'},
        {'controller.mcu.25', 'supervision.inputs.3', 'supervision.r_wdi.2'},
        {'controller.mcu.3', 'supervision.supervisor.1', 'supervision.gate.1', 'supervision.r_reset.2'},
        {'supervision.gate.4', 'supervision.r_sleep.1', 'motor.ic.3', 'motor.r_sleep.1'},
        {'controller.mcu.16', 'motor.ic.1', 'motor.r_in1.1'},
        {'controller.mcu.17', 'motor.ic.2', 'motor.r_in2.1'},
        {'controller.mcu.19', 'motor.ic.4', 'motor.r_fault.2'},
        {'controller.r_adc_hi.1', 'motor.ic.6', 'motor.r_current.1'},
    ]
    for pins in critical:
        assert frozenset(pins) in nets, f'Cross-block boundary changed: {sorted(pins)}'
    # No EN capacitor may reappear, including under a different address.
    reset = next(n for n in nets if 'controller.mcu.3' in n)
    assert not any(actual[p.rsplit('.', 1)[0]]['properties']['Reference'].startswith('C') for p in reset)
    # Includes both the supervision 1k and standalone bridge 10k sleep pulls.
    sleep_load_a = 3.3 * 1.02 / 990 + 3.3 * 1.02 / 9900 + 75e-6
    assert sleep_load_a < .004
    return {'components': len(actual), 'pins': sum(len(c['pads']) for c in actual.values()),
            'sleep_gate_max_load_a': sleep_load_a,
            'status': 'PASS: preserved block graphs and critical integration nets; no physical test'}


if __name__ == '__main__':
    graph = board_graph(ROOT / 'hw/layouts/blind-assembly/controller-test/controller-test.kicad_pcb')
    print(json.dumps(verify(graph), indent=2))
