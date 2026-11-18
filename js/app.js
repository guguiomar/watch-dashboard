const fmtEur = (n) =>
  n == null ? "—" : `${Math.round(n).toLocaleString("pt-PT")} €`;
const fmtPct = (n) => {
  if (n == null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1).replace(".", ",")} %`;
};
const fmtNum = (n) => (n == null ? "—" : n.toLocaleString("pt-PT"));

const kindLabel = {
  abaixo: "Abaixo do retalho",
  perto: "Perto do retalho",
  premio: "Prémio grande",
};

let DATA = null;
let INDICES = null;
let brand = "all";
let gender = "all";
let sort = "premium";
const charts = {};

async function boot() {
  const [watchesRes, indicesRes] = await Promise.all([
    fetch("data/watches.json"),
    fetch("data/indices.json"),
  ]);
  DATA = await watchesRes.json();
  INDICES = await indicesRes.json();
  document.getElementById("updated").textContent = formatDate(DATA.updated);
  document.getElementById("count-total").textContent = String(DATA.watches.length);
  bindFilters();
  renderSnapshots();
  renderYearlyChart();
  refresh();
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("pt-PT", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function bindFilters() {
  document.querySelectorAll("[data-filter]").forEach((group) => {
    group.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button");
      if (!btn) return;
      const key = group.dataset.filter;
      if (key === "brand") brand = btn.dataset.value;
      if (key === "gender") gender = btn.dataset.value;
      if (key === "sort") sort = btn.dataset.value;
      group.querySelectorAll("button").forEach((b) =>
        b.setAttribute("aria-pressed", String(b === btn))
      );
      refresh();
    });
  });
}

function filtered() {
  let list = DATA.watches.filter((w) => {
    if (brand !== "all" && w.brand !== brand) return false;
    if (gender !== "all" && w.gender !== gender) return false;
    return true;
  });
  list = list.slice().sort((a, b) => {
    if (sort === "demand") return (b.volume_1y || -1) - (a.volume_1y || -1);
    if (sort === "market") {
      const av = a.market_eur == null ? Infinity : a.market_eur;
      const bv = b.market_eur == null ? Infinity : b.market_eur;
      return av - bv;
    }
    const pa = a.premium_vs_pt;
    const pb = b.premium_vs_pt;
    if (pa == null && pb == null) return 0;
    if (pa == null) return 1;
    if (pb == null) return -1;
    return sort === "discount" ? pa - pb : pb - pa;
  });
  return list;
}

function nameMap(list) {
  const m = new Map(list.map((w) => [w.ref, longName(w)]));
  return (ref) => m.get(ref) || ref;
}

function refresh() {
  const list = filtered();
  renderCards(list);
  renderPremiumChart(list);
  renderCostChart(list);
  renderDemandCharts(list);
}

function renderSnapshots() {
  const host = document.getElementById("snapshots");
  const snaps = INDICES.charts.filter((c) => c.type === "snapshot");
  host.innerHTML = snaps
    .map((s) => {
      const chg = Object.entries(s.changes || {})
        .map(([k, v]) => {
          const label = { "1m": "1 mês", "1y": "1 ano", "5y": "5 anos", q3_2026: "3.º trim. 2026", "12m": "12 meses" }[k] || k;
          const cls = v > 0 ? "up" : v < 0 ? "down" : "";
          return `<span class="${cls}">${label} ${fmtPct(v)}</span>`;
        })
        .join("");
      return `<article class="snap">
        <div class="label">${s.title}</div>
        <div class="value">${s.value.toLocaleString("pt-PT")}${s.unit === "USD" ? " USD" : ""}</div>
        <div class="chg">${chg}</div>
        <p class="source">${s.source}. ${s.note}</p>
      </article>`;
    })
    .join("");
}

function renderYearlyChart() {
  const series = INDICES.charts.find((c) => c.id === "wc-yearly");
  const ctx = document.getElementById("chart-yearly");
  const caption = document.getElementById("chart-yearly-source");
  caption.innerHTML = `${series.note} Fonte: <a href="${series.source_url}">${series.source}</a>.`;
  charts.yearly = new Chart(ctx, {
    type: "bar",
    data: {
      labels: series.labels,
      datasets: [{
        label: "Variação anual",
        data: series.values,
        backgroundColor: series.values.map((v) => (v >= 0 ? "#215744" : "#8b2c2c")),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => fmtPct(c.parsed.y) } },
      },
      scales: {
        y: {
          ticks: { callback: (v) => `${v}%` },
          grid: { color: "#e6dfd3" },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

function destroy(name) {
  if (charts[name]) {
    charts[name].destroy();
    charts[name] = null;
  }
}

function isMobile() {
  return window.innerWidth < 700;
}

function shortName(w) {
  return w.ref;
}
function longName(w) {
  return `${w.brand} ${w.name} · ${w.ref}`;
}

function sizeWrap(canvas, n, rowPx = 28) {
  const wrap = canvas.parentElement;
  wrap.style.height = `${Math.max(260, n * rowPx + 48)}px`;
}

function renderPremiumChart(list) {
  destroy("premium");
  const rows = list.filter((w) => w.premium_vs_pt != null).sort((a, b) => a.premium_vs_pt - b.premium_vs_pt);
  const empty = document.getElementById("chart-premium-empty");
  const canvas = document.getElementById("chart-premium");
  if (!rows.length) {
    empty.hidden = false;
    canvas.style.display = "none";
    return;
  }
  empty.hidden = true;
  canvas.style.display = "block";
  sizeWrap(canvas, rows.length, 30);
  charts.premium = new Chart(canvas, {
    type: "bar",
    data: {
      labels: rows.map(shortName),
      datasets: [{
        label: "Prémio vs retalho PT",
        data: rows.map((w) => w.premium_vs_pt),
        backgroundColor: rows.map((w) => (w.premium_vs_pt > 20 ? "#8b2c2c" : w.premium_vs_pt > 0 ? "#a07d45" : "#215744")),
        borderRadius: 5,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: (items) => longName(rows.find((w) => w.ref === items[0].label) || {brand:"",name:items[0].label,ref:""}), label: (c) => fmtPct(c.parsed.x) } },
      },
      scales: {
        x: { ticks: { callback: (v) => `${v}%` }, grid: { color: "#e6dfd3" } },
        y: { afterFit: (ax) => { ax.width = isMobile() ? 96 : 120; }, ticks: { font: { size: 11 }, autoSkip: false }, grid: { display: false } },
      },
    },
  });
}

function renderCostChart(list) {
  destroy("cost");
  const rows = list.filter((w) => w.market_eur != null);
  const empty = document.getElementById("chart-cost-empty");
  const canvas = document.getElementById("chart-cost");
  if (!rows.length) {
    empty.hidden = false;
    canvas.style.display = "none";
    return;
  }
  empty.hidden = true;
  canvas.style.display = "block";
  sizeWrap(canvas, rows.length, 36);
  charts.cost = new Chart(canvas, {
    type: "bar",
    data: {
      labels: rows.map(shortName),
      datasets: [
        { label: "Retalho PT", data: rows.map((w) => w.retail_pt), backgroundColor: "#1b1814" },
        { label: "Mercado WC", data: rows.map((w) => w.market_eur), backgroundColor: "#a07d45" },
        { label: "Dealer WC", data: rows.map((w) => w.dealer_eur), backgroundColor: "#215744" },
        { label: "Desembarcado PT", data: rows.map((w) => w.landed_eur), backgroundColor: "#6b2d28" },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmtEur(c.parsed.x)}` } },
      },
      scales: {
        x: { ticks: { callback: (v) => `${Math.round(v / 1000)} mil €` }, grid: { color: "#e6dfd3" } },
        y: { afterFit: (ax) => { ax.width = isMobile() ? 96 : 120; }, ticks: { font: { size: 10 }, autoSkip: false }, grid: { display: false } },
      },
    },
  });
}

