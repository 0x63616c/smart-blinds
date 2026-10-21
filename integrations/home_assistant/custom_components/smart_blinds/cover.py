"""Group positions share physical height; individuals retain full travel."""
from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature, ATTR_POSITION
from .entity import SmartBlindsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([BlindCover(coordinator, "room"), *[
        BlindCover(coordinator, device["id"]) for device in coordinator.data["devices"]]])


class BlindCover(SmartBlindsEntity, CoverEntity):
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE |
                                CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION)

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator, device_id, "cover")
        self._attr_name = ("Room blinds (simulation)" if coordinator.data["mode"] == "simulation" else "Room blinds") if device_id == "room" else None

    @property
    def available(self):
        return super().available and (self.coordinator.data["mode"] != "physical_control" or self.state_data.get("control_configured", False))

    @property
    def current_cover_position(self):
        position = self.state_data.get("position")
        return round(position) if position is not None else None

    @property
    def is_closed(self):
        value = self.state_data.get("position")
        return value <= 0 if value is not None else None

    @property
    def is_opening(self):
        return self.state_data.get("state") == "opening"

    @property
    def is_closing(self):
        return self.state_data.get("state") == "closing"

    @property
    def extra_state_attributes(self):
        if self.device_id == "room":
            return {key: self.state_data.get(key) for key in
                    ("aligned", "spread_mm", "phase", "reason", "low_mm", "high_mm")}
        return {key: self.state_data.get(key) for key in ("height_mm", "referenced", "fault")}

    async def async_open_cover(self, **kwargs):
        await self.coordinator.move(self.device_id, 100)

    async def async_close_cover(self, **kwargs):
        await self.coordinator.move(self.device_id, 0)

    async def async_set_cover_position(self, **kwargs):
        await self.coordinator.move(self.device_id, kwargs[ATTR_POSITION])

    async def async_stop_cover(self, **kwargs):
        # STOP from any member cancels the one active group or individual job.
        await self.coordinator.stop()
