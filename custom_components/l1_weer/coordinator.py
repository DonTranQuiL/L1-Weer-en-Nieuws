import logging
import random
import os
from datetime import datetime, timedelta
import aiohttp
import asyncio
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, URL, DEBUG_FILE_NAME
from .parser import L1WeerParser

_LOGGER = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"
]

class L1WeerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, cache=None, initial_data=None, enable_news=True, debug_mode=False):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
            always_update=True # FIX 1: Forces UI to update even if data is identical
        )
        self.cache = cache
        self._last_data = initial_data or {}
        self.scrape_url = URL
        self.enable_news = enable_news
        self.debug_mode = debug_mode

    def _save_snapshot(self, html, reason):
        path = self.hass.config.path(f"l1_weer_debug_{reason}.html")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass
            
    def _save_debug_output(self, text_content):
        if not self.debug_mode:
            return
        path = os.path.join(os.path.dirname(__file__), DEBUG_FILE_NAME)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_content)
        except Exception as e:
            _LOGGER.error(f"Failed to write debug file: {e}")

    async def _async_update_data(self):
        hour = datetime.now().hour
        base_minutes = 120 if 1 <= hour <= 5 else 30

        jitter = random.randint(5, 45)
        await asyncio.sleep(jitter)

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "nl-NL,nl;q=0.9",
            "Cache-Control": "no-cache", # FIX 2: Ask server to bypass CDN cache
            "Pragma": "no-cache"
        }
        
        # FIX 2: Create unique timestamps to bust the website cache
        timestamp = int(datetime.now().timestamp() * 1000)
        live_weather_url = f"{self.scrape_url}?_={timestamp}"
        live_news_url = f"https://www.l1nieuws.nl/nieuws?_={timestamp}"

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. Fetch the Weather using the live URL
                async with session.get(live_weather_url, timeout=15) as response:
                    if response.status == 429:
                        self.update_interval = timedelta(hours=2)
                        raise UpdateFailed("Rate limited (429)")

                    if response.status != 200:
                        raise UpdateFailed(f"Server returned {response.status}")
                    
                    html_weer = await response.text()
                    debug_text = f"--- WEATHER HTML ---\n{html_weer}\n\n"
                    
                    parser = L1WeerParser(html_weer)
                    new_data = parser.extract_data()

                    # 2. Fetch the News (Only if enabled!) using the live URL
                    if self.enable_news:
                        try:
                            async with session.get(live_news_url, timeout=15) as news_resp:
                                if news_resp.status == 200:
                                    html_nieuws = await news_resp.text()
                                    debug_text += f"--- NEWS HTML ---\n{html_nieuws}\n"
                                    new_data["nieuws"] = parser.extract_news(html_nieuws)
                                else:
                                    new_data["nieuws"] = []
                        except Exception as e:
                            _LOGGER.warning(f"L1 Nieuws scraper error: {e}")
                            new_data["nieuws"] = []
                    else:
                        new_data["nieuws"] = []

                    self._save_debug_output(debug_text)

                    # FIX 3: Add a fresh timestamp so HA sees the payload as unique and updates the sensor
                    new_data["laatste_scrape_tijd"] = datetime.now().isoformat()

                    if not new_data.get("forecast"):
                        self._save_snapshot(html_weer, "missing_forecast")

                    if not new_data.get("current") and self._last_data:
                        return self._last_data
                    
                    self._last_data = new_data
                    if self.cache:
                        await self.cache.save(new_data)
                    
                    self.update_interval = timedelta(minutes=base_minutes)
                    return new_data

        except Exception as err:
            if self._last_data:
                return self._last_data
            raise UpdateFailed(f"Update error: {err}")
