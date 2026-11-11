import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

BASE_URL = "https://www.l1nieuws.nl"
ARTICLE_RE = re.compile(r"/(?:nieuws|sport)/\d+/")
DAY_RE = re.compile(r"^(Ma|Di|Wo|Do|Vr|Za|Zo)$", re.IGNORECASE)
TEMP_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
# Size requested from the L1 image CDN (it resizes on the fly, 16:9)
NEWS_IMAGE_WIDTH = 800
NEWS_IMAGE_HEIGHT = 450


def _text(elem, sep=" "):
    """Whitespace-normalised text of an element ("" when missing)."""
    if elem is None:
        return ""
    return " ".join(elem.get_text(sep, strip=True).split())


def _temp(elem):
    """First number in an element as a string ("7°" -> "7"), or None."""
    match = TEMP_RE.search(_text(elem))
    return match.group(0).replace(",", ".") if match else None


def _wind(elem):
    """Normalise "1 / 2 NNO" to the existing "1/2 NNO" style."""
    text = _text(elem)
    return re.sub(r"\s*/\s*", "/", text) if text else ""


def _icon(container):
    """(condition, icon_url) from the first weather icon <img> in container."""
    img = container.select_one(".weather-image img") if container else None
    if img is None and container is not None:
        img = container.find("img")
    if img is None:
        return "", ""
    src = img.get("src") or img.get("data-src") or ""
    return (img.get("alt") or "").strip(), src


def upscale_image(url, width=NEWS_IMAGE_WIDTH, height=NEWS_IMAGE_HEIGHT):
    """Ask the regiogroei image CDN for a larger 16:9 image (keeps cb etc.)."""
    if not url or "regiogroei.cloud" not in url:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "width" not in query and "height" not in query:
        return url
    query["width"] = str(width)
    query["height"] = str(height)
    query["aspect_ratio"] = "16:9"
    return urlunsplit(parts._replace(query=urlencode(query, safe=":")))


