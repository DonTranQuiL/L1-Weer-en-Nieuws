"""Parser tests against the saved L1 pages (Wednesday 11 Nov 2026)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from custom_components.l1_weer.parser import L1WeerParser, upscale_image

EXPECTED = [
    # day, max, min, rain, wind, sun, icon
    ("Wo", "7", "5", "90%", "1/2 NNO", "1 u", "motregen"),
    ("Do", "10", "3", "30%", "1/2 NW", "4 u", "half bewolkt"),
    ("Vr", "10", "-1", "10%", "2/3 W", "6 u", "half bewolkt"),
    ("Za", "9", "-3", "10%", "1/2 ZO", "7 u", "half bewolkt"),
    ("Zo", "11", "-1", "60%", "3/4 ZZW", "3 u", "half bewolkt"),
]


def test_forecast_matches_l1_table(weer_html: str) -> None:
    data = L1WeerParser(weer_html).extract_data()
    got = [
        (
            f["day"],
            f["temp"],
            f["min"],
            f["neerslag"],
            f["wind"],
            f["zon"],
            f["condition"],
        )
        for f in data["forecast"]
    ]
    assert got == EXPECTED
    for f in data["forecast"]:
        assert f["condition_icon"].startswith("https://s.regiogroei.cloud/")
        assert f["condition_icon"].endswith(".svg")
    assert "motregen" in data["forecast"][0]["condition_icon"]


def test_no_invented_zondag_row(weer_html: str) -> None:
    """The weather text mentions 'zondag'; that must not become a forecast row."""
    data = L1WeerParser(weer_html).extract_data()
    days = [f["day"] for f in data["forecast"]]
    assert "Zondag" not in days
    assert days[0] == "Wo"
    assert len(days) == 5


def test_current_block(weer_html: str) -> None:
    current = L1WeerParser(weer_html).extract_data()["current"]
    assert current["temperature"] == "7"
    assert "regen" in current["condition"].lower()
    assert "motregen" in (current["condition"] + current["condition_name"]).lower()
    assert current["condition"] == "(Mot)regen, droge perioden en waterkoud"
    assert current["condition_name"] == "motregen"
    assert current["condition_icon"].endswith(".svg")
    assert current["min"] == "5"
    assert current["max"] == "7"
    # Same keys/format as before: today's row
    assert current["zon"] == "1 u"
    assert current["neerslag"] == "90%"
    assert current["wind"] == "1/2 NNO"
    assert current["description"].startswith("Het blijft vanmiddag")
    assert "\nMorgen\n" in current["description"]


def test_fallback_without_li_wrapper(weer_html: str) -> None:
    """If the <li> wrapper class changes, the per-column classes still work."""
    soup = BeautifulSoup(weer_html, "html.parser")
    for li in soup.select("li.weather-forecast"):
        li["class"] = ["renamed-row"]
    data = L1WeerParser(str(soup)).extract_data()
    got = [(f["day"], f["temp"], f["min"], f["zon"]) for f in data["forecast"]]
    assert got == [(d, mx, mn, sun) for d, mx, mn, _r, _w, sun, _i in EXPECTED]


def test_garbage_page_gives_empty_result() -> None:
    data = L1WeerParser("<html><body>Zondag 12\u00b0C</body></html>").extract_data()
    assert data == {"current": {}, "forecast": []}


def test_news_lead_story_and_images(nieuws_html: str) -> None:
    news = L1WeerParser("").extract_news(nieuws_html)
    assert len(news) == 5
    lead = news[0]
    assert lead["titel"] == (
        "Slachtoffers Bas P. en hun ouders doen hun verhaal: 'Je bent een viezerik'"
    )
    assert lead["link"] == (
        "https://www.l1nieuws.nl/nieuws/3270692/"
        "slachtoffers-bas-p-en-hun-ouders-doen-hun-verhaal-je-bent-een-viezerik"
    )
    for article in news:
        assert article["titel"] == article["titel"].strip()
        assert "  " not in article["titel"]
        assert article["link"].startswith("https://www.l1nieuws.nl/")
        assert "width=800" in article["afbeelding"]
        assert "height=450" in article["afbeelding"]
        assert "width=264" not in article["afbeelding"]
        assert "cb=" in article["afbeelding"]
    assert len({a["link"] for a in news}) == 5


def test_upscale_image() -> None:
    url = (
        "https://i.regiogroei.cloud/abc.jpg?width=264&height=148"
        "&aspect_ratio=264:148&cb=123"
    )
    assert upscale_image(url) == (
        "https://i.regiogroei.cloud/abc.jpg?width=800&height=450"
        "&aspect_ratio=16:9&cb=123"
    )
    assert upscale_image("https://example.com/a.jpg?width=10") == (
        "https://example.com/a.jpg?width=10"
    )
    assert upscale_image("") == ""
