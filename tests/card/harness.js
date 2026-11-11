// Browser test harness for the L1 card. Runs in headless Chrome (see
// tests/test_card.py) after the card module; writes JSON results to #out.
const results = { errors: [], checks: {} };
const origError = console.error;
console.error = (...args) => { results.errors.push(args.map(String).join(" ")); origError(...args); };
window.addEventListener("error", (ev) => results.errors.push(String(ev.message)));
window.addEventListener("unhandledrejection", (ev) => results.errors.push(String(ev.reason)));

// Minimal stand-ins for Home Assistant elements.
customElements.define("ha-form", class extends HTMLElement {});
customElements.define("ha-card", class extends HTMLElement {});
customElements.define("ha-icon", class extends HTMLElement {});

const DATA = JSON.parse(document.getElementById("states").textContent);
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const clone = (v) => JSON.parse(JSON.stringify(v));
const W = "sensor.l1_huidige_temperatuur";
const N = "sensor.l1_laatste_nieuws";

function makeHass(states, extra = {}) {
  return { states, entities: DATA.entities, language: "nl", ...extra };
}

async function newCard(config, hass, tag = "l1-card", width = 480) {
  const box = document.createElement("div");
  box.style.width = `${width}px`;
  document.body.appendChild(box);
  const card = document.createElement(tag);
  card.setConfig(config);
  box.appendChild(card);
  card.hass = hass;
  await flush();
  return card;
}

const q = (card, sel) => card.shadowRoot.querySelector(sel);
const qa = (card, sel) => [...card.shadowRoot.querySelectorAll(sel)];
const txt = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : null);
const bad = (card) => ["undefined", "NaN", "null", "[object Object]"].filter((x) => txt(q(card, ".wrap")).includes(x));

