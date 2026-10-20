# Explicit bench C6 motion adapter

`BenchC6Io` implements the portable `MotionIo` interface with actual ESP-IDF
PCNT, MCPWM, ADC, GPIO and power-management calls. It is **not instantiated by
any shipped application**. The independent `board_io` component remains the
motor-disabled bring-up implementation. Never instantiate both on one board.

There are two initialization gates: `CONFIG_BLINDS_BENCH_MOTION` (default off,
requires IDF power management) and a `port::Profile` containing an explicit
qualification ID, measured motor/encoder polarity, a maximum duty ceiling,
and measured current-sensor gain/offset. An off build's `initialize()` returns
false before touching a pin. A valid software profile is an assertion supplied
by the bench harness; it is not proof that the measurements happened.

## Implemented behavior

- Initialization asserts motor request, charge and encoder OFF first, holds WDI
  HIGH, then allocates stopped PCNT and forced-LOW PWM. Native USB remains the
  console; no UART0 logging may take ownership of GPIO16/WDI.
- Quadrature PCNT uses two channels, signed accumulation, ±30,000 overflow
  points, and a provisional 1 µs input filter. Initialization temporarily locks
  APB at its maximum while setting that filter. The PCNT driver holds its own
  APB lock while enabled. Running readback also verifies the clock-dependent
  filter threshold. `set_counter_origin()` binds a new monotonic sensing epoch
  to a normalized coordinate; it never validates physical position.
- PWM is 20 kHz, 500 ticks at 10 MHz, with direction-specific drive/coast.
  Both bridge inputs are forced LOW during arming and stopping. Only one may
  be released to PWM. A reversal requires explicit coast before the opposite
  channel is accepted. A requested duty is rounded down, never up; below one
  tick it remains coast. This adapter never requests the `11` braking state.
- The adapter reads C6 GPIO routing and pad levels, PCR clock source/divider,
  MCPWM period/action/force/compare registers, and PCNT routing/actions/limits/
  pause/filter/event registers. An unapplied compare shadow is not accepted as
  the requested duty. Readback deliberately accepts either phase of the active
  PWM pad, while requiring the inactive pad LOW.
- `heartbeat_pulse()` produces one synchronous 2 µs WDI LOW pulse, then returns
  HIGH. There is no timer, interrupt, background task or DMA heartbeat. The
  portable executor owns the checked heartbeat schedule and fresh-evidence
  policy. PWM is refused until the first successful pulse. The final external
  thermal gate and watchdog remain independent of firmware.
- `sample_fast()` reads the real PCNT count and calibrated ADC1 channel2 current
  proxy, plus raw button/reference/shared-fault inputs. It stamps sampling at
  the beginning, rejects a read lasting over 1 ms, and increments a source
  sequence only for a successful sample. ADC timeout, absent calibration,
  rail saturation and implausible conversion fail closed. GPIO21 LOW means
  driver fault **or** the latched regeneration thermal trip, without pretending
  to distinguish them.
- Any invalid state, API failure or output discrepancy latches the adapter
  fault and immediately attempts independent motor OFF, both PWM LOW and
  charge OFF. Normal operation cannot resume on the same object. Teardown
  attempts all disarms before deleting resources and retains handles if an
  API deletion fails. The owning task must inspect `shutdown()`'s result.

The control task owns this object for its whole lifetime. Other tasks must send
messages rather than call its methods. No other PCNT/MCPWM allocation or GPIO
reconfiguration is supported; conflicting allocation is rejected by the fixed
unit0/operator0/timer0 GPIO-route readback. A qualified harness must also match
the adapter and `BenchMotionProfile` qualification IDs and duty ceilings.

## Timing and evidence boundaries

The portable executor measures each I/O operation against its 100 µs budget.
PWM compare update and stop-at-zero polls each have a 60 µs ceiling. A WDI call
also checks its local elapsed time against 100 µs; its acknowledgement follows
the falling edge by about the pulse duration, not a measured oscilloscope
latency. These are checked software deadlines, not a proof that ESP-IDF calls,
interrupt load, scheduling and the board meet them. The independent hardware
watchdog is still the bound if the processor stalls inside an operation.
Allocation and ADC calibration happen during initialization, outside motion.

Current is the DRV8874 IPROPI proxy at the filtered ADC branch, using the
measured profile gain (540 mV/A is only the schematic nominal). It is not pack
current, not an accurate signed regeneration measurement, and not a replacement
for the driver's independent current limit. ADC/PWM phase, RC settling, clipping,
noise, control-loop execution time, PWM truth table, encoder polarity/rate and
watchdog pulse/window timing must be qualified on the actual board.

No battery SOC, healthy pack, temperature, charger entitlement, calibrated
fabric height or valid reference is invented here. A future owning task must
combine fresh MAX17320/charger evidence with these fast samples without making
slow I2C calls or logging on the control/heartbeat path. Gauge failure, stale
pack evidence, a raw STOP press, clock/lease failure or lost reference must
inhibit the portable executor before a further heartbeat. Encoder power is
gated between sessions; a stored count does not prove that the blind stayed
stationary while asleep.

## Build and checks

The source is intentionally pinned to **ESP32-C6 / ESP-IDF v5.5.4** because its
readback uses public SoC register definitions as well as the driver API. A
version/target compile check rejects another platform until those definitions
are reviewed. The normal motor-disabled `firmware/esp-idf` target depends on
this component so the adapter source is compiled even while its initialization
permission is off. The Thread target does not instantiate or link this adapter
yet; the radio/control bridge is the next separate checkpoint.

Host checks:

```sh
cmake -S firmware -B work/firmware-check
cmake --build work/firmware-check -j4
ctest --test-dir work/firmware-check --output-on-failure
```

All seven host test targets pass locally. `port_checks_tests` injects invalid
clock/routing/action/force/compare/filter/limit states, wrong physical direction,
unapplied duty, a HIGH inactive bridge input, invalid qualification profiles,
ADC saturation and encoder accumulation overflow. The existing executor tests
cover ordering, every injected I/O failure, stale evidence, reversal, stall,
heartbeat deadlines and a deliberately synthetic motor/roller model.

The new adapter is awaiting the fresh pinned C6 CI cross-build. Earlier green
C6 builds covered the disabled adapter and portable executor, not this new
source. Nothing has been flashed or electrically tested.

Primary source review: Espressif's [MCPWM API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/mcpwm.html),
[PCNT API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/pcnt.html),
[ADC oneshot API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/adc_oneshot.html),
[calibration API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/adc_calibration.html),
and pinned v5.5.4 [C6 MCPWM LL](https://github.com/espressif/esp-idf/blob/v5.5.4/components/hal/esp32c6/include/hal/mcpwm_ll.h),
[PCNT driver](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_driver_pcnt/src/pulse_cnt.c),
[GPIO driver](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_driver_gpio/src/gpio.c)
and [C6 register headers](https://github.com/espressif/esp-idf/tree/v5.5.4/components/soc/esp32c6/register/soc).
