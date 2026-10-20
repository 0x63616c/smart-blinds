# Parked battery and source telemetry

The Wi-Fi motion image has a separate authenticated `POST /v1/telemetry` resource.
It copies completed observations from the actual sensor owner. A read performs
no bus I/O, wake, clock qualification, lease renewal, reference change or charging
operation. The existing fifteen-field motion status and all its age limits remain
unchanged. The image still ships with empty physical records and charging OFF.

An explicit physical read-only bridge connects this endpoint to Home Assistant
battery, USB-connected and charging diagnostics. This is implemented application
wiring, tested with the real HA framework, real loopback HTTP/DTLS and the portable
device endpoint. Actual C6 sensor/control task sources also run against an injected
SDK/bus. No device was flashed, commissioned or measured; loopback is not RF proof.

## Observations and presentation

The request is sixteen bytes: big-endian expected boot and nonzero correlation
nonce. The strict schema-1 JSON response is bounded to 768 bytes and echoes both.
It carries a response `sent_us` separately from every original source sample:

| Section | Origin | Display rule |
|---|---|---|
| `battery` | Completed joint gauge report; original boot/pack/bus epoch/serial/sample and SOC | Retained history through healthy park. Percentage becomes unknown after 30 minutes or a fault; original value/time remain diagnostic attributes. |
| `charger` | Verified inhibited OFF capture and its original start | `not_charging` only while the observation is valid, no source event is pending and age is at most 60 seconds. Otherwise unknown. `input_present` is BQ input presence, not Type-C attachment. |
| `pd` | Completed STUSB monitor observation and original bus/monitor epoch/serial/start | Attachment is the observed PORT_STATUS attach bit. A plugged-in but blocked source may be attached while BQ input is absent. `policy_observed` is historical constrained-current evidence, not a charging grant. After 60 seconds, pending event or fault, current presentation is unknown. |
| `fault` | First known owner failure, or pending runtime fault before detailed publication | A later successful reading cannot clear or replace an observed first cause. |
| `charge_authorized` | Image policy | Always false. This does not claim a measured charging current. |

Age is device-monotonic elapsed time plus the complete host exchange RTT and
subsequent host elapsed time, each rounded outward to milliseconds. No calibrated
clock is manufactured by this calculation. It is informational, not a substitute
for bounded motion clocks or the 30/100/250 ms supervision limits. Zero uptime is
a valid sample time; absence is represented by null.

The sensor owner publishes a fixed-size copy. Control readers keep their own
coherent mailbox authority. Network reading checks source-event/busy/epoch fences,
then samples response time **after** copying; a healthy newer publication cannot
appear to originate in the future merely because the reader began earlier.
The physical OFF guard likewise samples its clock after its fixed-size queue copy;
its original 30 ms limit, identity checks and actual pad checks remain intact.
An unqualified boot does not create a sensor park request before any qualified
I/O owner exists. A previously initialized lifetime still transitions and retires
if I/O qualification is lost; this does not waive its physical OFF proof.

The current application does **not** acquire the gauge periodically while parked.
Source-only polling does not refresh battery history or the parked continuity
interval. Long idle therefore eventually shows an unknown battery percentage.
Periodic sensor-owned informational acquisition is a separate product gap, not
something HTTP polling silently enables.

## One connection owner and explicit HA mode

See the [physical bridge](../../integrations/physical_bridge/README.md) and
[telemetry transport](../../integrations/telemetry_transport/README.md). One worker
per explicitly selected literal endpoint owns its native session and teardown.
Equivalent literal IP spellings are normalized before duplicate-owner checking.
No discovery, automatic boot adoption, reconnect, wake or command method exists.
A failure closes the owner and marks the device unavailable until explicit service
recovery. This bounded evaluation recovery is not final unattended behavior.

The service polls each healthy device once per fifteen-second idle interval, after
a bounded exchange. HA's one-second HTTP reads only copy its cache. This holds a
DTLS owner below the current server idle timeout, but adds radio exchanges: actual
AP/DTIM airtime, source-service cost and whole-pack energy still require measurement.
It causes no gauge wake. Do not claim the 60-day battery target from this cadence.

HA mode is chosen and pinned in local configuration. Simulator mode retains its
covers/alignment behavior. Physical read-only mode creates only diagnostic entities;
fault, pending state, source age and charging authorization are attributes. It
cannot be upgraded by a remote response, and does not create a cover or button.
No owner's HA configuration was changed.

## Remaining boundaries

Do not run this service alongside the per-job group transport for the same device.
Physical covers require a sole actor spanning telemetry, preflight, movement,
settling and verified OFF handoff; it must preserve the existing durable message
ledger and suppress diagnostics while motion is supervised. That integration is
not provided by this read-only checkpoint.

Actual gauge/pack/calibration/reference/factory records, commissioning, secure
updates, charge-enable control and local endpoint gestures remain absent. USB-only
startup at the OFF profile's 100 mA limit still needs radio-before-power gating and
measured TX-peak support. An observed source is not proof of dead-pack bootstrap.
The ST supply/bus revision and physical electrical qualification remain hardware
gates described in the [PD runtime contract](pd-source-runtime.md).