function renderDemandCharts(list) {
  destroy("volume");
  destroy("days");
  const rows = list.filter((w) => w.volume_1y != null).sort((a, b) => b.volume_1y - a.volume_1y);
  const empty = document.getElementById("chart-demand-empty");
  const vol = document.getElementById("chart-volume");
  const days = document.getElementById("chart-days");
  if (!rows.length) {
    empty.hidden = false;
    vol.style.display = "none";
    days.style.display = "none";
    return;
  }
  empty.hidden = true;
  vol.style.display = "block";
  days.style.display = "block";
  sizeWrap(vol, rows.length, 28);
  sizeWrap(days, rows.length, 28);
  const labels = rows.map(shortName);
  charts.volume = new Chart(vol, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Vendas a 1 ano", data: rows.map((w) => w.volume_1y), backgroundColor: "#6b2d28", borderRadius: 5 }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${fmtNum(c.parsed.x)} vendas` } } },
      scales: { x: { grid: { color: "#e6dfd3" } }, y: { afterFit: (ax) => { ax.width = isMobile() ? 96 : 120; }, ticks: { font: { size: 10 }, autoSkip: false }, grid: { display: false } } },
    },
  });
  charts.days = new Chart(days, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Dias medianos no mercado", data: rows.map((w) => w.days), backgroundColor: "#a07d45", borderRadius: 5 }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${String(c.parsed.x).replace(".", ",")} dias` } } },
      scales: { x: { grid: { color: "#e6dfd3" } }, y: { afterFit: (ax) => { ax.width = isMobile() ? 96 : 120; }, ticks: { font: { size: 10 }, autoSkip: false }, grid: { display: false } } },
    },
  });
}

