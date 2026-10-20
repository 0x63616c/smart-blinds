"""Constants for the local bridge integration."""
from homeassistant.const import Platform

DOMAIN = "smart_blinds"
CONF_BASE_URL = "base_url"
CONF_TOKEN = "access_token"
PLATFORMS = [Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
BATTERY_MAX_AGE_MS = 30 * 60 * 1000
