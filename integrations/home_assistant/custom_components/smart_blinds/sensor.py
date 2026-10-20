"""Battery values preserve unknown and stale states."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from .const import BATTERY_MAX_AGE_MS
from .entity import SmartBlindsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Battery(entry.runtime_data, item["id"])
                        for item in entry.runtime_data.data["devices"]])


class Battery(SmartBlindsEntity, SensorEntity):
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id, "battery")

    @property
    def native_value(self):
        age = self.state_data.get("battery_age_ms")
        if age is None or age > BATTERY_MAX_AGE_MS:
            return None
        return self.state_data.get("battery_percent")

    @property
    def extra_state_attributes(self):
        return {"sample_age_ms": self.state_data.get("battery_age_ms"), "simulation": True}