function svgFor(w) {
  const palettes = {
    Rolex: { metal: "#8a7a55", face: "#f3efe4", mark: "#1b1814" },
    Omega: { metal: "#8d9094", face: "#eceff3", mark: "#22262b" },
    Cartier: { metal: "#b9b3a8", face: "#f6f3ec", mark: "#3a2a22" },
    Panerai: { metal: "#7a7d80", face: "#e8e2d3", mark: "#2a2723" },
  };
  const p = palettes[w.brand] || palettes.Omega;
  const monogram = w.brand[0];
  if (w.ref.startsWith("WSTA") || w.name.includes("Tank")) {
    return tankSvg(p, monogram);
  }
  if (w.ref.startsWith("WSSA") || w.name.includes("Santos")) {
    return santosSvg(p, monogram);
  }
  if (w.ref.startsWith("WSPN") || w.name.includes("Panthère")) {
    return panthereSvg(p, monogram);
  }
  if (w.brand === "Panerai") return cushionSvg(p, monogram);
  return roundSvg(p, monogram, w.brand === "Rolex");
}

function roundSvg(p, letter, fluted) {
  const ticks = Array.from({ length: 12 }, (_, i) => {
    const a = ((i * 30 - 90) * Math.PI) / 180;
    const r1 = fluted ? 34 : 35;
    const r2 = 40;
    return `<line x1="${50 + r1 * Math.cos(a)}" y1="${50 + r1 * Math.sin(a)}" x2="${50 + r2 * Math.cos(a)}" y2="${50 + r2 * Math.sin(a)}" stroke="${p.mark}" stroke-width="${i % 3 === 0 ? 2.2 : 1}"/>`;
  }).join("");
  const flute = fluted
    ? Array.from({ length: 24 }, (_, i) => {
        const a = ((i * 15 - 90) * Math.PI) / 180;
        return `<circle cx="${50 + 46.5 * Math.cos(a)}" cy="${50 + 46.5 * Math.sin(a)}" r="1.4" fill="${p.metal}"/>`;
      }).join("")
    : "";
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
    <circle cx="50" cy="50" r="48" fill="${p.metal}"/>
    ${flute}
    <circle cx="50" cy="50" r="41" fill="${p.face}" stroke="${p.mark}" stroke-width="0.6"/>
    ${ticks}
    <text x="50" y="33" text-anchor="middle" font-family="Georgia, serif" font-size="9" fill="${p.mark}">${letter}</text>
    <line x1="50" y1="50" x2="50" y2="24" stroke="${p.mark}" stroke-width="2.2" stroke-linecap="round"/>
    <line x1="50" y1="50" x2="70" y2="50" stroke="${p.mark}" stroke-width="1.7" stroke-linecap="round"/>
    <circle cx="50" cy="50" r="2.1" fill="${p.mark}"/>
  </svg>`;
}

function santosSvg(p, letter) {
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
    <rect x="18" y="18" width="64" height="64" rx="6" fill="${p.metal}"/>
    <rect x="24" y="24" width="52" height="52" rx="3" fill="${p.face}" stroke="${p.mark}" stroke-width="0.6"/>
    <circle cx="22" cy="22" r="2.4" fill="${p.face}" stroke="${p.mark}" stroke-width="0.8"/>
    <circle cx="78" cy="22" r="2.4" fill="${p.face}" stroke="${p.mark}" stroke-width="0.8"/>
    <circle cx="22" cy="78" r="2.4" fill="${p.face}" stroke="${p.mark}" stroke-width="0.8"/>
    <circle cx="78" cy="78" r="2.4" fill="${p.face}" stroke="${p.mark}" stroke-width="0.8"/>
    <text x="50" y="40" text-anchor="middle" font-family="Georgia, serif" font-size="8" fill="${p.mark}">${letter}</text>
    <line x1="50" y1="50" x2="50" y2="32" stroke="${p.mark}" stroke-width="2" stroke-linecap="round"/>
    <line x1="50" y1="50" x2="66" y2="50" stroke="${p.mark}" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="50" cy="50" r="1.8" fill="${p.mark}"/>
  </svg>`;
}

