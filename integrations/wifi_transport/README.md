# Wi-Fi evaluation loopback fixture

This fixture uses the actual portable Wi-Fi policy/parser over real localhost
DTLS, with random disposable keys. Its OpenSSL server/client exercise the
same pinned vendor libcoap revision as the C6 image. It does **not** simulate a
Wi-Fi radio, GPIO, encrypted NVS or the C6 Mbed TLS backend.

No Home Assistant service, discovery, configuration write or owner-device access
is added. The existing motor-disabled `Session` client is reused. A test-only
raw motion request verifies that both motion routes always return 5.03.

From the repository root:

```sh
sh firmware/esp-idf-wifi/fetch_dependencies.sh
cmake -S integrations/wifi_transport -B work/wifi-transport-build \
  -DLIBCOAP_SOURCE_DIR="$PWD/work/wifi-idf-extra/coap/libcoap" \
  -DSB_ALLOW_CCM8_POLICY=ON
cmake --build work/wifi-transport-build -j4
SB_WIFI_LIBRARY="$PWD/work/wifi-transport-build/libsb_wifi.so" \
  python3 -m unittest integrations.wifi_transport.test_evaluation -v
```

On macOS use `libsb_wifi.dylib`; if CMake cannot locate Homebrew OpenSSL, pass
`-DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3`. OpenSSL 3.x is required.

`SB_ALLOW_CCM8_POLICY=ON` explicitly restricts **this fixture's SSL contexts**
to DTLS 1.2 PSK-AES128-CCM8 with `@SECLEVEL=0` because OpenSSL's higher default
policy can reject the eight-byte authentication tag. No system-wide security
setting is changed. The C6 resource also checks its exact negotiated protocol
and cipher. This is scoped interoperability research; production tag length
and security policy remain a decision before deployment.

Six tests pass locally: actual handshake/clock assessment, wrong identity/key,
record replay/corruption, malformed/old-boot wake and all motion rejection,
second-controller rejection without replacing the first, and network-loss
revocation without implicit reconnect. The test wrapper uses synthetic network
events; SDK event delivery, sleep wake and hardware interlocks require C6 bench
tests. The existing seven-peer fixture's intermittent timing failures remain a
separate investigation.
