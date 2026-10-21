"""An explicit rejoin operation; normal cover commands never align silently."""
from homeassistant.components.button import ButtonEntity
from .entity import SmartBlindsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Align(entry.runtime_data)])


class Align(SmartBlindsEntity, ButtonEntity):
    _attr_name = "Align at 50% (simulation)"
    _attr_icon = "mdi:align-horizontal-center"

    def __init__(self, coordinator):
        super().__init__(coordinator, "room", "align")
        self._attr_name = "Align at 50% (simulation)" if coordinator.data["mode"] == "simulation" else "Align at 50%"

    async def async_press(self):
        await self.coordinator.move("room", 50, align=True)
