# Executable motion lifecycle

Status: implemented portable C++17 control with injected hardware interfaces and host fault tests. The shipped C6 applications do not construct this executor or configure board outputs. `BenchMotionProfile.bench_qualified` defaults to false; an unqualified instance cannot touch I/O. The C6 build compiles the portable source. A separate [bench C6 adapter](../../firmware/esp-idf/components/motion_io/README.md) implements actual PCNT/MCPWM/ADC calls behind a default-off gate; measured motor parameters, physical qualification and application integration remain required. No motor has been energised by this software.

The source is [motion_executor.hpp](../../firmware/include/smart_blinds/motion_executor.hpp) and [motion_executor.cpp](../../firmware/src/motion_executor.cpp). It sits below the existing `Controller`: the controller owns physical height, scheduled trajectories, group alignment, reference validity and command authorization; the executor owns the bounded motor I/O sequence and the count-velocity loop. It is not a remote command endpoint. One control task must own both, generate `Output` from the current measurement on every cycle, and stop both on any fault. Neither layer may be bypassed by a radio or button handler.

## Lifecycle and output order

1. A new, monotonically increasing command bound to this boot opens sensing. Fresh pack/current/fault evidence is required before any write. The executor writes request HIGH, inputs `00`, WDI HIGH, charge OFF, then acquires an awake lock and enables the encoder rail. Charging stays disabled throughout movement and cleanup; no charger-enable API exists here.
2. After the profile's encoder-settle delay, the port starts a fresh counter epoch. Old samples are rejected. A stopped counter must be normalized to the calibrated direction and offset using the established physical-reference policy; clearing a counter does not establish a reference. Sensing expires after five seconds, including an attempted late arm.
3. Explicit arming requires a valid reference, matching calibration revision and encoder epoch, fresh power/feedback and a local control-validity deadline. Inputs `00` and WDI HIGH are applied before the external supervised motor request goes LOW. The [heartbeat policy](watchdog-heartbeat.md) then waits more than its 1 ms wake and 150 µs setup requirements and requires a fresh healthy cycle and acknowledged first falling edge. That iteration still coasts; PWM can begin on the following cycle.
4. The executor accepts only the controller's prepared, armed or moving output. Prepared/armed states coast. A scheduled move must finish this arming sequence **before** its scheduled start; waking/arming at the start instant would add inconsistent latency. The host plant test pre-arms 150 ms ahead and checks that no PWM occurs before the trajectory start.
5. Immediate `stop()` or fault cleanup first requests HIGH, then coasts, restores WDI HIGH, disables charging, stops the counter, gates the encoder rail and releases the awake lock. Immediate stop does not establish a stationary final count. The new [motion session](motion-session.md) uses controlled encoder settling for normal completion/STOP before retaining a position. Every independent cleanup operation is attempted even if another fails or the clock is broken. A failed/over-budget cleanup latches a fault; success is software-command evidence, not proof of motor-terminal voltage or stopping distance.

A raw local STOP overrides ordinary update validation. Buttons must be sampled in this same bounded task using the portable button policy. A task freeze cannot be repaired by its next software check: the independent watchdog and thermal/driver gates remain required. GPIO21 combines the driver fault and latched regeneration-overtemperature fault; both inhibit motion, without pretending that firmware can identify the source from that pin alone.

## Timing, evidence and ownership

The intended control period is 10 ms, with an executor maximum gap of 20 ms. There are no catch-up pulses. Every sample must have an increasing sequence and source timestamp, be no more than 10 ms old, belong to the current counter epoch and use the current calibration revision. Pack-readiness evidence may be at most 250 ms old; current and the shared fault level belong to the fresh fast sample. `power_ready` must represent independently validated pack/protector/temperature state, not total voltage alone. Missing/stuck-bus/stale data must become false; no bus transaction occurs inside the executor.

`control_valid_until_us` is a local monotonic deadline supplied by the trusted controller/adapter. Remote leases must already be authenticated, bound to this boot/command and conservatively translated from the qualified coordinator clock. Local physical commands need their own bounded task-owned authorization. The executor never extends a remote lease. It requires more than 20.5 ms remaining before accepting an active iteration, reserving the next 20 ms control deadline plus a 500 µs I/O margin. This is a software timing policy; it does not establish a physical cutoff guarantee when the processor or hardware fails.

