from bs4 import BeautifulSoup
import re

class L1WeerParser:
    def __init__(self, html):
        self.soup = BeautifulSoup(html, "html.parser")

    def extract_data(self):
        data = {"current": {}, "forecast": []}
        try:
            temp_elem = self.soup.find(class_=re.compile("weather-now__temp|temperature|temp|current", re.I))
            if temp_elem and re.search(r"\d", temp_elem.text):
                val = re.sub(r"[^0-9,.-]", "", temp_elem.text.replace(",", "."))
                if val:
                    data["current"]["temperature"] = val

            sun_elems = self.soup.select(".weather-forecast-sun")
            rain_elems = self.soup.select(".weather-forecast-rain")
            wind_elems = self.soup.select(".weather-forecast-wind")

            suns = [el.get_text(strip=True) for el in sun_elems]
            rains = [el.get_text(strip=True) for el in rain_elems]
            winds = [el.get_text(" ", strip=True).replace(" / ", "/") for el in wind_elems]

            if len(suns) > 0: 
                data["current"]["zon"] = suns[0]
            if len(rains) > 0: 
                data["current"]["neerslag"] = rains[0]
            if len(winds) > 0: 
                data["current"]["wind"] = winds[0]

            text = self.soup.get_text(separator=" ", strip=True)
            pattern = r"\b(Maandag|Dinsdag|Woensdag|Donderdag|Vrijdag|Zaterdag|Zondag|Ma|Di|Wo|Do|Vr|Za|Zo)\b[^\d]*?(-?\d+[.,]?\d*)\s*(?:\u00b0|C)"
            matches = re.finditer(pattern, text, re.IGNORECASE)
            seen_days = set()
            
            day_index = 1 
            for match in matches:
                day_str = match.group(1).capitalize()
                temp_str = match.group(2)
                
                if day_str not in seen_days:
                    seen_days.add(day_str)
                    forecast_entry = {"day": day_str, "temp": temp_str}
                    if day_index < len(suns): 
                        forecast_entry["zon"] = suns[day_index]
                    if day_index < len(rains): 
                        forecast_entry["neerslag"] = rains[day_index]
                    if day_index < len(winds): 
                        forecast_entry["wind"] = winds[day_index]
                    
                    data["forecast"].append(forecast_entry)
                    day_index += 1
                    
                if len(data["forecast"]) >= 5:
                    break
        except Exception:
            pass
            
        return data

    def extract_news(self, html):
        """Scrapes the top 5 articles using a robust URL-matching strategy"""
        news_list = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for all links on the L1 website
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                
                # Verify it points to an actual news or sport article (e.g. /nieuws/3118282/...)
                if not re.search(r"/(?:nieuws|sport)/\d+/", href):
                    continue
                    
                link = f"https://www.l1nieuws.nl{href}" if href.startswith("/") else href
                
                # Skip if we already have this article in our list
                if any(n["link"] == link for n in news_list):
                    continue
                    
                # 1. Grab the Title 
                title = ""
                heading = a_tag.find(["h1", "h2", "h3", "h4", "h5"])
                if heading:
                    title = heading.get_text(separator=" ", strip=True)
                else:
                    title = a_tag.get_text(separator=" ", strip=True)
                
                # If title is missing, it might be in a wrapper outside the link
                if not title or len(title) < 10:
                    parent = a_tag.find_parent(["article", "div", "li"])
                    if parent:
                        parent_heading = parent.find(["h1", "h2", "h3", "h4", "h5"])
                        if parent_heading:
                            title = parent_heading.get_text(separator=" ", strip=True)
                            
                # Final check: ignore empty links
                if not title or len(title) < 10:
                    continue 

                # 2. Grab the Image
                img_url = ""
                img_tag = a_tag.find("img")
                
                # If no image is inside the link, look at the parent container
                if not img_tag:
                    parent = a_tag.find_parent(["article", "div", "li"])
                    if parent:
                        img_tag = parent.find("img")
                        
                if img_tag:
                    # Capture the image (handles modern lazy-loading tags as well)
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""

                news_list.append({
                    "titel": title,
                    "link": link,
                    "afbeelding": img_url
                })
                
                if len(news_list) >= 5:
                    break
        except Exception:
            pass
            
        return news_list
