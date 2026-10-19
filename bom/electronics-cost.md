# Electronics cost sensitivity

**Planning calculation only. Not a quote or orderable BOM.**

The five major candidate ICs total **$10.97 per board** using the live public 1+ prices, before attrition/MOQ. The remaining $10.00 component allowance and $2.00 bare-board allowance are estimates, not sourced BOM totals.

| Eight-board scenario | Economic | Standard, single side |
|---|---:|---:|
| Assembly fee model | $58.96 | $122.74 |
| Assembly fee per board | $7.37 | $15.34 |
| Board + components + fee allowance, each | $30.34 | $38.31 |
| Eight-board allowance subtotal | $242.73 | $306.51 |

Assumes 45 unique parts, 15 ordinary Extended parts and 250 SMT joints per board. Basic/Preferred Extended feeder exemptions apply only where JLC confirms them. Standard includes a $16.42 fixture and $0.50 packing allowance. Quote-specific X-ray, special handling, storage, through-hole work, shipping and tax are excluded. [Published fee table](https://jlcpcb.com/help/article/pcb-assembly-price), [Basic/Preferred policy](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype).

The WROOM module retains Economic eligibility in the observed catalog. MINI is Standard Only. A smaller board can therefore cost more as a complete assembly. Black mask remains a preference: compare a black-board quote with the cheapest eligible color/finish before deciding.

| Shared infrastructure assumption | Extra per installed system | Extra spread over eight units |
|---|---:|---:|
| Additional Thread router budget | $0 | $0.00 |
| Additional Thread router budget | $50 | $6.25 |
| Additional Thread router budget | $100 | $12.50 |
| Gauge setup tools budget | $0 | $0.00 |
| Gauge setup tools budget | $100 | $12.50 |
| Gauge setup tools budget | $250 | $31.25 |

These infrastructure values are sensitivity inputs, not product recommendations or current tool quotes. The user's existing HomePod may be compatible; confirm its model. Gauge commissioning may need a supported adapter and chemistry/learning work even though the gauge IC itself is inexpensive.

Required items still outside this subtotal:

- Actual PCB fabrication quote and any panel tooling
- Actual complete line-item passive, protection FET, PD sink, connector and inductor BOM
- Component attrition and MOQ rounding
- X-ray inspection, handling and special component fees after quote
- Shipping, tax and import charges
- Cell pack fuse, insulation, nickel/interconnects, sense harness and thermistors
- Existing motor/cell inventory reconciliation
- Enclosure material, screws, bearings and wheel hardware
- USB PD supply and cable if existing supplies are unsuitable
- Gauge adapter, chemistry characterization, test fixture and load equipment

Regenerate from `bom/electronics-cost-model.json` and the dated sourcing snapshot with `python3 bom/electronics_cost.py`.
