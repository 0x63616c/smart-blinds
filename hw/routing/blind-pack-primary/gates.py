# Fixed fine-pitch CHG escape leaves DIS pin its own path.
n=net('protection.gauge',3)
track(n,F,.2,[[27.75,2.89],[27.75,2.1]],'CHG-pin-escape')
via(n,[27.75,2.1],'CHG-pin-transition',False)
# ['protection.gauge', 3] to ['protection.r_charge_gate', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',3)
track(n,B,.2,[[27.75,2.1],[28.55,1.3],[34.6,1.3],[35.2,1.0],[43.8,1.0],[44.1,1.3],[44.7,1.3],[45,1.0],[49.7,1.05]],'CHG-control')
via(n,[49.7, 1.05],'CHG-control-transition',False)
track(n,F,.2,[[49.7, 1.05], [50.57, 1.0]],'CHG-control')
# Local charge-gate network is separately routed from the source power bus.
n=net('protection.r_charge_gate',2)
track(n,F,.2,[[51.43,1],[52.3,1.2]],'charge-gate-resistor-escape')
via(n,[52.3,1.2],'charge-gate-low',False)
track(n,B,.2,[[52.3,1.2],[51.3,2.2],[51.3,7.5],[51.4,8]],'charge-gate-local-back')
via(n,[51.3,2.2],'charge-gate-FET',False)
track(n,F,.2,[[51.3,2.2],[52.6,3.525]],'charge-gate-FET-land')
via(n,[51.4,8],'charge-gate-cap',False)
track(n,F,.2,[[51.4,8],[51.18,7.1]],'charge-gate-cap-land')
track(raw,F,.2,[[52.02,7.1],[52.55,7.1]],'charge-gate-source-return')
n=net('protection.r_discharge_gate',2)
track(n,F,.2,[[61,4.43],[61,5.6],[59.4,5.6],[59.4,5.475]],'discharge-gate-local')
track(net('protection.gauge',6),F,.2,[[29.25,2.89],[30.2,2.8],[30.7,2.6],[31.37,1.6]],'PCKP-local-protected-input')

n=net('protection.gauge',4)
track(n,F,.2,[[28.25,2.89],[28.25,2.5],[28.45,2.15],[29.1,2.15],[29.9,2]],'DIS-pin-escape')
via(n,[29.9,2],'DIS-pin-transition',False)
# 3S CELL2 intentionally shares CELL1; this joins only those adjacent pins.
track(net('protection.gauge',21),F,.2,[[26.09,5.05],[26.09,4.55]],'CELL2-CELL1-local')
# ['protection.c_cell3', 2] to ['protection.c_cell1', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.c_cell3',2)
track(n,F,.2,[[22.42, 7.1], [22.0, 6.5], [20.0, 6.5], [19.58, 7.1]],'CELL3-return')
# ['protection.c_cell4', 2] to ['protection.c_cell3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.c_cell4',2)

