#!/usr/bin/env python3
"""Check selected encoder supply, physical graph and conditional design envelope."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph

PARTS = {
    'ic': ('TPS70950DBVR', 'C96028'),
    'gate': ('SN74AUP1G97DCKR', 'C2682139'),
    'r_enable': ('0402WGF1001TCE', 'C11702'),
    'c_input': ('CL10A105KB8NNNC', 'C15849'),
    'c_output': ('CL31A475KBHNNNE', 'C12881'),
    'c_gate': ('CL05B104KB54PNC', 'C307331'),
}


def groups(pins):
    nets = {}
    for pin, net in pins.items():
        nets.setdefault(net, set()).add(pin)
    return {frozenset(p) for p in nets.values()}


def verify(graph):
    actual = {c['properties']['atopile_address'].removeprefix('encoder.'): c for c in graph.values()}
    assert set(actual) == set(PARTS), 'Component set changed'
    for name, (mpn, code) in PARTS.items():
        assert actual[name]['properties']['Partnumber'] == mpn, name
        assert actual[name]['properties']['LCSC'] == code, name
    expected = json.loads((ROOT / 'hw/boards/blind-encoder/encoder-connectivity.json').read_text())['components']
    flatten = lambda d: {n+'.'+p: net for n, pins in d.items() for p, net in pins.items()}
    pins = flatten({n: c['pads'] for n, c in actual.items()})
    expected = flatten(expected)
    assert pins.keys() == expected.keys(), 'Physical terminal set changed'
    assert groups(pins) == groups(expected), 'Physical wiring changed'
    return len(actual), len(pins)


def calculate():
    graph = board_graph(ROOT / 'hw/layouts/blind-encoder/encoder-test/encoder-test.kicad_pcb')
    counts = verify(graph)
    by_name = {c['properties']['atopile_address'].removeprefix('encoder.'): n for n, c in graph.items()}
    faults = []
    for label, name, pin, other, other_pin in [
        ('enable_tied_to_sys', 'ic', '3', 'ic', '1'),
        ('reset_bypassed', 'gate', '1', 'gate', '5'),
        ('active_low_polarity_reversed', 'gate', '3', 'gate', '5'),
        ('input_output_short', 'ic', '5', 'ic', '1'),
    ]:
        changed = copy.deepcopy(graph)
        changed[by_name[name]]['pads'][pin] = changed[by_name[other]]['pads'][other_pin]
        try:
            verify(changed)
        except AssertionError:
            faults.append(label)
        else:
            raise AssertionError('Fault not detected: ' + label)
    curves = json.loads((HERE / 'capacitor-bias.json').read_text())
    # Samsung typical curves x -10% tolerance x -15% temperature x 0.9 aging
    # allowance. Neither curve nor aging allowance is a guaranteed lower bound.
    effective = {n: c['typical_uf']*.9*.85*.9 for n,c in curves.items()}
    assert effective['CL31A475KBHNNNE'] >= 1.5  # TI SBVS186H section8.1.1, Vout>=1.5V
    assert effective['CL10A105KB8NNNC'] >= .1  # Analog input decoupling recommendation.
    # TI table6.5: 1% accuracy, 10mV line, 50mV load; conservatively added here.
    output = [5*.99-.01-.05, 5*1.01+.01+.05]
    assert output[0] >= 4.75 and output[1] <= 5.25
    # 30mA includes provisional encoder and pullups; not a silicon current limit.
    load_a = .030
    dissipation = (13.2-output[0])*load_a
    rise_c = dissipation*212.1  # TI DBV JEDEC board thetaJA, not our final PCB.
    # AUP3V VOH>=2.55V at -4mA; EN high >=.9V. 75C resistor allowance.
    max_gate_load_a = 3.3*1.02/(1000*(1-.01-.0075))
    assert max_gate_load_a < .004
    assert 2.55 > .9
    # All four static combinations from Y = IN2 ? IN0 : IN1.
    table = []
    for reset in (0,1):
        for allow_n in (0,1):
            enabled = 0 if allow_n else reset
            table.append({'reset_n':reset,'allow_n':allow_n,'enabled':enabled})
            assert enabled == int(reset == 1 and allow_n == 0)
    return {'status':'PASS: selected-part identity, physical graph and conditional calculations only',
            'components':counts[0], 'physical_pins':counts[1], 'faults_detected':faults,
            'effective_capacitance_estimates_uf':effective,'output_planning_v':output,
            'load_planning_a':load_a,'ldo_dissipation_planning_w':dissipation,
            'reference_board_temperature_rise_c':rise_c,
            'gate_max_pull_down_load_a':max_gate_load_a,'logic_table':table,
            'hardware_tested':False,
            'limits':['Motor encoder voltage, pinout and current remain unmeasured.',
                      'Effective capacitance and thermal estimates do not qualify stability or enclosure temperature.',
                      'TPS709 EN pullup current and shutdown current have typical-only entries; startup, power-off leakage and output decay need bench checks.',
                      'No active output discharge; wait for measured encoder power-up and stable samples before accepting motion.',
                      'LDO short-circuit/thermal shutdown are not a 30mA harness current limit. Connector faults require system testing.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check', action='store_true');args=parser.parse_args()
    text=json.dumps(calculate(),indent=2)+'\n';p=HERE/'results.json'
    if args.check:
        assert p.read_text()==text,'Stale encoder results'
    else:
        p.write_text(text)
    print(text,end='')
