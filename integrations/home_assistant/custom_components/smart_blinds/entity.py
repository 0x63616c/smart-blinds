"""Common measured entity state and device identity."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SmartBlindsEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, device_id, suffix):
        super().__init__(coordinator)
        self.device_id = device_id
        bridge_id = coordinator.data["bridge_id"]
        self._attr_unique_id = f"{bridge_id}:{device_id}:{suffix}"
        if device_id == "room":
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, bridge_id)})
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{bridge_id}:{device_id}")},
                name=self.state_data["name"], manufacturer="Smart Blinds",
                model="Virtual blind", via_device_id=coordinator.bridge_device_id,
            )

    @property
    def state_data(self):
        if self.device_id == "room":
            return self.coordinator.data["group"]
        return next((item for item in self.coordinator.data["devices"] if item["id"] == self.device_id), {})

    @property
    def available(self):
        return super().available and self.state_data.get("available", False)
