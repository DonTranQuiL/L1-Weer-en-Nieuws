from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN, CONF_ENABLE_NEWS
from datetime import datetime

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Check if news is enabled
    enable_news = entry.options.get(CONF_ENABLE_NEWS, entry.data.get(CONF_ENABLE_NEWS, True))
    
    entities = [
        L1WeatherSensor(coordinator),
        L1UpdateDiagnostic(coordinator),
        L1StatusDiagnostic(coordinator)
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
        
        # --- 2. Forecast Days ---
        forecasts = data.get("forecast", [])
        for i, f in enumerate(forecasts):
            day_num = i + 1
            
            # A) The Pretty UI text for your dashboard (Using safe unicode escapes)
            day_text = f"{f.get('temp', '')}\u00b0C"
            extras = []
            
            # \u2600\uFE0F is Zon, \U0001F327\uFE0F is Regen, \U0001F4A8 is Wind
            if "zon" in f: 
                extras.append(f"\u2600\uFE0F {f['zon']}")
            if "neerslag" in f: 
                extras.append(f"\U0001F327\uFE0F {f['neerslag']}")
            if "wind" in f: 
                extras.append(f"\U0001F4A8 {f['wind']}")
            
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
                    
            # Voeg Neerslag toe (inclusief het % teken zoals je vroeg)
            if "neerslag" in f:
                attrs[f"dag_{day_num}_neerslag"] = f["neerslag"]
                
            # Voeg Windkracht toe (filtert de windrichting weg, dus "2/3 ZZO" wordt "2/3")
            if "wind" in f:
                wind_delen = f["wind"].split()
                if wind_delen:
                    attrs[f"dag_{day_num}_windkracht"] = wind_delen[0]
            
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
            "update_interval_minuten": interval.total_seconds() / 60 if interval else "Onbekend",
            "gebruikt_cache": "Ja" if not self.coordinator.data else "Nee",
        }

class L1NieuwsSensor(L1BaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "L1 Laatste Nieuws"
        self._attr_unique_id = "l1_laatste_nieuws"
        self._attr_icon = "mdi:newspaper-variant"

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
            
        attrs["raw_news_data"] = str(nieuws)
        return attrs
