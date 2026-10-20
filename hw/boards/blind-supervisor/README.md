# Motor supervision capture

**UNVERIFIED block, not a complete circuit or fabrication release.** Four ICs and ten passive parts compile in atopile 0.15.9. An independent audit checks all 49 PCB pins and the generated BOM. No motor has been connected.

The TPS3430 window watchdog watches a heartbeat owned solely by the healthy motor-control iteration. A missed or excessively fast heartbeat asserts WDO. This drives TPS3808G33 manual reset; its reset output disables the motor through an AUP logic gate and resets the C6. The supervisor holds reset after WDO releases, including when the MCU's reset state disables the watchdog early. Its separate voltage threshold also watches 3.3 V.

| State | Request | Watchdog | Driver |
|---|---|---|---|
| Idle, boot, flashing | HIGH via pull-up | Disabled | Disabled |
| Preparing a move | LOW, direction pins already `00` | Enabled | Awake, no commanded movement |
| Moving with healthy control iterations | LOW | Falling edges about every 20 ms | PWM permitted |
| Missed/early heartbeat or brownout | Reset asserted | Fault/reset | Disabled |
| After reset releases | HIGH via reset/default pull-up | Disabled | Stays disabled until a fresh command |

The request drives both watchdog policy and motor gating through the same buffered signal. GPIO17 therefore remains available for charger IRQ. The buffer addresses the watchdog SET input's unusually low 0.25 V LOW limit. The output gate is SN74AUP1G97, specified down to 0.8 V, so it continues operating below the motor driver's 1.5 V HIGH threshold. Pin maps follow [TPS3430](https://www.ti.com/lit/ds/symlink/tps3430.pdf), [TPS3808](https://www.ti.com/lit/ds/symlink/tps3808.pdf), [AUP gate](https://www.ti.com/lit/ds/symlink/sn74aup1g97.pdf) and [dual input buffer](https://www.ti.com/lit/ds/symlink/sn74lvc2g17.pdf) primary data sheets.

The 120 pF C0G timing capacitor gives a calculated upper window of about 57.74–71.35 ms and lower-window maximum of 8.92 ms, including component tolerance, temperature and a provisional 5 pF layout allowance. Firmware should feed on healthy iterations only, approximately every 20 ms, and refuse catch-up pulses. The proposed permitted edge interval is 10–45 ms. Before arming, WDI must already be HIGH while the request is HIGH. The first checked falling edge has no lower-window restriction and must follow watchdog setup and precede the earliest upper boundary. These calculations do not establish a measured 100 ms terminal cutoff; the driver turnoff delay, reset propagation, layout and coasting still need qualification.

TPS3808G33 has a minimum calculated trip threshold of 3.024 V and worst release threshold of 3.194 V. A 3.3 V ±2% supply leaves about 40 mV of static release margin. The intended TPS62902 internal fixed divider avoids external feedback tolerance; radio transients remain a routed-board test. The gate limits this block to −40…85°C; battery charging limits are narrower.

**Integration requirements:** remove the earlier C6 EN 1 µF RC capacitor when this supervisor supplies reset timing, or design a separately rated discharge path. Do not hang that capacitor directly on the 5 mA-rated reset output. Maintain the external request pull-up. Set WDI HIGH and both motor inputs LOW, then validate reference, power, faults and a fresh command before lowering the request. Apply PWM only after a healthy heartbeat and the driver's wake delay. Raise the request first when stopping. Reset invalidates the previous motion session; boot code must not replay an old command. The gate does not independently detect a mechanically stuck motor or an electrically damaged MCU output.

Further gaps are recorded in `supervisor-verification.json`: no full-controller ERC, routed PCB/DRC, measured parasitics, rail-transient qualification or physical fault injection. In particular, scope the request, reset, nSLEEP and motor terminals together during task freeze, interrupt lockout, debug halt and reset release. A green build is not that evidence.

```sh
ato build hw/boards/blind-supervisor -b supervisor-test --frozen -v
python3 hw/boards/blind-supervisor/check_supervisor.py
python3 -m unittest discover -s hw/boards/blind-supervisor -p 'test_*.py' -v
```

The dated sourcing comparison is in `bom/electronics-supervisor-sourcing.json`. TPS3431 catalog stock was insufficient for eight units at capture time; TPS3430 was shown eligible for Economic and Standard assembly. Prices exclude feeders, attrition, assembly and shipping. Nothing has been reserved or purchased.

The native KiCad schematic in `hw/schematics/blind-supervisor` independently exports all 49 physical pin connections. Its two explicit ERC findings are the externally supplied 3V3 and ground; there are no exclusions or artificial power flags. The integrated IO/supervisor/motor capture is in `hw/boards/blind-assembly`, including the removed EN capacitor and physical-pin boundary audit.
