# Longer motor/encoder service leads — 21 October 2026

Work-only sourcing recommendation; no BOM, cable length, circuit or order has been changed. Mechanical still owns the measured complete route and service slack.

| Use | Candidate | Construction | Observed availability/cost |
|---|---|---|---|
| Fixed motor-side power | Molex **2147581022** | 300 mm male-to-pigtail, 2-way dual-row Micro-Fit 3.0, 18 AWG UL1061, tin | DigiKey US page crawled today: 1,224 stock; $2.08 each, $1.769 at 10 |
| Encoder | Molex **151340403** / 0151340403 | 300 mm female-to-female, 4-way PicoBlade, 28 AWG UL1061, tin | TME indexed page: 22 stock, $8.41 each, $6.58 at 5; the tool reports a month-old crawl, so treat this as a lead to refresh, not reserved/current confirmed stock |

The motor assembly avoids cutting a 150 mm male-to-male cable in half. Molex's [2147581022 product](https://www.molex.com/en-us/products/part-detail/2147581022) identifies the length, gauge and gender. Its [manufacturer-generated specification](https://www.molex.com/en-us/products/part-detail/2147581022?display=pdf), generated 14 March 2025, explicitly lists **43025** as the mating receptacle family and **1.85 mm maximum insulation diameter**. That supports compatibility with the selected 43025-family female assembly, subject to final keyed 2-way pin-number/orientation verification. The page's 8.5 A contact maximum does not qualify the wire bundle or enclosed motor duty. Exact length datum/tolerance and stripped-end geometry still need the sales drawing or sample. [DigiKey stock/price](https://www.digikey.com/en/products/detail/molex/2147581022/12180481).

The encoder [manufacturer product](https://www.molex.com/en-us/products/part-detail/151340403) confirms 300 mm, 4 circuits, female–female, 1.25 mm pitch and 28 AWG UL1061. Use the full assembly with only the far connector removed if a soldered motor termination is chosen; do not halve it and silently lose the needed length. [TME listing](https://www.tme.eu/en/details/mx-15134-0403/wire-to-board-cable-assemblies/molex/151340403/) provides the indexed stock/price above. Its 1 A contact rating is sufficient only as a catalog screen for the provisional 30 mA encoder rail; correct pin order, actual encoder voltage and intact signal behavior remain to be checked. No unknown factory motor-wire length is credited.

For both, route length must include the fixed termination datum, bend allowances, retained strain relief, complete unplug/service motion and final trimming. A nominal 300 mm product does not itself establish that the final route fits. Keep the motor's 1.85 mm insulation envelope; no smaller wire OD is inferred from the gauge. Home-sensor lead length remains unspecified because its endpoint is not yet selected.
