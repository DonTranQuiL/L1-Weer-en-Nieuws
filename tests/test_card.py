"""Run the dashboard card in headless Chrome against real sensor attributes.

Skipped when no Chrome/Chromium is installed (GitHub's Ubuntu runners have one).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.l1_weer.const import CARD_FILENAME, DOMAIN
from custom_components.l1_weer.parser import L1WeerParser
from custom_components.l1_weer.sensor import L1NieuwsSensor, L1WeatherSensor

ROOT = Path(__file__).parent.parent
CARD = ROOT / "custom_components" / DOMAIN / "frontend" / CARD_FILENAME
HARNESS = Path(__file__).parent / "card" / "harness.js"
CHROME = next(
    (
        shutil.which(name)
        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        )
        if shutil.which(name)
    ),
    None,
)


def card_states(weer_html: str, nieuws_html: str) -> dict:
    """The two sensor states as the frontend sees them."""
    parser = L1WeerParser(weer_html)
    data = parser.extract_data()
    data["nieuws"] = parser.extract_news(nieuws_html)
    coordinator = SimpleNamespace(data=data, _last_data=data)
    weather = L1WeatherSensor(coordinator)
    news = L1NieuwsSensor(coordinator)
    states = {
        "sensor.l1_huidige_temperatuur": {
            "entity_id": "sensor.l1_huidige_temperatuur",
            "state": weather.native_value,
            "attributes": weather.extra_state_attributes,
        },
        "sensor.l1_laatste_nieuws": {
            "entity_id": "sensor.l1_laatste_nieuws",
            "state": news.native_value,
            "attributes": news.extra_state_attributes,
        },
    }
    entities = {eid: {"entity_id": eid, "platform": DOMAIN} for eid in states}
    return json.loads(json.dumps({"states": states, "entities": entities}, default=str))


def page(data: dict, body_style: str = "") -> str:
    payload = json.dumps(data).replace("</", "<\\/")
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        f"<body style='{body_style}'>"
        f"<script type='application/json' id='states'>{payload}</script>"
        "<pre id='out'></pre>"
        f"<script type='module'>{CARD.read_text('utf-8')}\n"
        f"{HARNESS.read_text('utf-8')}</script>"
        "</body></html>"
    )


def run_card(data: dict) -> dict:
    """Load the card and the harness in headless Chrome; return the results."""
    try:  # Playwright when available (more reliable locally), else --dump-dom
        return _run_playwright(data)
    except ImportError:
        pass
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "card.html"
        path.write_text(page(data), "utf-8")
        out = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={tmp}/profile",
                "--window-size=1200,900",
                "--virtual-time-budget=5000",
                "--dump-dom",
                path.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        ).stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', out, re.DOTALL)
    assert match, out[-2000:]
    return json.loads(html.unescape(match.group(1)))


def _run_playwright(data: dict) -> dict:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "card.html"
        path.write_text(page(data), "utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            try:
                tab = browser.new_page(viewport={"width": 1200, "height": 900})
                tab.goto(path.as_uri())
                tab.wait_for_function(
                    "document.getElementById('out').textContent.length > 2",
                    timeout=30000,
                )
                return json.loads(tab.locator("#out").text_content())
            finally:
                browser.close()


def test_card_is_ascii() -> None:
    CARD.read_text("utf-8").encode("ascii")


@pytest.mark.skipif(CHROME is None, reason="no Chrome/Chromium installed")
def test_card_in_browser(weer_html: str, nieuws_html: str) -> None:
    result = run_card(card_states(weer_html, nieuws_html))
    c = result["checks"]
    assert result["errors"] == [], result["errors"]

    # Weather view (default)
    assert c["view"] == "weather"
    assert c["seg"] == ["Weer", "Nieuws"]
    assert c["title"] == "L1 Weer Limburg"
    assert c["big"] == "7\u00b0"
    assert c["cond"] == "(Mot)regen, droge perioden en waterkoud"
    assert "motregen" in c["now_icon"]
    assert c["stats"] == ["5\u00b0 / 7\u00b0", "1 u", "90%", "1/2 NNO"]
    assert c["days"] == ["Vandaag", "Do", "Vr", "Za", "Zo"]
    assert c["hi"] == ["7\u00b0", "10\u00b0", "10\u00b0", "9\u00b0", "11\u00b0"]
    assert c["lo"] == ["5\u00b0", "3\u00b0", "-1\u00b0", "-3\u00b0", "-1\u00b0"]
    assert c["day_icons"] == 5
    assert c["report"] is True
    assert c["bad_weather"] == []
    assert c["renders_same"] == 0

    # News view
    assert c["news_view"] == "news"
    assert c["news_title"] == "L1 Laatste Nieuws"
    assert c["hero"].startswith("Slachtoffers Bas P.")
    assert "width=800" in c["hero_img"]
    assert c["rows"] == 4
    assert c["links"] == 5
    assert c["links_ok"] is True
    assert c["underline"] == "none"
    assert c["bad_news"] == []
    assert c["stored"] == "news"
    assert c["persisted"] == "news"

    # Options
    assert c["initial_news"] == "news"
    assert c["rows3"] == 2
    assert c["custom_title"] == "Mijn L1"
    assert c["no_forecast"] == 0
    assert c["no_report"] is True

    # Discovery, older attributes, safety, edge cases
    assert c["disc_big"] == "7\u00b0"
    assert c["disc_hero"].startswith("Slachtoffers Bas P.")
    assert c["legacy_days"] == 5
    assert c["legacy_hi"][:2] == ["7\u00b0", "10\u00b0"]
    assert c["legacy_hero"].startswith("Slachtoffers Bas P.")
    assert c["legacy_rows"] == 4
    assert c["xss_imgs"] == 0
    assert "<img" in c["xss_text"]
    assert c["xss_link"] == 0
    assert c["xss_fired"] == 0
    assert c["xss_b"] == 0
    assert "Geen L1-weerdata" in c["missing_weather"]
    assert "Geen L1-nieuws" in c["missing_news"]
    assert c["unavailable"] == "Niet beschikbaar"
    assert c["alias_view"] == "news"
    assert c["en_seg"] == ["Weather", "News"]
    assert c["narrow_overflow"] is False
    assert c["bad_config"] == "rejected"
    assert c["editor_fields"] == [
        "initial_view",
        "title",
        "entity_weather",
        "entity_news",
        "max_articles",
        "show_forecast",
        "show_description",
    ]
    assert c["stub"] == {"initial_view": "weather"}
    assert c["picker"] == ["l1-card"]
