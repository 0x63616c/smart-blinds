#!/usr/bin/env python3
"""BOM/source-bound fixed-network checks; not a BQ25798 silicon simulation."""
import argparse
import itertools
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
BOARD = REPO / 'hw/boards/blind-charger'


def bind_source(manifest):
    source = (BOARD / 'charger.ato').read_text()
    imports = dict((name,path) for path,name in re.findall(r'from "([^"]+)" import (\w+)',source))
    instances = dict(re.findall(r'^    (\w+) = new (\w+)',source,re.M))
    expected = {}
    for mpn,part in manifest['parts'].items():
        wrapper = (BOARD / part['wrapper']).resolve()
        text = wrapper.read_text()
        assert f'partno="{mpn}"' in text and f'supplier_partno="{part["lcsc"]}"' in text
        for instance in part['instances']:
            assert (BOARD/imports[instances[instance]]).resolve() == wrapper, instance
            expected[instance] = mpn
    physical = {name for name,cls in instances.items() if cls in imports}
    assert physical == set(expected), f'Unrated or missing parts: {physical ^ set(expected)}'
    limits = manifest['limits']
    for rail in ['source','battery','system']:
        match = re.search(rail+r'.voltage = ([\d.]+)V to ([\d.]+)V',source)
        assert match and tuple(map(float,match.groups())) == (limits[rail+'_min_v'],limits[rail+'_max_v']), rail
    match = re.search(r'logic.voltage = ([\d.]+)V \+/- ([\d.]+)%',source)
    assert match and tuple(map(float,match.groups())) == (limits['logic_nominal_v'],limits['logic_tolerance']*100)
    bom = BOARD/'build/builds/charger-test/charger-test.bom.json'
    actual = {}
    if bom.exists():
        for part in json.loads(bom.read_text())['components']:
            for usage in part['usages']:
                match = re.search(r'Charger3S\.(\w+)\|',usage['address'])
                assert match, usage
                actual[match[1]] = part['mpn']
        assert actual == expected, 'Rebuild: BOM disagrees with source/ratings'
    return len(expected),bom.exists()