# Staggered cell-input and thermistor escapes; each via has its own clear landing.
track(net('protection.gauge',23),F,.2,[[26.09,4.05],[25.5,4.05],[24.8,3.8]],'CELL3-escape')
via(net('protection.gauge',23),[24.8,3.8],'CELL3-input',False)
track(net('protection.gauge',24),F,.2,[[26.09,3.55],[25.5,2.9]],'BATTS-escape')
via(net('protection.gauge',24),[25.5,2.9],'BATTS-input',False)
# ['protection.gauge', 21] to ['protection.c_cell1', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',21)
track(n,F,.2,[[26.09, 5.05], [25.2, 5.1], [24.1, 4.0], [24.1, 3.6], [24.7, 3.0]],'CELL1-local')
via(n,[24.7, 3.0],'CELL1-local-transition',False)
track(n,B,.2,[[24.7, 3.0], [20.3, 6.3]],'CELL1-local')
via(n,[20.3, 6.3],'CELL1-local-transition',False)
track(n,F,.2,[[20.3, 6.3], [19.8, 6.7], [19.58, 7.1]],'CELL1-local')
# ['protection.gauge', 17] to ['protection.c_reg2', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',17)
track(n,F,.2,[[27.25, 6.71], [27.2, 7.2], [27.0, 7.4], [25.9, 7.4], [24.8, 6.5], [22.6, 6.5], [21.7, 5.6], [21.5, 5.5]],'REG2-cap')
# ['protection.gauge', 23] to ['protection.c_cell3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',23)
track(n,F,.2,[[26.09, 4.05], [25.1, 4.1], [24.8, 3.8]],'CELL3-local')
track(n,B,.2,[[24.8, 3.8], [21.6, 7.9]],'CELL3-local')
via(n,[21.6, 7.9],'CELL3-local-transition',False)
track(n,F,.2,[[21.6, 7.9], [21.58, 7.1]],'CELL3-local')
n=net('protection.c_cell4',2)
track(n,F,.2,[[24.42,7.1],[24.8,7.9]],'CELL4-return-escape')
via(n,[24.8,7.9],'CELL4-return-via',False)
track(n,B,.2,[[24.8,7.9],[21.6,7.9]],'CELL4-return-back')
# ['protection.c_cell4', 1] to ['protection.gauge', 24]; inspected scratch proposal, then actual DRC.
n=net('protection.c_cell4',1)
track(n,F,.2,[[23.58, 7.1], [23.6, 7.6], [24.5, 8.5], [24.8, 8.6], [25.1, 8.5], [25.6, 8.0]],'BATTS-local')
via(n,[25.6, 8.0],'BATTS-local-transition',False)
track(n,B,.2,[[25.6, 8.0], [24.5, 6.0], [25.5, 4.2], [25.5, 2.9]],'BATTS-local')
track(n,F,.2,[[25.5, 2.9], [26.09, 3.55]],'BATTS-local')
# ['protection.r_balance1', 2] to ['protection.c_cell1', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance1',2)
track(n,F,.2,[[22.48, 1.4], [21.0, 2.9], [19.58, 7.1]],'CELL1-balance')
# ['protection.c_cell1', 2] to ['protection.c_reg2', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_cell1',2)
track(n,F,.2,[[20.42, 7.1], [20.0, 7.7], [19.2, 7.7], [19.0, 7.5], [19.0, 6.7], [19.4, 5.7]],'CELL1-quiet-return')
via(n,[19.4, 5.7],'CELL1-quiet-return-transition',False)
track(n,B,.2,[[19.4, 5.7], [21.2, 4.3]],'CELL1-quiet-return')
via(n,[21.2, 4.3],'CELL1-quiet-return-transition',False)
track(n,F,.2,[[21.2, 4.3], [22.2, 4.3], [23.5, 5.5]],'CELL1-quiet-return')
# ['protection.r_supply', 2] to ['protection.c_supply', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_supply',2)
# ['protection.r_balance3', 2] to ['protection.c_cell3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance3',2)
track(n,F,.2,[[10.5, 5.98], [12.7, 10.5], [13.1, 10.9], [14.9, 11.3], [16.5, 11.3], [21.58, 7.1]],'CELL3-balance')
# ['protection.r_balance1', 1] to ['fuse1', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance1',1)
track(n,F,.2,[[19.52, 1.4], [15.0, 1.545]],'J1-balance-tap')
# ['protection.r_balance4', 1] to ['fuse3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance4',1)
track(n,F,.2,[[73.0, 3.02], [67.0, 1.545]],'BATTS-power-tap')
# ['protection.r_discharge_gate', 1] to ['protection.gauge', 4]; inspected scratch proposal, then actual DRC.
n=net('protection.r_discharge_gate',1)
# ['protection.r_balance3', 1] to ['fuse2', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance3',1)
# ['protection.r_supply', 1] to ['protection.r_balance4', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_supply',1)
track(n,F,.2,[[75.37, 6.5], [73.0, 3.02]],'gauge-RAW-feed')
# ['protection.c_supply', 1] to ['protection.r_supply', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_supply',1)
# ['protection.r_pack_sense', 1] to ['protection.discharge_fet', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_pack_sense',1)
# ['gauge_alert_test', 1] to ['protection.r_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('gauge_alert_test',1)
track(n,F,.2,[[37.7, 100.0], [38.07, 102.5]],'ALRT-test')
# ['protection.r_alert', 2] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_alert',2)
# ['protection.r_scl', 2] to ['protection.z_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_scl',2)
# ['protection.r_sda', 2] to ['protection.z_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_sda',2)
# ['harness_charger_ntc_return', 1] to ['charger_ntc_return', 1]; inspected scratch proposal, then actual DRC.
n=net('harness_charger_ntc_return',1)
track(n,F,.2,[[77.0, 94.8], [71.6, 97.1], [71.1, 97.2], [50.7, 97.2], [46.9, 101.1], [44.3, 101.4], [42.7, 101.4], [40.9, 99.6], [30.0, 94.5]],'charger-NTC-return')
# ['harness_charger_ntc_sense', 1] to ['charger_ntc_sense', 1]; inspected scratch proposal, then actual DRC.
n=net('harness_charger_ntc_sense',1)
track(n,F,.2,[[71.0, 94.8], [65.6, 92.5], [65.1, 92.4], [50.1, 92.4]],'charger-NTC-sense')
via(n,[50.1, 92.4],'charger-NTC-sense-transition',False)
track(n,B,.2,[[50.1, 92.4], [41.4, 92.4]],'charger-NTC-sense')
via(n,[41.4, 92.4],'charger-NTC-sense-transition',False)
track(n,F,.2,[[41.4, 92.4], [28.1, 92.4], [26.0, 94.5]],'charger-NTC-sense')
# ['protection.r_sda', 1] to ['harness_gauge_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_sda',1)
# ['protection.r_scl', 1] to ['harness_gauge_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_scl',1)
# ['protection.z_sda', 2] to ['protection.z_scl', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.z_sda',2)
# ['protection.z_scl', 2] to ['protection.z_alert', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.z_scl',2)
# ['ntc1_return', 1] to ['ntc2_return', 1]; inspected scratch proposal, then actual DRC.
n=net('ntc1_return',1)
track(n,F,.2,[[14.0, 94.5], [17.6, 92.9], [19.6, 92.9], [22.0, 94.5]],'NTC-return-link')
# ['ntc2_return', 1] to ['protection.z_sda', 2]; inspected scratch proposal, then actual DRC.
n=net('ntc2_return',1)
# ['protection.z_sda', 2] to ['protection.c_supply', 2]; inspected scratch proposal, then actual DRC.
n=net('ntc2_return',1)
track(n,F,.2,[[43.7,89.7],[29.0,22.6]],'interface-quiet-ground')
via(n,[29.0, 22.6],'interface-quiet-ground-transition',False)
track(n,B,.2,[[29.0, 22.6], [26.0, 6.6]],'interface-quiet-ground')
via(n,[26.0, 6.6],'interface-quiet-ground-transition',False)
track(n,F,.2,[[26.0, 6.6], [23.7, 4.2], [23.6, 1.9], [24.28, 1.2]],'interface-quiet-ground')
# ['protection.r_balance4', 2] to ['protection.c_cell4', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_balance4',2)
track(n,F,.2,[[73.0, 5.98], [73.0, 7.3]],'BATTS-filter-link')
via(n,[73.0, 7.3],'BATTS-filter-link-transition',False)
track(n,B,.2,[[73.0, 7.3], [73.6, 9.0]],'BATTS-filter-link')
via(n,[73.6, 9.0],'BATTS-filter-link-transition',False)
track(n,F,.2,[[73.6, 9.0], [69.4, 11.3], [65.8, 11.3]],'BATTS-filter-link')
via(n,[65.8, 11.3],'BATTS-filter-link-transition',False)
track(n,B,.2,[[65.8, 11.3], [46.3, 28.0], [44.6, 28.1], [39.4, 22.9]],'BATTS-filter-link')
via(n,[39.4, 22.9],'BATTS-filter-link-transition',False)
track(n,F,.2,[[39.4, 22.9], [35.1, 22.6]],'BATTS-filter-link')
via(n,[35.1, 22.6],'BATTS-filter-link-transition',False)
track(n,B,.2,[[35.1, 22.6], [27.4, 10.4]],'BATTS-filter-link')
via(n,[27.4, 10.4],'BATTS-filter-link-transition',False)
track(n,F,.2,[[27.4, 10.4], [24.5, 8.5], [24.2, 8.2], [23.58, 7.1]],'BATTS-filter-link')
# ['ntc2_sense', 1] to ['protection.gauge', 16]; inspected scratch proposal, then actual DRC.
n=net('ntc2_sense',1)
track(n,F,.2,[[18.0, 94.5], [19.3, 93.6]],'TH2-sense-link')
via(n,[19.3, 93.6],'TH2-sense-link-transition',False)
track(n,B,.2,[[19.3, 93.6], [25.0, 29.4]],'TH2-sense-link')
via(n,[25.0, 29.4],'TH2-sense-link-transition',False)
track(n,F,.2,[[25.0, 29.4], [25.0, 22.6]],'TH2-sense-link')
via(n,[25.0, 22.6],'TH2-sense-link-transition',False)
track(n,B,.2,[[25.0, 22.6], [27.0, 15.6]],'TH2-sense-link')
via(n,[27.0, 15.6],'TH2-sense-link-transition',False)
track(n,F,.2,[[27.0, 15.6], [29.9, 12.7]],'TH2-sense-link')
via(n,[29.9, 12.7],'TH2-sense-link-transition',False)
track(n,B,.2,[[29.9, 12.7], [30.7, 11.9], [30.9, 11.5], [30.9, 10.6], [29.6, 9.3], [29.1, 9.2], [28.1, 8.6], [27.8, 8.3], [27.7, 7.6]],'TH2-sense-link')
via(n,[27.7, 7.6],'TH2-sense-link-transition',False)
track(n,F,.2,[[27.7, 7.6], [27.75, 6.71]],'TH2-sense-link')
# ['protection.gauge', 7] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',7)
# ['protection.gauge', 9] to ['protection.z_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',9)

