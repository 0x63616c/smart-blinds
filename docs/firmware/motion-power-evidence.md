# Motion power evidence

The motion path now has a concrete host-tested assessor for actual MAX17320
readback and BQ25798 charge-OFF status. It does not ship a qualified pack profile,
clear POR, program NVM, enable charging or instantiate a motor. The radio session
will consume this evidence; its command binding is a separate next checkpoint.

## Read time and conversion age

A successful I2C transfer is evidence that a register was read, not that its ADC
just converted. MAX17320 active-mode current measurements update about every
351.5 ms; each external thermistor updates every 1.4 s times the enabled
thermistor count. With two thermistors that is about 2.8 s per channel. The pack
voltage channels have another important condition: without `nPackCfg.BtPkEn`,
Batt/PCKP update only every 22.4 s. These primary timings are nominal operating
behavior, not our measured worst-case bound. [ADI Rev12 pp79,95–100](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)

`PackProfile` therefore requires explicit full-profile verification bound to
this MCU boot, verified thermistor placement, a verified timing model, 3S plus
exactly TH1/TH2, `BtPkEn`, enabled protection/checksum, disabled hibernate and
10 mΩ sense resistance. Exact identity and configuration words must match live
readback. Proposed period bounds are 400 ms for voltage and 3.2 s for the two
thermistors, **unqualified until measured**. No code sets those approval flags
from raw transport success. The local `pack_binding` is an association supplied
by the commissioning path, not a cryptographic identity read from the gauge.
Full protection-register verification and its trusted record loader remain
required; the existing partial gauge tool cannot issue this profile.

`GaugeMonitor` waits one full qualified temperature period after first observing
a healthy active device (or after an observed bus/profile/reset/mode failure).
It carries three separate times:

| Evidence | Meaning |
|---|---|
| `observed_us` | Beginning of the successful register capture; protection/bus observation must be no older than 250 ms |
| `voltage_earliest_us` | Capture start minus the qualified worst-case voltage update interval |
| `temperature_earliest_us` | Capture start minus the qualified worst-case temperature update interval |

These earliest times deliberately precede receipt. Reading unchanged values
again can update the observation time, but does not make the earlier conversion
bounds equal to receipt. The assessor rejects future/backward times, stale
capture, wrong profile, POR, data-not-ready, hibernate, disabled FETs, protection
faults, cell range/imbalance, pack versus protected/cell voltage inconsistency,
and either thermistor outside the conservative 10–40°C window. `Full` alone is
not a discharging fault; independent protection and the regeneration clamp must
still be physically qualified. Undefined/reserved status bits are not treated
as known faults. [ADI status and protection registers, pp91–94,120](https://www.analog.com/media/en/technical-documentation/data-sheets/max17320.pdf)

The C6 read-only reader now captures 23 registers and repeats five status words
at the end. It ORs observed fault/mode bits and ANDs FET-on status across that
capture, preventing a visible transition from disappearing. Individual
thermistors come from 13Ah/139h through the documented second I2C address. It
retains bounded transfers and no data-register writes. POR requires an explicit
future recovery path; this component does not silently clear it.

Gauge current is slow pack telemetry. It is never the motor jam signal. The
C6 motion adapter independently samples the fast DRV8874 IPROPI ADC branch,
with a qualified gain/offset and saturation checks. Out-of-range SOC is absent,
not converted into a plausible battery percentage. Unqualified gauge values
remain diagnostic and are not a validated SOC accuracy claim.

## Battery operation while USB is absent

The existing charger `capture()` intentionally requires a present qualified USB
source and a fresh ADC conversion for charging review. It is unsuitable as the
condition for moving an unplugged blind.

The separate `capture_off()` first requests/verifies independent CE OFF, then
checks the configured register image and actual status. It accepts absent USB
and ordinary insertion/removal flags; charging, OTG, backup, watchdog expiry,
missing battery, protection/thermal/timer faults and profile mismatches fail.
The only write is the documented watchdog reset after the initial inspection;
EN_CHG stays zero, ADC is not started, and the image is checked again afterward.
This observation has a 250 ms acceptance budget. It neither asserts source
entitlement nor permits charging. The worker must publish failed reads too,
replacing prior good evidence immediately. [TI BQ25798 register map, Sections7.5.1.11–7.5.1.35](https://www.ti.com/lit/ds/symlink/bq25798.pdf)

`motion_power()` joins that report to the gauge assessment. It carries the
older status-observation time into the executor's existing 250 ms
`power_sampled_us` check while independently validating the slower voltage and
temperature bounds. This timestamp represents fresh protection/configuration
observation, not fresh ADC conversion. Charging remains disabled throughout
motion. A dedicated sensor worker performs I2C; the motor/heartbeat task receives
bounded snapshots and never waits on that bus. Loss/staleness of either report
removes readiness before another control heartbeat.

## Validation

All eight host CTest targets pass, including source-age and qualification tests,
invalid individual cells/thermistors, reset/hibernate/FET faults, stale/future
captures, loss/reconnection warmup, unplugged charger status, every injected
OFF-capture transfer failure, charge/OTG/profile corruption and timeout. Test
profiles and data are synthetic fixtures, not commissioned hardware settings.
The modified C6 reader and charger wrapper await their fresh pinned SDK build.
No pack, bus, charger, motor or owner network was accessed.
