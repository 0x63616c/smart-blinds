# Trade Study: Radio, sleep and coordinated movement

**Date:** 2026-10-19
**Status:** OPEN

## 1. Context

Seven installed blinds should reach 60–90 days between charges on 3S2P packs. The user accepts a few seconds before remote movement, while local buttons should respond immediately. Group motion needs a common clock, all-member readiness and frequent supervision once awake. The user may already own a HomePod; its model, Thread network and Home Assistant arrangement are not verified. No transport is selected or measured yet.

## 2. Options

### Option A: ESP32-C6, Thread sleepy device and local group coordinator

A sleepy end device polls its parent while idle and stays awake during commands/movement. OpenThread exposes a configurable poll interval; 1 s is an initial experiment, not a measured current/latency result. A powered border router provides IPv6 reachability. A local coordinator handles shared-height semantics; custom authenticated application messages are required unless implemented as a Matter extension. A Thread network alone does not provide a ready-made Home Assistant cover integration. [OpenThread poll API](https://openthread.io/reference/group/api-link-link), [Espressif OpenThread](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/openthread.html)

### Option B: ESP32-C6, Wi-Fi with modem and automatic light sleep

Use the existing access point and a local coordinator. Connected sleep behavior depends on the access point, link and firmware configuration. Espressif distinguishes modem/automatic light sleep, which can preserve a connection, from explicit light/deep sleep, which does not. Wake/reconnect every few seconds must be energy-measured; quoting deep-sleep current for a responsive Wi-Fi device is invalid. [Espressif sleep documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-reference/system/sleep_modes.html)

### Option C: ESP32-C6, Matter over Thread plus group coordinator

Matter can expose standard individual covers and offers a commissioning ecosystem. Exact shared-datum, future-start and fail-together behavior still needs a coordinator and an explicitly implemented extension; issuing seven ordinary percentage commands is insufficient. An actual Matter firmware/commissioning/update implementation is needed, not just Thread radio support. HA currently documents Matter OTA failures when Apple border routers are present. [HA Matter](https://www.home-assistant.io/integrations/matter/)

## 3. Comparison Table

| Criterion | A: Custom Thread | B: Connected Wi-Fi | C: Matter over Thread |
|---|---|---|---|
| Idle power prospect | Good candidate for periodic short polls; measurement required | Potentially higher; strongly dependent on AP and traffic | Good candidate, with stack/subscription overhead to measure |
| Added home equipment | Compatible powered border router unless already available | Existing Wi-Fi AP | Compatible border router and Matter controller |
| Home Assistant work | Own coordinator bridge and secure onboarding | Own coordinator bridge; familiar IP transport | Standard cover integration plus custom group coordination |
| Coordinated start | Explicit protocol under our control | Explicit protocol under our control | Extra group protocol beyond ordinary per-cover actions |
| Firmware effort | Thread onboarding, authenticated protocol, updates | Wi-Fi credentials, authenticated protocol, reconnect/power tuning | Matter commissioning, attributes, extensions and update paths |
| Existing HomePod | Possible IP route, credentials and commissioning unresolved | Irrelevant | Mini/2nd generation may supply route; update constraint applies |
| PCB effect | C6 retains option; antenna keepout required | Same C6; Wi-Fi peaks affect regulator | Same C6, sufficient flash needed for stack and update partitions |
| Current sourcing cost | Exact module stock/package/assembly quote pending electrical study | Same candidate module, no added radio | Same candidate module, flash requirement may affect part |

## 4. Recommendation

**Rationale:** prototype option A for battery behavior while retaining Wi-Fi in the C6 module. Keep the portable control core independent of the radio. Compare measured idle Wh/day, command latency and seven-device fault behavior before final selection. The current tests implement the command/coordinator semantics only.

**What we're giving up:** a custom Thread protocol requires our own onboarding and integration work; it cannot be described as Matter plug-and-play. Option C may ultimately improve setup but must preserve the special group behavior. Home Assistant lists HomePod mini and HomePod 2nd generation as border routers; ownership of an unspecified HomePod is insufficient evidence. [HA Thread](https://www.home-assistant.io/integrations/thread/)

**When to revisit:** confirmed HomePod model/network credentials, selected module/flash size, real standby power and a working commissioning/update demonstration. Keep wired recovery on the PCB. For any Matter choice with Apple routing, validate an alternative update path rather than promise HA OTA. [HA update limitation](https://www.home-assistant.io/integrations/matter/#matter-ota-device-updates)