# Six coordinated gauge escapes; smaller vias are confined to this fine-pitch region.
via(net('protection.gauge',9),[31.4,4.7],'SDA-pin-transition',False,compact=True)
# ['protection.gauge', 15] to ['protection.shunt', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',15)
track(n,B,.2,[[28.4, 8], [31.3, 7.7], [45.7, 4]],'CSP-refined-isolated')
# ['protection.gauge', 14] to ['protection.shunt', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',14)
track(n,B,.2,[[29.4, 8.6], [48.3, 4]],'CSN-refined-isolated')
# ['protection.gauge', 13] to ['protection.c_reg3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',13)
# ['protection.c_supply', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_supply',2)
# ['protection.gauge', 12] to ['protection.r_aoldo', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',12)
track(n,F,.2,[[29.91, 6.05], [30.6, 6.3]],'AOLDO-refined-local')
via(n,[30.6, 6.3],'AOLDO-refined-local-transition',False,compact=True)
track(n,B,.2,[[30.6, 6.3], [31.2, 6.7], [32.9, 6.7], [33.3, 6.3]],'AOLDO-refined-local')
via(n,[33.3, 6.3],'AOLDO-refined-local-transition',False,compact=True)
track(n,F,.2,[[33.3, 6.3], [33.57, 6.9]],'AOLDO-refined-local')
# ['protection.gauge', 11] to ['protection.r_pfail', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',11)
track(n,F,.2,[[29.91, 5.55], [30.9, 5.7], [31.2, 6.0], [31.8, 5.97]],'PFAIL-refined-local')
# ['protection.gauge', 7] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',7)
track(net('protection.r_balance3',1),F,.2,[[10.5,3.02],[9.3,5.3],[9.3,6.7],[12.2,10.6],[12.9,11.3],[14.9,11.8],[26.9,11.8],[28.9,9.75],[30.3,9.75],[31.6,11.5],[37.2,11.8]],'J2-balance-tap-open-corridor')
# ['protection.gauge', 7] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',7)
# ['protection.gauge', 8] to ['protection.z_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',8)
# ['protection.gauge', 10] to ['ntc1_sense', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',10)
# ['protection.gauge', 4] to ['protection.r_discharge_gate', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',4)
track(n,F,.2,[[28.25, 2.89], [28.3, 2.4], [28.5, 2.2], [29.9, 2.0]],'DIS-refined-control')
track(n,B,.2,[[29.9, 2.0], [43.1, 1.7]],'DIS-refined-control')
via(n,[43.1, 1.7],'DIS-refined-control-transition',False,compact=False)
track(n,F,.2,[[43.1, 1.7], [46.1, 1.3], [48.8, 1.7]],'DIS-refined-control')
via(n,[48.8, 1.7],'DIS-refined-control-transition',False,compact=False)
track(n,B,.2,[[48.8, 1.7], [50.9, 1.7], [52.0, 0.6], [52.3, 0.5], [58.1, 1.0]],'DIS-refined-control')
via(n,[58.1, 1.0],'DIS-refined-control-transition',False,compact=False)
track(n,F,.2,[[58.1, 1.0], [63.8, 1.0], [64.9, 2.0], [65.1, 2.5], [65.1, 7.9]],'DIS-refined-control')
via(n,[65.1, 7.9],'DIS-refined-control-transition',False,compact=False)
track(n,B,.2,[[65.1, 7.9], [61.9, 5.1]],'DIS-refined-control')
via(n,[61.9, 5.1],'DIS-refined-control-transition',False,compact=False)
track(n,F,.2,[[61.9, 5.1], [61.6, 4.0], [61.0, 3.57]],'DIS-refined-control')
# ['protection.gauge', 9] to ['protection.z_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',9)
track(n,F,.2,[[29.91, 4.55], [31.4, 4.7]],'SDA-final-uplink')
track(n,B,.2,[[31.4, 4.7], [35.2, 4.6], [35.6, 5.0], [35.6, 5.4], [34.9, 6.1], [34.8, 6.1]],'SDA-final-uplink')
via(n,[34.8, 6.1],'SDA-final-uplink-transition',False,compact=True)
track(n,F,.2,[[34.8, 6.1], [35.1, 6.6], [35.1, 8.3]],'SDA-final-uplink')
via(n,[35.1, 8.3],'SDA-final-uplink-transition',False,compact=True)
track(n,B,.2,[[35.1, 8.3], [33.8, 12.3]],'SDA-final-uplink')
via(n,[33.8, 12.3],'SDA-final-uplink-transition',False,compact=False)
track(n,F,.2,[[33.8, 12.3], [30.8, 15.3], [30.6, 16.7]],'SDA-final-uplink')
via(n,[30.6, 16.7],'SDA-final-uplink-transition',False,compact=False)
track(n,B,.2,[[30.6, 16.7], [30.4, 17.4], [29.6, 28.2]],'SDA-final-uplink')
via(n,[29.6, 28.2],'SDA-final-uplink-transition',False,compact=False)
track(n,F,.2,[[29.6, 28.2], [30.1, 84.7], [31.6, 91.2]],'SDA-final-uplink')
via(n,[31.6, 91.2],'SDA-final-uplink-transition',False,compact=False)



