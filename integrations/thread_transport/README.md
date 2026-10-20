# Native Thread transport evaluation

This is a working **motor-disabled** host adapter using libcoap and OpenSSL, with a typed Python interface. It exchanges real CoAP over DTLS with an explicitly configured peer. A loopback-only test peer implements the same status/wake/clock/readiness resources and uses the firmware's `RadioWindow` and clock-probe policies. It does not run the OpenThread/C6 stack.

Eighteen local tests passed on macOS arm64 with libcoap **v4.3.5b** (`851533c3cf63d16984d370ce39d586ecb3694971`) and OpenSSL **3.5.9**. They established actual DTLS 1.2 sessions using **PSK-AES128-CCM8**, reused one session across requests, exercised seven simultaneous independent sessions, and rejected wrong keys/identities before resource access. They also tested malformed wake requests, boot/sequence replay, no active-window extension, expiry/cooldown, peer reboot, timeout queue disposal, exact encrypted-record replay and ciphertext corruption. Clock tests add known-offset arithmetic, asymmetric network delay, source-stamped freshness, challenge replay, clock reversal and sleep invalidation.

All peers were on IPv6 loopback, using fresh disposable random keys held in memory. No home network/device, HA installation, commissioning store or C6 hardware was touched. The fixture's radio-window clock advances explicitly for expiry tests; clock exchange uses a monotonic host clock with test-only fault injection. These tests do not measure a real ten-second radio timer, RF power or Thread latency.

## Explicit CCM8 security-policy exception

