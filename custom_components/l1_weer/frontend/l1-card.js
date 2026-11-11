// L1 Weer & Nieuws card: one card with a "Weer | Nieuws" switch in the header.
// Weather view: current temperature, L1 icon, today's figures and a 5-day row.
// News view: a hero story and compact rows. Plain custom element, no build
// step. Keep this file ASCII-only (use \u escapes).
const VERSION = "1.1.0";
const DOMAIN = "l1_weer";
const DEG = "\u00b0";
const DASH = "\u2013";
const DEFAULT_WEATHER = "sensor.l1_huidige_temperatuur";
const DEFAULT_NEWS = "sensor.l1_laatste_nieuws";
const VIEWS = ["weather", "news"];
const DEFAULTS = { initial_view: "weather", max_articles: 5, show_forecast: true, show_description: true };
const STORE_PREFIX = "l1-card:view:";

const I18N = {
  nl: {
    weather: "Weer", news: "Nieuws", weather_title: "L1 Weer Limburg", news_title: "L1 Laatste Nieuws",
    today: "Vandaag", sun: "Zon", rain: "Neerslag", wind: "Wind", report: "Weerbericht",
    no_weather: "Geen L1-weerdata gevonden. Controleer de weer-entiteit.",
    no_news: "Geen L1-nieuws gevonden. Staat nieuws aan in de integratie-opties?",
    unavailable: "Niet beschikbaar", view_switch: "Weergave",
    editor: {
      title: "Titel (leeg = automatisch)", entity_weather: "Weer-entiteit", entity_news: "Nieuws-entiteit",
      initial_view: "Startweergave", max_articles: "Aantal artikelen", show_forecast: "Meerdaagse verwachting",
      show_description: "Weerbericht (uitklapbaar)", weather: "Weer", news: "Nieuws",
    },
  },
  en: {
    weather: "Weather", news: "News", weather_title: "L1 Weather Limburg", news_title: "L1 Latest News",
    today: "Today", sun: "Sun", rain: "Rain", wind: "Wind", report: "Forecast text",
    no_weather: "No L1 weather data found. Check the weather entity.",
    no_news: "No L1 news found. Is news enabled in the integration options?",
    unavailable: "Unavailable", view_switch: "View",
    editor: {
      title: "Title (empty = automatic)", entity_weather: "Weather entity", entity_news: "News entity",
      initial_view: "Initial view", max_articles: "Number of articles", show_forecast: "Multi-day forecast",
      show_description: "Forecast text (collapsible)", weather: "Weather", news: "News",
    },
  },
};

function tr(hass) {
  const lang = ((hass && hass.language) || "nl").slice(0, 2);
  return I18N[lang] || I18N.nl;
}

function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Only http(s) links and images; anything else becomes "".
function safeUrl(value) {
  const url = String(value || "").trim();
  return /^https?:\/\//i.test(url) ? url : "";
}

function num(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(String(value).replace(",", "."));
  return Number.isFinite(n) ? Math.round(n) : null;
}

function temp(value) {
  const n = num(value);
  return n === null ? DASH : `${n}${DEG}`;
}

function isWeather(state) {
  const a = (state && state.attributes) || {};
  return Array.isArray(a.forecast) || a.dag_1_temperatuur !== undefined;
}

function isNews(state) {
  const a = (state && state.attributes) || {};
  return Array.isArray(a.nieuws) || a.artikel_1_titel !== undefined;
}

// Configured entity, else the default id, else the first L1 sensor that looks right.
function resolveEntity(hass, configured, fallback, test) {
  if (!hass) return configured || fallback;
  if (configured) return configured;
  if (hass.states[fallback]) return fallback;
  const registry = hass.entities || {};
  const ids = Object.keys(hass.states).filter((id) => id.startsWith("sensor."));
  const ours = ids.filter((id) => registry[id] && registry[id].platform === DOMAIN);
  return ours.find((id) => test(hass.states[id])) || ids.find((id) => test(hass.states[id])) || fallback;
}

