#!/usr/bin/env python3
"""Check selected pack-circuit identity, physical nets and stated arithmetic.

No cell short circuit, fuse clearing, gauge model or MOSFET transient is simulated.
Those cannot be inferred from the normal circuit graph or nominal I²t values.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[3]
BOARD=ROOT/'hw/boards/blind-carrier'
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,one,parse


def groups(pins):
    return {frozenset(k for k,v in pins.items() if v==net) for net in set(pins.values())}


def verify(actual,expected):
    assert actual.keys()==expected.keys(),'Physical pin set mismatch'
    assert groups(actual)==groups(expected),'Physical net mismatch'


def calculate():
    manifest=json.loads((BOARD/'carrier-ratings.json').read_text())
    contract=json.loads((BOARD/'carrier-connectivity.json').read_text())
    parts=manifest['parts'];lim=manifest['limits'];source=(BOARD/'carrier.ato').read_text()
    imports={name:path for path,name in re.findall(r'from "([^"]+)" import (\w+)',source)}
    instances=dict(re.findall(r'^    (\w+) = new (\w+)',source,re.M));expected_parts={}
    for mpn,p in parts.items():
        path=(BOARD/p['wrapper']).resolve();text=path.read_text()
        assert f'partno="{mpn}"' in text and f'supplier_partno="{p["lcsc"]}"' in text
        for instance in p['instances']:
            assert (BOARD/imports[instances[instance]]).resolve()==path
            expected_parts[instance]=mpn
    assert {n for n,c in instances.items() if c in imports}==set(expected_parts),'Missing part rating'
    for port,net in contract['external_cell_negative_connections'].items():
        target={'RAW_GND':'raw_ground','JUNCTION1':'junction1','JUNCTION2':'junction2'}[net]
        assert f'    {port} ~ {target}\n' in source
    assert 'pack.voltage = 9V to 12.6V' in source
    assert 'gauge.CELL2 ~ gauge.CELL1' in source
    bom=BOARD/'build/builds/carrier-test/carrier-test.bom.json'
    if bom.exists():
        actual_parts={}
        for p in json.loads(bom.read_text())['components']:
            for use in p['usages']:
                name=re.search(r'ProtectedCarrier\.(\w+)\|',use['address'])[1]
                actual_parts[name]=p['mpn']
        assert actual_parts==expected_parts,'Local BOM differs; rebuild'
    graph=board_graph(ROOT/'hw/layouts/blind-carrier/carrier-test/carrier-test.kicad_pcb')
    actual={}
    for comp in graph.values():
        name=comp['properties']['atopile_address'].removeprefix('carrier.')
        for number,net in comp['pads'].items():actual[name+'.'+number]=net
    expected={name+'.'+pin:net for name,pins in contract['components'].items() for pin,net in pins.items()}
    verify(actual,expected)
    mutations={}
    short={pin:actual['gauge.15'] if net==actual['gauge.14'] else net for pin,net in actual.items()}
    mutations['shunt_bypass']=short
    wrong=actual.copy();wrong['gauge.22']=actual['gauge.23'];mutations['wrong_3S_cell_short']=wrong
    wrong=actual.copy();wrong['charge_fet.4']=actual['discharge_fet.4'];mutations['gate_controls_shorted']=wrong
    wrong=actual.copy();wrong['fuse1a.1']=actual['fuse1a.2'];mutations['cell_branch_fuse_bypassed']=wrong
    # Independent six-fault guard for UG7177 Figure3 connector-side/PACK- clamps.
    for signal,pin in [('sda','9'),('scl','8'),('alert','7')]:
        wrong=actual.copy();wrong['z_'+signal+'.2']=actual['gauge.20'];mutations['z_'+signal+'_wrong_raw_return']=wrong
        wrong=actual.copy();wrong['z_'+signal+'.1']=actual['gauge.'+pin];mutations['z_'+signal+'_wrong_series_side']=wrong
    for label,wrong in mutations.items():
        try:verify(wrong,expected)
        except AssertionError:pass
        else:raise AssertionError('Undetected negative control '+label)
    # Confirm corrected manufacturer fuse and shunt land dimensions.
    for filename,centre,size in [('FUSE-SMD_L6.1-W2.7.kicad_mod',2.455,[1.96,3.15]),('R2512.kicad_mod',2.855,[1.65,3.68])]:
        fp=parse((ROOT/'hw/parts/blind-carrier'/filename).read_text())
        pads=children(fp,'pad')
        assert sorted(float(one(p,'at')[1]) for p in pads)==[-centre,centre]
        assert all(list(map(float,one(p,'size')[1:]))==size for p in pads)
    f=parts['AON7400A'];g=parts['MAX17320G22+'];r=parts['1206W4F1000T5E'];shunt=parts['WSL2512R0100FEA'];fuse=parts['0451003.MRL']
    current=lim['pack_path_planning_a'];cell=lim['cell_fault_calculation_v'];rmin=r['resistance_ohm']*(1-r['tolerance'])
    # This ideal-switch upper bound exceeds the documented 3-ohm minimum case.
    balance_current_upper=cell/rmin;balance_power_upper=cell*cell/rmin
    assert balance_current_upper<g['balance_pin_max_a']
    assert balance_power_upper<r['power_at_70c_w']
    lower_balance_typ=4.15/(r['resistance_ohm']+g['balance_switch_typ_ohm'])
    upper_balance_typ=4.15/(2*r['resistance_ohm']+g['balance_switch_typ_ohm'])
    assert g['charge_pump_6v_min_v']>4.5 and g['charge_pump_6v_max_v']<f['vgs_abs_v']
    assert f['vds_v']>lim['pack_normal_max_v']*2
    shunt_power=current**2*shunt['resistance_ohm']*(1+shunt['tolerance'])
    assert shunt_power<shunt['power_at_70c_w']
    fet_loss=current**2*2*f['rds_4v5_max_25c_ohm']
    fuse_loss=6*(current/2)**2*fuse['cold_resistance_nom_ohm']
    holder_loss=6*(current/2)**2*lim['holder_path_resistance_assumption_ohm']
    assert current/2<fuse['rated_current_a']*fuse['continuous_derating_25c']
    # This ONLY holds for equal current division at25C; no thermally safe pass.
    canonical={}
    for pin,net in sorted(expected.items()):canonical.setdefault(net,[]).append(pin)
    return {'status':'PASS of circuit identity, physical pin equivalence and scoped arithmetic',
            'components':len(graph),'physical_pins':len(actual),'negative_controls_detected':sorted(mutations),
            'semantic_graph_sha256':hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest(),
            'pack_path_planning_a':current,'shunt_max_initial_loss_w':shunt_power,
            'shunt_max_initial_drop_v':current*shunt['resistance_ohm']*(1+shunt['tolerance']),
            'fet_pair_max_25c_loss_w':fet_loss,'fet_pair_hot_planning_loss_w':fet_loss*lim['assumed_rds_hot_multiplier'],
            'six_fuses_nominal_cold_loss_w':fuse_loss,'six_holder_loss_at_assumed_path_resistance_w':holder_loss,
            'one_missing_parallel_cell_holder_loss_w':current**2*lim['holder_path_resistance_assumption_ohm'],
            'cell1_balance_current_ideal_switch_upper_a':balance_current_upper,
            'balance_resistor_power_ideal_switch_upper_w':balance_power_upper,
            'cell1_balance_current_typ_at_4v15_a':lower_balance_typ,'other_cell_balance_current_typ_at_4v15_a':upper_balance_typ,
            'equal_branch_current_a':current/2,'branch_fuse_25c_continuous_derated_current_a':fuse['rated_current_a']*.75,
            'local_bom_policy':'Validate ignored local BOM when present; absence is not a build claim',
            'limits':'Fuse cold resistance and melting I2t are nominal. No clearing-time/energy, short-circuit interruption, hot-holder or MOSFET SOA proof.',
            'release_gates':manifest['unresolved']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    result=json.dumps(calculate(),indent=2)+'\n';path=Path(__file__).with_name('results.json')
    if a.check:assert path.read_text()==result,'Stale carrier results'
    else:path.write_text(result)
    print(result,end='')
