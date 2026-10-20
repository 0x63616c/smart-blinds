# Motor-disabled C6 Wi-Fi evaluation

Separate ESP-IDF target for associated Wi-Fi automatic light sleep. The
[evaluation contract](../../docs/firmware/wifi-evaluation.md) explains the radio
decision, explicit OFF behavior and physical qualification gates.

**Default behavior: no join and no board GPIO initialization without approved,
existing encrypted configuration. No credentials are supplied by this project.**
With configuration, this image holds the motor, charger and encoder power
permissions OFF. Buttons wake the radio only. Motion/status-of-motion routes
return 5.03; no control worker, PWM, I2C, charging or updater is instantiated.

## Pinned build

From the repository root:

```sh
sh firmware/esp-idf-wifi/fetch_dependencies.sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf-wifi \
  espressif/idf:v5.5.4@sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b \
  idf.py -D SB_COAP_DIR=/project/work/wifi-idf-extra/coap \
    -B /project/work/c6-wifi-build set-target esp32c6 build size
```

The fetch script selects exact sources; CMake rejects tracked modifications or
different revisions. It does not install global tools or implicitly flash:

| Dependency | Immutable selection |
|---|---|
| ESP-IDF | v5.5.4, image digest above |
| Espressif idf-extra-components | `cad43839020fc329722035a35640a54e06fee09b` |
| Its libcoap submodule | `d9b4031ee61df1a40ecec46fe3817a1f985b3919` |
| RISC-V toolchain in image | `esp-14.2.0_20260121`, GCC 14.2.0 |

The vendor `coap_config.h` must precede public CoAP headers, including when
IPv6 is disabled. This image initially uses explicit IPv4 endpoints. The
underlying protocol still binds authenticated identity, boot nonce and owner,
not just the IP address.

Local final build on 2026-10-20: binary **1,014,176 bytes (`0xf79a0`)**;
**886,368 bytes (`0xd8660`, 47%)** remain in each 1,900,544-byte OTA slot.
Static DIRAM usage is 169,624 bytes, leaving 282,488 bytes before runtime
allocations; this is not measured free heap. Two slots are reserved, but no
OTA download, verification or rollback service exists.

Local binary SHA-256:
`73b17884a5d7021827af5480ac084df13fef880edb454ed0ce7784123a4e1d06`.
Build timestamps/tool paths can change binary hashes; the CI artifact is the
evidence for its exact committed source. No hardware was flashed or tested.

## Configuration contract, not a provisioning command

Default boot first requires `esp_flash_encryption_enabled()`, an encrypted
`nvs_keys` partition, valid previously provisioned keys and successful
`nvs_flash_secure_init()`. It intentionally does not call the automatic key
generation path. It reads only namespace `sb_wifi`:

| Key | NVS type / accepted value |
|---|---|
| `approved` | u8, exactly 1 after explicit commissioning review |
| `board` | u8, exactly 1 for this repository's reviewed GPIO profile |
| `ssid` | string, 1–32 bytes |
| `password` | string, 8–63 printable ASCII bytes, WPA2/WPA3 passphrase |
| `identity` | string, 1–32 ASCII letters, digits, `_` or `-` |
| `psk` | blob, 32 bytes, independently generated random per-device key |

The nonzero-key check is structural, not an entropy test. Provisioning must
generate and protect the key correctly. There are no sample reusable secrets,
NVS write commands, key logging or owner-network defaults here. Wi-Fi SDK
credential storage is RAM-only and temporary passphrase buffers are zeroized.

`CONFIG_SB_WIFI_PLAINTEXT_DISPOSABLE_BENCH` defaults OFF. Enabling it is an
explicit exception solely for disposable test-AP credentials and keys; it calls
secure-init with a null configuration and does not create encryption keys.
It still requires the approved board/configuration record. This exception is
not suitable for owner or production credentials. The application does not
enable flash encryption, secure boot, eFuses or other irreversible settings.
Those require a separate reviewed factory procedure.

## Runtime limits

`WIFI_PS_MIN_MODEM` plus CPU automatic light sleep is used while safely idle.
The internal RC clock requires no external 32 kHz crystal. Awake windows switch
to `WIFI_PS_NONE` and acquire both no-light-sleep and maximum-frequency locks.
Clock assessment is discarded on return to idle; the physical model is never
declared qualified in this target.

There is one DTLS 1.2 owner with per-device PSK, checked against
`TLS-PSK-WITH-AES-128-CCM-8`. The eight-byte tag is still a production security
choice. Network/queue/PM failures and renegotiation invalidate the current
owner. Connection loss during a wake window latches unavailable; no active
session migration or replay occurs. Mbed TLS renegotiation is disabled in the
configuration, with an additional event-level rejection in the resource owner.
Three association attempts and five DTLS
error events per boot are conservative evaluation limits that may require
restart after an outage, not final unattended recovery behavior.

`gpio_hold_en` keeps the explicitly selected motor/charger/encoder outputs OFF.
Sleep pin switching is disabled for those pads and the two button inputs; GPIO
peripheral power stays on. No code releases those holds. Missing configuration
leaves GPIOs untouched and relies on the board's reviewed hardware defaults.
Actual hold/reset behavior, current draw and fault response require bench
qualification before any qualified motion target can use this path.

## Host checks

```sh
cmake -S firmware -B work/control-build
cmake --build work/control-build -j4
ctest --test-dir work/control-build --output-on-failure
```

Twelve targets pass locally, including configuration, association backoff,
one-owner lifetime, button-only radio wake, operation deadlines and parser
rejections. [Localhost DTLS tests](../../integrations/wifi_transport/README.md)
exercise this same policy/parser with disposable keys. C6 Mbed TLS peer
interoperability and over-the-air behavior remain unverified.
