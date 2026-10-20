#!/usr/bin/env python3
"""Verify two-board pack partition against the independently audited carrier graph.

This is a net/part/geometry check, not fuse clearing or cell safety validation.
Four permanent wire links are modeled explicitly, since they are not PCB tracks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import parse, children, one

RAILS = {'raw_ground':'RAW_GND', 'junction1':'JUNCTION1', 'junction2':'JUNCTION2', 'raw_top':'RAW_TOP'}
HARNESS = {'pack_positive':'PACK_TOP', 'pack_ground':'PACK_GND', 'gauge_sda':'SDA_HOST', 'gauge_scl':'SCL_HOST',
           'charger_ntc_sense':'CHARGER_NTC', 'charger_ntc_return':'CHARGER_NTC_RETURN'}

def groups(pins):
    return {frozenset(k for k,v in pins.items() if v == net) for net in set(pins.values())}

def verify(actual, expected):
    assert actual.keys() == expected.keys(), 'Physical pin set differs'
    assert groups(actual) == groups(expected), 'Physical net equivalence differs'

def collect():
    graphs, actual = {}, {}
    for board in ('primary', 'companion'):
        g = board_graph(ROOT/f'hw/layouts/blind-pack-{board}/{board}-test/{board}-test.kicad_pcb')
        graphs[board] = g
        for c in g.values():
            name = c['properties']['atopile_address'].removeprefix('carrier.')
            for pin, net in c['pads'].items():
                actual[f'{board}.{name}.{pin}'] = f'{board}:{net}'
    return graphs, actual

def join_rails(pins, swapped=False):
    # Harness soldering is a separate controlled assembly step, not inferred
    # from similar net names generated independently on the two PCBs.
    pairs = [('raw_ground','raw_ground'), ('junction1','junction1'), ('junction2','junction2'), ('raw_top','raw_top')]
    if swapped:
        pairs[1:3] = [('junction1','junction2'), ('junction2','junction1')]
    rename = {pins[f'companion.link_{b}.1']: pins[f'primary.link_{a}.1'] for a,b in pairs}
    return {p: rename.get(n,n) for p,n in pins.items()}

def expected_graph():
    contract = json.loads((ROOT/'hw/boards/blind-carrier/carrier-connectivity.json').read_text())['components']
    result = {}
    for name, pins in contract.items():
        if name.startswith('fuse'):
            board = 'primary' if name.endswith('a') else 'companion'
            target = f'{board}.{name[:-1]}'
        else:
            target = f'primary.protection.{name}'
        result.update({target+'.'+p:n for p,n in pins.items()})
    for board, suffix in [('primary','A'), ('companion','B')]:
        for name, net in RAILS.items():
            result[f'{board}.link_{name}.1'] = net
        for i, negative in [(1,'RAW_GND'),(2,'JUNCTION1'),(3,'JUNCTION2')]:
            result[f'{board}.holder{i}.1'] = f'CELL{i}{suffix}_POS'
            result[f'{board}.holder{i}.2'] = negative
    for name, net in HARNESS.items():
        result[f'primary.harness_{name}.1'] = net
    for i in (1,2):
        result[f'primary.ntc{i}_sense.1'] = f'NTC{i}'
        result[f'primary.ntc{i}_return.1'] = 'RAW_GND'
    result['primary.charger_ntc_sense.1'] = 'CHARGER_NTC'
    result['primary.charger_ntc_return.1'] = 'CHARGER_NTC_RETURN'
    result['primary.gauge_alert_test.1'] = 'ALERT_HOST'
    return result

def check_holder():
    path = ROOT/'hw/parts/blind-holders/BAT-TH_BH-21700-A5BJ001.kicad_mod'
    fp = parse(path.read_text()); pads = children(fp, 'pad')
    electrical = {p[1]:p for p in pads if p[1]}
    assert set(electrical) == {'1','2'}
    for number, x in [('1',-40),('2',40)]:
        p = electrical[number]
        assert list(map(float,one(p,'at')[1:3])) == [x,0]
        assert one(p,'drill')[1] == 'oval'
        assert list(map(float,one(p,'drill')[2:])) == [1,3.7]
        assert list(map(float,one(p,'size')[1:])) == [1.5,4.2]
    mechanical = {(tuple(map(float,one(p,'at')[1:3])),float(one(p,'drill')[1])) for p in pads if not p[1]}
    assert mechanical == {((34.3,-8.5),4.),((-34.3,8.5),4.),((-38.75,-11.5),2.)}
    assert all(p[2]=='np_thru_hole' for p in pads if not p[1])

def check_wire_features():
    for name in ('WirePad18','WirePadSignal'):
        library=parse((ROOT/f'hw/parts/blind-pack-features/{name}.kicad_sym').read_text())
        symbol=one(library,'symbol');assert symbol[1]==name
        units=children(symbol,'symbol');assert len(units)==2
        assert [u[1] for u in units]==[name+'_0_1',name+'_1_1']
        assert len(children(units[0],'circle'))==1 and not children(units[0],'symbol')
        pin=one(units[1],'pin');assert pin[1:3]==['passive','line']
        assert one(pin,'number')[1]=='1'
        assert one(pin,'at')[1:]==['-3.81','0','0']
        footprint=next(p for p in children(symbol,'property') if p[1]=='Footprint')
        assert footprint[2]=='blind-pack-features:'+name
    mechanical=parse((ROOT/'hw/parts/blind-pack-features/MountingHole_M3_3.4mm.kicad_mod').read_text())
    assert set(one(mechanical,'attr')[1:])=={'board_only','exclude_from_pos_files','exclude_from_bom'}
    pads=children(mechanical,'pad');assert len(pads)==1
    assert pads[0][1:4]==['','np_thru_hole','circle']
    assert not children(pads[0],'net') and one(pads[0],'drill')[1:] == ['3.4']

def calculate():
    graphs, raw = collect(); actual = join_rails(raw); expected = expected_graph()
    verify(actual, expected); check_holder(); check_wire_features()
    original=(ROOT/'hw/boards/blind-carrier/carrier.ato').read_text().split('    gauge = new Part_MAX17320G22_')[1].split('\nmodule CarrierTest:')[0]
    extracted=(ROOT/'hw/boards/blind-pack-primary/protection.ato').read_text().split('    gauge = new Part_MAX17320G22_')[1]
    assert extracted==original, 'Extracted protection core changed; independent review required'
    for board, count in [('primary',33),('companion',6)]:
        bom=ROOT/f'hw/boards/blind-pack-{board}/build/builds/{board}-test/{board}-test.bom.json'
        if bom.exists():
            components=json.loads(bom.read_text())['components']
            assert sum(len(c['usages']) for c in components)==count
            assert all(not c['mpn'].startswith('WirePad') for c in components)
    mutations = {'intercarrier_middle_rails_swapped':join_rails(raw,True)}
    for label, a, b in [
        ('primary_branch_fuse_bypass','primary.fuse1.1','primary.fuse1.2'),
        ('companion_branch_fuse_bypass','companion.fuse3.1','companion.fuse3.2'),
        ('protected_ground_bypassed','primary.harness_pack_ground.1','primary.link_raw_ground.1'),
        ('wrong_cell2_short','primary.protection.gauge.22','primary.protection.gauge.23'),
        ('charger_ntc_return_joined_raw_ground','primary.harness_charger_ntc_return.1','primary.link_raw_ground.1')]:
        changed = actual.copy(); changed[a] = actual[b]; mutations[label] = changed
    for label, changed in mutations.items():
        try:
            verify(changed,expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('Undetected regression: '+label)
    # All six purchased pigtail conductors are 18 AWG, even the signal wires.
    primary = {c['properties']['atopile_address'].removeprefix('carrier.'):c for c in graphs['primary'].values()}
    for name in HARNESS:
        assert primary['harness_'+name]['footprint']=='blind-pack-features:WirePad18'
    for board in ('primary','companion'):
        source = (ROOT/f'hw/boards/blind-pack-{board}/carrier.ato').read_text()
        assert source.count('new Part_BH_21700_A5BJ001') == 3
        assert source.count('new Part_0451003_MRL') == 3
    canonical = sorted(sorted(g) for g in groups(expected))
    files = sorted([*ROOT.glob('hw/boards/blind-pack-*/*.ato'), *ROOT.glob('hw/parts/blind-holders/*.ato'),
                    *ROOT.glob('hw/parts/blind-holders/*.kicad_mod'), *ROOT.glob('hw/parts/blind-pack-features/*')])
    return {'status':'PASS: two-board circuit partition, independent reference pin contract, holder geometry and six negative controls',
            'boards':{k:{'footprints':len(g),'physical_pins':sum(len(c['pads']) for c in g.values())} for k,g in graphs.items()},
            'purchased_components':{'primary':33,'companion':6}, 'permanent_intercarrier_wires':4,
            'semantic_graph_sha256':hashlib.sha256(json.dumps(canonical).encode()).hexdigest(),
            'negative_controls_detected':sorted(mutations),
            'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},
            'limits':['Unrouted. Geometric placement checks are separate; no thermal/current or physical-fit qualification.',
                      'Wire landing diameter is a design choice; actual stripped 18 AWG strand/tinning fit must be checked.',
                      'Holder drawing gives no current rating and no validated reverse-insertion protection.',
                      'Fuse clearing, mismatched-cell equalization, failed-short FET faults, complete NVM settings and physical cell temperature sensing remain unresolved.',
                      'Four raw rails must remain permanently retained and insulated inside the screwed cassette.',
                      'An open middle-node interconnect can leave companion cell voltages unmonitored; this topology is not single-open-fault tolerant.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    text=json.dumps(calculate(),indent=2)+'\n';path=Path(__file__).with_name('results.json')
    if args.check:
        assert path.read_text()==text, 'Stale pack check results'
    else:
        path.write_text(text)
    print(text,end='')