# ['protection.gauge', 10] to ['ntc1_sense', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',10)
track(n,F,.2,[[29.91, 5.05], [32.3, 5.4], [32.7, 5.8], [32.7, 11.0]],'TH1-final-uplink')
via(n,[32.7, 11.0],'TH1-final-uplink-transition',False,compact=True)
track(n,B,.2,[[32.7, 11.0], [32.1, 12.7]],'TH1-final-uplink')
via(n,[32.1, 12.7],'TH1-final-uplink-transition',False,compact=False)
track(n,F,.2,[[32.1, 12.7], [27.4, 17.4]],'TH1-final-uplink')
via(n,[27.4, 17.4],'TH1-final-uplink-transition',False,compact=False)
track(n,B,.2,[[27.4, 17.4], [27.4, 26.0]],'TH1-final-uplink')
via(n,[27.4, 26.0],'TH1-final-uplink-transition',False,compact=False)
track(n,F,.2,[[27.4, 26.0], [17.7, 90.9], [17.4, 91.5], [16.6, 92.3], [15.7, 92.7], [11.7, 92.8], [10.0, 94.5]],'TH1-final-uplink')
# ['protection.gauge', 7] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',7)
track(n,F,.2,[[29.91, 3.55], [31.6, 3.4], [32.6, 4.1]],'ALRT-refined-uplink')
via(n,[32.6, 4.1],'ALRT-refined-uplink-transition',False,compact=True)
track(n,B,.2,[[32.6, 4.1], [35.4, 4.2], [38.8, 5.1]],'ALRT-refined-uplink')
via(n,[38.8, 5.1],'ALRT-refined-uplink-transition',False,compact=False)
track(n,F,.2,[[38.8, 5.1], [38.8, 8.9]],'ALRT-refined-uplink')
via(n,[38.8, 8.9],'ALRT-refined-uplink-transition',False,compact=False)
track(n,B,.2,[[38.8, 8.9], [38.5, 9.8], [39.2, 13.1], [40.2, 22.8]],'ALRT-refined-uplink')
via(n,[40.2, 22.8],'ALRT-refined-uplink-transition',False,compact=False)
track(n,F,.2,[[40.2, 22.8], [36.6, 54.4]],'ALRT-refined-uplink')
via(n,[36.6, 54.4],'ALRT-refined-uplink-transition',False,compact=False)
track(n,B,.2,[[36.6, 54.4], [34.9, 93.1]],'ALRT-refined-uplink')
via(n,[34.9, 93.1],'ALRT-refined-uplink-transition',False,compact=False)
track(n,F,.2,[[34.9, 93.1], [37.0, 97.1]],'ALRT-refined-uplink')
via(n,[37.0, 97.1],'ALRT-refined-uplink-transition',False,compact=False)