`MotionIo` operations are synchronous with a checked 100 µs budget. They must not allocate, log, write flash, wait on I2C or service networking. PWM must force the opposite input LOW, apply the selected bounded duty and verify the applied command. WDI is one task-owned LOW pulse of at least 1 µs followed by HIGH; it must not be driven by an autonomous timer, interrupt or logging output. Feeds occur only after successful current output application and fresh healthy iterations. The real port timestamps its synchronous pulse, but worst-case scheduling and I/O latency on the C6 still require physical qualification.

Faults latch for the lifetime of the executor. The same command cannot be reopened after a normal stop. The owner must explicitly stop and inspect the result before backend teardown, and must not reconstruct an executor to erase replay/fault history within a boot. An unknown reboot creates a new boot identity and leaves physical position unreferenced. Counter epochs, saved counts and chain indices cannot prove absolute fabric height; see [reference recovery](2026-10-19-reference-and-recovery.md).

## Velocity, reversal and provisional parameters

`Calibration::count_rate()` converts fabric mm/s using the directional local slope of the calibrated count-to-height map. At a knot, upward travel uses the next segment and downward travel uses the previous segment. Outward motion at a calibrated endpoint is rejected. The executor compares that desired count rate with the fresh measured count difference, then applies feed-forward plus a PI correction with bounded duty and conditional integral accumulation. It coasts when the correction would require an opposing drive; it never uses the `11` low-side brake state.

Changing direction first coasts and clears the integral. Reverse drive is withheld until the minimum coast interval has elapsed and both measured speed and current are below their profile thresholds. Failure to settle within the reversal timeout faults. Continuous applied duty without encoder progress also faults. The higher-level controller separately checks wrong direction, physical tracking error, endpoint range and trajectory timeout. These checks do not detect all mechanical slip; independent physical-reference checks remain necessary.

The defaults are deliberately provisional: 50% maximum duty, 30 mm/s fabric speed, 20,000 counts/s ceiling, 5 ms encoder settling, 20 ms reversal coast, 500 ms reversal timeout, 400 ms no-progress timeout, 3 A current trip and 9.6 V minimum pack voltage. They are test parameters, not approved motor or battery limits. The explicit nonzero qualification ID must ultimately identify a reviewed record covering encoder polarity/rate, loop gains, load and friction, stop distance, reversal/regeneration, thermal behavior, current calibration and fault timing. A boolean cannot establish those facts. Counter scale, maximum safe speed and gain tuning remain measurable configuration rather than blockers to implementing the software structure.

## Reproducible checks and remaining boundary

Run `cmake -S firmware -B work/firmware-check`, `cmake --build work/firmware-check`, then `ctest --test-dir work/firmware-check --output-on-failure`. The motion test joins the host suite. It covers operation-by-operation failures, over-budget operations including cleanup, permanently latched faults, malformed/stale/future evidence, lease margin, expired sensing, output validation, immediate STOP, heartbeat order, nonlinear slope conversion, reversal waiting/timeout and no-progress shutdown.

The test also connects the actual controller and executor through two illustrative first-order motor plants with different response gains. Both cross a calibration-slope change and reach the commanded physical endpoint; reversed plant wiring causes the controller's wrong-direction/reference-loss stop. The plants are intentionally synthetic and are not identified models of the purchased motors. These tests establish logic behavior, not actual settling, precision, current, battery runtime or wall-mounted safety. The existing C6 adapter checkpoint passed both pinned ESP-IDF builds at `4486b2a`; this new settling/session checkpoint requires its own fresh cross-build. No C6 motor interoperability or hardware test is claimed.

## Actual C6 adapter checkpoint

The separate [bench C6 adapter](../../firmware/esp-idf/components/motion_io/README.md)
now implements this executor's I/O interface with hardware PCNT, MCPWM, calibrated
ADC, synchronous WDI pulses and register/pad readback. It remains uninstantiated
and initialization is disabled by default. The shipped application has no active
motion entry point. Host tests cover its portable measurement/readback acceptance
rules; its fresh cross-build and physical qualification are recorded separately
in that component's README. The radio-to-executor integration is not complete yet.

The [bounded session](motion-session.md) now joins the portable controller and
executor with boot/session/clock/source-time checks and controlled settling. The
Thread resources and sensor-worker publication are not connected to it yet.
`holding_qualified` defaults false; `begin_settling()` cannot yield a retained
count without that measured holding assertion. Fault cleanup still inhibits
immediately and never produces a stationary-count proof.
