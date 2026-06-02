/* AI Trends — static browser. Vanilla JS, no deps.
   Loads a small manifest + trends index up front; paper shards are fetched on
   demand (one conference-year at a time) so the initial payload stays light. */

const DATA = "data/";
const PAGE = 24;
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
};

const state = {
  manifest: null,
  trends: new Map(), // "CONF|YEAR" -> trend
  shardCache: new Map(), // file -> papers[]
  trendSel: { conf: null, year: null },
  shownCount: PAGE,
  filtered: [],
};

const trendKey = (c, y) => `${c}|${y}`;

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`fetch ${path}: ${res.status}`);
  return res.json();
}

/* ---------- bootstrap ---------- */
async function init() {
  try {
    const [manifest, trends] = await Promise.all([
      getJSON(DATA + "manifest.json"),
      getJSON(DATA + "trends.json"),
    ]);
    state.manifest = manifest;
    for (const t of trends) state.trends.set(trendKey(t.conference, t.year), t);

    renderHeroStats();
    buildTrendPickers();
    buildFilters();
    selectLatestTrend();
    applyFilters(); // populate the browse list with the default venue/year
  } catch (err) {
    $("#trend-panel").innerHTML = `<p class="empty">Could not load data (${err.message}).</p>`;
  }
}

function confLabels() {
  // conferences that actually have shards, in manifest order
  const withData = new Set(state.manifest.shards.map((s) => s.conference));
  return state.manifest.conferences.map((c) => c.label).filter((l) => withData.has(l));
}
function yearsFor(conf) {
  return state.manifest.shards
    .filter((s) => s.conference === conf)
    .map((s) => s.year)
    .sort((a, b) => b - a);
}
function shardFile(conf, year) {
  const s = state.manifest.shards.find((x) => x.conference === conf && x.year === year);
  return s ? s.file : null;
}

/* ---------- hero ---------- */
function renderHeroStats() {
  const papers = state.manifest.shards.reduce((n, s) => n + s.count, 0);
  const stats = [
    [papers.toLocaleString(), "papers"],
    [confLabels().length, "conferences"],
    [state.manifest.years.length, "years"],
    [state.manifest.topics.length, "topics tracked"],
  ];
  $("#hero-stats").replaceChildren(
    ...stats.map(([num, label]) =>
      el("div", { className: "stat" }, [
        el("span", { className: "stat__num", textContent: num }),
        el("span", { className: "stat__label", textContent: label }),
      ])
    )
  );
}

/* ---------- trends ---------- */
function buildTrendPickers() {
  const confRow = $("#conf-pills");
  confRow.replaceChildren(
    ...confLabels().map((label) =>
      el("button", {
        className: "pill",
        type: "button",
        textContent: label,
        onclick: () => {
          state.trendSel.conf = label;
          const years = yearsFor(label);
          if (!years.includes(state.trendSel.year)) state.trendSel.year = years[0];
          renderTrend();
        },
      })
    )
  );
}

function renderYearPills() {
  const years = yearsFor(state.trendSel.conf);
  $("#year-pills").replaceChildren(
    ...years.map((y) =>
      el("button", {
        className: "pill",
        type: "button",
        textContent: y,
        onclick: () => {
          state.trendSel.year = y;
          renderTrend();
        },
      })
    )
  );
}

function selectLatestTrend() {
  // newest year overall, preferring a conference that has it
  const newest = Math.max(...state.manifest.years);
  const shard = state.manifest.shards
    .filter((s) => s.year === newest)
    .sort((a, b) => b.count - a.count)[0];
  state.trendSel = { conf: shard.conference, year: shard.year };
  renderTrend();
}

function rankList(kind, topics) {
  if (!topics.length) return el("p", { className: "empty", textContent: "—" });
  return el(
    "ol",
    { className: "rank" },
    topics.map((name) =>
      el("li", {}, [
        el("button", {
          className: "chip",
          type: "button",
          title: `Browse ${name} papers`,
          onclick: () => drillTo(name),
        }, [
          el("span", { className: "chip__rank" }),
          el("span", { className: "chip__name", textContent: name }),
        ]),
      ])
    )
  );
}

function renderChart(counts) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if (!entries.length) return el("p", { className: "empty", textContent: "No counts." });
  const max = entries[0][1];
  const rows = entries.map(([name, val]) =>
    el("button", { className: "bar", type: "button", title: `Browse ${name}`, onclick: () => drillTo(name) }, [
      el("span", { className: "bar__name", textContent: name }),
      el("div", { className: "bar__track" }, [
        el("div", { className: "bar__fill", style: `width:${Math.max(2, (val / max) * 100)}%` }),
      ]),
      el("span", { className: "bar__val", textContent: val }),
    ])
  );
  return el("div", { className: "chart" }, [
    el("p", { className: "chart__h", textContent: "Most papers" }),
    ...rows,
  ]);
}

