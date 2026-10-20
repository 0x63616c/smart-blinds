"""Fixed-source/physical-net checks and explicitly conditional level margins."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'));from generate_schematics import board_graph

def calculate():
 d=json.loads((HERE/'shared-power-bus.json').read_text());g=board_graph(ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb');a={c['properties']['atopile_address']:c for c in g.values()};pins={n+'.'+p:v for n,c in a.items() for p,v in c['pads'].items()};r=d['pullup'];q=d['interrupt'];lo,hi=d['rail_v'];rlo=r['resistance_ohm']*(1-r['tolerance']-r['temperature_allowance']);rhi=r['resistance_ohm']*(1+r['tolerance']+r['temperature_allowance'])
 assert a[r['address']]['properties']['Partnumber']==r['mpn'] and a[r['address']]['properties']['LCSC']==r['lcsc']
 irq=pins['usb.pd.19'];assert {p for p,n in pins.items() if n==irq}==set(q['physical_pins'])
 assert pins['r_power_irq.1']==pins['usb.pd.22']==pins['controller.mcu.2']==pins['usb.c_vsys.1']
 assert pins['usb.c_vsys.2']==pins['usb.pd.10'] and pins['usb.pd.22']!=pins['usb.pd.24']
 assert a['usb.c_vsys']['properties']['Partnumber']==d['vsys']['bypass_mpn']
 assert 'usb.r_sda' not in a and 'usb.r_scl' not in a
 assert pins['usb.pd.7']==pins['charger.ic.14']==pins['controller.mcu.12']
 assert pins['usb.pd.8']==pins['charger.ic.15']==pins['controller.mcu.11']
 assert pins['usb.pd.7']!=pins['usb.pd.8']
 # Same common supply sets both pullup voltage and MCU VIH; correlate VDD.
 sink=hi/rlo;low_margin=q['mcu_vil_vdd_fraction']*lo-max(q['st_vol_v_at_3ma'],q['bq_vol_v_at_5ma']);leak_budget=(1-q['mcu_vih_vdd_fraction'])*lo/rhi
 high_margin=(1-q['mcu_vih_vdd_fraction'])*lo-q['conditional_total_high_sink_allowance_a']*rhi
 assert sink < .003 and low_margin>0 and high_margin>0 and hi*hi/rlo<r['rated_power_w']
 return {'status':'Physical nets/selected pullup PASS; high-state and bus level bounds remain conditional','interrupt_pullup_sink_ceiling_a':sink,'interrupt_low_margin_to_mcu_v':low_margin,'total_sink_leakage_budget_for_mcu_high_a':leak_budget,'high_margin_if_total_sink_leakage_at_most_10ua_v':high_margin,'pullup_power_upper_w':hi*hi/rlo,'unproven_high_bound':q['missing_bound'],'i2c_worst_table_low_margin_v':d['i2c']['st_vil_max_v']-d['i2c']['bq_sda_vol_max_v_at_5ma'],'i2c_qualification_required':True,'energy_wh_60d_typ_max_at_stated_conditions':[3.3*x*24*60/d['vsys']['power_efficiency_assumption'] for x in (d['vsys']['idle_typ_a_25c'],d['vsys']['idle_max_a_25c'])],'vsys_bypass_planning_estimate_uf_at_higher_5v_curve':json.loads((ROOT/'hw/sim/blind-usb/capacitor-bias.json').read_text())['CL10A105KB8NNNC']['samples']['5']['typical_capacitance_uf']*.9*.85*.9,'hardware_qualified':False}
if __name__=='__main__':
 result=calculate();(HERE/'shared-power-bus-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
