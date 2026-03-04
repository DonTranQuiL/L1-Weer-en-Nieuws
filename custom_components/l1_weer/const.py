DOMAIN = "l1_weer"
URL = "https://www.l1nieuws.nl/weer"
CACHE_FILE = "l1_weer_cache.json"

# New Configuration Constants
CONF_ENABLE_NEWS = "enable_news"
CONF_DEBUG_MODE = "debug_mode"
DEBUG_FILE_NAME = "scrape_output.txt"
# Using Unicode escape \u00b0 for the degree symbol to prevent encoding errors
WEATHER_DATA_MAP = {
    "temperature": {"name": "Temperatuur", "unit": "\u00b0C", "icon": "mdi:thermometer"},
    "condition": {"name": "Conditie", "unit": None, "icon": "mdi:weather-cloudy"},
    "wind_speed": {"name": "Windsnelheid", "unit": "km/u", "icon": "mdi:wind"},
    "wind_direction": {"name": "Windrichting", "unit": None, "icon": "mdi:compass"},
    "rain_chance": {"name": "Regenkans", "unit": "%", "icon": "mdi:weather-rainy"},
    "forecast_short": {"name": "Verwachting Kort", "unit": None, "icon": "mdi:text-short"},
}