function forecastFrom(attrs) {
  if (Array.isArray(attrs.forecast) && attrs.forecast.length) return attrs.forecast;
  // Older integration versions: rebuild from the flat dag_N_* attributes.
  const out = [];
  for (let i = 1; i <= 7; i += 1) {
    if (attrs[`dag_${i}_temperatuur`] === undefined) break;
    out.push({
      day: "", temp: attrs[`dag_${i}_temperatuur`], min: attrs[`dag_${i}_min`],
      zon: attrs[`dag_${i}_zonuren`] !== undefined ? `${attrs[`dag_${i}_zonuren`]} u` : "",
      neerslag: attrs[`dag_${i}_neerslag`] || "", wind: attrs[`dag_${i}_windkracht`] || "",
    });
  }
  return out;
}

function newsFrom(attrs) {
  if (Array.isArray(attrs.nieuws)) return attrs.nieuws;
  const out = [];
  for (let i = 1; i <= 10; i += 1) {
    const titel = attrs[`artikel_${i}_titel`];
    if (!titel) break;
    out.push({ titel, link: attrs[`artikel_${i}_link`], afbeelding: attrs[`artikel_${i}_afbeelding`] });
  }
  return out;
}

const ICONS = {
  sun: "mdi:weather-sunny", rain: "mdi:weather-pouring", wind: "mdi:weather-windy",
  temp: "mdi:thermometer",
};

function stat(icon, label, value) {
  return `<div class="stat" title="${esc(label)}"><ha-icon icon="${icon}"></ha-icon><span>${esc(value || DASH)}</span></div>`;
}