function tankSvg(p, letter) {
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
    <rect x="28" y="16" width="44" height="68" rx="2" fill="${p.metal}"/>
    <rect x="32" y="22" width="36" height="56" fill="${p.face}"/>
    <rect x="32" y="22" width="3" height="56" fill="${p.metal}"/>
    <rect x="65" y="22" width="3" height="56" fill="${p.metal}"/>
    <text x="50" y="40" text-anchor="middle" font-family="Georgia, serif" font-size="8" fill="${p.mark}">${letter}</text>
    <line x1="50" y1="50" x2="50" y2="30" stroke="${p.mark}" stroke-width="1.8" stroke-linecap="round"/>
    <line x1="50" y1="50" x2="62" y2="50" stroke="${p.mark}" stroke-width="1.4" stroke-linecap="round"/>
    <circle cx="50" cy="50" r="1.5" fill="${p.mark}"/>
  </svg>`;
}

function panthereSvg(p, letter) {
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
    <rect x="24" y="22" width="52" height="56" rx="14" fill="${p.metal}"/>
    <rect x="29" y="27" width="42" height="46" rx="10" fill="${p.face}"/>
    <text x="50" y="42" text-anchor="middle" font-family="Georgia, serif" font-size="8" fill="${p.mark}">${letter}</text>
    <line x1="50" y1="50" x2="50" y2="34" stroke="${p.mark}" stroke-width="1.8" stroke-linecap="round"/>
    <line x1="50" y1="50" x2="64" y2="50" stroke="${p.mark}" stroke-width="1.4" stroke-linecap="round"/>
    <circle cx="50" cy="50" r="1.6" fill="${p.mark}"/>
  </svg>`;
}

function cushionSvg(p, letter) {
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true">
    <rect x="14" y="14" width="72" height="72" rx="22" fill="${p.metal}"/>
    <rect x="22" y="22" width="56" height="56" rx="16" fill="${p.face}" stroke="${p.mark}" stroke-width="1"/>
    <rect x="78" y="42" width="10" height="16" rx="2" fill="${p.metal}"/>
    <text x="50" y="40" text-anchor="middle" font-family="Georgia, serif" font-size="9" fill="${p.mark}">${letter}</text>
    <line x1="50" y1="50" x2="50" y2="30" stroke="${p.mark}" stroke-width="2.2" stroke-linecap="round"/>
    <line x1="50" y1="50" x2="68" y2="50" stroke="${p.mark}" stroke-width="1.7" stroke-linecap="round"/>
    <circle cx="50" cy="50" r="2" fill="${p.mark}"/>
  </svg>`;
}

function renderCards(list) {
  const host = document.getElementById("cards");
  if (!list.length) {
    host.innerHTML = `<p class="empty">Nenhum modelo neste filtro.</p>`;
    return;
  }
  host.innerHTML = list
    .map((w) => {
      const demand =
        w.volume_1y == null
          ? "—"
          : `${fmtNum(w.volume_1y)} / ${String(w.days).replace(".", ",")} d`;
      return `<article class="card">
        <div class="card-top">
          ${svgFor(w)}
          <div class="card-id">
            <p class="brand">${w.brand}</p>
            <h3>${w.name}</h3>
            <div class="tags">
              <span class="tag">${w.ref}</span>
              <span class="tag">${w.gender === "mulher" ? "Mulher" : "Homem"}</span>
            </div>
          </div>
        </div>
        <dl class="nums">
          <div><dt>Retalho PT</dt><dd>${fmtEur(w.retail_pt)}</dd></div>
          <div><dt>Mercado WC</dt><dd>${fmtEur(w.market_eur)}</dd></div>
          <div><dt>Prémio vs PT</dt><dd>${fmtPct(w.premium_vs_pt)}</dd></div>
          <div><dt>Retenção WC</dt><dd>${fmtPct(w.wc_retention)}</dd></div>
          <div><dt>Dealer WC</dt><dd>${fmtEur(w.dealer_eur)}</dd></div>
          <div><dt>Desembarcado</dt><dd>${fmtEur(w.landed_eur)}</dd></div>
          <div><dt>Procura (1 ano / dias)</dt><dd>${demand}</dd></div>
          <div><dt>Tendência 1 ano</dt><dd>—</dd></div>
        </dl>
        <div class="leitura ${w.leitura_kind}">
          <strong>${kindLabel[w.leitura_kind]}</strong>
          ${w.leitura}
          ${w.wc_caveat ? `<div style="margin-top:8px;opacity:.85">${w.wc_caveat}</div>` : ""}
        </div>
        <div class="card-links">
          ${w.official_url ? `<a href="${w.official_url}" rel="noopener">Página oficial / retalhista</a>` : ""}
          ${w.wc_url ? `<a href="${w.wc_url}" rel="noopener">WatchCharts</a>` : ""}
        </div>
      </article>`;
    })
    .join("");
}

boot().catch((err) => {
  document.getElementById("cards").innerHTML =
    `<p class="empty">Não foi possível carregar os dados. ${err.message}</p>`;
});
