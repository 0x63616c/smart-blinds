# Home Assistant and local coordinator

This directory contains a tested, transport-independent coordinator engine. **It is not yet an installed Home Assistant integration, MQTT daemon, Matter implementation or radio bridge.** Run the nine scenarios with:

```sh
python3 -m unittest discover -s integrations/home_assistant -p 'test_*.py' -v
```

`coordinator.py` prepares one shared physical-height trajectory, waits for every member, commits a future start and renews short running leases only after all members acknowledge. A missing member, fault, reboot or stale active report stops the group. Local STOP is always a node action first. The [control contract](../../docs/firmware/control-contract.md) specifies transport and clock boundaries.

## Proposed Home Assistant surface

| Entity/action | Meaning |
|---|---|
| Group cover: “Blinds · aligned” | 0–100% of the group's common physical range; all bottom edges finish at one height |
| Group alignment action | Explicitly bring unequal starting levels together, then permit normal synced moves |
| Individual cover for each blind | Its own calibrated full travel; use this for individual full-open/full-close |
| Stop group | Stop every member immediately when awake; offline devices stop on lease expiry |
| Per-device battery percentage | Last measured/estimated percentage with timestamp and validity; never substitute zero for unknown |
| Charging state | Charging / full / not charging / temperature hold / fault / unknown |
| Diagnostics | Bottom-edge height, calibration/reference validity, last seen, signal, firmware revision, pack voltage/current and fault |
| Group status | Preparing / waiting / moving / aligned / needs alignment / fault, with missing device identified |

A group slider must address the coordinator, not a stock HA group forwarding the same percentage to each cover. Display measured state, not optimistic state. If the members disagree, do not publish an average that looks perfectly aligned; expose the spread and mark group position unavailable until calibrated/aligned.

## MQTT adapter contract (candidate)

A future local daemon can bridge either Wi-Fi or Thread nodes into HA using MQTT discovery. HA's cover entity supports separate state/position/availability topics and defaults to 0 closed, 100 open. The group entity's percentage maps to the common physical range; individual entities map to their own ranges. [Home Assistant MQTT cover](https://www.home-assistant.io/integrations/cover.mqtt/)

Suggested topics under `smart-blinds/v1/`:

| Topic | Payload/policy |
|---|---|
| `groups/room/set_position` | New user intent, percentage 0..100; unretained, adapter rejects retained deliveries |
| `groups/room/command` | OPEN, CLOSE, STOP; unretained |
| `groups/room/state` | Measured HA state (`opening`, `closing`, `stopped`, `open`, `closed`) |
| `groups/room/position` | Measured group percentage only when members are in agreement |
| `groups/room/availability` | Available only with all required members and coordinator reachable; LWT offline |
| `devices/<id>/telemetry` | Source sample timestamp, boot ID, sequence, physical height, reference, power, fault and firmware state |

Only discovery/state may be retained. Movement requests never are. QoS duplicates are expected; boot/sequence checks provide idempotence. On process/broker reconnect discard historical motion intent, cancel pending jobs and wait for a fresh user request. Transport messages between coordinator and nodes require authentication, per-device identity, bounded lifetime and exact uint64 parsing. TLS broker credentials and per-device secrets stay outside the repository.

Idle telemetry can be less frequent than command polls. Proposed initial battery reporting: every 15 minutes while idle, promptly after a move and every minute while charging; include the last sample time. Group readiness always asks for a fresh report. Mark a battery reading stale after two missed reporting intervals instead of pretending it is current. While moving, the supervision report interval is ≤100 ms. These are prototype power/latency settings to measure, not runtime claims.

## Installation work remaining

Choose and implement secure provisioning, transport, service packaging, discovery, credential storage, operational logging and update/recovery. Check the actual Home Assistant deployment and HomePod model before relying on an existing Thread border router. A custom Thread node will not appear as a Matter cover automatically. No Home Assistant configuration has been changed by this work.
