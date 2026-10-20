#!/usr/bin/env python3
"""Source/BOM/pad/rating checks of the selected 3.3 V circuit; no silicon model."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BOARD = REPO/'hw/boards/blind-regulator'
sys.path.insert(0,str(REPO/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,one,parse


def calculate():
    manifest=json.loads((BOARD/'regulator-ratings.json').read_text())
    parts=manifest['parts']; limits=manifest['limits'];ic=parts['TPS62902RPJR'];inductor=parts['MWSA0402S-1R0MT']
    source=(BOARD/'regulator.ato').read_text()
    imports={name:path for path,name in re.findall(r'from "([^"]+)" import (\w+)',source)}
    instances=dict(re.findall(r'^    (\w+) = new (\w+)',source,re.M))
    expected={}
    for mpn,part in parts.items():
        wrapper=(BOARD/part['wrapper']).resolve();text=wrapper.read_text()
        assert f'partno="{mpn}"' in text and f'supplier_partno="{part["lcsc"]}"' in text
        for instance in part['instances']:
            assert (BOARD/imports[instances[instance]]).resolve()==wrapper, instance
            expected[instance]=mpn
    physical={n for n,cls in instances.items() if cls in imports}
    assert physical==set(expected),f'Unrated or missing parts: {physical ^ set(expected)}'
    assert f"source.voltage = {limits['source_min_v']}V to {limits['source_max_v']}V" in source
    assert 'logic.voltage = 3.3V +/- 2%' in source
    bom_path=BOARD/'build/builds/regulator-test/regulator-test.bom.json'
    bom_checked=False
    if bom_path.exists():
        actual={}
        for part in json.loads(bom_path.read_text())['components']:
            for use in part['usages']:
                name=re.search(r'LogicSupply\.(\w+)\|',use['address']).group(1)
                actual[name]=part['mpn']
        assert actual==expected,'BOM mismatch; rebuild required'
        bom_checked=True
    # Physical numbers independently checked against TI pin table, not Ato aliases.
    pin_contract={
        'ic':{'1':'PG','2':'SW','3':'3V3','4':'GND','5':'EN','6':'SYS','7':'MODE','8':'SS','9':'NC_VSET'},
        'r_enable':{'1':'SYS','2':'EN'},'r_mode':{'1':'MODE','2':'GND'},
        'r_pg':{'1':'3V3','2':'PG'},'c_softstart':{'1':'SS','2':'GND'},
        'inductor':{'1':'SW','2':'3V3'},
        'c_input':{'1':'SYS','2':'GND'},'c_input2':{'1':'SYS','2':'GND'},'c_input_fast':{'1':'SYS','2':'GND'},
        'c_output1':{'1':'3V3','2':'GND'},'c_output2':{'1':'3V3','2':'GND'},'c_output_fast':{'1':'3V3','2':'GND'}}
    pcb=REPO/'hw/layouts/blind-regulator/regulator-test/regulator-test.kicad_pcb'
    graph=board_graph(pcb);actual={};exp={}
    for component in graph.values():
        name=component['properties']['atopile_address'].removeprefix('regulator.')
        for pin,net in component['pads'].items():actual[name+'.'+pin]=net
    for name,pins in pin_contract.items():
        for pin,net in pins.items():exp[name+'.'+pin]=net
    def groups(pins):
        return {frozenset(k for k,v in pins.items() if v==net) for net in set(pins.values())}
    assert actual.keys()==exp.keys() and groups(actual)==groups(exp),'Physical pin contract mismatch'
    # Primary footprint recommendation: pads1.5x2.5,2.2mm gap. Body maximum +courtyard.
    fp=parse((REPO/'hw/parts/blind-regulator/IND-SMD_L4.4-W4.2.kicad_mod').read_text())
    pads=children(fp,'pad')
    assert sorted(float(one(p,'at')[1]) for p in pads)==inductor['reviewed_pad_centres_x_mm']
    assert all(list(map(float,one(p,'size')[1:]))==inductor['reviewed_pad_mm'] for p in pads)
    assert ic['recommended_input_min_v']<=limits['source_min_v']<=limits['source_max_v']<=ic['recommended_input_max_v']
    assert parts['0402WGF2612TCE']['resistance_ohm']==ic['mode_resistance_ohm']
    assert parts['0402WGF2612TCE']['tolerance']<ic['resistor_tolerance_allowed']
    vmin=limits['logic_nominal_v']*(1-ic['vset_accuracy']);vmax=limits['logic_nominal_v']*(1+ic['vset_accuracy'])
    assert vmin>limits['supervisor_release_worst_v']
    lmin=inductor['inductance_h']*(1-inductor['tolerance'])*(1-limits['inductance_dc_drop_planning'])
    # TI Eq4/5: AEE preserves current ripple; frequency is NOT always2.5MHz.
    ripple=limits['source_max_v']*ic['aee_ton_coefficient_s']/lmin
    normal_peak=limits['load_max_a']+ripple/2
    assert normal_peak<ic['high_side_limit_min_a']
    rms=math.sqrt(limits['load_max_a']**2+ripple**2/12)
    fault_planning=ic['high_side_limit_max_a']+limits['source_max_v']/lmin*ic['propagation_delay_typ_s']
    assert fault_planning<inductor['current_at_20_percent_drop_a'] # Conditional comparison, not max guarantee.
    pg_current=limits['logic_nominal_v']*(1+limits['logic_target_tolerance'])/(10000*.99)
    assert pg_current<ic['pg_sink_max_a']
    softstart=parts['0402B473K500NT']['capacitance_f']/ic['softstart_current_typ_a']*ic['softstart_vref_nominal_v']+ic['softstart_offset_typ_s']
    assert softstart>.001
    for part in parts.values():
        if 'rated_voltage_v' in part:
            voltage=limits['source_max_v'] if any(n.startswith('c_input') for n in part['instances']) else vmax
            assert part['rated_voltage_v']>voltage*2
    return {'status':'PASS of source, optional local BOM, compiled physical pins and stated arithmetic',
            'component_count':len(expected),'physical_pin_count':len(actual),'local_bom_policy':'Validate generated BOM when local build artifacts exist',
            'internal_vset_static_range_v':[vmin,vmax],
            'static_margin_above_supervisor_release_v':vmin-limits['supervisor_release_worst_v'],
            'effective_inductance_planning_h':lmin,'aee_ripple_planning_a_pp':ripple,
            'one_amp_load_peak_planning_a':normal_peak,'inductor_rms_planning_a':rms,
            'inductor_copper_loss_planning_w':rms*rms*inductor['dcr_max_ohm'],
            'fault_peak_using_typical_delay_only_a':fault_planning,'pg_pullup_max_a':pg_current,
            'softstart_nominal_s':softstart,
            'limits':'AEE coefficient and fault propagation are typical. Results are conditional estimates, not maximum transient guarantees.',
            'release_gates':manifest['unresolved']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    result=json.dumps(calculate(),indent=2)+'\n';path=HERE/'results.json'
    if a.check:assert path.read_text()==result,'Regulator report stale'
    else:path.write_text(result)
    print(result,end='')
