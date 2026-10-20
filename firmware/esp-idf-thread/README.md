# C6 Thread / DTLS evaluation — motor disabled

This **separate** ESP-IDF 5.5.4 target evaluates the full OpenThread minimal-end-device stack and standard CoAP over DTLS. It does not replace the original `firmware/esp-idf` bring-up image. No motor, charger, encoder, button or watchdog GPIO is configured. There is no movement endpoint, validated clock qualification, calibration or battery-readiness claim. New secure clock/readiness resources assess a deliberately unvalidated timing model.

The source uses ESP-IDF's OpenThread and mbedTLS components, not the host simulator's HMAC packet codec. `otCoapSecureSetPsk` selects the standard DTLS PSK/AES-128-CCM-8 path. Only the secure CoAP service is started; there is no unauthenticated CoAP fallback. The application does not embed or generate an operational dataset or application key. [OpenThread secure CoAP API](https://openthread.io/reference/group/api-coap-secure)

## Build and scope

From the repository root:

```sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf-thread \
  espressif/idf:v5.5.4 idf.py -B /project/work/c6-thread-build set-target esp32c6 build
```

The same pinned multi-architecture image digest as the bring-up target can be used:
`sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b`.
The hardened radio target at commit `28433e1` cross-built successfully in [pinned CI run 39357729073](https://github.com/0x63616c/smart-blinds/actions/runs/39357729073). Its application binary is **737,040 bytes** (`0xb3f10`), leaving **1,163,504 bytes (61%)** free in each 1,900,544-byte app slot. The full OpenThread MTD and mbedTLS secure-CoAP stack linked successfully. The downloaded CI artifact SHA-256 is `58f78fd96137864ac29d4d4fdf59b72e0b7b43012219ce1a3a3782b81a9078fa`.

This prior binary confirms compilation of the startup-authorization and status-handler checks. The subsequently added clock/readiness resources await a fresh pinned cross-build; its size is not yet measured. No hardware was flashed, no Thread network was joined and no C6 DTLS peer handshake was exercised. Runtime RAM, power, timing and C6 interoperability remain unmeasured.

The custom partition table reserves two `0x1d0000` byte (1.8125 MiB) OTA app slots in 4 MiB flash, plus NVS, OTA selection data, PHY data and a coredump area. An OTA partition layout does **not** implement download, signature verification, rollback, recovery or safe stationary update policy. Full final application fit must be rechecked as motor, gauge, provisioning and update code are added.

Host radio-window tests are independent of IDF:

```sh
cmake -S firmware/radio -B work/radio-tests
cmake --build work/radio-tests
ctest --test-dir work/radio-tests --output-on-failure
```

They test boot/sequence binding, offline rejection, no extension while awake, expiry and cooldown, reconnect replay rejection, clock reversal, zero boot and overflow. They do not measure Thread power or prove a cryptographic handshake on hardware.

## No automatic commissioning

The default image does **not** initialize the radio stack without valid application approval/key records. After those pass, it initializes the stack but does **not** enable IPv6/Thread joining or the DTLS server unless all of these existing records are present:

- A complete commissioned OpenThread operational dataset, checked by `otDatasetIsCommissioned`.
- Read-only application NVS namespace `sb_thread`, key `approved` with uint8 value 1.
- A separate 32-byte nonzero `psk` blob and `identity` string of 1–32 ASCII letters, digits, underscore or hyphen.

The boot ID uses the documented internal entropy source before RF or application ADC initialization; it is never restored from storage. [Espressif random-number guidance](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/system/random.html)

Pinned IDF `esp_openthread_start()` creates the stack worker/netif and main loop; it does not call `esp_openthread_auto_start()` or enable IPv6/Thread. The application also checks the disabled role/interface invariant under the stack lock before examining the saved dataset. Only the final explicit calls enable networking. [IDF v5.5.4 stack startup source](https://github.com/espressif/esp-idf/blob/v5.5.4/components/openthread/src/esp_openthread.cpp#L236-L296)

No writer or commissioning UI is supplied. The approval marker is an explicit provisioning record, not a cryptographic protection mechanism. NVS initialization errors fail without erasing storage. Dataset presence alone never triggers joining. No default Thread network is formed, no key is logged and no CLI exposes a credential-writing path. Secure provisioning, per-device key generation/rotation/revocation and encrypted storage remain prerequisites for a deployed product. This prototype has not enabled irreversible secure-boot or flash-encryption eFuses.

## Bounded secure resources

The service is CoAP/DTLS on UDP 5684. It accepts confirmable requests only.

| Resource | Request | Result |
|---|---|---|
| `v1/status` | GET with empty body after DTLS authentication | Boot ID and last accepted wake sequence as exact 16-digit hex strings, awake state, `motor_enabled:false`, `clock_qualified:false` |
| `v1/wake` | POST exactly 16 binary bytes: uint64 boot ID followed by uint64 strictly increasing request sequence, both big-endian | Up to 10 seconds in awake receiving mode; never motion authorization |
| `v1/clock` | POST boot/probe sequence, 16 bytes | Device receive/send timestamps for a one-use four-timestamp exchange |
| `v1/qualify` | POST boot/probe/host-send/host-receive, 32 bytes | Experimental clock assessment; model remains unvalidated |
| `v1/readiness` | GET with empty body | Source-stamped clock diagnostics; always `motor_ready:false` |

Clock probes require an awake window, expire within 500 ms before proof, and assessments last at most 1 s with a 10 ms uncertainty cap. Sleep/detach/reboot discards them. The [clock contract](../../docs/firmware/clock-qualification.md) specifies asymmetric-delay bounds, drift assumptions, source freshness and remaining qualification gates.

A state-changing request needs the current boot ID. Replays, wrong boots, malformed bodies and requests during an active/cooldown window are rejected. No repeated request extends the 10-second deadline. At expiry the radio returns to sleepy operation for at least 5 seconds before another window. Detach cancels the awake state and cannot bypass cooldown. Clock reversal latches the software policy offline until reboot. The deadline is a software timer and requested task/lock budget; actual scheduling and RF current still need measurement.

Idle mode sets `RxOnWhenIdle=false`, MTD mode and an initial 1000 ms poll period. Accepted wake temporarily sets `RxOnWhenIdle=true` and acquires CPU-frequency/no-light-sleep locks. The expiry task blocks without periodic wakeups while idle. No deep-sleep network-retention claim is made. The exact IDF light-sleep configuration follows the vendor's [sleepy-device example](https://github.com/espressif/esp-idf/tree/v5.5.4/examples/openthread/ot_sleepy_device/light_sleep). USB debugging/board circuitry can dominate measured idle consumption.

A five-attempt DTLS startup budget stops the secure service until reboot if exhausted. This is a conservative evaluation behavior, not the final availability policy; malicious connection attempts could deny service. Handshake latency while polling, authenticated-session lifetime, rekey behavior and bounded recovery must be evaluated before selecting production settings.

## Host transport direction

The [native libcoap host adapter](../../integrations/thread_transport/README.md) now exercises actual localhost DTLS sessions, including seven concurrent peers, replay/corruption and bounded wake semantics. It remains a motor-disabled adapter; keep one authenticated session per blind and feed responses into the existing Python coordinator through a small typed boundary. libcoap supports PSK and certificate configuration; the OpenThread side already supplies a DTLS implementation. Avoid spawning a command-line client for every lease or placing PSKs in command-line arguments. A command-line client is only an interoperability fixture with disposable test keys. [libcoap encryption/session API](https://libcoap.net/doc/reference/develop/man_coap_encryption.html)

Python aiocoap's TinyDTLS transport is another possible adapter, but it adds a native DTLS binding and its own lifecycle/packaging constraints. Keep it as an evaluated alternative; the real host-to-C6 session interop has not been tested. [aiocoap TinyDTLS transport](https://aiocoap.readthedocs.io/en/latest/module/aiocoap.transports.tinydtls.html)

DTLS record anti-replay does not replace boot identity, command sequence, source age, monotonic clock translation or readiness checks. The current secure resources cannot execute the coordinator's movement protocol. The localhost libcoap peer test does not establish C6 interoperability. Its explicit CCM8/OpenSSL policy exception is an open production security decision. Next work is the fresh clock-resource cross-build, actual OpenThread peer interoperability, a validated timing profile, strict compact movement/status schemas and coordinator lifecycle integration, before any actuation is enabled.
