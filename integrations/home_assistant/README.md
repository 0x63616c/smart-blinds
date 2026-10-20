# Home Assistant and local coordinator

The `custom_components/smart_blinds` directory is an installable Home Assistant integration for the [seven-blind simulator bridge](../bridge/README.md). It is tested with **Home Assistant 2026.10.2**. It accepts an explicitly selected simulator mode or a separate [physical read-only telemetry bridge](../physical_bridge/README.md). No user's Home Assistant configuration has been changed and no physical blind is controlled.

Simulator mode adds one shared-height room cover, seven individual covers, seven battery sensors, seven charging indicators and an explicit **Align at 50%** button. Simulation is visible in the device/entity names. The group percentage uses the common physical range; individual covers use their own full travel. A stock HA cover group forwarding seven identical percentages would not preserve bottom-edge alignment.

## Try in a local test Home Assistant

1. Copy `custom_components/smart_blinds` into the test HA configuration directory's `custom_components` folder and restart that test instance.
2. Run the simulator bridge in the same host/network namespace using its README instructions. It binds only to loopback. HA OS/add-on and separate-container packaging are not supplied yet.
3. In Settings → Devices & services → Add integration, choose Smart Blinds. Use `http://127.0.0.1:8765` and the simulator's access token. Choose Simulator in the mode selector.
4. Move the room cover to 50%, or use an individual full-open/full-close command. Individual commands can leave the group unaligned; use the separate alignment button before the next synced group move.

The token stays in HA's private config-entry storage. Do not commit that storage or the simulator token file. Plain HTTP is permitted only to loopback/localhost; network URLs require HTTPS with certificate verification. Redirects are disabled, responses are size-bounded and requests have a five-second timeout. Commands are never retried automatically because a lost acknowledgment does not establish that a movement request was rejected.

The component displays reported position, not the requested target. An unaligned group has unknown position, not an average that suggests alignment. Missing members make the group unavailable. A disconnected bridge makes its entities unavailable. Battery samples older than 30 minutes become unknown, never zero; the current simulator's battery/charging data is explicitly synthetic.

The room cover's 0/100 endpoints are its **common reachable endpoints**. Use individual covers for each blind's physical fully open/closed position. Stop from any cover aborts the one active bridge job. Rejoin can move members different distances and finish at different times; normal synchronized travel requires aligned starting edges.

## Verification

The dependency-free coordinator and bridge tests run on a normal Python installation:

```sh
python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py' -v
python3 -m unittest discover -s integrations/bridge -p 'test_*.py' -v
```

The HA framework tests, including the physical loopback path, require the telemetry fixture library built as described in its [README](../telemetry_transport/README.md), with `SB_TELEMETRY_LIBRARY` set to its absolute path. They need Python 3.14.2 or newer within the supported HA version and the pinned requirements:

```sh
python3.14 -m venv work/ha-test-venv
work/ha-test-venv/bin/pip install -r integrations/home_assistant/ha_tests/requirements.txt
work/ha-test-venv/bin/pytest -q integrations/home_assistant/ha_tests
```

The HA tests exercise real config flows, entities, services, unload and state handling. One test sends a real HA service call through a real authenticated loopback HTTP connection into the seven-member coordinator, verifies all members have the same physical target and stops them. Other tests mock HTTP replies to inject authentication failures, stale battery data, unaligned positions, missing members and failed commands. None demonstrates RF performance, a flashed MCU or movement on hardware.

## Coordinator and source freshness

`coordinator.py` is a transport-independent engine. It prepares one physical trajectory, records each authenticated queue receipt separately from readiness, waits for every member to report ready, and commits a future start. It renews each queued peer's lease every 100 ms during preparation, commit and motion. The original prepare source timestamp sets the initial lease floor; a late or duplicate receipt never retimes it. A missing member, fault, reboot or stale active report stops the group. Local STOP acts on the node first. The [control contract](../../docs/firmware/control-contract.md) defines the safety and timing boundaries.

`prepare_queued()` is a receipt-only hook and cannot refresh source telemetry or mark a member ready. The owner must deliver its returned envelopes and call `tick()` throughout preparation. Prepared/committed ACKs and reports require `SourceStamp(sample_ms, sequence, clock_error_ms)`. The authenticated adapter must translate the **source's actual measurement time** into the coordinator's monotonic epoch with a bounded error. `freshness.py` rejects replayed or delayed samples even when delivered now; clock uncertainty subtracts from the source timestamp for age calculation. The host fixture authenticates serialized messages but shares a clock. The separate DTLS client and bounded group adapter implement clock assessment and real localhost coordinator binding; device provisioning and the sole physical HA connection owner for movement remain open. Queued peers must report within 250 ms of the original prepare source time and continue supplying fresh source reports; missed lease scheduling aborts without catch-up sends.

Proposed hardware telemetry cadence is every 15 minutes idle, promptly after movement and every minute charging; active supervision is at most 100 ms. HA's one-second HTTP refresh is only presentation and user intent. It does not renew device leases or keep the radio awake. The bridge supervises motion separately. These proposed radio settings still need measured energy and latency results.

## Physical diagnostics

Choose Physical telemetry (read only) only for the explicitly paired `/v2/state` bridge. This creates battery, USB-connected and charging entities; no covers or buttons. Battery uses the existing 30-minute display limit; source and inhibited charging observations have independent 60-second limits. Original sample times, boot, last SOC and source faults are retained as attributes. The current MCU runtime does not periodically acquire the gauge while parked, so long idle eventually shows unknown SOC. HTTP refresh cannot refresh that observation. Nine framework tests include real HA → authenticated HTTP → localhost DTLS → portable endpoint, plus the existing simulator tests. See the [telemetry contract](../../docs/firmware/parked-telemetry.md).

## Physical deployment work remaining

Implement and validate the C6 transport, onboarding, authenticated clock estimation, per-message strict decoding, persistent identity, secure updates and recovery, service packaging and real pack/reference state. Confirm the actual HA deployment and HomePod model. A HomePod can be a compatible Thread border router, but it is neither this coordinator nor proof that a custom Thread device is a Matter cover. See the [concrete Thread plan](../../docs/firmware/thread-transport-plan.md) and [radio trade](../../docs/firmware/2026-10-19-radio-and-sleep.md).

The current custom integration follows HA's [config-entry flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/), [data coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) and [cover entity](https://developers.home-assistant.io/docs/core/entity/cover/) interfaces. It is a project integration, not an official Home Assistant integration or a HACS release.
