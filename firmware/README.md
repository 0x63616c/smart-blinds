# Smart Blinds firmware

Portable control software plus default-unqualified ESP32-C6 targets. The separate
[Wi-Fi motion target](esp-idf-wifi-motion/README.md) binds authenticated commands to
the owned motion session, C6 motor port and power readers. Its empty physical
records and default-OFF compile option prevent motor initialization. The
[radio-only evaluation](esp-idf-wifi/README.md), Thread target and
[bring-up image](esp-idf/README.md) remain available separately.
**No device has been flashed or validated on the purchased motor.** All seventeen
portable test targets and the pinned Wi-Fi motion default/bench builds pass
locally; see the [runtime evidence and limits](../docs/firmware/wifi-motion.md).

```sh
cmake -S firmware -B work/firmware-build
cmake --build work/firmware-build
ctest --test-dir work/firmware-build --output-on-failure
work/firmware-build/group_demo
python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py' -v
python3 -m unittest discover -s firmware/tools -p 'test_*.py' -v
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

[MAX17320 tooling](../docs/firmware/max17320-commissioning.md) provides register reads, offline partial configuration arithmetic and readback comparison. It cannot program NVM; the full pack profile and hardware tests remain open.

## Before motor enable

All default limits in `Limits` are illustrative test values, including current, voltage and speed. Replace them with measured, reviewed settings for the actual motor, gearing, pack and blind. The core is not a safety-rated controller. The board's independent current limiting, battery protection and default-off output remain necessary.

The executor, board pin mapping, authenticated transport and clock checks are
implemented as reviewed checkpoints, with physical timing and electrical
qualification still pending. Remaining implementation includes local endpoint
ownership/gestures, qualified gauge continuity integration, persistent calibration
and record admission, credential commissioning, charge permission, homing and
firmware update/recovery. The physical reference procedure must be completed
before calling `establish_reference`; the software cannot infer a bottom-edge
height from an encoder counter at boot.
