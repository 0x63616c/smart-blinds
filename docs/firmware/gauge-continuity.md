# Battery observation after MCU light sleep

The read-only module is now integrated into the experimental C6 motion runtime
through the joint power mailbox. Power freshness rules and motor-disabled
defaults are unchanged. There is no supplied production qualification record. It has no
write, flag-clear, gauge-wake, NVM, charger or motor-control operation.

The previous runtime restarted gauge history after every idle gap, adding
2.8–4 seconds for the qualified thermal conversion period. The new owner can
retain that history across a proven bounded idle; it still requires full cold
warmup after a longer clean idle. The MAX17320 is supplied independently from
the raw pack and can continue its own measurements during C6 light sleep.
Preserving that *history* can avoid repeated warmup; reusing a cached battery
reading cannot.

## Qualification and the private continuity ticket

`firmware/include/smart_blinds/gauge_continuity.hpp` and
`firmware/src/gauge_continuity.cpp` add a read-only bounded capture and a wrapper
around `GaugeMonitor`, with its existing admission predicates shared by
complete and incremental validation.

The default profile is invalid. A trusted local commissioning path would have
to supply the existing boot-bound pack profile, gauge ROM ID, exact live/shadow
configuration, measured maximum light-sleep interval and verified continuous
conversion behavior. It must also establish exclusive bus/write ownership:
no other code or fixture may change mode/configuration or clear sticky fault
evidence without first invalidating continuity.

The monitor binds boot, bus generation, monitoring-session generation, installed
pack and qualification. These are local evidence, not network approvals.
It keeps a private, non-copyable RAM ticket only after the original complete
warmup and a fresh healthy observation. It cannot export or restore that ticket.

1. `park_light_sleep` requires a fresh ready observation and unchanged context.
   The caller must establish that only the MCU sleeps and the gauge remains
   independently powered in its qualified mode. Readiness is withdrawn.
2. `resume_light_sleep` consumes that transition, checks context and elapsed
   time, and demands a complete new read beginning at or after resume.
3. Both ends of the capture must match identity, configuration and health
   requirements. Only then is the original active-history retained.
4. Any unknown reset, bus rebuild, monitoring-session change, pack intervention,
   configuration writer, stale/repeated/overlapping capture, mode/fault change
   or ambiguous power transition latches unavailable. No later healthy read
   repairs the ticket. Recovery requires a new trusted monitor session and
   the original full warmup.

Snapshots cannot prove that an external writer changed and restored settings
or cleared fault history between reads. Exclusive ownership and physical
continuity qualification are therefore substantive gates, not implementation
claims. A radio connection change alone is not a battery conversion timestamp;
any replacement or ambiguity in the monitoring owner must invalidate context.

## Exact register evidence

Source: [ADI MAX17320 Rev12 (7/25)](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf),
pages 21, 76, 91–94, 99, 108–109, 113 and 120–121. The locally inspected PDF SHA-256 is
`6477d1dea98912172a0dfb313d65ab148711c39806eb130ad8ab6dc9a6b41e85`.
Tables 67–69 were checked visually for merged Config2 fields.

All configuration values must also equal the complete commissioned values.

| Register | Additional requirement |
|---|---|
| nConfig `0x1B0` | Mask `0x0168` clear: reserved D8, COMMSH D6, ALSH D5, FTHRM D3; fixed D4 set |
| Config `0x00B` | Mask `0x81EA` clear: reserved D15/D8/D5/D1, SHIP D7, COMMSH D6, FTHRM D3; ETHRM D4 set |
| Config2 `0x0AB` | Mask `0xC023` clear: POR_CMD D15, reserved D14/D5/D1/D0; fixed D4 set |
| nHibCfg `0x1BB` | EnHib D15 clear |
| Status `0x000`, Status2 `0x0B0`, FStat `0x03D` | POR D1, Hib D1 and DNR D0 clear respectively |
| ProtStatus `0x0D9`, ProtAlrt `0x0AF` | Mask `0xDFFF` clear; only Full D13 allowed |
| nBattStatus `0x1A8`, FETStatus `0x0F1` | Permanent-failure high byte clear; both low FET-on bits set |
| nROMID0…3 `0x1BC`…`0x1BF` | All four words match the commissioned gauge; reject all-zero/all-one identity |

Read order is monotonic start, guard A, payload, guard B, monotonic finish:

```text
guard: 000 0AF 0D9 0B0 03D 0F1 1A8 00B 0AB 1B0 1BB
       1BC 1BD 1BE 1BF 021 1B5 1B8 1B9 1CF 1CA
payload: 006 0DA 01C 01B 0D8 0D7 0D6 0DB 13A 139
```

