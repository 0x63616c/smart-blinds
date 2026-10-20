#!/usr/bin/env python3
"""Preserve independently reviewed blocks and check power/control boundaries."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph

BLOCKS=[('control','blind-assembly','controller-test',''),
        ('usb','blind-usb','usb-test','usb'),
        ('charger','blind-charger','charger-test','charger'),
        ('logic_supply','blind-regulator','regulator-test','regulator'),
        ('encoder','blind-encoder','encoder-test','encoder')]


def addresses(graph):
    return {c['properties']['atopile_address']:c for c in graph.values()}


def groups(graph):
    nets={}
    for name,c in graph.items():
        for pin,net in c['pads'].items():
            nets.setdefault(net,set()).add(name+'.'+pin)
    return {frozenset(pins) for pins in nets.values()}


def verify(graph):
    actual=addresses(graph);expected_names=set()
    for prefix,folder,target,source_prefix in BLOCKS:
        reference=addresses(board_graph(ROOT/f'hw/layouts/{folder}/{target}/{target}.kicad_pcb'))
        reference={prefix+('.'+name if not source_prefix else name[len(source_prefix):]):c for name,c in reference.items()}
        projected={name:c for name,c in actual.items() if name.startswith(prefix+'.')}
        assert reference.keys()==projected.keys(),f'{prefix}: component set changed'
        expected_names.update(reference)
        for name,c in reference.items():
            for prop in ('Partnumber','LCSC'):
                assert c['properties'][prop]==projected[name]['properties'][prop],f'{name}: part changed'
        assert groups(reference)==groups(projected),f'{prefix}: internal nets changed'
    assert actual.keys()==expected_names,'Unexpected integrated components'
    pins={name+'.'+pin:net for name,c in actual.items() for pin,net in c['pads'].items()}
    # Independent physical-number boundary anchors, not .ato alias names.
    shared=[
        ['usb.efuse.6','charger.ic.2','charger.ic.3','charger.ic.8','charger.ic.9'],
        ['charger.ic.22','charger.ic.23','control.motor.ic.11'],
        ['charger.ic.25','logic_supply.ic.6','encoder.ic.1'],
        ['logic_supply.ic.3','control.controller.mcu.2','encoder.gate.5'],
        ['control.controller.mcu.20','charger.r_permission_base.1'],
        ['control.controller.mcu.24','charger.ic.21'],
        ['control.controller.mcu.11','charger.ic.15'],
        ['control.controller.mcu.12','charger.ic.14'],
        ['usb.connector.A6','usb.connector.B6','control.controller.r_dp.2'],
        ['usb.connector.A7','usb.connector.B7','control.controller.r_dm.2'],
        ['encoder.ic.5','control.controller.r_a_up.1','control.controller.r_b_up.1'],
        ['encoder.gate.6','control.controller.mcu.21'],
        ['encoder.gate.1','control.controller.mcu.3'],
        ['usb.efuse.8','charger.ic.10','logic_supply.ic.4','control.motor.ic.9','encoder.ic.2'],
    ]
    for group in shared:
        assert len({pins[p] for p in group})==1, f'Broken integration: {group}'
    # Raw USB, switched input, pack, SYS, logic, VENC, PMID and GND are distinct.
    isolated=['usb.efuse.5','usb.efuse.6','charger.ic.22','charger.ic.25',
              'logic_supply.ic.3','encoder.ic.5','charger.ic.29','charger.ic.10']
    assert len({pins[p] for p in isolated})==len(isolated),'Power domains shorted'
    # The unpowered PD factory bus must not join the always-on host/gauge bus.
    buses=['usb.pd.7','usb.pd.8','charger.ic.14','charger.ic.15']
    assert len({pins[p] for p in buses})==4,'Factory/host buses shorted'
    return {'status':'PASS: block preservation and integration boundaries, not a routed or tested board',
            'components':len(actual),'physical_pins':len(pins),'blocks':len(BLOCKS)}


if __name__=='__main__':
    print(json.dumps(verify(board_graph(ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb')),indent=2))
