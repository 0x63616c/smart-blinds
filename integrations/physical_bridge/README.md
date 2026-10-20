# Physical telemetry bridge — read only

This service connects explicitly selected, already paired devices to Home Assistant
battery and USB diagnostics. It does not commission devices or expose movement,
alignment, charging or qualification operations. No devices are selected by default.
Do not run another motion/telemetry controller for the same device at the same time.

Each device has one owned DTLS session, one in-flight exchange and a fifteen-second
idle interval between reads. HTTP `GET /v2/state` only copies cached values; it does
not trigger a sensor or radio request. A failed owner closes without automatic
reconnect or boot adoption. Service recovery is explicit and not final unattended
recovery behavior. Literal address aliases cannot create duplicate owners.

Build the [client-only transport](../telemetry_transport/README.md) with
`SB_BUILD_TEST_PEER=OFF`. A private JSON pairing file supplies `bridge_id` and a
`devices` array, each with exactly `id`, `name`, `host`, `port`, `identity`,
`key_file`, and `boot`. Host is a literal unicast IP (no scoped addresses in this
checkpoint). Boot is sixteen lowercase hex digits from an independently approved
pairing process; it is never discovered/adopted by this service. Key files are
private regular files containing exactly 32 raw bytes. Relative key paths resolve
beside the pairing file. There is no production pairing tool yet.

Given those pre-existing private records, the explicit service entry point is:

```sh
python3 -m integrations.physical_bridge.server \
  --pairings /absolute/private/pairings.json \
  --token-file /absolute/private/bridge-token \
  --library /absolute/client-only/libsb_telemetry.so
```

This starts connections; it is not a dry run. It has not been run against an
owner's devices. The HTTP listener binds only `127.0.0.1:8766`, requires a token
of at least 32 non-whitespace characters and accepts no command routes. Keep
all configuration/token/key files outside Git. The loopback packaging assumes
the same host/network namespace as HA; HA OS/add-on packaging is still open.

In the HA integration choose **Physical telemetry (read only)** with this local
URL and token. It creates battery, USB-connected and charging diagnostics only.
Stale readings become unknown rather than zero. Original age/boot/sample fields,
last battery value, pending source state and fault remain inspectable. Battery
currently becomes stale after 30 minutes because parked periodic gauge acquisition
is not implemented. See the [full contract and remaining physical gates](../../docs/firmware/parked-telemetry.md).

Tests use real localhost DTLS and HTTP, seven disposable peer fixtures, strict
mode/boot/age checks, duplicate-address rejection and owner-failure shutdown.
They are not physical-hardware, radio, charging or battery-life evidence.