def calculate():
    m = json.loads((BOARD/'charger-ratings.json').read_text())
    count,bom_checked = bind_source(m)
    p,limits = m['parts'],m['limits']
    ic=p['BQ25798RQMR']; winding=p['CYA0630-2.2UH']
    by_instance = {instance:part for part in p.values() for instance in part['instances']}
    def resistance(name): return by_instance[name]['resistance_ohm']
    def corners(name):
        part=by_instance[name]
        return [part['resistance_ohm']*(1+x*part['tolerance']) for x in [-1,1]]
    def ntc_resistance(temperature_c):
        table=m['external_ntc']['nominal_table_c_ohm']
        for (ta,ra),(tb,rb) in zip(table,table[1:]):
            if ta <= temperature_c <= tb:
                return math.exp(math.log(ra)+(temperature_c-ta)/(tb-ta)*math.log(rb/ra))
        raise ValueError(temperature_c)
    def crossing(rtop,rbottom,ratio):
        resistance=1/(1/(rtop*ratio/(1-ratio))-1/rbottom)
        low,high=-10.,70.
        for _ in range(60):
            mid=(low+high)/2
            if ntc_resistance(mid)>resistance: low=mid
            else: high=mid
        return (low+high)/2
    records=[]
    for regn,rt,rb,leak in itertools.product([ic['regn_min_v'],ic['regn_max_v']],corners('r_ilim_top'),corners('r_ilim_bottom'),[-ic['ilim_leak_a'],ic['ilim_leak_a']]):
        voltage=regn*rb/(rt+rb)+leak*rt*rb/(rt+rb)
        records.append((voltage,max(.1,(voltage-1)/.8)))
    assert min(x[0] for x in records)>1.0, 'Startup may remain HiZ'
    assert max(x[1] for x in records)<.35
    assert resistance('r_prog')==ic['program_3s_750khz_ohm']
    temp={}
    for name,thresholds in ic['ntc_threshold_ratios'].items():
        values=[crossing(rt,rb,v) for rt,rb,v in itertools.product(corners('r_ts_top'),corners('r_ts_bottom'),thresholds)]
        temp[name]={'nominal_c':crossing(resistance('r_ts_top'),resistance('r_ts_bottom'),thresholds[1]),'resistor_comparator_corners_c':[min(values),max(values)],'excludes':'NTC resistance/B tolerance, self-heating and mounting lag'}
    ntc_open=min(corners('r_ts_bottom'))/(max(corners('r_ts_top'))+min(corners('r_ts_bottom')))
    assert ntc_open>max(ic['ntc_threshold_ratios']['cold'])
    inductance_min=winding['inductance_h']*(1-winding['tolerance'])
    frequency_min=ic['frequency_nominal_hz']*ic['frequency_min_planning_factor']
    # Vout*(1-Vout/Vin) peaks at Vin/2. Bound all supported output voltages.
    buck_v=min(max(limits['source_max_v']/2,limits['battery_min_v']),limits['system_max_v'])
    buck_ripple=buck_v*(1-buck_v/limits['source_max_v'])/(inductance_min*frequency_min)
    boost_v=min(max(limits['system_max_v']/2,limits['source_min_v']),limits['source_max_v'])
    boost_ripple=boost_v*(1-boost_v/limits['system_max_v'])/(inductance_min*frequency_min)
    peak=max(limits['charge_limit_a']+buck_ripple/2,limits['input_limit_max_a']+boost_ripple/2,2)
    assert peak<winding['saturation_a_30_percent_drop']
    rms=math.sqrt(limits['input_limit_max_a']**2+boost_ripple**2/12)
    assert rms<winding['rms_a_40c_rise']
    assert ic['input_recommended_min_v']<=limits['source_min_v']<=limits['source_max_v']<=ic['input_recommended_max_v']
    assert limits['battery_max_v']<ic['battery_abs_max_v'] and limits['system_max_v']<ic['system_abs_max_v']
    assert p['AO3400A']['vds_max_v']>ic['regn_max_v']
    assert p['AO3400A']['vgs_abs_max_v']>limits['logic_nominal_v']*(1+limits['logic_tolerance'])
    assert p['MMBT3906LT1G']['vce_abs_max_v']>limits['logic_nominal_v']*(1+limits['logic_tolerance'])
    for part in p.values():
        if 'capacitance_f' in part:
            rail=ic['regn_max_v'] if part is p['CL21A475KAQNNNE'] else limits['source_max_v']
            assert part['max_voltage_v']>=limits['ceramic_voltage_derating']*rail
        if 'resistance_ohm' in part and part is not p['0402WGF1000TCE']:
            power=ic['regn_max_v']**2/(part['resistance_ohm']*(1-part['tolerance']))
            assert power*limits['resistor_power_derating']<=part['max_power_w']
    assert p['CL21A475KAQNNNE']['capacitance_f']==4.7e-6
    assert p['0402B473K500NT']['capacitance_f']==47e-9
    assert p['0402B102K500NT']['capacitance_f']==1e-9
    assert p['CL31A106KBHNNNE']['capacitance_f']==10e-6
    return {'scope':'Fixed-network arithmetic tied to source and selected MPNs; no BQ25798 loop or silicon simulation.','physical_components':count,'build_bom_checked':bom_checked,
        'ilim_v_range':[min(x[0] for x in records),max(x[0] for x in records)],'ilim_command_a_range':[min(x[1] for x in records),max(x[1] for x in records)],
        'usb_note':'Not proof of 100 mA USB pre-enumeration compliance. Radio/charge stay off; input current and inrush need measurement.',
        'ntc':temp,'ntc_open_min_regn_ratio':ntc_open,'ntc_short_regn_ratio':0,
        'inductor_peak_bound_a':peak,'inductor_rms_bound_a':rms,'inductor_sat_30percent_drop_a':winding['saturation_a_30_percent_drop'],
        'inductor_rms_40c_rise_rating_a':winding['rms_a_40c_rise'],'inductor_dcr_max_ohm':winding['dcr_max_ohm'],'inductor_dcr_loss_at_input_limit_w':limits['input_limit_max_a']**2*winding['dcr_max_ohm'],
        'ce_pull_power_w':ic['regn_max_v']**2/min(corners('r_ce')),
        'proposed_charge_target_v':limits['charge_target_v'],'charge_target_plus_accuracy_planning_v':limits['charge_target_v']*(1+ic['charge_voltage_error_test_12p6v_upper']),
        'charge_gpio_contract':'Active LOW, PNP inversion, external pullup; absent 3V3 leaves NFET gate pulled down.',
        'system_steady_planning_range_v':[limits['system_min_v'],limits['system_max_v']],
        'release_gates':m['unresolved']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args()
    result=json.dumps(calculate(),indent=2)+'\n'
    if args.write: (ROOT/'results.json').write_text(result)
    print(result,end='')
