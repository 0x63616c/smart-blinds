# Authenticated clock assessment

The motor-disabled Thread target and native host adapter now exchange boot-bound, one-use timing probes over DTLS. They calculate a conservative time interval and return source-stamped readiness diagnostics. **The experimental oscillator model is unvalidated: `clock_model_validated`, `clock_qualified` and `motor_ready` remain false.** No GPIO or motion endpoint is enabled by this work.

The portable implementation is `firmware/include/smart_blinds/clock_bounds.hpp`; `clock_protocol.hpp` shares the exact readiness representation between the C6 and loopback fixture. The host arithmetic is in `integrations/thread_transport/clock.py`. The native tests exercise actual libcoap/OpenSSL sessions and deliberate encrypted-packet delays. They do not run OpenThread, measure C6 clock drift or prove RF timing.

## Protocol

All requests are confirmable, authenticated CoAP. Every binary integer is an unsigned 64-bit big-endian value. JSON identities and timestamps use exactly 16 lowercase hexadecimal digits, avoiding floating-point truncation. Each probe sequence must be nonzero and strictly increase within a device boot. A reconnect reads status and readiness to learn the current boot and last probe; it never restores a previous assessment.

| Resource | Body | Response |
|---|---|---|
| `GET v1/status` | Empty | Existing boot/wake state; unchanged contract |
| `POST v1/wake` | Boot, wake sequence | Existing bounded 10 s radio window; unchanged contract |
| `POST v1/clock` | Boot, probe sequence (16 bytes) | Boot, probe, device receive `t2` and send `t3` timestamps |
| `POST v1/qualify` | Boot, probe, host send `t1`, host receive `t4` (32 bytes) | Source-stamped assessment/readiness, or rejection |
| `GET v1/readiness` | Empty | Boot, last probe, source sample time, awake/clock diagnostics and `motor_ready:false` |

The host records `t1` immediately before its native request and `t4` immediately after the response. The device records `t2` at handler entry and `t3` before serializing its reply. Crypto, wrappers, formatting, queues and network transit therefore widen the observed interval; they are not silently subtracted as known latency. The follow-up must match the device's single stored probe. The device reconstructs the same exchange from its own `t2/t3` and the echoed `t1/t4`. A submitted matching proof is consumed even if its arithmetic is rejected. Starting a newer probe immediately discards older timing evidence.

Wrong boot/probe, reused sequence, malformed body, sleep, reversed clock or a proof older than 500 ms is rejected. Return to sleepy mode, detach, radio-policy failure or reboot invalidates clock evidence. Timing requests do not extend the awake deadline. DTLS replay checks, CoAP transaction binding and application boot/probe checks are separate protections.

## Bound, not equal-delay assumption

Define offset as **device time minus host time**. With nonnegative path delays and locally ordered timestamps, the zero-drift offset lies in:

```text
lower = t3 - t4
upper = t2 - t1
```

Unequal outward/return delays remain inside this interval. The midpoint is only a convenient estimate; its uncertainty is half the full interval width, rounded upward. The implementation pads both ends by `ceil(round_trip × 1000 / 1,000,000) + 2 us`, then grows uncertainty by another `ceil(age × 1000 / 1,000,000)`. These are **explicit experimental assumptions**: a combined relative-offset growth budget of 1000 ppm, in both local time domains, and a 2 us timestamp guard. They are not C6 or host oscillator specifications. The four-timestamp arrangement is standard; this interval policy is the project's conservative derivation. [NTP four-timestamp equations](https://www.rfc-editor.org/rfc/rfc5905.html#section-8)

Round trips over 500 ms, invalid signed timestamp range, reversed clocks or device processing time greater than host round trip are rejected. The last check can conservatively reject an otherwise usable exchange when two oscillators have different rates. It never narrows the interval to force acceptance.

An assessment must fit a **10 ms** maximum absolute error, remains valid for at most **1 s**, and can expire sooner as the drift allowance grows. A readiness source timestamp is translated through the entire offset interval: the earliest possible source time determines its worst possible age. If that age exceeds **100 ms**, or even the earliest possible source time is in the future, the host rejects it. Receipt time alone cannot refresh old telemetry. Host uncertainty is discarded on an ambiguous/failed exchange; there is no automatic probe retry.

## Why the default remains unqualified

ESP Timer advances using RTC time after light sleep and restarts after deep sleep. The awake radio window holds a no-light-sleep power lock, and all prior timing evidence is discarded before returning to sleep. This avoids carrying an awake estimate across RTC compensation. It does not prove an oscillator tolerance, task latency or radio deadline. [ESP-IDF 5.5.4 ESP Timer documentation](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/system/esp_timer.html#sleep-mode-considerations)

A measured clock profile must cover host timing, C6 temperature/supply variation, awake frequency stability, timestamp quantization and worst scheduling behavior. That profile needs a reviewed version/identity and both peers must agree before a production build may set `model_validated=true`. No remote resource or configuration toggle in this image can set it.

The existing motion coordinator proposes a start 3 s ahead. A 1 s clock assessment cannot cover that schedule by itself: a future adapter must refresh bounded clock evidence during preparation, verify it through the scheduled start and stop on lost qualification while moving. It must also bind calibration, physical reference, pack health, motor-driver readiness, watchdog state and command lease. `Readiness` objects here are diagnostics, never cached authorization tokens. The HA bridge still uses the simulator and cannot actuate through this transport.

## Verification

The portable clock test is included in the normal firmware CTest build. It simulates known offsets, asymmetric paths and a drifting oscillator, and checks overflow, staleness, boot/probe binding, sleep invalidation and latched clock reversal. Native transport tests preserve the earlier nine DTLS tests and add timing tests, including 40 ms one-way delay, 20 ms each-way delay, delayed authenticated readiness, consumed proofs, source-clock jumps and return to sleep.

```sh
cmake -S firmware -B work/firmware-build
cmake --build work/firmware-build
ctest --test-dir work/firmware-build --output-on-failure
# With the native fixture built; use .so on Linux:
SB_THREAD_LIBRARY="$PWD/work/thread-transport-build/libsb_thread.dylib" \
  python3 -m unittest integrations.thread_transport.test_transport integrations.thread_transport.test_clock -v
```

Local host tests pass. The added C6 resources still require the pinned ESP-IDF cross-build for this source revision, followed by actual C6/Thread interoperability and hardware timing measurements. Previous radio binary sizes are not size measurements for these additions.
