#!/usr/bin/env python3
"""Estimate effective banks from sampled primary typical curves, not nominal labels.

Tolerance, -15% X5R temperature and an explicit 10% aging allowance are multiplied
with typical bias data. This is a planning sensitivity, NOT a guaranteed joint
worst-case distribution. Confirmation of real capacitance remains a release gate.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def calculate():
    curves = json.loads((HERE/'capacitor-bias.json').read_text())
    charger = json.loads((ROOT/'hw/boards/blind-charger/charger-ratings.json').read_text())
    regulator = json.loads((ROOT/'hw/boards/blind-regulator/regulator-ratings.json').read_text())
    rows = []
    for name,manifest,mpn,prefix,voltage,minimum in [
        ('charger_vbus',charger,'CL31A106KBHNNNE','c_input',20,2),
        ('charger_pmid_no_backup',charger,'CL31A106KBHNNNE','c_pmid',20,4),
        ('charger_sys',charger,'CL31A106KBHNNNE','c_sys',13.2,6),
        ('charger_bat',charger,'CL31A106KBHNNNE','c_bat',12.6,3),
        ('regulator_input',regulator,'CL31A106KBHNNNE','c_input',13.2,3),
        ('regulator_output_local',regulator,'CL21A226MAYNNNE','c_output',3.366,10)]:
        part=manifest['parts'][mpn]
        instances=[x for x in part['instances'] if x.startswith(prefix)]
        bias=curves[mpn]['samples'][str(voltage)]['typical_capacitance_uf']
        estimated=len(instances)*bias*(1-part['tolerance'])*.85*.9
        assert estimated >= minimum, f'{name}: estimated effective capacitance below minimum'
        rows.append({'bank':name,'mpn':mpn,'instances':instances,'voltage_v':voltage,
                     'nominal_total_uf':len(instances)*curves[mpn]['nominal_uf'],
                     'typical_biased_total_uf':round(len(instances)*bias,5),
                     'estimated_with_tolerance_temperature_aging_uf':round(estimated,5),
                     'ic_required_minimum_uf':minimum,'estimated_margin_percent':round(100*(estimated/minimum-1),2)})
    return {'status':'PASS of stated planning assumptions only',
            'sources':['https://www.ti.com/lit/ds/symlink/bq25798.pdf section6.3',
                       'https://www.ti.com/lit/ds/symlink/tps62902.pdf section6.3'],
            'temperature_factor':.85,'aging_planning_factor':.9,'banks':rows,
            'excluded':'100 nF bypass contribution, unguaranteed bias/temperature interaction, actual aging duration, ESL/ESR, layout and load transients',
            'release_gate':'Confirm effective capacitance and ripple/stability on assembled boards; disable BQ backup mode (70 uF minimum if enabled).'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    text=json.dumps(calculate(),indent=2)+'\n';path=HERE/'capacitance-results.json'
    if a.check: assert path.read_text()==text,'Capacitance report stale'
    else: path.write_text(text)
    print(text,end='')
