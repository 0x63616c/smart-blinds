#!/usr/bin/env python3
"""Preserve independently reviewed blocks and check power/control boundaries."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph

BLOCKS=[('controller','blind-io','controller-test','controller'),
        ('supervision','blind-supervisor','supervisor-test','block'),
        ('motor','blind-controller','motor-test','bridge'),
        ('regen','blind-regen','regen-test','regen'),
        ('usb','blind-usb','usb-test','usb'),
        ('charger','blind-charger','charger-test','charger'),
        ('logic_supply','blind-regulator','regulator-test','regulator'),
        ('encoder','blind-encoder','encoder-test','encoder')]


def addresses(graph):
    result={}
    for c in graph.values():
        address=c['properties'].get('atopile_address')
        assert address and address not in result,'Empty or duplicate component address'
        result[address]=c
    return result


def groups(graph):
    nets={}
    for name,c in graph.items():
        for pin,net in c['pads'].items():
            nets.setdefault(net,set()).add(name+'.'+pin)
    return {frozenset(pins) for pins in nets.values()}


def verify(graph):
    actual=addresses(graph);expected_names=set();expected_groups=[];expected_pins=set()
    for prefix,folder,target,source_prefix in BLOCKS:
        reference=addresses(board_graph(ROOT/f'hw/layouts/{folder}/{target}/{target}.kicad_pcb'))
        reference={prefix+('.'+name if not source_prefix else name[len(source_prefix):]):c for name,c in reference.items()}
        projected={name:c for name,c in actual.items() if name.startswith(prefix+'.')}
        assert reference.keys()==projected.keys(),f'{prefix}: component set changed'
        expected_names.update(reference)
        expected_groups.extend(groups(reference))
        expected_pins.update(name+'.'+pin for name,c in reference.items() for pin in c['pads'])
        for name,c in reference.items():
            for prop in ('Partnumber','LCSC'):
                assert c['properties'][prop]==projected[name]['properties'][prop],f'{name}: part changed'
        assert groups(reference)==groups(projected),f'{prefix}: internal nets changed'
    extra={'r_power_irq':('0402WGF1002TCE','C25744'),
           'thermal_gate':('SN74AUP1G97DCKR','C2682139'),
           'r_thermal_sleep':('0402WGF1001TCE','C11702'),
           'c_thermal_gate':('CL05B104KB54PNC','C307331'),
           'q_thermal_fault':('AO3400A','C20917'),
           'pack_connector.header':('430450600','C127367'),
           'encoder_port.header':('532610471','C696092'),
           'home_port.header':('532610371','C293630'),
           'home_esd':('TPD2E2U06DRLR','C1972959')}
    bare_features={'motor_output.landing1','motor_output.landing2'}
    extra_pad_numbers={'r_power_irq':range(1,3),'thermal_gate':range(1,7),'r_thermal_sleep':range(1,3),
        'c_thermal_gate':range(1,3),'q_thermal_fault':range(1,4),
        'pack_connector.header':range(1,7),'encoder_port.header':range(1,5),
        'home_port.header':range(1,4),'home_esd':range(1,6),
        'motor_output.landing1':[1],'motor_output.landing2':[1]}
    assert actual.keys()==expected_names | extra.keys() | bare_features,'Unexpected integrated components'
    for name,(mpn,code) in extra.items():
        assert actual[name]['properties']['Partnumber']==mpn and actual[name]['properties']['LCSC']==code,name
    for name in bare_features:
        c=actual[name]
        assert c['footprint'].endswith(':WirePad18'),f'{name}: solder landing changed'
        assert set(c['pads'])=={'1'},f'{name}: landing pin changed'
        assert 'exclude_from_bom' in c['attributes'],f'{name}: not a purchased part'
    for name,numbers in extra_pad_numbers.items():
        expected={str(n) for n in numbers}
        assert set(actual[name]['pads'])==expected,f'{name}: physical pin set changed'
        expected_pins.update(name+'.'+n for n in expected)
    pins={name+'.'+pin:net for name,c in actual.items() for pin,net in c['pads'].items()}
    # Independent physical-number boundary anchors, not .ato alias names.
    shared=[
        ['motor_output.landing1.1','motor.ic.8'],
        ['motor_output.landing2.1','motor.ic.10'],
        ['encoder_port.header.1','home_port.header.1','motor.ic.9',
         'home_esd.1','home_esd.2','home_esd.4'],
        ['encoder_port.header.2','encoder.ic.5'],
        ['encoder_port.header.3','controller.r_a_series.1','controller.enc_esd.3'],
        ['encoder_port.header.4','controller.r_b_series.1','controller.enc_esd.5'],
        ['home_port.header.3','controller.r_home_series.1','home_esd.3','home_esd.5'],
        ['pack_connector.header.1','charger.ic.22'],
        ['pack_connector.header.2','charger.ic.10','pack_connector.header.6'],
        ['pack_connector.header.3','charger.ic.15'],
        ['pack_connector.header.4','charger.ic.14'],
        ['pack_connector.header.5','charger.ic.16'],
        ['usb.efuse.6','charger.ic.2','charger.ic.3','charger.ic.8','charger.ic.9'],
        ['charger.ic.22','charger.ic.23','motor.ic.11','regen.detector.5','regen.thermal_supply.1'],
        ['charger.ic.25','logic_supply.ic.6','encoder.ic.1'],
        ['logic_supply.ic.3','controller.mcu.2','encoder.gate.5','thermal_gate.5','c_thermal_gate.1',
         'charger.q_permission.2','motor.r_fault.1','supervision.c_gate.1','usb.pd.22','r_power_irq.1'],
        ['controller.mcu.20','charger.r_permission_base.1'],
        ['controller.mcu.24','charger.ic.21','usb.pd.19','r_power_irq.2'],
        ['controller.mcu.11','charger.ic.15','usb.pd.8'],
        ['controller.mcu.12','charger.ic.14','usb.pd.7'],
        ['usb.connector.A6','usb.connector.B6','controller.r_dp.2'],
        ['usb.connector.A7','usb.connector.B7','controller.r_dm.2'],
        ['encoder.ic.5','controller.r_a_up.1','controller.r_b_up.1'],
        ['encoder.gate.6','controller.mcu.21'],
        ['encoder.gate.1','controller.mcu.3'],
        ['usb.efuse.8','charger.ic.10','logic_supply.ic.4','motor.ic.9','encoder.ic.2',
         'thermal_gate.1','thermal_gate.2','r_thermal_sleep.2','c_thermal_gate.2',
         'controller.c_adc.2','regen.c_detector.2','supervision.c_gate.2'],
        ['controller.mcu.18','supervision.inputs.1'],
        ['controller.mcu.25','supervision.inputs.3'],
        ['controller.mcu.3','supervision.supervisor.1'],
        ['controller.mcu.16','motor.ic.1'],
        ['controller.mcu.17','motor.ic.2'],
        ['controller.mcu.19','motor.ic.4','q_thermal_fault.3'],
        ['q_thermal_fault.2','motor.ic.9'],
        ['q_thermal_fault.1','regen.q_hold.1','regen.q_cutoff.1'],
        ['controller.r_adc_hi.1','motor.ic.6'],
        ['supervision.gate.4','thermal_gate.3'],
        ['regen.thermostat.3','thermal_gate.6'],
        ['thermal_gate.4','motor.ic.3','r_thermal_sleep.1'],
    ]
    for group in shared:
        assert len({pins[p] for p in group})==1, f'Broken integration: {group}'
    assert pins.keys()==expected_pins,'Integrated pin set differs'
    # Form the COMPLETE expected net partition from independent block contracts
    # plus the reviewed physical-pin boundary joins above. Net names are not
    # authority. Extra parts start as isolated pins until explicitly joined.
    roots={p:p for p in expected_pins}
    def root(p):
        while roots[p]!=p:
            roots[p]=roots[roots[p]];p=roots[p]
        return p
    for group in [*expected_groups,*shared]:
        first,*rest=sorted(group)
        for p in rest:roots[root(p)]=root(first)
    expected_partition={}
    for p in expected_pins:expected_partition.setdefault(root(p),set()).add(p)
    wanted={frozenset(v) for v in expected_partition.values()}
    actual_partition=groups(actual)
    if actual_partition!=wanted:
        merged=[sorted({root(p) for p in group}) for group in actual_partition if len({root(p) for p in group})>1]
        raise AssertionError(f'Global net partition differs; unexpected joins: {merged}')
    # Raw USB, switched input, pack, SYS, logic, VENC, PMID and GND are distinct.
    isolated=['usb.efuse.5','usb.efuse.6','charger.ic.22','charger.ic.25',
              'logic_supply.ic.3','encoder.ic.5','charger.ic.29','charger.ic.10']
    assert len({pins[p] for p in isolated})==len(isolated),'Power domains shorted'
    # Powered PD shares the owned bus; SDA and SCL remain distinct.
    assert pins['supervision.gate.4']!=pins['motor.ic.3'],'Thermal motor inhibit bypassed'
    assert pins['usb.pd.7'] != pins['usb.pd.8'],'SDA/SCL shorted'
    assert pins['usb.pd.22'] != pins['usb.pd.24'],'VSYS/raw VDD shorted'
    assert pins['usb.pd.19'] != pins['usb.pd.16'],'Interrupt incorrectly uses autonomous gate'
    assert list(pins.values()).count(pins['home_port.header.2'])==1,'Reserved home pin is connected'
    assert pins['motor_output.landing1.1']!=pins['motor_output.landing2.1'],'Motor leads shorted'
    assert pins['encoder_port.header.3']!=pins['encoder_port.header.4'],'Encoder channels shorted'
    return {'status':'PASS: block preservation and integration boundaries, not a routed or tested board',
            'components':len(actual),'physical_pins':len(pins),'blocks':len(BLOCKS)}


if __name__=='__main__':
    print(json.dumps(verify(board_graph(ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb')),indent=2))