(async () => {
  const c = results.checks;
  try {
    localStorage.clear();
    const card = await newCard({}, makeHass(DATA.states));
    c.view = q(card, ".seg .on").dataset.view;
    c.seg = qa(card, ".seg button").map((b) => b.textContent);
    c.title = txt(q(card, ".title"));
    c.big = txt(q(card, ".big"));
    c.cond = txt(q(card, ".cond"));
    c.now_icon = q(card, "img.now-icon")?.getAttribute("src") || "";
    c.stats = qa(card, ".stat span").map(txt);
    c.days = qa(card, ".day .dname").map(txt);
    c.hi = qa(card, ".day .hi").map(txt);
    c.lo = qa(card, ".day .lo").map(txt);
    c.day_icons = qa(card, ".day img.dicon").length;
    c.report = !!q(card, "details.report");
    c.bad_weather = bad(card);

    // Same state objects again: no re-render.
    let renders = 0;
    const real = card._render.bind(card);
    card._render = () => { renders += 1; real(); };
    card.hass = makeHass(DATA.states);
    c.renders_same = renders;
    card._render = real;

    // Switch to news
    q(card, '.seg button[data-view="news"]').click();
    await flush();
    c.news_view = q(card, ".seg .on").dataset.view;
    c.news_title = txt(q(card, ".title"));
    c.hero = txt(q(card, ".hero-title"));
    c.hero_img = q(card, ".hero-img img")?.getAttribute("src") || "";
    c.rows = qa(card, ".row").length;
    const links = qa(card, "a");
    c.links = links.length;
    c.links_ok = links.every((a) => a.target === "_blank" && a.rel.includes("noopener") && a.href.startsWith("https://www.l1nieuws.nl/"));
    const heroTitle = q(card, ".hero-title");
    c.underline = getComputedStyle(q(card, "a.hero")).textDecorationLine;
    c.title_color = getComputedStyle(heroTitle).color;
    c.stored = localStorage.getItem("l1-card:view:sensor.l1_huidige_temperatuur|sensor.l1_laatste_nieuws|");
    c.bad_news = bad(card);

    // Persisted view after a "refresh" (new card, same config)
    const again = await newCard({}, makeHass(DATA.states));
    c.persisted = q(again, ".seg .on").dataset.view;

    // initial_view and max_articles
    localStorage.clear();
    const news3 = await newCard({ initial_view: "news", max_articles: 3, title: "Mijn L1" }, makeHass(DATA.states));
    c.initial_news = q(news3, ".seg .on").dataset.view;
    c.rows3 = qa(news3, ".row").length;
    c.custom_title = txt(q(news3, ".title"));

    // show_forecast false
    const noFc = await newCard({ show_forecast: false, show_description: false }, makeHass(DATA.states));
    c.no_forecast = qa(noFc, ".day").length;
    c.no_report = !q(noFc, "details.report");

    // Auto-discovery of renamed entities
    localStorage.clear();
    const renamed = {
      "sensor.weer_x": { ...clone(DATA.states[W]), entity_id: "sensor.weer_x" },
      "sensor.nieuws_x": { ...clone(DATA.states[N]), entity_id: "sensor.nieuws_x" },
    };
    const disc = await newCard({}, makeHass(renamed, {
      entities: { "sensor.weer_x": { platform: "l1_weer" }, "sensor.nieuws_x": { platform: "l1_weer" } },
    }));
    c.disc_big = txt(q(disc, ".big"));
    q(disc, '.seg button[data-view="news"]').click();
    await flush();
    c.disc_hero = txt(q(disc, ".hero-title"));

    // Older integration (flat attributes only)
    localStorage.clear();
    const old = clone(DATA.states);
    delete old[W].attributes.forecast;
    delete old[N].attributes.nieuws;
    const legacy = await newCard({}, makeHass(old));
    c.legacy_days = qa(legacy, ".day").length;
    c.legacy_hi = qa(legacy, ".day .hi").map(txt);
    q(legacy, '.seg button[data-view="news"]').click();
    await flush();
    c.legacy_hero = txt(q(legacy, ".hero-title"));
    c.legacy_rows = qa(legacy, ".row").length;

    // XSS and unsafe links
    localStorage.clear();
    const evil = clone(DATA.states);
    evil[N].attributes.nieuws[0] = { titel: "<img src=x onerror=window.__xss=1> Boos", link: "javascript:alert(1)", afbeelding: "javascript:x" };
    evil[W].attributes.condition = "<b>vet</b>";
    const x = await newCard({ initial_view: "news" }, makeHass(evil));
    await flush();
    c.xss_imgs = qa(x, ".hero img").length;
    c.xss_text = txt(q(x, ".hero-title"));
    c.xss_link = qa(x, 'a[href^="javascript"]').length;
    c.xss_fired = window.__xss ? 1 : 0;
    q(x, '.seg button[data-view="weather"]').click();
    await flush();
    c.xss_b = qa(x, ".cond b").length;

    // Missing entities
    localStorage.clear();
    const none = await newCard({}, makeHass({}));
    c.missing_weather = txt(q(none, ".notice"));
    q(none, '.seg button[data-view="news"]').click();
    await flush();
    c.missing_news = txt(q(none, ".notice"));

    // Unavailable
    localStorage.clear();
    const un = clone(DATA.states);
    un[W].state = "unavailable";
    const u = await newCard({ initial_view: "weather" }, makeHass(un));
    c.unavailable = txt(q(u, ".big"));

    // Aliases
    localStorage.clear();
    const alias = await newCard({}, makeHass(DATA.states), "l1-news-card");
    c.alias_view = q(alias, ".seg .on").dataset.view;

    // English
    const en = await newCard({ initial_view: "weather" }, makeHass(DATA.states, { language: "en" }));
    c.en_seg = qa(en, ".seg button").map((b) => b.textContent);

    // Narrow layout does not overflow
    const narrow = await newCard({ initial_view: "weather" }, makeHass(DATA.states), "l1-card", 300);
    const wrap = q(narrow, ".wrap");
    c.narrow_overflow = wrap.scrollWidth > wrap.clientWidth + 1;

    // Bad config
    try {
      document.createElement("l1-card").setConfig({ initial_view: "radar" });
      c.bad_config = "accepted";
    } catch (_err) {
      c.bad_config = "rejected";
    }

    // Editor and picker
    const editor = document.createElement(customElements.get("l1-card").getConfigElement().tagName.toLowerCase());
    editor.hass = makeHass(DATA.states);
    editor.setConfig({ initial_view: "news" });
    c.editor_fields = (editor.querySelector("ha-form")?.schema || []).map((s) => s.name);
    c.stub = customElements.get("l1-card").getStubConfig();
    c.picker = window.customCards.map((cc) => cc.type);
  } catch (err) {
    results.errors.push(`harness: ${err && err.stack ? err.stack : err}`);
  }
  document.getElementById("out").textContent = JSON.stringify(results);
})();
