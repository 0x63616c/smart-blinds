# Authenticated C6 motion runtime

The Thread application now connects secure resource callbacks to the reviewed
motion session and real C6 I/O/evidence components. **Its shipped configuration
is empty and motor-disabled.** Creating the runtime starts tasks and queues;
it does not configure a motor, charger, encoder, ADC or I2C pin without all local
qualification gates. No board was accessed, flashed or commissioned.

## Ownership and execution

| Owner | Work | Boundary |
|---|---|---|
| OpenThread lock owner | Verify authenticated confirmable CoAP requests; decode exactly 80 bytes; assign DTLS connection generations; publish network/clock state | Copies request values into the four-entry SPSC inbox; no retained packet pointers, I2C or GPIO |
| Control task, priority 8 | Own `BenchC6Io`, `MotionSession`, physical reference, ADC/PCNT sampling and every motor/watchdog write | Normal awake cadence is a 10 ms wait after work; notification can wake it earlier. Session/executor enforce actual elapsed limits; no catch-up or independent WDI timer |
| Power task, priority 3 | Own I2C0 GPIO10/11, MAX17320 reader, OFF-only BQ25798 policy and gauge assessor | Finite 10 ms I2C transactions and existing capture deadlines; never calls a motor operation or writes a GPIO |
| Radio policy task | Apply receiver/PM policy under OpenThread lock | Keeps receiver awake through an accepted motion/settling session, bounded by the session's independent 240 s ceiling |

Length-one FreeRTOS queues copy network state, power observations and control
status. Their types are asserted trivially copyable. The control task peeks
without waiting; missing data is invalid. Physical reference uses a distinct
one-entry local queue. No network method can supply it.

The only producer of the motion inbox is the serialized secure resource owner.
The OpenThread connection-event callback invalidates prior clock evidence and
allocates a new local generation after each completed DTLS handshake. The
inbox's message replay floor survives reconnect. Connection generations never
come from a request. The pinned vendor header exposes this callback in
`otCoapSecureSetClientConnectEventCallback`; the [secure CoAP API](https://openthread.io/reference/group/api-coap-secure)
documents connection events separately from packet processing.

## Resources

`POST v1/motion` accepts the existing [80-byte request](motion-session.md#binary-request)
after DTLS authentication. A `2.04 {"queued":true}` response acknowledges only a
copy into the inbox, **not** accepted preparation, readiness, PWM or completion.
Malformed frames get 4.00; unavailable, replayed and full-queue requests get
5.03. STOP bypasses a full queue after authentication/boot/sequence checks.
Duplicate CoAP transmissions may receive the stack's cached response; the
application's boot/message checks still prevent executing the motion twice.

`GET v1/motion-status`, empty body, returns the latest control snapshot:

- Exact 16-digit hex `boot`, `sampled_us`, `command`, `last_message` and
  `power_sampled_us`. These are source observations, not receipt timestamps.
- Named `phase` and `result`, plus `io_qualified`, `fresh`, `ready`,
  `reference_valid`, `awake_required`, and optional `height_mm`.
- `power_ready` and optional `soc_percent`, derived from the actual qualified
  pack/OFF-charger observations. No dummy voltage or charge level is supplied.

Readiness is false if control data is more than 30 ms old, I/O is unqualified or
power evidence has expired. It also checks the current ingress evidence, so a
failed clock qualification/disconnect revokes readiness before the worker's
next publication. The coordinate remains explicitly source-stamped
diagnostic data when stale. The old `v1/readiness` endpoint remains the separate
clock diagnostic schema with `motor_ready:false`; use `v1/motion-status` for the
control session. Status/wake use `io_qualified` for initialized backend
qualification; they do not label this as live motor output.

The existing Python/libcoap client deliberately accepts only the motor-disabled
status contract and does not yet expose these motion resources. Its coordinator
binding is a following step; no production Home Assistant actuation is implied.

## Clock and power evidence

Starting a new clock probe clears that probe's diagnostic assessment but retains
the preceding accepted bound for the control worker. Successful qualification
replaces it. Failed assessment, stale bounds, sleep, detach and reconnect clear
it. No pending probe extends its age. The session's fixed projection still
rejects excessive drift rather than stepping trajectory time.

The qualified sensor path sets up the already-reviewed OFF charger profile
using the 9 V profile's input threshold. It never enables CE or EN_CHG. Selecting
this OFF profile is not USB current entitlement, and the application has no
charge-enable path. A read-only inhibit adapter checks the charge-request output
route, output-enable and pad HIGH; only the control owner writes that pin.

Each sensing episode receives a new local generation. Old captures are rejected
even if a previous observation is under the 250 ms age limit. The gauge monitor
warms again after idle, including short gaps that occur during an I2C transaction.
Every power snapshot preserves conversion-age bounds and bus observation times.
A failed gauge read is published before trying another device. Configuration,
bus, protection and charger readback failures latch the power path unavailable
for that boot; there is no automatic bus recovery, NVM programming or stale-good
fallback. A hung worker loses readiness through the existing age limits.

## Qualification and local controls

An active build requires `CONFIG_BLINDS_BENCH_MOTION`, matching measured
port/controller qualification IDs, a valid calibration, qualified passive
holding, commissioned pack/readback/thermal timing, a validated clock model,
verified task/bus timing and current-boot binding. Individual component checks
still apply. `motion_config{}` supplies none of these. A radio NVS approval bit
or saved Thread dataset cannot substitute for them.

The control worker accepts a boot-bound independently observed local reference
through `reference()`. A saved encoder count, periodic chain index or network
packet is insufficient. The complete owner-facing commissioning/recovery
workflow and persistent record verification remain to be implemented.

During an awake session, each real fast sample includes raw buttons, so any
press has STOP priority over queued commit/lease/prepare. Idle button wake and
tap-to-endpoint control are not integrated in this checkpoint. GPIO0/1 remain
reserved. In particular, the existing light-sleep peripheral-power-down option
requires the vendor's RTC/LP wake approach; ordinary digital GPIO wake cannot be
assumed sufficient. [ESP-IDF C6 GPIO wake guidance](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/system/sleep_modes.html#gpio-wakeup-light-sleep-only)

## Validation

All eleven portable host targets pass locally, including the existing complete
session/settling failure suite and the new runtime tests. New tests exercise
copied-payload ownership, full queue plus priority STOP, 20,000 frames across
concurrent producer/consumer threads, reconnect replay, retained clock during a
pending probe, invalidation, expired power, sensing-generation isolation, source
stamps and default qualification refusal.

Both application builds use the existing pinned ESP-IDF 5.5.4 CI image:
`espressif/idf:v5.5.4@sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b`.
This new application wiring awaits its fresh CI result. Earlier `2561ced` builds
prove the preceding session/component source, not this runtime. Actual task
latency, stack/RAM budget, light-sleep retention, ADC/I2C behavior, clock drift,
radio/DTLS interoperability with a C6 and physical STOP remain unmeasured gates.