# ['protection.gauge', 13] to ['protection.c_reg3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',13)
# ['protection.c_supply', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_supply',2)
# ['protection.r_pfail', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_pfail',2)
# ['protection.r_aoldo', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_aoldo',2)

# ['protection.gauge', 13] to ['protection.c_reg3', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',13)
track(n,F,.2,[[29.25, 6.71], [29.8, 6.7]],'REG3-flipped-local')
via(n,[29.8, 6.7],'REG3-flipped-local-transition',False,compact=True)
track(n,B,.2,[[29.8, 6.7], [30.8, 3.8], [32.1, 2.5], [32.4, 2.5]],'REG3-flipped-local')
via(n,[32.4, 2.5],'REG3-flipped-local-transition',False,compact=True)
track(n,F,.2,[[32.4, 2.5], [33.8, 2.2]],'REG3-flipped-local')
# ['protection.c_supply', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_supply',2)
track(n,F,.2,[[24.28, 1.2], [23.6, 3.6], [23.7, 4.2], [26.0, 6.6]],'quiet-flipped-local')
track(n,B,.2,[[26.0, 6.6], [29.5, 7.3], [30.4, 7.2]],'quiet-flipped-local')
via(n,[30.4, 7.2],'quiet-flipped-local-transition',False,compact=True)
track(n,F,.2,[[30.4, 7.2], [31.8, 8.6]],'quiet-flipped-local')
via(n,[31.8, 8.6],'quiet-flipped-local-transition',False,compact=True)
track(n,B,.2,[[31.8, 8.6], [33.3, 8.3]],'quiet-flipped-local')
via(n,[33.3, 8.3],'quiet-flipped-local-transition',False,compact=True)
track(n,F,.2,[[33.3, 8.3], [34.2, 7.3], [34.2, 4.6], [33.8, 4.2]],'quiet-flipped-local')
# ['protection.gauge', 8] to ['protection.z_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',8)
track(n,F,.2,[[29.91, 4.05], [31.6, 4.1], [32.9, 5.4], [33.6, 5.4]],'SCL-relieved-final')
via(n,[33.6, 5.4],'SCL-relieved-final-transition',False,compact=True)
track(n,B,.2,[[33.6, 5.4], [34.8, 5.3]],'SCL-relieved-final')
via(n,[34.8, 5.3],'SCL-relieved-final-transition',False,compact=True)
track(n,F,.2,[[34.8, 5.3], [35.4, 5.9], [35.6, 6.6], [35.7, 8.1], [35.7, 11.1]],'SCL-relieved-final')
via(n,[35.7, 11.1],'SCL-relieved-final-transition',False,compact=True)
track(n,B,.2,[[35.7, 11.1], [35.6, 12.4]],'SCL-relieved-final')
via(n,[35.6, 12.4],'SCL-relieved-final-transition',False,compact=False)
track(n,F,.2,[[35.6, 12.4], [31.1, 17.4]],'SCL-relieved-final')
via(n,[31.1, 17.4],'SCL-relieved-final-transition',False,compact=False)
track(n,B,.2,[[31.1, 17.4], [31.1, 30.0], [42.6, 41.5], [42.9, 42.4], [42.9, 84.3], [50.7, 92.1], [50.8,92.4]],'SCL-relieved-final')