These are logical register addresses. Normal addresses below `0x100` map to
7-bit I²C `0x36`; shadow addresses map to `0x0B` with the low pointer byte.
The payload is SOC, pack voltage, current, selected temperature, three cells,
protected voltage and the two individual thermistors.

There are 52 word reads, each bounded to 10 ms, with a total ceiling of 250 ms.
The bus implementation must enforce the per-transfer timeout; the portable
reader also checks actual time after each transfer. It cannot interrupt a
broken bus implementation which never returns. First error stops all further
transfers. Both guards are checked independently; fault bits are ORed and
FET-on bits ANDed into the legacy evidence.

The new report retains existing worst-case conversion-age bounds:
`capture_start - qualified_period`. It does not call a read a conversion.
Existing limits remain **250 ms observation age, 750 ms voltage age and 4.25 s
temperature age**. Constant thermal values are valid; a changing value is not
proof of a conversion deadline. DNR and the gauge Timer are not ADC timestamps.

## Completed reports during active refresh

The standalone owned adapter retains exactly the previous completed publication
during an ordinary active read. It preserves that report's original source
times, values and binding; a new ready serial supersedes it only after the
whole capture passes. The old report still expires at its original age limit.
This avoids withdrawing it for all 52 transactions merely because a healthy
refresh began.

A synchronous observer revokes the epoch at the first detected read/clock
failure or received guard/value that proves an existing violation. Both
guards are checked word by word; cross-field checks wait only until their
required operands from this capture have arrived. Full final validation still
runs. Partial evidence can reject but cannot grant readiness. A shared atomic
first-fault latch preserves the original diagnostic through retirement and
later failures.

Park/resume and cancellation still withdraw the old publication. A late
successful transfer cannot restore a retired generation. Unreported worker
loss remains bounded by source-age expiry; the code cannot immediately detect
a task which silently stops or interrupt an SDK call which never returns.

The runtime instead uses the [joint mailbox](power-mailbox.md), which publishes
the completed charger/gauge pair and sole serial together. Control and status
take independent immediate snapshots through a pinned selector. The sensor owner
closes the window before parking; control releases PM locks only after matching
closure and actual OFF evidence. A clean expired interval retires the old
session, closes its handles on their owner, and reconstructs a new cold session
without reusing its report. No qualification records or button admission are added.
See the [sensor runtime](sensor-runtime.md) for the charger watchdog lifetime.

## Response and energy targets

Ordinary local motion within 250 ms of a valid tap release is a **target** only
with qualified continuity, a fresh complete gauge/charger read and normal
encoder/watchdog arming. The 52-read ceiling alone does not guarantee it.
Cold/uncertain state still needs full warmup or supervised recovery; do not
silently queue a normal action to run after an unrelated recovery.

Raw STOP must bypass this warmup and reach the existing bounded control path;
the target remains at most 20 ms plus physical inhibit propagation, pending
hardware measurement. This module implements neither button handling nor
motion binding.

Full-active gauge current is 38 µA typical, 57 µA maximum at ≤50°C, excluding pulsed
thermistor measurement. At 10.8 V this is approximately 0.591/0.886 Wh over 60 days.
Full-active mode is already required by the current pack profile. Retaining
the software ticket requires no periodic MCU/radio poll during idle. Actual
thermistor, regulator, protection and leakage costs remain measurement gates.
Forced thermistor bias remains disabled.

## Tests and remaining work

`gauge_continuity_tests` covers successful bounded read order, every one of the
52 read failures and clock reversals, per-transfer/total deadlines, forbidden
mode bits, cold history, repeated qualified sleep, unchanged temperatures,
new source-age calculations, stale/future/replayed/overlapping captures,
identity/configuration/fault changes in either guard, context loss and ticket
reuse. It also checks every bit mutation of all head/tail guard words against
independent original masks, and all 65,536 raw values of each payload word
against a frozen pre-change numeric policy. Healthy later reads cannot
silently repair a failed instance.

The [read-only C6 adapter](../../firmware/esp-idf/components/gauge_continuity/README.md)
implements bounded capture with explicit task/epoch ownership and publication
invalidation in the qualified runtime branch. Default and bench C6 builds
compile that wiring; empty records still prohibit initialization. Host tests
also run the actual sensor/control workers over a fake SDK, including short
idle, hours-long cold restart, independent readers and blocked-transfer closure.
Physical conversion continuity, handoff timing and installed pack qualification
remain required. The separate original
Thread-labelled host group timing failure remains unresolved; this module does
not explain that failure or validate C6 scheduling or battery life.
