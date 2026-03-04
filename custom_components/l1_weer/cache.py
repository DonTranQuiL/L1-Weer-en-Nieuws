from homeassistant.helpers.storage import Store

class PersistentCache:
    """Simple storage for last known data."""

    def __init__(self, hass, key):
        self.store = Store(hass, 1, key)

    async def save(self, data):
        await self.store.async_save(data)

    async def load(self):
        return await self.store.async_load()

    async def clear(self):
        """Removes the cache file entirely."""
        await self.store.async_remove()