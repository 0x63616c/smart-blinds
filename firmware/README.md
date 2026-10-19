# Smart Blinds firmware

Fresh, hardware-independent control groundwork. **No firmware image has been built for a selected MCU, flashed, or validated on the purchased motor.** The control core returns a physical fabric velocity request; a future board port must close the encoder speed loop and implement the actual motor, power, radio and sensor drivers.

```sh
cmake -S firmware -B work/firmware-build
cmake --build work/firmware-build
ctest --test-dir work/firmware-build --output-on-failure
work/firmware-build/group_demo
python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py' -v
```

The C++17 library has no platform dependencies or heap allocation. It implements:

- Monotonic piecewise calibration between normalized encoder counts and bottom-edge height above one room datum; no extrapolation beyond measured travel.
- The intersection of all members' physical travel ranges. Group 50% is the midpoint of **that common height range**, independent of blind lengths.
- An acceleration-limited physical trajectory shared by aligned blinds, with local position correction.
- Prepare/commit/scheduled start, boot-bound command sequences, expired-message rejection and short running leases.
- Immediate stop, offline local endpoint moves, current/voltage/driver guards, missed-control-deadline detection, no-encoder and tracking fault handling.
- Fault latches and loss of reference. A reboot cannot restore an old target and start moving.

Tests cover nonlinear calibration, common ranges, differing lengths, duplicate/stale commands, missing commit/leases, incorrect clocks, local override and an ideal seven-device trajectory. The ideal actuator test verifies the software coordinate logic; it does **not** simulate real motor inertia, clutch slip, radio loss, torque or RF interference.

Read the [control contract](../docs/firmware/control-contract.md), [radio trade study](../docs/firmware/2026-10-19-radio-and-sleep.md), [hardware interface](../docs/firmware/hardware-interface.md) and [Home Assistant contract](../integrations/home_assistant/README.md).

## Before motor enable

All default limits in `Limits` are illustrative test values, including current, voltage and speed. Replace them with measured, reviewed settings for the actual motor, gearing, pack and blind. The core is not a safety-rated controller. The board's independent current limiting, battery protection and default-off output remain necessary.

Remaining implementation includes the encoder velocity loop, MCU pin assignment, watchdog/output-enable hardware, authenticated transport, clock synchronization estimator, persistent calibration with corruption checks, low-power transitions, battery state-of-charge estimation, homing and commissioning flow, and firmware recovery/update path. The physical reference procedure must be completed before calling `establish_reference`; the software cannot infer a bottom-edge height from an encoder counter at boot.