class L1WeerParser:
    def __init__(self, html):
        self.soup = BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------ weather
    def _parse_forecast_rows(self):
        """One dict per <li class="weather-forecast"> row (first row is today)."""
        forecast = []
        for row in self.soup.select("li.weather-forecast"):
            day = _text(row.select_one(".weather-forecast-day"))
            if not DAY_RE.match(day):
                continue
            entry = {"day": day.capitalize()}
            max_temp = _temp(row.select_one(".weather-forecast-max-temp"))
            min_temp = _temp(row.select_one(".weather-forecast-min-temp"))
            if max_temp is not None:
                entry["temp"] = max_temp
            if min_temp is not None:
                entry["min"] = min_temp
            sun = _text(row.select_one(".weather-forecast-sun"))
            rain = _text(row.select_one(".weather-forecast-rain"))
            wind = _wind(row.select_one(".weather-forecast-wind"))
            if sun:
                entry["zon"] = sun
            if rain:
                entry["neerslag"] = rain
            if wind:
                entry["wind"] = wind
            condition, icon = _icon(row.select_one(".weather-forecast-weather-icon"))
            if condition:
                entry["condition"] = condition
            if icon:
                entry["condition_icon"] = icon
            forecast.append(entry)
            if len(forecast) >= 5:
                break
        return forecast

    def _parse_forecast_fallback(self):
        """Narrow fallback: zip the per-column classes if the <li> wrapper changes.

        Only uses the forecast column elements themselves, never free page text.
        """
        days = [_text(e) for e in self.soup.select(".weather-forecast-day")]
        maxes = [_temp(e) for e in self.soup.select(".weather-forecast-max-temp")]
        mins = [_temp(e) for e in self.soup.select(".weather-forecast-min-temp")]
        suns = [_text(e) for e in self.soup.select(".weather-forecast-sun")]
        rains = [_text(e) for e in self.soup.select(".weather-forecast-rain")]
        winds = [_wind(e) for e in self.soup.select(".weather-forecast-wind")]
        forecast = []
        for i, day in enumerate(days[:5]):
            if not DAY_RE.match(day):
                continue
            entry = {"day": day.capitalize()}
            for key, values in (
                ("temp", maxes),
                ("min", mins),
                ("zon", suns),
                ("neerslag", rains),
                ("wind", winds),
            ):
                if i < len(values) and values[i]:
                    entry[key] = values[i]
            forecast.append(entry)
        return forecast

    def _parse_current(self, forecast):
        current = {}
        today = self.soup.select_one(".weather-today")
        temp = _temp(today.select_one(".current-temp")) if today else None
        if temp is None:
            temp = _temp(self.soup.select_one(".current-temp"))
        if temp is not None:
            current["temperature"] = temp

        if today is not None:
            condition, icon = _icon(today)
            if icon:
                current["condition_icon"] = icon
            if condition:
                current["condition_name"] = condition

        summary = _text(self.soup.select_one(".short-summary"))
        if summary:
            current["condition"] = summary
        elif current.get("condition_name"):
            current["condition"] = current["condition_name"]

        # "5° / 7° - 1 / 2 NNO"
        info = _text(self.soup.select_one(".weather-stats .summary-information"))
        if info:
            temps = re.findall(r"(-?\d+)\s*\u00b0", info)
            if len(temps) >= 2:
                current["min"], current["max"] = temps[0], temps[1]
            wind = re.search(r"(\d+)\s*/\s*(\d+)\s*([NOZW]{1,3})?\s*$", info)
            if wind:
                current["wind"] = " ".join(
                    p for p in (f"{wind.group(1)}/{wind.group(2)}", wind.group(3)) if p
                )

        description = self.soup.select_one(".groei-wa-weather-summary-description-text")
        if description is not None:
            lines = [
                " ".join(line.split())
                for line in description.get_text("\n").split("\n")
            ]
            text = "\n".join(line for line in lines if line)
            if text:
                current["description"] = text

        # Today's row fills in zon/neerslag/wind (same as before) and min/max
        if forecast:
            first = forecast[0]
            for key, src in (
                ("zon", "zon"),
                ("neerslag", "neerslag"),
                ("wind", "wind"),
                ("min", "min"),
                ("max", "temp"),
                ("condition_icon", "condition_icon"),
                ("condition_name", "condition"),
            ):
                if key not in current and first.get(src):
                    current[key] = first[src]
        return current

    def extract_data(self):
        data = {"current": {}, "forecast": []}
        try:
            forecast = self._parse_forecast_rows() or self._parse_forecast_fallback()
            data["forecast"] = forecast
            data["current"] = self._parse_current(forecast)
        except Exception:
            pass
        return data

    # --------------------------------------------------------------------- news
    @staticmethod
    def _article_from_link(a_tag):
        heading = a_tag.find(["h1", "h2", "h3", "h4", "h5"])
        title = _text(heading) if heading else ""
        img_tag = a_tag.find("img")
        if not title and img_tag is not None:
            title = " ".join((img_tag.get("alt") or "").split())
        if not title:
            parent = a_tag.find_parent(["article", "li"])
            if parent is not None:
                title = _text(parent.find(["h1", "h2", "h3", "h4", "h5"]))
        if img_tag is None:
            parent = a_tag.find_parent(["article", "li"])
            if parent is not None:
                img_tag = parent.find("img")
        img_url = ""
        if img_tag is not None:
            img_url = img_tag.get("data-src") or img_tag.get("src") or ""
        return title, upscale_image(img_url)

    def extract_news(self, html):
        """Top 5 articles from the /nieuws page (article cards first)."""
        news_list = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            links = [
                a
                for a in soup.select("a.navigation-link[href]")
                if ARTICLE_RE.search(a["href"])
            ]
            # Fallback when the card class changes: any article link
            if not links:
                links = [
                    a
                    for a in soup.find_all("a", href=True)
                    if ARTICLE_RE.search(a["href"])
                ]

            for a_tag in links:
                href = a_tag["href"]
                link = f"{BASE_URL}{href}" if href.startswith("/") else href
                if any(n["link"] == link for n in news_list):
                    continue
                title, img_url = self._article_from_link(a_tag)
                if not title or len(title) < 10:
                    continue
                news_list.append({"titel": title, "link": link, "afbeelding": img_url})
                if len(news_list) >= 5:
                    break
        except Exception:
            pass

        return news_list
