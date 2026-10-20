"""Real HA setup, config flow and service paths against the bridge contract."""
from copy import deepcopy

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from integrations.bridge.simulator import Simulation
from custom_components.smart_blinds.api import BridgeError, normalize_url, validate_state
from custom_components.smart_blinds.const import DOMAIN

URL = "http://127.0.0.1:8765"
TOKEN = "test-only-" + "s" * 40


@pytest.fixture
def state():
    return Simulation(1000).state()


@pytest.fixture
def entry():
    return MockConfigEntry(domain=DOMAIN, unique_id="smart-blinds-simulator",
                           data={"base_url": URL, "access_token": TOKEN})


def entity_id(hass, domain, device, kind):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN,
            f"smart-blinds-simulator:{device}:{kind}")


def last_post(mock):
    return [call for call in mock.mock_calls if call[0] == "POST"][-1]


async def setup(hass, entry, aioclient_mock, state):
    aioclient_mock.get(URL + "/v1/state", json=state)
    aioclient_mock.post(URL + "/v1/move", json={"accepted": True}, status=202)
    aioclient_mock.post(URL + "/v1/stop", json={"accepted": True}, status=202)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_flow_auth_duplicate_and_setup(hass, aioclient_mock, state):
    aioclient_mock.get(URL + "/v1/state", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER},
                            data={"base_url": URL, "access_token": TOKEN})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL + "/v1/state", json=state)
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
                            {"base_url": URL, "access_token": TOKEN})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER},
                            data={"base_url": URL, "access_token": TOKEN})
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_entities_services_and_no_optimistic_position(hass, entry, aioclient_mock, state):
    await setup(hass, entry, aioclient_mock, state)
    covers = hass.states.async_all("cover")
    assert len(covers) == 8
    assert len(hass.states.async_all("sensor")) == 7
    assert len(hass.states.async_all("binary_sensor")) == 7
    group = entity_id(hass, "cover", "room", "cover")
    measured = hass.states.get(group).attributes["current_position"]
    await hass.services.async_call("cover", "set_cover_position", {"entity_id": group, "position": 50}, blocking=True)
    assert last_post(aioclient_mock)[2] == {"target": "room", "position": 50, "align": False}
    assert hass.states.get(group).attributes["current_position"] == measured
    individual = entity_id(hass, "cover", "blind-7", "cover")
    await hass.services.async_call("cover", "open_cover", {"entity_id": individual}, blocking=True)
    assert last_post(aioclient_mock)[2] == {"target": "blind-7", "position": 100, "align": False}
    align = entity_id(hass, "button", "room", "align")
    await hass.services.async_call("button", "press", {"entity_id": align}, blocking=True)
    assert last_post(aioclient_mock)[2] == {"target": "room", "position": 50, "align": True}
    await hass.services.async_call("cover", "stop_cover", {"entity_id": individual}, blocking=True)
    assert last_post(aioclient_mock)[1].path == "/v1/stop"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unaligned_group_and_stale_battery_preserve_unknown(hass, entry, aioclient_mock, state):
    state["group"]["aligned"] = False
    state["group"]["position"] = None
    state["devices"][0]["battery_age_ms"] = 1800001
    await setup(hass, entry, aioclient_mock, state)
    group = hass.states.get(entity_id(hass, "cover", "room", "cover"))
    assert group.attributes.get("current_position") is None
    assert group.attributes["aligned"] is False
    assert hass.states.get(entity_id(hass, "sensor", "blind-1", "battery")).state == "unknown"
    assert hass.states.get(entity_id(hass, "binary_sensor", "blind-1", "charging")).state == "unknown"


async def test_failed_commands_do_not_change_state_or_retry(hass, entry, aioclient_mock, state):
    await setup(hass, entry, aioclient_mock, state)
    group = entity_id(hass, "cover", "room", "cover")
    previous = hass.states.get(group).attributes["current_position"]
    aioclient_mock.clear_requests()
    aioclient_mock.post(URL + "/v1/move", status=409)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("cover", "set_cover_position", {"entity_id": group, "position": 50}, blocking=True)
    assert aioclient_mock.call_count == 1
    assert hass.states.get(group).attributes["current_position"] == previous


async def test_disconnect_and_missing_member_unavailable(hass, entry, aioclient_mock, state):
    state["devices"][1]["available"] = False
    state["group"]["available"] = False
    await setup(hass, entry, aioclient_mock, state)
    assert hass.states.get(entity_id(hass, "cover", "room", "cover")).state == "unavailable"
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL + "/v1/state", status=503)
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
    assert all(s.state == "unavailable" for s in hass.states.async_all("cover"))


def test_invalid_state_url_and_unknown_battery(state):
    for url in ("http://192.168.1.2:8765", "http://user:pass@localhost", "http://localhost/path", "file:///tmp/bridge"):
        with pytest.raises(ValueError):
            normalize_url(url)
    assert normalize_url("https://blinds.example/") == "https://blinds.example"
    assert normalize_url(URL) == URL
    for change in (lambda s: s.update(mode="hardware"),
                   lambda s: s["group"].update(position=float("nan")),
                   lambda s: s["group"].update(aligned=False),
                   lambda s: s["devices"][0].update(battery_percent=101),
                   lambda s: s["devices"][0].update(battery_age_ms=-1)):
        invalid = deepcopy(state)
        change(invalid)
        with pytest.raises(BridgeError):
            validate_state(invalid)
    state["devices"][0]["battery_percent"] = None
    state["devices"][0]["battery_age_ms"] = None
    assert validate_state(state)["devices"][0]["battery_percent"] is None


async def test_real_ha_service_through_authenticated_simulator(hass, socket_enabled):
    """Use a real loopback socket, real HA entities and the group coordinator."""
    import threading
    from integrations.bridge.server import SimulatorServer

    def start_server():
        server = SimulatorServer(TOKEN, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    server, thread = await hass.async_add_executor_job(start_server)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="smart-blinds-simulator",
        data={"base_url": f"http://127.0.0.1:{server.server_port}", "access_token": TOKEN})
    try:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        group = entity_id(hass, "cover", "room", "cover")
        await hass.services.async_call("cover", "set_cover_position",
                                      {"entity_id": group, "position": 50}, blocking=True)
        with server.lock:
            assert server.simulation.job.phase.value == "armed"
            assert {node.pending["target_height_mm"] for node in server.simulation.nodes.values()} == {1030}
        await hass.services.async_call("cover", "stop_cover", {"entity_id": group}, blocking=True)
        with server.lock:
            assert server.simulation.job.phase.value == "aborted"
            assert all(node.state == "idle" for node in server.simulation.nodes.values())
        assert await hass.config_entries.async_unload(entry.entry_id)
    finally:
        def shutdown():
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        await hass.async_add_executor_job(shutdown)
