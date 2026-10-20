"""HA refreshes the bridge; the bridge owns timing-critical group leases."""
from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BridgeAuthError, BridgeClient, BridgeError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartBlindsCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry, client: BridgeClient):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=1))
        self.client = client

    async def _async_update_data(self):
        try:
            state = await self.client.async_state()
            if state["bridge_id"] != self.config_entry.unique_id:
                raise BridgeError("Bridge identity changed")
            return state
        except BridgeAuthError as exc:
            raise ConfigEntryAuthFailed("Bridge authentication failed") from exc
        except BridgeError as exc:
            raise UpdateFailed(str(exc)) from exc

    async def move(self, target, position, *, align=False):
        try:
            await self.client.async_move(target, position, align=align)
        except BridgeError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.async_request_refresh()

    async def stop(self):
        try:
            await self.client.async_stop()
        except BridgeError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.async_request_refresh()
