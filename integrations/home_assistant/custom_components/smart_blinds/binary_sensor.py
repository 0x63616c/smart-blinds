"""Charging and reference diagnostics from bridge state."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .const import BATTERY_MAX_AGE_MS
from .entity import SmartBlindsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = [Charging(coordinator, item["id"]) for item in coordinator.data["devices"]]
    if coordinator.data["mode"] != "simulation":
        entities += [UsbConnected(coordinator, item["id"]) for item in coordinator.data["devices"]]
    async_add_entities(entities)


class Charging(SmartBlindsEntity, BinarySensorEntity):
    _attr_name = "Charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id, "charging")

    @property
    def is_on(self):
        physical = self.coordinator.data["mode"] != "simulation"
        age = self.state_data.get("charger_age_ms" if physical else "battery_age_ms")
        return self.state_data.get("charging") if age is not None and age <= (60000 if physical else BATTERY_MAX_AGE_MS) else None


class UsbConnected(SmartBlindsEntity, BinarySensorEntity):
    _attr_name = "USB connected"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id, "usb")

    @property
    def is_on(self):
        return self.state_data.get("usb_connected")

    @property
    def extra_state_attributes(self):
        return {"sample_age_ms": self.state_data.get("pd_age_ms"),
                "source_sample_us": self.state_data.get("pd_sample_us"),
                "observed_pd_state": self.state_data.get("pd_state"),
                "pending": self.state_data.get("pending"), "fault": self.state_data.get("fault"),
                "charge_authorized": False}
