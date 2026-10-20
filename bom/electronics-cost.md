# Electronics cost sensitivity

**Planning calculation only. Not a quote or orderable BOM.**

Historical architecture sensitivity. The current three-board component demand is tracked in [captured parts](README.md#captured-electronic-parts); the older allowance below is not the current device budget.

Single assembled PCB baseline for comparison only; proposed separate protected carrier adds PCB, setup and interconnect costs.

The five major candidate ICs total **$14.85 per board** using the live public 1+ prices, before attrition/MOQ. The remaining $10.00 component allowance and $2.00 bare-board allowance are estimates, not sourced BOM totals.

| Eight-board scenario | Economic | Standard, single side |
|---|---:|---:|
| Assembly fee model | $58.96 | $122.74 |
| Assembly fee per board | $7.37 | $15.34 |
| Board + components + fee allowance, each | $34.22 | $42.20 |
| Eight-board allowance subtotal | $273.79 | $337.57 |

Assumes 45 unique parts, 15 ordinary Extended parts and 250 SMT joints per board. Basic/Preferred Extended feeder exemptions apply only where JLC confirms them. Standard includes a $16.42 fixture and $0.50 packing allowance. Quote-specific X-ray, special handling, storage, through-hole work, shipping and tax are excluded. [Published fee table](https://jlcpcb.com/help/article/pcb-assembly-price), [Basic/Preferred policy](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype).

The WROOM module retains Economic eligibility in the observed catalog. MINI is Standard Only. A smaller board can therefore cost more as a complete assembly. Black mask remains a preference: compare a black-board quote with the cheapest eligible color/finish before deciding.

| Shared infrastructure assumption | Extra per installed system | Extra spread over eight units |
|---|---:|---:|
| Additional Thread router budget | $0 | $0.00 |
| Additional Thread router budget | $50 | $6.25 |
| Additional Thread router budget | $100 | $12.50 |

Router values are sensitivity inputs, not product recommendations or current quotes. The user's existing HomePod may be compatible; confirm its model.

| Gauge setup comparison for eight units | Gauge ICs | Mandatory adapter assumption | Subtotal |
|---|---:|---:|---:|
| Provisional MAX17320G22+, direct host | $46.72 | $0 incremental | $46.72 |
| BQ40Z50-R2 + TI EV2400 | $15.66 | $208.95 | $224.61 |

MAX costs $31.06 more in ICs but $177.89 less including the dated EV2400 price. The $0 adapter figure assumes commissioning through the controller's USB/I2C bridge, which remains to be validated; it does not mean free bench equipment or zero implementation time. TI's supported setup needs Windows; MKS adapter pricing remains unverified. [Commissioning evidence](../docs/electrical/gauge-commissioning.md).

The new holder request is priced separately: TH MYOUNG A5 holders cost about $7.35/device at48 pieces plus about $0.65/device THT labor for an eight-device batch. SMT B1 holders cost $5.45/device but are Standard Only. Neither holder is yet qualified for motor current; carrier PCB/setup, fuses and connectors are additional. These figures are **not included above**. [Carrier comparison](../docs/electrical/battery-carrier-trade.md).

Required items still outside this subtotal:

- Actual PCB fabrication quote and any panel tooling
- Separate battery carrier fabrication and additional PCBA setup/feeder costs
- Six battery holders per unit, cell-level fuses, interconnects and retention hardware
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
