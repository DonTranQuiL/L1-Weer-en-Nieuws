from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_NEWS, DOMAIN


def _to_int(value):
    """'7' / '-1' / '7.0' -> int, anything else -> None."""
    try:
        return round(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _zon_hours(value):
    """'4 u' / '4 uur' -> 4, anything else -> None."""
    if value is None:
        return None
    return _to_int(str(value).replace("uur", "").replace("u", "").strip())


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Check if news is enabled
    enable_news = entry.options.get(
        CONF_ENABLE_NEWS, entry.data.get(CONF_ENABLE_NEWS, True)
    )

    entities = [
        L1WeatherSensor(coordinator),
        L1UpdateDiagnostic(coordinator),
        L1StatusDiagnostic(coordinator),
    ]

    # Only load the news sensor if opted in
    if enable_news:
        entities.append(L1NieuwsSensor(coordinator))

    async_add_entities(entities)


class L1BaseSensor(CoordinatorEntity, SensorEntity):
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "l1_weer_limburg")},
            "name": "L1 Weer (Limburg)",
            "manufacturer": "TranQuiL",
        }


class L1WeatherSensor(L1BaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "L1 Huidige Temperatuur"
        self._attr_unique_id = "l1_weer_current_temp"
        self._attr_native_unit_of_measurement = "\u00b0C"
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    # Bulky structured attributes for the dashboard card; keep them out of
    # the recorder database.
    _unrecorded_attributes = frozenset({"forecast", "description", "condition_icon"})

    @property
    def native_value(self):
        data = self.coordinator.data or getattr(self.coordinator, "_last_data", {})
        return data.get("current", {}).get("temperature")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or getattr(self.coordinator, "_last_data", {})
        attrs = {}

        # --- 1. Current Weather Attributes ---
        current = data.get("current", {})
        if "zon" in current:
            attrs["Zon"] = current["zon"]
        if "neerslag" in current:
            attrs["Neerslag"] = current["neerslag"]
        if "wind" in current:
            attrs["Wind"] = current["wind"]
        if current.get("condition"):
            attrs["condition"] = current["condition"]
        if current.get("condition_name"):
            attrs["condition_name"] = current["condition_name"]
        if current.get("condition_icon"):
            attrs["condition_icon"] = current["condition_icon"]
        if _to_int(current.get("min")) is not None:
            attrs["temp_min"] = _to_int(current.get("min"))
        if _to_int(current.get("max")) is not None:
            attrs["temp_max"] = _to_int(current.get("max"))
        if current.get("description"):
            attrs["description"] = current["description"]

        # --- 2. Forecast Days ---
        forecasts = data.get("forecast", [])
        structured = []
        for i, f in enumerate(forecasts):
            day_num = i + 1

            # A) The Pretty UI text for your dashboard (Using safe unicode escapes)
            day_text = f"{f.get('temp', '')}\u00b0C"
            extras = []

            # \u2600\uFE0F is Zon, \U0001F327\uFE0F is Regen, \U0001F4A8 is Wind
            if "zon" in f:
                extras.append(f"\u2600\ufe0f {f['zon']}")
            if "neerslag" in f:
                extras.append(f"\U0001f327\ufe0f {f['neerslag']}")
            if "wind" in f:
                extras.append(f"\U0001f4a8 {f['wind']}")

            if extras:
                day_text += f" | {' | '.join(extras)}"

            attrs[f["day"]] = day_text

            # B) The Clean Numerical Attributes for the UI Automations
            if "zon" in f:
                try:
                    clean_zon = f["zon"].replace(" u", "").replace("uur", "").strip()
                    attrs[f"dag_{day_num}_zonuren"] = int(clean_zon)
                except ValueError:
                    pass

            if "temp" in f:
                try:
                    attrs[f"dag_{day_num}_temperatuur"] = int(f["temp"])
                except ValueError:
                    pass

            if _to_int(f.get("min")) is not None:
                attrs[f"dag_{day_num}_min"] = _to_int(f.get("min"))

            # Voeg Neerslag toe (inclusief het % teken zoals je vroeg)
            if "neerslag" in f:
                attrs[f"dag_{day_num}_neerslag"] = f["neerslag"]

            # Voeg Windkracht toe (filtert de windrichting weg, dus "2/3 ZZO" wordt "2/3")
            if "wind" in f:
                wind_delen = f["wind"].split()
                if wind_delen:
                    attrs[f"dag_{day_num}_windkracht"] = wind_delen[0]

            # C) Structured entry for the dashboard card
            wind = f.get("wind", "")
            structured.append(
                {
                    "day": f.get("day", ""),
                    "temp": _to_int(f.get("temp")),
                    "min": _to_int(f.get("min")),
                    "zon": f.get("zon", ""),
                    "zonuren": _zon_hours(f.get("zon")),
                    "neerslag": f.get("neerslag", ""),
                    "wind": wind,
                    "windkracht": wind.split()[0] if wind.split() else "",
                    "condition": f.get("condition", ""),
                    "condition_icon": f.get("condition_icon", ""),
                }
            )

        attrs["forecast"] = structured

        # --- 3. Raw Data for Debugging ---
        attrs["raw_data"] = str(data)
        return attrs


class L1UpdateDiagnostic(L1BaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "L1 Weer Laatste Update"
        self._attr_unique_id = "l1_weer_last_update"
        self._attr_icon = "mdi:clock-check"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        if self.coordinator.data:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return "Uit Cache (Wacht op timer)"


class L1StatusDiagnostic(L1BaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "L1 Weer Status"
        self._attr_unique_id = "l1_weer_status"
        self._attr_icon = "mdi:check-network-outline"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        has_data = self.coordinator.data or getattr(self.coordinator, "_last_data", {})
        return "OK" if has_data else "Fout"

    @property
    def extra_state_attributes(self):
        interval = getattr(self.coordinator, "update_interval", None)
        url = getattr(self.coordinator, "scrape_url", "https://www.l1nieuws.nl/weer")

        return {
            "bron_url": url,
            "update_interval_minuten": interval.total_seconds() / 60
            if interval
            else "Onbekend",
            "gebruikt_cache": "Ja" if not self.coordinator.data else "Nee",
        }


class L1NieuwsSensor(L1BaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "L1 Laatste Nieuws"
        self._attr_unique_id = "l1_laatste_nieuws"
        self._attr_icon = "mdi:newspaper-variant"

    _unrecorded_attributes = frozenset({"nieuws"})

    @property
    def native_value(self):
        data = self.coordinator.data or getattr(self.coordinator, "_last_data", {})
        nieuws = data.get("nieuws", [])
        return f"{len(nieuws)} Artikelen" if nieuws else "Geen Nieuws"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or getattr(self.coordinator, "_last_data", {})
        nieuws = data.get("nieuws", [])
        attrs = {}

        for i, article in enumerate(nieuws):
            num = i + 1
            attrs[f"artikel_{num}_titel"] = article.get("titel", "")
            attrs[f"artikel_{num}_link"] = article.get("link", "")
            attrs[f"artikel_{num}_afbeelding"] = article.get("afbeelding", "")

        attrs["nieuws"] = [
            {
                "titel": a.get("titel", ""),
                "link": a.get("link", ""),
                "afbeelding": a.get("afbeelding", ""),
            }
            for a in nieuws
        ]
        attrs["raw_news_data"] = str(nieuws)
        return attrs
