"""Sensor attributes: old keys stay, new structured keys are added."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.l1_weer.parser import L1WeerParser
from custom_components.l1_weer.sensor import L1NieuwsSensor, L1WeatherSensor


def _coordinator(weer_html: str, nieuws_html: str) -> SimpleNamespace:
    parser = L1WeerParser(weer_html)
    data = parser.extract_data()
    data["nieuws"] = parser.extract_news(nieuws_html)
    return SimpleNamespace(data=data, _last_data=data)


def test_weather_attributes(weer_html: str, nieuws_html: str) -> None:
    sensor = L1WeatherSensor(_coordinator(weer_html, nieuws_html))
    assert sensor.native_value == "7"
    attrs = sensor.extra_state_attributes

    # Existing keys, now aligned with today (Wednesday) as dag_1
    assert attrs["dag_1_temperatuur"] == 7
    assert attrs["dag_2_temperatuur"] == 10
    assert attrs["dag_5_temperatuur"] == 11
    assert attrs["dag_1_zonuren"] == 1
    assert attrs["dag_2_zonuren"] == 4
    assert attrs["dag_2_neerslag"] == "30%"
    assert attrs["dag_2_windkracht"] == "1/2"
    assert attrs["Zon"] == "1 u"
    assert attrs["Neerslag"] == "90%"
    assert attrs["Wind"] == "1/2 NNO"
    assert attrs["Do"] == (
        "10\u00b0C | \u2600\ufe0f 4 u | \U0001f327\ufe0f 30% | \U0001f4a8 1/2 NW"
    )
    for day in ("Wo", "Do", "Vr", "Za", "Zo"):
        assert day in attrs
    assert "raw_data" in attrs

    # New keys
    assert [attrs[f"dag_{i}_min"] for i in range(1, 6)] == [5, 3, -1, -3, -1]
    assert attrs["temp_min"] == 5
    assert attrs["temp_max"] == 7
    assert attrs["condition"] == "(Mot)regen, droge perioden en waterkoud"
    assert attrs["condition_icon"].endswith(".svg")
    forecast = attrs["forecast"]
    assert [f["day"] for f in forecast] == ["Wo", "Do", "Vr", "Za", "Zo"]
    assert forecast[1] == {
        "day": "Do",
        "temp": 10,
        "min": 3,
        "zon": "4 u",
        "zonuren": 4,
        "neerslag": "30%",
        "wind": "1/2 NW",
        "windkracht": "1/2",
        "condition": "half bewolkt",
        "condition_icon": forecast[1]["condition_icon"],
    }
    assert "forecast" in L1WeatherSensor._unrecorded_attributes


def test_news_attributes(weer_html: str, nieuws_html: str) -> None:
    sensor = L1NieuwsSensor(_coordinator(weer_html, nieuws_html))
    assert sensor.native_value == "5 Artikelen"
    attrs = sensor.extra_state_attributes
    assert attrs["artikel_1_titel"].startswith("Slachtoffers Bas P.")
    assert attrs["artikel_1_link"].startswith("https://www.l1nieuws.nl/nieuws/")
    assert "width=800" in attrs["artikel_1_afbeelding"]
    assert len(attrs["nieuws"]) == 5
    assert attrs["nieuws"][0]["titel"] == attrs["artikel_1_titel"]
    assert "raw_news_data" in attrs
