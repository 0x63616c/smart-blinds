"""Fixed selected-part bound calculations and circuit fault controls.
No semiconductor waveform, thermal qualification or general transient proof.
"""
import itertools, math

def calculate_protection(m,actual,verify,expected):
 p=m['parts'];lim=m['limits'];chip=p['TPS26600PWPR'];tvs=p['TVS1800DRVR']
 dt=lim['cutoff_temperature_excursion_c']
 def resistance(mpn):
  a=p[mpn];e=a['tolerance']+a['tempco_planning_ppm_c']*1e-6*dt
  return [a['resistance_ohm']*(1-e),a['resistance_ohm']*(1+e)]
 rt=resistance('0402WGF3903TCE');rb=resistance('RT0402BRD0730K1L')
 def trip(threshold):
  a=[v*(1+t/b)+i*t for v,t,b,i in itertools.product(threshold,rt,rb,[-chip['ovp_leakage_a'],chip['ovp_leakage_a']])]
  return [min(a),max(a)]
 rising=trip(chip['ovp_rising_v']);falling=trip(chip['ovp_falling_v'])
 assert 15*1.05 < rising[0] < rising[1] < tvs['standoff_v']
 assert rising[1] < lim['raw_max_v'] < chip['input_op_max_v'] < chip['input_abs_max_v']
 assert p['ESDA25P35-1U1M']['clamp_35a_8_20_max_v'] < chip['input_op_max_v']
 assert tvs['clamp_35a_8_20_at_125c_max_v'] < min(p['STUSB4500QTR']['vdd_abs_max_v'],p['TPS259470LRPWR']['input_abs_max_v'])
 assert tvs['clamp_35a_8_20_at_125c_max_v'] < p['RB521S30T1G']['reverse_rating_v']
 # OVP pin at specified raw pulse, and top resistor stress, using independent extrema.
 raw_clamp=p['ESDA25P35-1U1M']['clamp_35a_8_20_max_v']
 ovp_pin_max=raw_clamp*rb[1]/(rt[0]+rb[1])+chip['ovp_leakage_a']*rb[1]
 assert ovp_pin_max < 4
 assert raw_clamp**2/rt[0] < p['0402WGF3903TCE']['rated_power_w']
 rla=resistance('0402WGF1201TCE');rlb=resistance('0402WGF4701TCE')
 rl=[a+b for a,b in zip(rla,rlb)];assert rl[0]>=chip['ilim_resistor_min_ohm']
 # Scaling a characterized test point through TI Eq.5 is an inference. Bench gate.
 ilim=[chip['ilim_at_5360_a'][0]*5360/rl[1],chip['ilim_at_5360_a'][1]*5360/rl[0]]
 assert lim['nominal_charger_input_a']*(1+lim['charger_error_allowance']) < ilim[0]
 assert ilim[1]+lim['aux_reserve_a'] < lim['contract_a']
 # Temperature/tolerance/aging allowance for a low-voltage slew capacitor.
 c=p['0402B473K500NT'];cmin=c['capacitance_f']*(1-c['tolerance'])*.85*.9;cmax=c['capacitance_f']*(1+c['tolerance'])*1.15
 slew=[chip['dvdt_gain'][0]*chip['dvdt_charge_a'][0]/cmax,chip['dvdt_gain'][1]*chip['dvdt_charge_a'][1]/cmin]
 cap_upper=(4.7+3)*1.1*1.15*1e-6 # guarded cap + three ST reservoirs, referred wholly to VBUS
 inrush=cap_upper*slew[1]
 power={str(i):i*i*chip['ron_fulltemp_max_ohm']+15.75*chip['iq_on_max_a'] for i in [1.0,1.5,1.65]}
 bleed=resistance('0402WGF1003TCE');assert 24.7**2/bleed[0]<p['0402WGF1003TCE']['rated_power_w']
 # Do not use shutdown-only leakage as a guaranteed OVP off-state specification.
 decay_nominal_s=100000*7.7e-6*math.log(17.6/.8)
 mutants={}
 def wrong(label,pin,netpin):
  q=actual.copy();q[pin]=actual[netpin];mutants[label]=q
 wrong('ST_VDD_returns_to_unguarded_raw','d_vdd.2','connector.A4B9')
 wrong('monitor_returns_to_unguarded_raw','r_raw_dis1.1','connector.A4B9')
 wrong('sink_gate_pullup_returns_to_unguarded_raw','q_enable.2','connector.A4B9')
 wrong('cutoff_bypassed','cutoff.15','cutoff.1')
 wrong('RTN_incorrectly_shorted_to_system_ground','cutoff.8','cutoff.9')
 wrong('UVLO_wrongly_selects_14V9_preset','cutoff.3','cutoff.8')
 wrong('thermal_pad_wrong_reference','cutoff.17','cutoff.9')
 wrong('guarded_TVS_input_disconnected','tvs_guarded.5','cutoff.7')
 wrong('OVP_divider_ground_reference_wrong','r_cutoff_ov_bottom.2','cutoff.9')
 wrong('charger_PD_gate_bypassed','efuse.1','cutoff.1')
 for name,q in mutants.items():
  try:verify(q,expected)
  except AssertionError:pass
  else:raise AssertionError('Undetected fault: '+name)
 return {'added_components':10,'ovp_rising_v':rising,'ovp_falling_v':falling,'normal_15v5percent_margin_v':rising[0]-15.75,'ovp_pin_at_41v_upper_v':ovp_pin_max,'conditional_current_limit_a':ilim,'current_limit_evidence':'scaled 5.36k specified bounds; 5.9k series network not independently specified','slew_planning_v_per_s':slew,'guarded_cap_planning_upper_f':cap_upper,'guarded_startup_inrush_estimate_a':inrush,'additional_tps26600_power_fulltemp_w':power,'datasheet_testboard_deltaT_estimate_c_at_1p5a':power['1.5']*chip['thermal_rja_ti_test_board_c_w'],'bleed_17p6_to_0p8_nominal_s_without_leakage':decay_nominal_s,'ovp_response_max_s':None,'physical_negative_controls_detected':sorted(mutants),'qualification_limits':['No bound on assembly pulse overshoot or OVP maximum delay','No complete switch-fault coverage','Thermal resistance depends on actual RTN copper, vias and enclosure','No guaranteed OVP off-leakage/bleed discharge-time bound','Startup includes unknown active ST draw and downstream BQ dynamic load; estimated capacitor inrush only','No stated product USB/ESD/surge compliance']}
