# L1 Weer & Nieuws Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)][hacs]
[![Project Maintenance][maintenance_badge]](https://github.com/malosaaa/L1-Weer-en-Nieuws)

This custom component for Home Assistant allows you to monitor up-to-date weather data and the latest news specifically for the Limburg region from [L1 Nieuws](https://www.l1nieuws.nl/). It works by scraping the data directly from the L1 website, providing detailed weather forecasts and news articles without requiring an official API.

> **Disclaimer:** This integration relies on web scraping. If L1 Nieuws drastically changes the HTML structure of its website, this integration might break until it is updated. The integration is built with a smart randomized interval to prevent overloading their servers.

***

## Features

* ✅ **Easy UI-Based Setup**: Configure entirely through the Home Assistant user interface. No `configuration.yaml` required for setup.
* ✅ **Multi-Sensor Data**: Scrapes current temperature, sun hours, precipitation, wind speed, and a clean 5-day forecast.
* ✅ **Optional News Scraper**: Automatically fetches the top 5 latest news articles (Title, Link, and Image). This can be toggled on or off at any time.
* ✅ **Smart Persistent Cache**: Saves data locally. Home Assistant boots up lightning-fast with the last known data without immediately hammering the L1 website.
* ✅ **Robust Service Calls**: Includes custom actions to manually refresh data, wipe the cache, or clear debug files.
* ✅ **Diagnostic Sensors**: Includes sensors to monitor the health, update status, and cache usage of the integration.
* ✅ **Rich Attributes**: Highly detailed attributes attached to the sensors, making it incredibly powerful for complex automations.

## Installation

### Method 1: HACS (Home Assistant Community Store) - Recommended

1.  Ensure you have [HACS](https://hacs.xyz/) installed.
2.  Go to HACS -> Integrations -> Click the 3-dots menu in the top right -> **Custom Repositories**.
3.  In the "Repository" field, paste this URL: `https://github.com/malosaaa/L1-Weer-en-Nieuws`
4.  For "Category", select **Integration**.
5.  Click **Add**.
6.  The "L1 Weer & Nieuws" integration will now appear in your HACS integrations list. Click **Install** or **Download**.
7.  Restart Home Assistant.

### Method 2: Manual Installation

1.  Using a file access tool (like Samba or File Editor), navigate to the `custom_components` directory in your Home Assistant `config` folder.
2.  Create a new folder named `l1_weer`.
3.  Copy all the files from this repository into the new `l1_weer` folder.
4.  Restart Home Assistant.

## Configuration & Options

After installing and restarting, you can set up the integration.

1.  Navigate to **Settings** -> **Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button in the bottom right.
3.  Search for "**L1 Weer & Nieuws**" and select it.
4.  You will be prompted to choose if you want to enable the News scraper and Debug mode. Click **Submit**.

**Adjusting Options Later:**
You can click the **Configure** button on the integration card at any time to:
* Toggle the News fetching on or off.
* Turn **Debug Mode** on or off (useful for troubleshooting; writes a raw HTML copy to a `scrape_output.txt` file in the integration folder).

## Sensors Provided

The integration creates the following sensors. All predictive data and news articles are stored as attributes within these main sensors.

| Sensor Name | Entity ID | Description |
| :--- | :--- | :--- |
| **Current Temperature** | `sensor.l1_huidige_temperatuur` | Main weather sensor. State is the current temperature in °C. Attributes contain today's conditions (`Zon`, `Neerslag`, `Wind`) and the 5-day forecast (`dag_1_temperatuur`, etc.). |
| **Latest News** | `sensor.l1_laatste_nieuws` | State is the number of articles found. Attributes contain the top 5 articles (`artikel_1_titel`, `artikel_1_link`, `artikel_1_afbeelding`, etc.). |
| **Last Update** | `sensor.l1_weer_laatste_update` | (Diagnostic) Timestamp of the last successful web scrape or "Uit Cache". |
| **Status** | `sensor.l1_weer_status` | (Diagnostic) Shows "OK" or "Fout" and includes cache usage details in attributes. |

## Service Calls (Actions)

This integration provides three highly useful services that you can use in your automations or trigger manually via the **Developer Tools > Services** panel:

| Service | Description |
| :--- | :--- |
| `l1_weer.manual_refresh` | Forces an immediate update of the weather and news data, ignoring the standard background timer. |
| `l1_weer.clear_cache` | Clears the local JSON cache stored in Home Assistant. Very useful if the data appears stuck or corrupt. |
| `l1_weer.clear_debug_file` | Deletes the `scrape_output.txt` debug file from the integration directory to save space when debug mode is on. |

## Automations & Attributes

The sensors contain dozens of hidden attributes under the hood, making the automation possibilities endless. 

### Example: High Wind Warning Notification
Here is an example of how you can trigger a push notification to your phone if high winds (wind force 5 or above) are predicted for today (`dag_1`):

```yaml
alias: "L1 Weather: High Wind Warning"
trigger:
  - platform: numeric_state
    entity_id: sensor.l1_huidige_temperatuur
    attribute: dag_1_windkracht
    above: 4
action:
  - service: notify.notify
    data:
      title: "🌬️ Wind Warning"
      message: "Attention! Wind force {{ state_attr('sensor.l1_huidige_temperatuur', 'dag_1_windkracht') }} is predicted today in Limburg. Secure loose items in your garden!"
mode: single
```

## Dashboard Card Setup

Complete your dashboard with these ready-to-use Markdown / Grid cards! 

*(Note: Double-check that your entity IDs exactly match the ones in your system)*.

### 📰 News Card
```yaml
type: grid
cards:
  - type: heading
    heading: Laatste Nieuws
  - type: markdown
    content: >-
      ## 📰 L1 Laatste Nieuws

      {% set entity = 'sensor.l1_laatste_nieuws' %}

      {% for i in range(1, 6) %} 
        {% set title = state_attr(entity, 'artikel_' ~ i ~ '_titel') %} 
        {% set link = state_attr(entity, 'artikel_' ~ i ~ '_link') %} 
        {% set img = state_attr(entity, 'artikel_' ~ i ~ '_afbeelding') %}

        {% if title %} 
          <a href="{{ link }}" target="_blank">
            <img src="{{ img }}" style="width: 100%; border-radius: 12px; margin-bottom: 8px; box-shadow: 0px 4px 10px rgba(0,0,0,0.15);">
          </a>

          <div style="font-size: 1.15em; font-weight: bold; line-height: 1.3; margin-bottom: 15px;">
            <a href="{{ link }}" target="_blank" style="text-decoration: none; color: var(--primary-text-color);">
              {{ title }}
            </a>
          </div>
        {% endif %} 
      {% endfor %}
```

### 🌤️ Weather Card
```yaml
type: grid
cards:
  - type: heading
    heading: Weer
  - type: markdown
    content: >-
      {% set e = 'sensor.l1_huidige_temperatuur' %}

      <div align="center">
        <h2>🌤️ L1 Weer Limburg</h2>
        <h1 style="font-size: 3em; margin: 0;">{{ states(e) }}°C</h1>
      </div>

      <br> Vandaag <br> ☀️ Zon: {{ state_attr(e, 'Zon') }}   🌧️ Regen: {{ state_attr(e, 'Neerslag') }}   💨 Wind: {{ state_attr(e, 'Wind') }}

      ---

      <br> 📅 Verwachting komende dagen

      {% for dag in ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo'] %}
        {% if state_attr(e, dag) != None %}
      **{{ dag }}:** {{ state_attr(e, dag) }}
        {% endif %}
      {% endfor %}
```

[hacs]: https://hacs.xyz
[hacs_badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[maintenance_badge]: https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge
