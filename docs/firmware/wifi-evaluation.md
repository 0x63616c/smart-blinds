# Wi-Fi evaluation

**Associated Wi-Fi with automatic light sleep now leads the radio evaluation.**
The existing Thread target remains a separate fallback/research target. Neither
target has proved the two-to-three-month battery goal, seven-device radio timing
or operation on the owner's network.

The separate [`esp-idf-wifi`](../../firmware/esp-idf-wifi/README.md) image is an
executable, **motor-disabled** evaluation. It implements Wi-Fi association,
authenticated DTLS status/wake/clock requests, bounded awake periods and explicit
session ownership. Motor and charging outputs stay held OFF. It does not contain
a motion worker, ADC/I2C reader, commissioning service or OTA endpoint. A wake or
successful clock exchange never grants motion permission.

## Why evaluate this mode first?

Espressif's C6 reference reports 0.919 mA at DTIM1, 0.368 mA at DTIM3 and
0.172 mA at DTIM10 for associated automatic light sleep in a shielded environment.
Those are module reference figures, not whole-pack measurements. The DTIM3
modem-sleep/frequency-scaling result is 13.9 mA, so CPU automatic light sleep and
the absence of unnecessary polling matter materially.
[Espressif Wi-Fi power measurements](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/low-power-mode/low-power-mode-wifi.html).

