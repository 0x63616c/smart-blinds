# Protected carrier checks

`python3 hw/sim/blind-carrier/checks.py --check` verifies fixed part identity,
optional local BOM, the independently authored physical-pin contract and thermal/
balancing arithmetic. It detects a shunt bypass, wrong3S tap short, shorted FET gate
controls and bypassed branch fuse. It also checks the corrected fuse/shunt pads.

The pack-current envelope includes motor plus logic. Rds hot scaling, holder
resistance and equal current division are explicit assumptions. No short-circuit
current, fuse total-clearing energy, MOSFET SOA, gauge accuracy, holder temperature,
cell-insertion fault or physical safety is proven. All open gates are retained in
`results.json`; changing the assumed resistance cannot turn them into tested facts.
