# Informational authenticated transport

`TelemetrySession` exposes only `poll()` and `close()`. Its separate native handle
also rejects every route except `POST /v1/telemetry`. Explicit pre-existing PSK,
identity, literal endpoint and expected boot are required; this library provisions
nothing. Nonce/boot/schema/identity/time errors close the session without replay,
retry or reconnect. Readings cannot become motion readiness or charging authority.
See the [wire and age contract](../../docs/firmware/parked-telemetry.md).

Build from the repository root using the existing immutable dependency fetch:

```sh
sh firmware/esp-idf-wifi/fetch_dependencies.sh
cmake -S integrations/telemetry_transport -B work/telemetry-build \
  -DLIBCOAP_SOURCE_DIR="$PWD/work/wifi-idf-extra/coap/libcoap" \
  -DSB_ALLOW_CCM8_POLICY=ON -DSB_BUILD_TEST_PEER=ON
cmake --build work/telemetry-build -j4
SB_TELEMETRY_LIBRARY="$PWD/work/telemetry-build/libsb_telemetry.so" \
  python3 -m unittest integrations.telemetry_transport.test_telemetry integrations.physical_bridge.test_bridge -v
```

On macOS the library suffix is `.dylib`; Homebrew OpenSSL may require
`-DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3`. The vendor libcoap revision is
`d9b4031ee61df1a40ecec46fe3817a1f985b3919`; tracked dependency changes reject.
The existing ESP-IDF fetch pins extra-components at
`cad43839020fc329722035a35640a54e06fee09b`.

The explicitly enabled evaluation cipher is DTLS 1.2 PSK-AES128-CCM8. The 64-bit
tag requires a narrowed per-library OpenSSL security-level override. This does not
change system crypto settings or establish a production security decision. Keys
in tests are fresh disposable bytes; fixture readings are explicitly synthetic.
The host fixture uses OpenSSL, not the ESP32-C6 Mbed TLS backend. No actual-radio
or MCU/host interoperability is claimed.

`SB_BUILD_TEST_PEER` defaults OFF. A client-only library excludes all synthetic
server exports; do not deploy the fixture build. Both variants retain the same
explicit evaluation crypto policy. Existing evaluation/motion native constructors
keep their original route allowlists and wire schemas.