# ['protection.r_pfail', 2] to ['protection.c_supply', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_pfail',2)
track(n,F,.2,[[31.8, 6.83], [30.4, 7.2]],'PFAIL-final-return')
# ['protection.r_aoldo', 2] to ['protection.c_reg3', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.r_aoldo',2)
track(n,F,.2,[[34.43, 6.9], [34.2, 6.3]],'AOLDO-final-return')
# ['protection.c_supply', 1] to ['protection.r_supply', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.c_supply',1)
track(n,F,0.15,[[25.12, 1.2], [25.1, 1.1], [24.6, 0.6], [23.6, 0.6]],'IN-final-narrow')
via(n,[23.6, 0.6],'IN-final-narrow-transition',False,compact=False)
track(n,B,0.15,[[23.6, 0.6], [20.2, 3.3]],'IN-final-narrow')
via(n,[20.2, 3.3],'IN-final-narrow-transition',False,compact=False)
track(n,F,0.15,[[20.2, 3.3], [18.0, 5.3], [17.8, 5.4], [16.9, 5.4], [16.6, 5.1], [15.8, 4.9]],'IN-final-narrow')
via(n,[15.8, 4.9],'IN-final-narrow-transition',False,compact=False)
track(n,B,0.15,[[15.8, 4.9], [15.6, 6.1], [15.6, 7.1], [16.0, 7.8], [17.4, 9.2], [17.4, 12.5]],'IN-final-narrow')
via(n,[17.4, 12.5],'IN-final-narrow-transition',False,compact=False)
track(n,F,0.15,[[17.4, 12.5], [23.7, 12.5], [26.4, 15.2], [26.4, 15.8], [26.6, 16.1], [26.8, 16.2], [27.7, 16.2], [30.2, 13.7]],'IN-final-narrow')
via(n,[30.2, 13.7],'IN-final-narrow-transition',False,compact=False)
track(n,B,0.15,[[30.2, 13.7], [35.1, 13.9]],'IN-final-narrow')
via(n,[35.1, 13.9],'IN-final-narrow-transition',False,compact=False)
track(n,F,0.15,[[35.1, 13.9], [40.3, 17.4]],'IN-final-narrow')
via(n,[40.3, 17.4],'IN-final-narrow-transition',False,compact=False)
track(n,B,0.15,[[40.3, 17.4], [42.4, 22.6]],'IN-final-narrow')
via(n,[42.4, 22.6],'IN-final-narrow-transition',False,compact=False)
track(n,F,0.15,[[42.4, 22.6], [53.9, 22.6]],'IN-final-narrow')
via(n,[53.9, 22.6],'IN-final-narrow-transition',False,compact=False)
track(n,B,0.15,[[53.9, 22.6], [69.4, 10.6]],'IN-final-narrow')
via(n,[69.4, 10.6],'IN-final-narrow-transition',False,compact=False)
track(n,F,0.15,[[69.4, 10.6], [76.0, 6.9], [76.23, 6.5]],'IN-final-narrow')
# ['protection.r_pack_sense', 1] to ['protection.discharge_fet', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_pack_sense',1)
track(n,F,0.2,[[32.23, 1.6], [33.1, 1.1], [34.5, 0.7]],'PCKP-refined-final')
via(n,[34.5, 0.7],'PCKP-refined-final-transition',False,compact=True)
track(n,B,0.2,[[34.5, 0.7], [35.2, 0.5], [44.5, 0.6]],'PCKP-refined-final')
via(n,[44.5, 0.6],'PCKP-refined-final-transition',False,compact=False)
track(n,F,0.2,[[44.5, 0.6], [49.5, 0.4], [56.3, 0.4], [59.4, 3.525]],'PCKP-refined-final')

