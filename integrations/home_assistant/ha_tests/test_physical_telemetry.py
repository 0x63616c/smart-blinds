"""HA -> authenticated HTTP -> owned native DTLS -> portable device endpoint."""
import threading

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_blinds.api import BridgeClient, BridgeError, validate_physical_state
from integrations.physical_bridge.service import PhysicalBridge
from integrations.physical_bridge.server import PhysicalServer
from integrations.physical_bridge.test_bridge import pairing, await_state, TOKEN
from integrations.telemetry_transport.fixture import Peer, LIBRARY
from integrations.thread_transport.client import _now_us
import pytest


async def test_real_physical_read_only_entities_and_independent_sample_ages(hass, socket_enabled):
    offset = [0]

    def start():
        peer = Peer()
        bridge = PhysicalBridge("physical-fixture", [pairing(peer)], LIBRARY,
                                clock=lambda: _now_us()+offset[0])
        await_state(bridge)
        server = PhysicalServer(TOKEN, bridge, port=0)
        worker = threading.Thread(target=server.serve_forever); worker.start()
        return peer, bridge, server, worker

    peer, bridge, server, worker = await hass.async_add_executor_job(start)
    entry = MockConfigEntry(domain="smart_blinds", unique_id="physical-fixture", data={
        "base_url": f"http://127.0.0.1:{server.server_port}", "access_token": TOKEN,
        "mode": "physical_read_only"})
    entry.add_to_hass(hass)
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.states.async_all("cover")
        assert not hass.states.async_all("button")
        registry = er.async_get(hass)

        def entity(domain, suffix):
            return registry.async_get_entity_id(domain, "smart_blinds", f"physical-fixture:blind-1:{suffix}")

        battery, usb, charging = entity("sensor", "battery"), entity("binary_sensor", "usb"), entity("binary_sensor", "charging")
        assert float(hass.states.get(battery).state) == 42.188
        assert hass.states.get(battery).attributes["simulation"] is False
        assert hass.states.get(usb).state == "on"
        assert hass.states.get(charging).state == "off"
        original = hass.states.get(battery).attributes["source_sample_us"]
        requests = peer.requests
        await entry.runtime_data.async_refresh()
        assert peer.requests == requests  # HTTP is cache-only.
        with pytest.raises(BridgeError):
            await entry.runtime_data.client.async_move("room", 50)
        assert peer.requests == requests

        offset[0] = 61_000_000
        await entry.runtime_data.async_refresh()
        assert float(hass.states.get(battery).state) == 42.188
        assert hass.states.get(usb).state == "unknown"
        assert hass.states.get(charging).state == "unknown"
        offset[0] = 1_801_000_000
        await entry.runtime_data.async_refresh()
        assert hass.states.get(battery).state == "unknown"
        assert hass.states.get(battery).attributes["source_sample_us"] == original
        assert hass.states.get(battery).attributes["last_observed_percent"] == 42.188
        assert peer.requests == requests
        assert await hass.config_entries.async_unload(entry.entry_id)
    finally:
        def close():
            server.shutdown(); server.server_close(); worker.join(timeout=1)
            peer.__exit__()
        await hass.async_add_executor_job(close)


def test_physical_mode_cannot_be_selected_by_response_or_command_payload():
    with pytest.raises(BridgeError):
        validate_physical_state({"schema_version": 1, "mode": "simulation"})
    # Existing configuration defaults to simulation; explicit local selection is required.
    client = BridgeClient(None, "http://127.0.0.1:8766", TOKEN)
    assert client.mode == "simulation"