function renderTrend() {
  // sync pressed states
  for (const p of document.querySelectorAll("#conf-pills .pill"))
    p.setAttribute("aria-pressed", p.textContent === state.trendSel.conf);
  renderYearPills();
  for (const p of document.querySelectorAll("#year-pills .pill"))
    p.setAttribute("aria-pressed", String(p.textContent) === String(state.trendSel.year));

  const t = state.trends.get(trendKey(state.trendSel.conf, state.trendSel.year));
  const panel = $("#trend-panel");
  if (!t) {
    panel.replaceChildren(el("p", { className: "empty", textContent: "No trend data." }));
    return;
  }
  const baseline = t.previous_year ? ` vs ${t.previous_year}` : " (no prior year)";
  panel.replaceChildren(
    el("div", {}, [
      el("div", { className: "cols" }, [
        el("div", { className: "col col--top" }, [
          el("h3", { className: "col__h", textContent: "Top" }),
          rankList("top", t.top),
        ]),
        el("div", { className: "col col--emerging" }, [
          el("h3", { className: "col__h", textContent: "Emerging" + (t.previous_year ? "" : " —") }),
          rankList("emerging", t.emerging),
        ]),
        el("div", { className: "col col--fading" }, [
          el("h3", { className: "col__h", textContent: "Fading" }),
          rankList("fading", t.fading),
        ]),
      ]),
      el("p", { className: "result-meta", textContent: `${state.trendSel.conf} ${state.trendSel.year}${baseline}` }),
    ]),
    renderChart(t.counts || {})
  );
}

/* ---------- drill-down: trends -> browse ---------- */
function drillTo(topic) {
  $("#f-conf").value = state.trendSel.conf;
  syncYearOptions();
  $("#f-year").value = String(state.trendSel.year);
  ensureTopicOption(topic);
  $("#f-topic").value = topic;
  $("#f-search").value = "";
  applyFilters();
  $("#browse").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- browse ---------- */
function buildFilters() {
  const confSel = $("#f-conf");
  confSel.replaceChildren(
    ...confLabels().map((l) => el("option", { value: l, textContent: l }))
  );
  const topicSel = $("#f-topic");
  topicSel.append(
    ...state.manifest.topics.map((t) => el("option", { value: t, textContent: t }))
  );
  confSel.value = state.manifest.shards.find((s) => s.year === Math.max(...state.manifest.years)).conference;
  syncYearOptions();

  confSel.addEventListener("change", () => { syncYearOptions(); applyFilters(); });
  $("#f-year").addEventListener("change", applyFilters);
  topicSel.addEventListener("change", applyFilters);
  $("#f-sort").addEventListener("change", applyFilters);
  $("#f-search").addEventListener("input", debounce(applyFilters, 180));
  $("#more-btn").addEventListener("click", () => { state.shownCount += PAGE; paintPapers(); });
}

function syncYearOptions() {
  const years = yearsFor($("#f-conf").value);
  $("#f-year").replaceChildren(...years.map((y) => el("option", { value: y, textContent: y })));
}

function ensureTopicOption(topic) {
  const sel = $("#f-topic");
  if (![...sel.options].some((o) => o.value === topic))
    sel.append(el("option", { value: topic, textContent: topic }));
}

async function applyFilters() {
  const conf = $("#f-conf").value;
  const year = Number($("#f-year").value);
  const topic = $("#f-topic").value;
  const q = $("#f-search").value.trim().toLowerCase();
  const file = shardFile(conf, year);
  const list = $("#papers");

  if (!file) { list.replaceChildren(); $("#result-meta").textContent = "No data."; return; }

  let papers = state.shardCache.get(file);
  if (!papers) {
    list.replaceChildren(el("li", { className: "loading", textContent: "Loading papers…" }));
    try {
      papers = await getJSON(DATA + file);
      state.shardCache.set(file, papers);
    } catch (err) {
      $("#result-meta").textContent = `Could not load papers (${err.message}).`;
      list.replaceChildren();
      return;
    }
  }

  state.filtered = papers.filter((p) => {
    if (topic && !p.topics.includes(topic)) return false;
    if (q) {
      const hay = (p.title + " " + p.abstract + " " + p.authors.join(" ")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  if ($("#f-sort").value === "citations") {
    state.filtered.sort((a, b) => (b.citations ?? -1) - (a.citations ?? -1));
  }
  state.shownCount = PAGE;
  paintPapers();
}

function paintPapers() {
  const list = $("#papers");
  const slice = state.filtered.slice(0, state.shownCount);
  list.replaceChildren(...slice.map(paperCard));
  const total = state.filtered.length;
  $("#result-meta").textContent = total
    ? `${total.toLocaleString()} paper${total === 1 ? "" : "s"} · showing ${slice.length}`
    : "No papers match these filters.";
  $("#more-wrap").hidden = state.shownCount >= total;
}

function paperCard(p) {
  const authors = p.authors.length
    ? p.authors.slice(0, 6).join(", ") + (p.authors.length > 6 ? ", et al." : "")
    : "";
  const titleNode = p.pdf
    ? el("a", { href: p.pdf, target: "_blank", rel: "noopener", textContent: p.title })
    : document.createTextNode(p.title);
  const venueText = Number.isFinite(p.citations)
    ? `${p.conference} ${p.year} · ${p.citations.toLocaleString()} cites`
    : `${p.conference} ${p.year}`;
  return el("li", { className: "paper" }, [
    el("div", { className: "paper__top" }, [
      el("h3", { className: "paper__title" }, [titleNode]),
      el("span", { className: "paper__venue", textContent: venueText }),
    ]),
    authors ? el("p", { className: "paper__authors", textContent: authors }) : null,
    p.abstract ? el("p", { className: "paper__abstract", textContent: p.abstract }) : null,
    el("div", { className: "tags" }, p.topics.map((t) =>
      el("button", {
        className: "tag", type: "button", textContent: t, title: `Filter by ${t}`,
        onclick: () => { ensureTopicOption(t); $("#f-topic").value = t; applyFilters(); },
      })
    )),
  ]);
}

/* ---------- util ---------- */
function debounce(fn, ms) {
  let id;
  return (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); };
}

init();