**The build defaults to refusing this cipher policy.** OpenSSL's normal security levels reject CCM8 because its authentication tag is 64 bits. The current OpenThread `otCoapSecureSetPsk` path selects this constrained-device suite. For this local interoperability evaluation, `SB_ALLOW_CCM8_POLICY=ON` permits exactly `PSK-AES128-CCM8:@SECLEVEL=0` in this private libcoap build. Both successful-session and response checks require DTLS 1.2 and that exact cipher. There is no plaintext or alternative-cipher fallback, and no system OpenSSL configuration is changed. This explicit exception is not a claim that the suite meets OpenSSL's normal policy. [OpenSSL security levels](https://docs.openssl.org/3.2/man3/SSL_CTX_set_security_level/), [OpenThread secure CoAP API](https://openthread.io/reference/group/api-coap-secure)

The production choice remains open: review the 64-bit tag, per-device key lifecycle, traffic/attempt limits and PSK's lack of forward secrecy, or select a full-tag secure transport supported by both endpoints. Do not turn this evaluation option into an unnoticed deployment default. The host adapter deliberately exposes no actuation capability.

## Reproduce without Docker

Requires Git, CMake 3.20+, a C/C++17 compiler, Python 3.10+ and OpenSSL **3.x development files**. OpenSSL 4 is rejected because this pinned libcoap release uses APIs removed there. No system packages or configuration are modified by the build.

From the repository root, obtain the pinned dependency in ignored scratch space:

```sh
git clone --depth 1 --branch v4.3.5b https://github.com/obgm/libcoap.git work/libcoap-src
cmake -S integrations/thread_transport -B work/thread-transport-build \
  -DLIBCOAP_SOURCE_DIR="$PWD/work/libcoap-src" \
  -DSB_BUILD_TEST_PEER=ON -DSB_ALLOW_CCM8_POLICY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build work/thread-transport-build -j 4
```

CMake verifies the exact Git commit and rejects tracked dependency modifications. On macOS with multiple OpenSSL installations, add `-DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3` to the configure command. The project does not fetch dependencies during configuration. On Ubuntu, the usual prerequisites are `build-essential cmake git libssl-dev python3`.

Run the real network tests:

```sh
# macOS
SB_THREAD_LIBRARY="$PWD/work/thread-transport-build/libsb_thread.dylib" \
  python3 -m unittest integrations.thread_transport.test_transport integrations.thread_transport.test_clock -v

# Linux
SB_THREAD_LIBRARY="$PWD/work/thread-transport-build/libsb_thread.so" \
  python3 -m unittest integrations.thread_transport.test_transport integrations.thread_transport.test_clock -v
```

The test peer and UDP replay fixture bind only `::1`. Tests require local IPv6 sockets. `SB_BUILD_TEST_PEER` defaults OFF and must remain off for an installed adapter build. It removes the fixture's C entry points entirely. The separate CCM8 policy remains an explicit decision even for a fixture-free build.

## Adapter contract

`Session(library_path, host_literal, port, identity, key_bytes, timeout_ms=3000)` creates one persistent native session. Hosts must be explicit unicast IPv4/IPv6 literals; there is no DNS, discovery or automatic device selection. An operational installation needs reachable Thread IPv6 addresses and credentials supplied by a deliberate commissioning flow. The native-library path is an administrator-controlled installation choice, never a value accepted from an untrusted device.

- `status()` returns an immutable `Status(boot, last_wake, awake)`. Exact-width hexadecimal boot/sequence fields preserve all 64 bits. Unexpected fields/types, duplicate JSON keys and ambiguous values fail closed. Current responses must state that motion and clock qualification are unavailable.
- `wake(boot, sequence)` requires a matching status-derived boot and a new uint64 sequence. It requests a ten-second radio window and returns that budget. It does not authorize motion, extend the current window or calibrate a clock. The host consumes attempted sequences even when their outcome is uncertain.
- `readiness()` reports source-stamped, motor-disabled diagnostics. Without a matching fresh assessment, source age is unknown. It never represents motion permission.
- `qualify_clock(boot, sequence)` performs an authenticated four-timestamp exchange and a one-use proof. It rejects excessive uncertainty and stale source data. The model remains unvalidated, so a successful assessment still reports `clock_qualified:false` and `motor_ready:false`. See the [clock contract](../../docs/firmware/clock-qualification.md).
- `close()` or the context manager disposes of the session and queued traffic. A failed exchange permanently closes that object's network path. Recovery requires constructing a new session and obtaining fresh status; no command is automatically restored or replayed.
- Calls are synchronous and serialized per session. Run them in coordinator worker threads, outside HA's event loop and the control task. Seven separate sessions can progress concurrently. Request deadlines are 1–5000 ms; the native I/O loop checks them at approximately 10 ms intervals, subject to operating-system scheduling. Close waits for a current bounded call; it is not an asynchronous STOP implementation.

The adapter exposes only fixed status, wake, clock, qualify and readiness resources; there is no arbitrary URI or movement request API. Requests are confirmable CoAP, with one library retransmission allowed within the request deadline; retransmission keeps the same CoAP transaction and is distinct from creating another wake intent. On timeout the native context/session is destroyed, removing any delayed transmission queue. Response tokens bind the answer to the active request, and responses are limited to 512 bytes. DTLS anti-replay and application boot/sequence checks protect different layers. [libcoap session lifecycle](https://libcoap.net/doc/reference/4.3.5/man_coap_session.html), [libcoap PSK setup](https://libcoap.net/doc/reference/4.3.5/man_coap_encryption.html)

Keys are passed in memory, copied into lifetime-owned native storage, never logged or placed in command-line arguments, and cleansed from native storage when closed. The caller's Python `bytes` and the crypto library's own storage have their normal lifetime rules; this is not proof of complete process-memory erasure. No production key vault, key rotation, identity revocation or secure onboarding is implemented.

## Remaining acceptance gates

The local peer uses libcoap/OpenSSL on both ends. **Actual C6/OpenThread interoperability remains untested.** It must cover PSK identity behavior, cipher negotiation, sleepy polling during handshake, seven children, session lifetime/rekey, parent restart, packet loss and measured power/wake latency. The C6's five-attempt server shutdown policy also needs availability testing.

Authenticated four-timestamp assessment and source-stamped diagnostics are implemented and host-tested. A measured, agreed clock model, compact prepare/commit/report/lease schemas, movement lifetime and integration into the existing coordinator remain future work. Until those exist and pass the hardware safeguards, the HA bridge stays in simulation mode. This transport has no motor endpoint, no firmware updater and no permission to provision or actuate a real device.
