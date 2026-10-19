#!/usr/bin/env python3
"""Render an explicitly provisional eight-board cost sensitivity model."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent
model = json.loads((base / "electronics-cost-model.json").read_text())
parts = json.loads((base / "electronics-sourcing-snapshot.json").read_text())["parts"]
by_mpn = {part["mpn"]: part for part in parts}
n, a, f = model["units"], model["assumptions"], model["fees"]
core = sum(by_mpn[mpn]["metadata"]["initialPrice"] for mpn in model["selected_candidate_mpns"])
joints = n * a["smt_joints_per_unit"] * f["smt_per_joint"]
economic = f["economic_setup"] + f["economic_stencil"] + a["ordinary_extended_part_numbers"] * f["economic_extended_feeder"] + joints
standard = f["standard_single_side_setup"] + f["standard_single_side_stencil"] + a["unique_total_part_numbers"] * f["standard_feeder_all_unique"] + joints + a["standard_fixture_allowance_usd"] + a["standard_packing_allowance_usd"]
component_allowance = core + a["other_components_per_unit_usd"]
lines = ["# Electronics cost sensitivity", "", "**Planning calculation only. Not a quote or orderable BOM.**", "",
         "The five major candidate ICs total **$%.2f per board** using the live public 1+ prices, before attrition/MOQ. The remaining $%.2f component allowance and $%.2f bare-board allowance are estimates, not sourced BOM totals." % (core,a["other_components_per_unit_usd"],a["pcb_per_unit_usd"]), "",
         "| Eight-board scenario | Economic | Standard, single side |", "|---|---:|---:|",
         f"| Assembly fee model | ${economic:.2f} | ${standard:.2f} |",
         f"| Assembly fee per board | ${economic/n:.2f} | ${standard/n:.2f} |",
         f"| Board + components + fee allowance, each | ${component_allowance+a['pcb_per_unit_usd']+economic/n:.2f} | ${component_allowance+a['pcb_per_unit_usd']+standard/n:.2f} |",
         f"| Eight-board allowance subtotal | ${n*(component_allowance+a['pcb_per_unit_usd'])+economic:.2f} | ${n*(component_allowance+a['pcb_per_unit_usd'])+standard:.2f} |", "",
         "Assumes 45 unique parts, 15 ordinary Extended parts and 250 SMT joints per board. Basic/Preferred Extended feeder exemptions apply only where JLC confirms them. Standard includes a $16.42 fixture and $0.50 packing allowance. Quote-specific X-ray, special handling, storage, through-hole work, shipping and tax are excluded. [Published fee table](https://jlcpcb.com/help/article/pcb-assembly-price), [Basic/Preferred policy](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype).", "",
         "The WROOM module retains Economic eligibility in the observed catalog. MINI is Standard Only. A smaller board can therefore cost more as a complete assembly. Black mask remains a preference: compare a black-board quote with the cheapest eligible color/finish before deciding.", "",
         "| Shared infrastructure assumption | Extra per installed system | Extra spread over eight units |", "|---|---:|---:|"]
for label,key in [("Additional Thread router","added_thread_router_budget_usd"),("Gauge setup tools","shared_gauge_setup_tools_budget_usd")]:
    for value in a[key]:
        lines.append(f"| {label} budget | ${value:.0f} | ${value/n:.2f} |")
lines += ["", "These infrastructure values are sensitivity inputs, not product recommendations or current tool quotes. The user's existing HomePod may be compatible; confirm its model. Gauge commissioning may need a supported adapter and chemistry/learning work even though the gauge IC itself is inexpensive.", "", "Required items still outside this subtotal:", ""]
lines += ["- " + item for item in model["unpriced_required_items"]]
lines += ["", "Regenerate from `bom/electronics-cost-model.json` and the dated sourcing snapshot with `python3 bom/electronics_cost.py`.", ""]
(base / "electronics-cost.md").write_text("\n".join(lines))
print(f"Core ICs ${core:.2f}; eight-unit assembly model Economic ${economic:.2f}, Standard ${standard:.2f}")
