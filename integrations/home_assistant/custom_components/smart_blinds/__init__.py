"""Home Assistant interface with explicit simulation or read-only physical mode."""
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

from .api import BridgeClient
from .const import CONF_BASE_URL, CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import SmartBlindsCoordinator


async def async_setup_entry(hass, entry):
    coordinator = SmartBlindsCoordinator(hass, entry, BridgeClient(
        async_get_clientsession(hass), entry.data[CONF_BASE_URL], entry.data[CONF_TOKEN], entry.data.get("mode", "simulation")))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    physical = coordinator.data["mode"] == "physical_read_only"
    bridge_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name="Smart Blinds simulator" if coordinator.data["mode"] == "simulation" else "Smart Blinds", manufacturer="Smart Blinds",
        model="Physical read-only bridge" if physical else "Physical control bridge" if coordinator.data["mode"] == "physical_control" else "Seven-blind software simulator",
    )
    coordinator.bridge_device_id = bridge_device.id
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.BINARY_SENSOR] if physical else PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
        if entry.data.get("mode") == "physical_read_only" else PLATFORMS)
