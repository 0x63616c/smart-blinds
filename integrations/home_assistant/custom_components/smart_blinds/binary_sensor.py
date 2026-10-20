"""Charging and reference diagnostics from bridge state."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .const import BATTERY_MAX_AGE_MS
from .entity import SmartBlindsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Charging(entry.runtime_data, item["id"])
                        for item in entry.runtime_data.data["devices"]])


class Charging(SmartBlindsEntity, BinarySensorEntity):
    _attr_name = "Charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id, "charging")

    @property
    def is_on(self):
        age = self.state_data.get("battery_age_ms")
        return self.state_data.get("charging") if age is not None and age <= BATTERY_MAX_AGE_MS else None