The pinned C6 configuration supports its **internal RC oscillator**; this
evaluation assumes no external 32 kHz crystal. The guide calls it 150 kHz and the
C6 Kconfig labels it 136 kHz; both select `CONFIG_RTC_CLK_SRC_INT_RC`. This does
not establish a precise motion clock. Clock evidence is invalidated on return to
idle and the physical clock model remains unqualified.
[Pinned recommended configuration](https://github.com/espressif/esp-idf/blob/v5.5.4/docs/en/api-guides/low-power-mode/low-power-mode-soc.rst#L346-L399),
[C6 clock choices](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_hw_support/port/esp32c6/Kconfig.rtc).

For scale, 0.368 mA at 3.3 V is about 0.125 mA from a 10.8 V pack at an assumed
90% conversion efficiency, before other board loads. At the provisional
305.8 seconds of daily movement, reducing awake radio current from an assumed
150 mA to the documented 73 mA Thread RX figure saves only about 1.53 Wh over
60 days. Motor load and whole-board idle consumption can dominate that saving.
The module specifies Wi-Fi RX around 78 mA and substantially higher transmit
peaks; regulator/transient qualification is still required.
[C6-WROOM module electrical data](https://documentation.espressif.com/esp32-c6-wroom-1_wroom-1u_datasheet_en.html).

The current verbose seven-peer loopback protocol exceeded the entire
250 kbit/s Thread PHY before overhead. Even the studied compact exchange had
insufficient comfortable mesh airtime at existing supervision limits.
[Supporting radio trade study](radio-trade-study.md) records frame, retry,
polling, multi-hop and 60-day energy calculations. No deadlines were widened.

## Executed boundary

The initial build has **no default credentials and does not join any network**.
Before any Wi-Fi or board GPIO initialization it requires an explicitly approved
board/configuration record in existing encrypted NVS. Default boot additionally
requires already-enabled flash encryption and valid existing encrypted NVS keys.
Missing/invalid storage stops the application. It does not erase NVS, generate
keys, burn eFuses or enable encryption. A separately named, default-OFF build
exception permits only disposable bench credentials; it is not a commissioning
path for the owner's network.

The app uses STA mode, WPA2-or-better authentication and RAM-only Wi-Fi SDK
credential storage. Per-device DTLS identities/keys are read from approved NVS.
No credential is printed. There is no default SoftAP, discovery-based selection,
BLE commissioning or automatic transport migration. The host test fixture uses
random disposable keys on loopback only.

Idle uses `WIFI_PS_MIN_MODEM` and automatic CPU light sleep. Its receive delay
depends on the AP DTIM; a 100-TU beacon with DTIM3 would imply a 307 ms interval,
before losses or queueing. An authenticated wake grants a 10-second awake
window with replay protection and a five-second cooldown; it cannot extend an
existing window. Awake operation selects `WIFI_PS_NONE` and holds
`ESP_PM_NO_LIGHT_SLEEP` and `ESP_PM_CPU_FREQ_MAX`. SDK events and physical
buttons wake the blocking loop through an ISR-capable event descriptor, avoiding
an idle 10 ms polling task.
[Wi-Fi power-save behavior](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c6/api-guides/wifi.html#wi-fi-power-saving),
[IDF event descriptor API](https://github.com/espressif/esp-idf/blob/v5.5.4/components/vfs/include/esp_vfs_eventfd.h).

The selected GPIO profile preloads and holds motor request, charger permission
and encoder permission HIGH (OFF), WDI HIGH and both motor inputs LOW. These
pins and GPIO0/1 buttons explicitly opt out of automatic sleep pin switching;
the peripheral power domain remains enabled for GPIO wake. Buttons only wake
this evaluation, so **physical blind movement is not implemented in this image**.
There is no hold-release or PWM code. Pad/mux verification, queue overflow and
power-management errors latch an unavailable state.
[Sleep GPIO switching](https://github.com/espressif/esp-idf/blob/v5.5.4/components/esp_pm/Kconfig#L81-L92).

DTLS has one authenticated owner. A second controller cannot replace it.
Pending SDK network events block new application requests before the owner
drains the queue. Address change, network loss, DTLS close/error and renegotiation
invalidate ownership/clock evidence. No pending request is replayed on reconnect.
The policy's future operation hooks forbid recovery or sleep during owned work;
the evaluation never calls those hooks and always rejects motion routes.

Three association attempts per boot, each with an eight-second deadline and
30/120-second backoff, bound scanning. Five DTLS error events latch service OFF.
These conservative **evaluation limits can leave remote access unavailable until
restart after an ordinary AP outage or bad traffic**. They are not final
unattended recovery behavior. A later production recovery policy must be bounded,
stationary and acquire new ownership; it must never resume an old motion.

## Evidence and remaining checks

Local evidence: the pinned full C6 image compiles; twelve portable CTest targets
pass; six real localhost OpenSSL DTLS tests exercise the same portable policy
and parser. These tests cover wrong credentials, record replay/corruption,
malformed/stale-boot wake, second-controller rejection, network loss, clock
assessment and unconditional motion-route rejection.

The host fixture does **not** prove Mbed TLS interoperability on a C6, RF delivery,
sleep current, wake-pin behavior or physical output safety. The new image has
not been flashed. Encrypted storage and secure-boot commissioning need a separate
reviewed factory procedure; compile success does not provision either.

Before enabling any motion integration:

- Measure actual AP beacon/DTIM, association retention and buffered unicast
  latency, including DHCP, ARP, multicast and normal background traffic.
- Measure at least 24 hours of whole-pack idle consumption, Wi-Fi RX/TX peaks,
  GPIO levels across sleep/wake/reset and button response.
- Prove the physical clock model, worker scheduling, IO/power evidence and
  watchdog behavior. Keep the existing 300 ms source lease, 100 ms accepted
  source age, 30 ms readiness bound and 20 ms control-gap limit.
- Measure seven-peer preflight and active exchanges on Wi-Fi. The proposed
  radio-only associated wake-to-preflight target is 1.5 seconds. The current
  temperature monitor separately needs 2.8–4 seconds after a long idle gap,
  before the common scheduled start. Fresh sensing while the MCU sleeps and
  prompt local-button response remain under review; neither timing is a
  measured promise.
- Only after those gates, connect the reviewed motion runtime with explicit
  qualification. No reconnect, address migration, rekey or OTA may resume an
  active job. Preserve definitive OFF/settling evidence before idle sleep.

The prior loopback `fault/io` and source-age intermittent failures remain an
open investigation with first-fault diagnostics and a deliberate stall
regression. Passing this separate Wi-Fi checkpoint does not resolve them.