class L1Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULTS };
    this._view = null;
    this._seen = [];
    this._onClick = this._onClick.bind(this);
  }

  static getConfigElement() {
    return document.createElement("l1-card-editor");
  }

  static getStubConfig() {
    return { initial_view: "weather" };
  }

  setConfig(config) {
    if (!config || typeof config !== "object" || Array.isArray(config)) {
      throw new Error("Invalid configuration");
    }
    if (config.initial_view !== undefined && !VIEWS.includes(config.initial_view)) {
      throw new Error("initial_view must be 'weather' or 'news'");
    }
    this._config = { ...DEFAULTS, ...this._defaults(), ...config };
    this._view = this._storedView() || this._config.initial_view;
    this._seen = [];
    if (this._hass) this._render();
  }

  // Overridden by the thin legacy aliases below.
  _defaults() {
    return {};
  }

  set hass(hass) {
    this._hass = hass;
    const ids = this._entities();
    const seen = [ids.weather, ids.news, hass.states[ids.weather], hass.states[ids.news], hass.language];
    if (seen.some((v, i) => v !== this._seen[i])) {
      this._seen = seen;
      this._render();
    }
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return this._view === "news" ? 2 + Math.min(this._config.max_articles, 5) : 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _entities() {
    return {
      weather: resolveEntity(this._hass, this._config.entity_weather, DEFAULT_WEATHER, isWeather),
      news: resolveEntity(this._hass, this._config.entity_news, DEFAULT_NEWS, isNews),
    };
  }

  _storeKey() {
    const c = this._config;
    return `${STORE_PREFIX}${c.entity_weather || DEFAULT_WEATHER}|${c.entity_news || DEFAULT_NEWS}|${c.title || ""}`;
  }

  _storedView() {
    try {
      const v = window.localStorage.getItem(this._storeKey());
      return VIEWS.includes(v) ? v : null;
    } catch (_err) {
      return null;
    }
  }

  _setView(view) {
    if (!VIEWS.includes(view) || view === this._view) return;
    this._view = view;
    try {
      window.localStorage.setItem(this._storeKey(), view);
    } catch (_err) {
      // private mode / storage disabled: keep it for this session only
    }
    this._render();
  }

  _onClick(ev) {
    const btn = ev.composedPath().find((el) => el.dataset && el.dataset.view);
    if (btn) {
      ev.preventDefault();
      this._setView(btn.dataset.view);
    }
  }

  _render() {
    if (!this._hass) return;
    const t = tr(this._hass);
    const view = this._view === "news" ? "news" : "weather";
    const title = this._config.title || (view === "news" ? t.news_title : t.weather_title);
    const body = view === "news" ? this._renderNews(t) : this._renderWeather(t);
    const seg = VIEWS.map((v) => `<button type="button" role="tab" data-view="${v}" aria-selected="${v === view}" class="${v === view ? "on" : ""}">${esc(t[v])}</button>`).join("");
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="wrap">
          <div class="head">
            <div class="brand"><span class="mark">L1</span><span class="title">${esc(title)}</span></div>
            <div class="seg" role="tablist" aria-label="${esc(t.view_switch)}">${seg}</div>
          </div>
          <div class="body ${view}">${body}</div>
        </div>
      </ha-card>`;
    this.shadowRoot.querySelector(".seg").addEventListener("click", this._onClick);
    this.shadowRoot.querySelectorAll("img").forEach((img) => {
      img.addEventListener("error", () => img.classList.add("broken"), { once: true });
    });
  }

  _renderWeather(t) {
    const state = this._hass.states[this._entities().weather];
    if (!state) return `<div class="notice">${esc(t.no_weather)}</div>`;
    const a = state.attributes || {};
    const days = forecastFrom(a);
    const today = days[0] || {};
    const unavailable = state.state === "unavailable" || state.state === "unknown";
    const icon = safeUrl(a.condition_icon || today.condition_icon);
    const condition = a.condition || a.condition_name || today.condition || "";
    const min = a.temp_min !== undefined ? a.temp_min : today.min;
    const max = a.temp_max !== undefined ? a.temp_max : today.temp;
    let html = `<div class="now">
      ${icon ? `<img class="now-icon" src="${esc(icon)}" alt="${esc(a.condition_name || condition)}">` : `<ha-icon class="now-icon mdi" icon="mdi:weather-partly-cloudy"></ha-icon>`}
      <div class="now-main">
        <div class="big">${unavailable ? esc(t.unavailable) : temp(state.state)}</div>
        ${condition ? `<div class="cond">${esc(condition)}</div>` : ""}
      </div>
    </div>
    <div class="stats">
      ${stat(ICONS.temp, "min / max", `${temp(min)} / ${temp(max)}`)}
      ${stat(ICONS.sun, t.sun, a.Zon || today.zon)}${stat(ICONS.rain, t.rain, a.Neerslag || today.neerslag)}
      ${stat(ICONS.wind, t.wind, a.Wind || today.wind)}
    </div>`;
    if (this._config.show_forecast !== false && days.length) {
      html += `<div class="days">${days.slice(0, 5).map((d, i) => {
        const dIcon = safeUrl(d.condition_icon);
        return `<div class="day${i === 0 ? " today" : ""}">
          <div class="dname">${esc(i === 0 ? t.today : d.day || DASH)}</div>
          ${dIcon ? `<img class="dicon" src="${esc(dIcon)}" alt="${esc(d.condition || "")}" title="${esc(d.condition || "")}">` : `<div class="dicon"></div>`}
          <div class="dtemp"><span class="hi">${temp(d.temp)}</span><span class="lo">${temp(d.min)}</span></div>
          <div class="dmeta" title="${esc(t.rain)}"><ha-icon icon="mdi:water-outline"></ha-icon>${esc(d.neerslag || DASH)}</div>
          <div class="dmeta" title="${esc(t.sun)}"><ha-icon icon="mdi:white-balance-sunny"></ha-icon>${esc(d.zon || DASH)}</div>
          <div class="dmeta" title="${esc(t.wind)}"><ha-icon icon="mdi:weather-windy"></ha-icon>${esc(d.wind || DASH)}</div>
        </div>`;
      }).join("")}</div>`;
    }
    if (this._config.show_description !== false && a.description) {
      const paras = String(a.description).split("\n").filter(Boolean);
      html += `<details class="report"><summary>${esc(t.report)}</summary>${paras.map((p) => `<p>${esc(p)}</p>`).join("")}</details>`;
    }
    return html;
  }

  _renderNews(t) {
    const state = this._hass.states[this._entities().news];
    const max = Math.max(1, Math.min(10, num(this._config.max_articles) || DEFAULTS.max_articles));
    const items = state ? newsFrom(state.attributes || {}).filter((n) => n && n.titel).slice(0, max) : [];
    if (!items.length) return `<div class="notice">${esc(t.no_news)}</div>`;
    const link = (n, cls, inner) => {
      const href = safeUrl(n.link);
      return href
        ? `<a class="${cls}" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>`
        : `<div class="${cls}">${inner}</div>`;
    };
    const img = (n, cls) => {
      const src = safeUrl(n.afbeelding);
      return `<div class="${cls}">${src ? `<img src="${esc(src)}" alt="" loading="lazy">` : ""}</div>`;
    };
    const [hero, ...rest] = items;
    return link(hero, "hero", `${img(hero, "hero-img")}<div class="hero-title">${esc(hero.titel)}</div>`)
      + (rest.length ? `<div class="rows">${rest.map((n) => link(n, "row", `${img(n, "thumb")}<div class="row-title">${esc(n.titel)}</div>`)).join("")}</div>` : "");
  }
}

const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; container-type: inline-size; }
  .wrap { padding: 14px 16px 16px; color: var(--primary-text-color); }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
  .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .mark { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px;
    border-radius: 8px; background: linear-gradient(135deg, #1f5fd6, #0b3a8f); color: #fff; font-weight: 800;
    font-size: 14px; letter-spacing: -.5px; box-shadow: 0 1px 3px rgba(0,0,0,.35); }
  .title { font-size: 1.1em; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .seg { flex: none; display: inline-flex; padding: 3px; border-radius: 999px;
    background: var(--secondary-background-color, rgba(127,127,127,.15)); border: 1px solid var(--divider-color); }
  .seg button { appearance: none; border: 0; background: transparent; color: var(--secondary-text-color);
    font: inherit; font-size: .85em; font-weight: 600; padding: 5px 12px; border-radius: 999px; cursor: pointer; }
  .seg button.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .seg button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }
  .notice { color: var(--secondary-text-color); font-size: .9em; padding: 8px 0; }
  img.broken { visibility: hidden; }

  .now { display: flex; align-items: center; gap: 14px; }
  .now-icon { width: 72px; height: 72px; flex: none; object-fit: contain; --mdc-icon-size: 64px; color: var(--secondary-text-color); }
  .big { font-size: 3em; font-weight: 300; line-height: 1; }
  .cond { margin-top: 4px; color: var(--secondary-text-color); font-size: .95em; line-height: 1.3; }
  .stats { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 4px; }
  .stat { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 999px; font-size: .85em;
    background: var(--secondary-background-color, rgba(127,127,127,.12)); --mdc-icon-size: 16px; }
  .stat ha-icon { color: var(--secondary-text-color); }
  .days { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; margin-top: 14px;
    padding-top: 12px; border-top: 1px solid var(--divider-color); }
  .day { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 6px 2px; border-radius: 10px; text-align: center; }
  .day.today { background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .dname { font-weight: 600; font-size: .9em; }
  .dicon { width: 36px; height: 36px; object-fit: contain; }
  .dtemp { display: flex; gap: 6px; align-items: baseline; }
  .hi { font-weight: 600; }
  .lo { color: var(--secondary-text-color); font-size: .9em; }
  .dmeta { display: inline-flex; align-items: center; gap: 2px; font-size: .75em; color: var(--secondary-text-color);
    white-space: nowrap; --mdc-icon-size: 13px; }
  .report { margin-top: 12px; border-top: 1px solid var(--divider-color); padding-top: 10px; font-size: .9em; }
  .report summary { cursor: pointer; color: var(--secondary-text-color); font-weight: 600; }
  .report p { margin: 8px 0 0; line-height: 1.45; color: var(--primary-text-color); }

  a { color: inherit; text-decoration: none; }
  a:hover .hero-title, a:hover .row-title { color: var(--primary-color); }
  a:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; border-radius: 10px; }
  .hero { display: block; }
  .hero-img, .thumb { position: relative; overflow: hidden; background: var(--secondary-background-color, rgba(127,127,127,.15)); }
  .hero-img { aspect-ratio: 16 / 9; border-radius: var(--ha-card-border-radius, 12px); }
  .hero-img img, .thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
  .hero-title { margin-top: 10px; font-size: 1.15em; font-weight: 700; line-height: 1.3; color: var(--primary-text-color); }
  .rows { margin-top: 12px; border-top: 1px solid var(--divider-color); }
  .row { display: flex; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
  .row:last-child { border-bottom: 0; padding-bottom: 0; }
  .thumb { flex: none; width: 104px; aspect-ratio: 16 / 9; border-radius: 8px; }
  .row-title { font-size: .95em; font-weight: 500; line-height: 1.35; color: var(--primary-text-color);
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  @container (max-width: 380px) {
    .wrap { padding: 12px; }
    .title { font-size: 1em; }
    .seg button { padding: 4px 9px; }
    .big { font-size: 2.4em; }
    .now-icon { width: 56px; height: 56px; }
    .thumb { width: 84px; }
    .dmeta:last-child { display: none; }
  }
`;

class L1CardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._config) return;
    const t = tr(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => tr(this._hass).editor[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...this._config, ...ev.detail.value };
        for (const key of Object.keys(config)) {
          if (config[key] === "" || config[key] === undefined || config[key] === null) delete config[key];
        }
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.schema = [
      { name: "initial_view", selector: { select: { mode: "dropdown", options: [
        { value: "weather", label: t.editor.weather }, { value: "news", label: t.editor.news },
      ] } } },
      { name: "title", selector: { text: {} } },
      { name: "entity_weather", selector: { entity: { domain: "sensor", integration: DOMAIN } } },
      { name: "entity_news", selector: { entity: { domain: "sensor", integration: DOMAIN } } },
      { name: "max_articles", selector: { number: { min: 1, max: 10, mode: "box" } } },
      { name: "show_forecast", selector: { boolean: {} } },
      { name: "show_description", selector: { boolean: {} } },
    ];
    this._form.data = { ...DEFAULTS, ...this._config };
    if (this._hass) this._form.hass = this._hass;
  }
}

// Thin aliases: same card, different starting view (not listed in the picker).
class L1NewsCard extends L1Card {
  _defaults() {
    return { initial_view: "news" };
  }
}
class L1WeatherCard extends L1Card {
  _defaults() {
    return { initial_view: "weather" };
  }
}

if (!customElements.get("l1-card")) customElements.define("l1-card", L1Card);
if (!customElements.get("l1-card-editor")) customElements.define("l1-card-editor", L1CardEditor);
if (!customElements.get("l1-news-card")) customElements.define("l1-news-card", L1NewsCard);
if (!customElements.get("l1-weather-card")) customElements.define("l1-weather-card", L1WeatherCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "l1-card")) {
  window.customCards.push({
    type: "l1-card",
    name: "L1 Weer & Nieuws",
    description: "L1 Limburg: weather (now + 5 days) and the latest news, with a Weer | Nieuws switch.",
    preview: true,
    documentationURL: "https://github.com/DonTranQuiL/L1-Weer-en-Nieuws",
  });
}
console.info(`%c L1-CARD %c ${VERSION} `, "color:#fff;background:#1f5fd6;font-weight:700", "color:#1f5fd6;background:#fff");
