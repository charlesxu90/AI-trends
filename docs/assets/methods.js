/* AI Trends — Method Tree / Application Tree pages. Vanilla JS, no deps.
   Renders one tree file (``<body data-tree>``: data/ontology.json by default,
   data/applications.json on the Application Tree page) as one hierarchy:
     domain -> task family -> task   (or theme -> area -> application)
   Each task lists its landmark methods grouped by year ("2015 — ResNet, …",
   linked to arXiv / the paper), plus a collapsible list of the top-cited
   matching papers from the tracked conferences, grouped by year. Below it:
   classification heuristics and tag facets. */

const DATA = "data/";
const TREE_FILE = document.body.dataset.tree || "ontology.json";
const ROOT_LABEL = document.body.dataset.root || "AI methods";
const TOP_UNIT = document.body.dataset.topUnit || "domains"; // what level-1 nodes are called
const LEAF_UNIT = document.body.dataset.leafUnit || "tasks"; // what end nodes are called
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
};

const state = { domains: [], methods: {}, facets: [], heuristics: [], selected: 0 };

const slug = (s) => s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const pad = (n) => String(n).padStart(2, "0");
const kids = (n) => n.children || [];
const leafCount = (n) => (kids(n).length ? kids(n).reduce((a, c) => a + leafCount(c), 0) : 1);
const domainSlug = (d) => slug(d.code || d.name);
const fmt = (n) => Number(n || 0).toLocaleString();
const scholar = (title) => `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;

/* ---------- bootstrap ---------- */
async function init() {
  initNavToggle();
  try {
    const res = await fetch(DATA + TREE_FILE);
    if (!res.ok) throw new Error(`fetch ${TREE_FILE}: ${res.status}`);
    const onto = await res.json();
    state.domains = onto.domains;
    state.methods = onto.methods || {};
    state.facets = onto.facets || [];
    state.heuristics = onto.heuristics || [];
  } catch (err) {
    $("#tree-view").replaceChildren(el("p", { className: "empty", textContent: `Could not load the method tree (${err.message}).` }));
    return;
  }
  state.selected = indexFromHash();
  renderView();
  if (location.hash) scrollToDomain();
  renderGuide();

  window.addEventListener("hashchange", () => {
    state.selected = indexFromHash();
    renderView();
    scrollToDomain();
  });
}

function indexFromHash() {
  const want = decodeURIComponent(location.hash.slice(1));
  const i = state.domains.findIndex((d) => domainSlug(d) === want);
  return i >= 0 ? i : 0;
}

function scrollToDomain() {
  const node = document.getElementById("d-" + domainSlug(state.domains[state.selected]));
  if (node) node.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- tree ---------- */
function renderView() {
  $("#tree-view").replaceChildren(
    el("div", { className: "otree" }, [
      el("div", { className: "otree__root" }, [
        el("h1", { className: "otree__root-name", textContent: ROOT_LABEL }),
        el("span", { className: "count", textContent: `${state.domains.length} ${TOP_UNIT} · ${state.domains.reduce((n, x) => n + leafCount(x), 0)} ${LEAF_UNIT}` }),
      ]),
      el("ul", { className: "tree__list tree__list--top" },
        state.domains.map((d, i) => domainNode(d, i, i === state.selected))),
    ])
  );
}

function countBadge(node, unit) {
  const parts = [];
  if (unit) parts.push(`${leafCount(node)} ${unit}`);
  if (node.paper_count != null) parts.push(`${fmt(node.paper_count)} papers`);
  return el("span", { className: "count", textContent: parts.join(" · ") });
}

function domainNode(d, i, open) {
  return el("li", { className: "node node--domain", id: "d-" + domainSlug(d) }, [
    el("details", { open }, [
      el("summary", { className: "node__sum node__sum--domain" }, [
        el("span", { className: "node__code", textContent: d.code ? `${pad(i + 1)} · ${d.code}` : pad(i + 1) }),
        el("span", { className: "node__name" }, d.name),
        countBadge(d, LEAF_UNIT),
      ]),
      d.summary ? el("p", { className: "node__summary", textContent: d.summary }) : null,
      el("ul", { className: "tree__list" }, kids(d).map((f) => familyNode(f, open))),
    ]),
  ]);
}

function familyNode(f, open) {
  return el("li", { className: "node node--family" }, [
    el("details", { open }, [
      el("summary", { className: "node__sum" }, [
        el("span", { className: "node__name" }, f.name),
        countBadge(f, LEAF_UNIT),
      ]),
      el("ul", { className: "tree__list" }, kids(f).map(taskNode)),
    ]),
  ]);
}

function taskNode(t) {
  return el("li", { className: "node node--task" }, [
    el("div", { className: "task" }, [
      el("div", { className: "task__head" }, [
        el("span", { className: "task__name" }, t.name),
        t.paper_count != null ? el("span", { className: "count", textContent: `${fmt(t.paper_count)} papers` }) : null,
      ]),
      landmarkRows(t.examples || []),
      corpusBlock(t, !(t.examples || []).length),
    ]),
  ]);
}

/* "2015 — ResNet, ViT" rows, oldest first: the task's historical arc. */
function landmarkRows(examples) {
  if (!examples.length) return null;
  const byYear = new Map();
  for (const name of examples) {
    const ref = state.methods[name];
    const year = ref ? ref.year : "—";
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year).push([name, ref]);
  }
  const years = [...byYear.keys()].sort((a, b) => (a === "—") - (b === "—") || a - b);
  return el("dl", { className: "years years--landmarks" }, years.flatMap((y) => [
    el("dt", { className: "years__y", textContent: y }),
    el("dd", { className: "years__items" }, joinNodes(byYear.get(y).map(([name, ref]) =>
      el("a", {
        className: "method",
        href: ref && ref.url ? ref.url : scholar(ref ? ref.title : name),
        target: "_blank", rel: "noopener",
        title: ref ? `${ref.title} (${ref.year})` : name,
      }, name)
    ))),
  ]));
}

/* Collapsible "top papers in tracked conferences", newest year first;
   open by default when the node has no landmark methods to show instead. */
function corpusBlock(t, open = false) {
  if (!t.papers || !t.papers.length) return null;
  return el("details", { className: "corpus", open }, [
    el("summary", { className: "corpus__sum", textContent: `Top papers in tracked conferences (${fmt(t.paper_count)})` }),
    el("dl", { className: "years" }, t.papers.flatMap((g) => [
      el("dt", { className: "years__y", textContent: g.year }),
      el("dd", { className: "years__items" }, joinNodes(g.papers.map((p) =>
        el("span", { className: "paper-ref" }, [
          el("a", { href: p.url, target: "_blank", rel: "noopener", title: p.title, textContent: clip(p.name, 64) }),
          el("span", { className: "paper-ref__meta", textContent: ` ${p.conference}${p.citations != null ? ` · ${fmt(p.citations)} cites` : ""}` }),
        ])
      ))),
    ])),
    t.keywords && t.keywords.length
      ? el("p", { className: "corpus__kw", textContent: `Matched on: ${t.keywords.map((k) => k.replace(/^\^/, "title: ")).join(", ")}` })
      : null,
  ]);
}

const clip = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

function joinNodes(nodes) {
  return nodes.flatMap((n, i) => (i ? [", ", n] : [n]));
}

/* ---------- classification guide ---------- */
function renderGuide() {
  if (!$("#guide")) return; // only the Method Tree page has a guide section
  $("#guide-heuristics").replaceChildren(
    ...state.heuristics.map((h) => el("li", { textContent: h }))
  );
  $("#guide-facets").replaceChildren(
    ...state.facets.map((f) =>
      el("div", { className: "facet" }, [
        el("h3", { className: "facet__name", textContent: f.name }),
        el("p", { className: "facet__tags" }, f.tags.map((t) => el("span", { className: "tag-chip", textContent: t }))),
      ])
    )
  );
  $("#guide").hidden = !state.heuristics.length && !state.facets.length;
}

/* ---------- header menu (same behaviour as the main page) ---------- */
function initNavToggle() {
  const inner = $(".site-head__inner");
  const btn = $(".nav-toggle");
  const nav = $("#site-nav");
  if (!inner || !btn || !nav) return;
  const setOpen = (open) => {
    inner.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
  };
  btn.addEventListener("click", () => setOpen(btn.getAttribute("aria-expanded") !== "true"));
  nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setOpen(false)));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
}

init();