# PACK- clamp spine, distinct from RAW_GND gauge and NTC quiet return.
track(pack_ground,F,.8,[[43.69,94.5],[43.69,100.5]],'ESD-ground-front-bus')
track(pack_ground,F,.6,[[43.69,98],[44.59,98]],'ESD-ground-via-escape')
via(pack_ground,[44.59,98.0],'ESD-ground-transition',False)
track(pack_ground,B,.8,[[44.59,98],[49.5,97.4],[53,94.8]],'ESD-pack-return')
# ['ntc2_return', 1] to ['protection.c_supply', 2]; inspected scratch proposal, then actual DRC.
n=net('ntc2_return',1)
track(n,F,0.2,[[22.0, 94.5], [24.6, 91.9], [31.8, 91.9], [42.6, 91.0], [42.9, 90.9], [43.4, 90.3], [43.7, 89.7]],'NTC-separated-return')
# ['protection.gauge', 9] to ['protection.r_sda', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',9)
track(n,B,0.2,[[31.6, 91.2], [31.9, 96.1]],'SDA-resistor-tail')
via(n,[31.9, 96.1],'SDA-resistor-tail-transition',False,compact=False)
track(n,F,0.2,[[31.9, 96.1], [36.9, 98.4]],'SDA-resistor-tail')
via(n,[36.9, 98.4],'SDA-resistor-tail-transition',False,compact=False)
track(n,B,0.2,[[36.9, 98.4], [44.6, 98.8], [44.7, 98.9]],'SDA-resistor-tail')
via(n,[44.7, 98.9],'SDA-resistor-tail-transition',False,compact=False)
track(n,F,0.2,[[44.7, 98.9], [45.1, 99.1], [46.0, 99.1], [46.43, 98.5]],'SDA-resistor-tail')
# ['protection.gauge', 8] to ['protection.r_scl', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',8)
track(n,B,0.2,[[50.8, 92.4], [50.6, 94.0]],'SCL-resistor-tail')
via(n,[50.6, 94.0],'SCL-resistor-tail-transition',False,compact=False)
track(n,F,0.2,[[50.6, 94.0], [50.6, 95.8], [46.43, 100.5]],'SCL-resistor-tail')
# ['protection.gauge', 7] to ['protection.r_alert', 2]; inspected scratch proposal, then actual DRC.
n=net('protection.gauge',7)
track(n,B,0.2,[[37, 97.1], [36.3, 98.1], [36.1, 100.4], [36.3, 100.8], [36.9, 101.4], [38.7, 101.85]],'ALRT-resistor-tail')
via(n,[38.7, 101.85],'ALRT-resistor-tail-transition',False,compact=False)
track(n,F,0.2,[[38.7, 101.85], [38.93, 102.5]],'ALRT-resistor-tail')
# ['harness_gauge_sda', 1] to ['protection.z_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('harness_gauge_sda',1)
track(n,F,0.4,[[59.0, 94.8], [57.4, 96.5]],'SDA-harness-clamp')
via(n,[57.4, 96.5],'SDA-harness-clamp-transition',False,compact=False)
track(n,B,0.4,[[57.4, 96.5], [57.9, 97.4], [58.0, 98.1], [57.7, 99.0], [55.0, 101.7], [54.1, 102.0], [51.3, 102.5], [48.3, 102.5], [42.7, 99.4]],'SDA-harness-clamp')
via(n,[42.7, 99.4],'SDA-harness-clamp-transition',False,compact=False)
track(n,F,0.4,[[42.7, 99.4], [40.31, 94.5]],'SDA-harness-clamp')
# ['harness_gauge_scl', 1] to ['protection.z_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('harness_gauge_scl',1)
track(n,F,0.4,[[65.0, 94.8], [63.3, 96.5]],'SCL-harness-clamp')
via(n,[63.3, 96.5],'SCL-harness-clamp-transition',False,compact=False)
track(n,B,0.4,[[63.3, 96.5], [55.1, 102.4], [52.5, 103.0], [51.3, 103.2], [46.0, 103.2], [42.6, 100.2]],'SCL-harness-clamp')
via(n,[42.6, 100.2],'SCL-harness-clamp-transition',False,compact=False)
track(n,F,0.4,[[42.6, 100.2], [42.4, 100.1], [42.0, 99.7], [40.31, 97.5]],'SCL-harness-clamp')
# ['protection.r_sda', 1] to ['protection.z_sda', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_sda',1)
track(n,F,0.2,[[45.57, 98.5], [44.7, 96.9]],'SDA-series-connection')
via(n,[44.7, 96.9],'SDA-series-connection-transition',False,compact=False)
track(n,B,0.2,[[44.7, 96.9], [41.2, 94.6]],'SDA-series-connection')
via(n,[41.2, 94.6],'SDA-series-connection-transition',False,compact=False)
track(n,F,0.2,[[41.2, 94.6], [40.31, 94.5]],'SDA-series-connection')
# ['protection.r_scl', 1] to ['protection.z_scl', 1]; inspected scratch proposal, then actual DRC.
n=net('protection.r_scl',1)
track(n,F,0.2,[[45.57, 100.5], [45.7, 99.8]],'SCL-series-connection')
via(n,[45.7, 99.8],'SCL-series-connection-transition',False,compact=False)
track(n,B,0.2,[[45.7, 99.8], [47.6, 101.3]],'SCL-series-connection')
via(n,[47.6, 101.3],'SCL-series-connection-transition',False,compact=False)
track(n,F,0.2,[[47.6, 101.3], [46.9, 101.6], [45.3, 101.9]],'SCL-series-connection')
via(n,[45.3, 101.9],'SCL-series-connection-transition',False,compact=False)
track(n,B,0.2,[[45.3, 101.9], [42.6, 100.2]],'SCL-series-connection')
track(n,F,0.2,[[42.6, 100.2], [42.1, 99.7], [40.31, 97.5]],'SCL-series-connection')
# ['gauge_alert_test', 1] to ['protection.z_alert', 1]; inspected scratch proposal, then actual DRC.
n=net('gauge_alert_test',1)
track(n,F,0.4,[[37.7, 100.0], [40.31, 100.5]],'ALRT-test-clamp')
