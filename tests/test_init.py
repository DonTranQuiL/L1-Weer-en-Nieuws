"""Setup registers the dashboard card and creates the sensors."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.l1_weer.const import CARD_URL, DOMAIN, VERSION
from custom_components.l1_weer.parser import L1WeerParser


async def test_setup_registers_card(
    hass: HomeAssistant, weer_html: str, nieuws_html: str
) -> None:
    parser = L1WeerParser(weer_html)
    data = parser.extract_data()
    data["nieuws"] = parser.extract_news(nieuws_html)

    hass.config.components.add("frontend")
    entry = MockConfigEntry(domain=DOMAIN, data={"enable_news": True})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.l1_weer.add_extra_js_url") as add,
        patch(
            "custom_components.l1_weer.coordinator.L1WeerCoordinator._async_update_data",
            return_value=data,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    urls = [c.args[1] for c in add.call_args_list]
    assert len(urls) == 1
    assert urls[0].startswith(f"{CARD_URL}?v={VERSION}-")
    assert len(urls[0].rsplit("-", 1)[1]) == 8

    ent_reg = er.async_get(hass)
    weather_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "l1_weer_current_temp")
    news_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "l1_laatste_nieuws")
    state = hass.states.get(weather_id)
    assert state is not None
    assert state.state == "7"
    assert state.attributes["dag_1_temperatuur"] == 7
    assert state.attributes["dag_2_temperatuur"] == 10
    news = hass.states.get(news_id)
    assert news is not None
    assert news.attributes["artikel_1_titel"].startswith("Slachtoffers Bas P.")
