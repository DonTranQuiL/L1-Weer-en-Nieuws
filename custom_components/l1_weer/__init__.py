import logging
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform
from .const import DOMAIN, CONF_ENABLE_NEWS, CONF_DEBUG_MODE, DEBUG_FILE_NAME
from .coordinator import L1WeerCoordinator
from .cache import PersistentCache

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up L1 Weer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Load options (or fallback to data from initial setup)
    enable_news = entry.options.get(CONF_ENABLE_NEWS, entry.data.get(CONF_ENABLE_NEWS, True))
    debug_mode = entry.options.get(CONF_DEBUG_MODE, entry.data.get(CONF_DEBUG_MODE, False))

    # Load cache directly using your working structure
    cache = PersistentCache(hass, f"{DOMAIN}_{entry.entry_id}")
    initial_data = await cache.load() or {}

    # Pass the new settings to the coordinator
    coordinator = L1WeerCoordinator(
        hass, 
        cache=cache, 
        initial_data=initial_data, 
        enable_news=enable_news, 
        debug_mode=debug_mode
    )
    
    # SMART STARTUP: Only force an instant refresh if the cache is completely empty
    if not initial_data:
        _LOGGER.warning("Geen cache gevonden. Eerste data wordt nu direct binnengehaald...")
        await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Listen for option updates (so if a user turns off news, the integration reloads)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # --- Register Service Calls ---
    async def handle_manual_refresh(call: ServiceCall):
        _LOGGER.info("Manual refresh triggered for L1 Weer")
        await coordinator.async_request_refresh()

    async def handle_clear_cache(call: ServiceCall):
        _LOGGER.info("Clearing L1 Weer cache")
        await cache.clear()
        
    async def handle_clear_debug_file(call: ServiceCall):
        _LOGGER.info("Clearing L1 Weer debug output file")
        debug_path = os.path.join(os.path.dirname(__file__), DEBUG_FILE_NAME)
        if os.path.exists(debug_path):
            os.remove(debug_path)

    hass.services.async_register(DOMAIN, "manual_refresh", handle_manual_refresh)
    hass.services.async_register(DOMAIN, "clear_cache", handle_clear_cache)
    hass.services.async_register(DOMAIN, "clear_debug_file", handle_clear_debug_file)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)