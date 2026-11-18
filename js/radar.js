/* G Watch Radar — Edição 01 */
(function () {
  "use strict";

  const EUR = new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
  const NUM = new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 0 });
  const NUM1 = new Intl.NumberFormat("pt-PT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  const INK = "#1B1814";
  const GOLD = "#C89612";
  const NAVY = "#1E2A36";
  const MUTED = "#6E675D";
  const PAPER2 = "#E8E1D4";
  const UP = "#A63C24";
  const DOWN = "#3E5A46";

  function money(n) {
    return n == null ? "—" : EUR.format(n);
  }
  function pct(n) {
    if (n == null) return "—";
    const sign = n > 0 ? "+" : "";
    return sign + NUM1.format(n) + " %";
  }
  function signalClass(s) {
    if (s === "abaixo do retalho") return "abaixo";
    if (s === "prémio") return "premio";
    return "perto";
  }
  function shortSeller(name) {
    return (name || "").replace(/\s*\/\s*.+$/, "").trim();
  }
  function isSearch(o) {
    const t = ((o.condition || "") + " " + (o.note || "")).toLowerCase();
    return (
      /chrono24/i.test(o.seller) ||
      t.includes("pesquisa") ||
      o.price_eur == null && t.includes("catálogo")
    );
  }
  function rankedOffers(offers) {
    const copy = (offers || []).slice();
    copy.sort((a, b) => {
      const ap = a.price_eur != null ? 0 : isSearch(a) ? 2 : 1;
      const bp = b.price_eur != null ? 0 : isSearch(b) ? 2 : 1;
      if (ap !== bp) return ap - bp;
      if (a.price_eur != null && b.price_eur != null) return a.price_eur - b.price_eur;
      return 0;
    });
    return copy;
  }

  /* —— Typographic SVG watches (no logos, no photos) —— */
  function illustrate(w) {
    const ref = w.ref;
    const brand = w.brand;
    if (brand === "Cartier") {
      if (/WSTA/.test(ref)) return svgTank();
      if (/WSPN/.test(ref)) return svgPanthere();
      if (/WSBB/.test(ref)) return svgBallon();
      return svgSantos();
    }
    if (brand === "Panerai") return svgPanerai(ref);
    if (/126710BLRO/.test(ref)) return svgRound({ bezel: "pepsi", lume: true });
    if (/126500LN/.test(ref)) return svgChrono({ dial: "#F7F1E6", bezel: INK, tachy: true });
    if (/126610/.test(ref)) return svgRound({ bezel: INK, lume: true, pip: true });
    if (/279174|278274|126334/.test(ref)) return svgDatejust();
    if (/310\.30/.test(ref)) return svgChrono({ dial: "#1B1814", bezel: INK, tachy: true, light: true });
    if (/210\.30/.test(ref)) return svgRound({ bezel: "#2A3A44", wave: true, lume: true });
    if (/220\.10/.test(ref)) return svgAquaTerra();
    if (/131\.10/.test(ref)) return svgConstellation();
    return svgRound({ bezel: INK });
  }

  function svgWrap(inner, vb) {
    return `<svg viewBox="${vb || "0 0 120 148"}" aria-hidden="true">${inner}</svg>`;
  }

  function hands(cx, cy, r, color, hour, min) {
    const aH = (hour / 12) * Math.PI * 2 - Math.PI / 2;
    const aM = (min / 60) * Math.PI * 2 - Math.PI / 2;
    const hx = cx + Math.cos(aH) * r * 0.48;
    const hy = cy + Math.sin(aH) * r * 0.48;
    const mx = cx + Math.cos(aM) * r * 0.68;
    const my = cy + Math.sin(aM) * r * 0.68;
    return `<line x1="${cx}" y1="${cy}" x2="${hx}" y2="${hy}" stroke="${color}" stroke-width="2.2" stroke-linecap="round"/>
      <line x1="${cx}" y1="${cy}" x2="${mx}" y2="${my}" stroke="${color}" stroke-width="1.4" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="2" fill="${color}"/>`;
  }

  function minutePips(cx, cy, r, color, n) {
    let s = "";
    for (let i = 0; i < (n || 60); i++) {
      if (n === 12 && i % 1 === 0) {
        const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
        const x1 = cx + Math.cos(a) * (r - 4);
        const y1 = cy + Math.sin(a) * (r - 4);
        const x2 = cx + Math.cos(a) * (r - 1);
        const y2 = cy + Math.sin(a) * (r - 1);
        s += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${i % 3 === 0 ? 1.6 : 0.8}"/>`;
      }
    }
    return s;
  }

  function hourMarks(cx, cy, r, color) {
    let s = "";
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const long = i % 3 === 0;
      const x1 = cx + Math.cos(a) * (r - (long ? 7 : 5));
      const y1 = cy + Math.sin(a) * (r - (long ? 7 : 5));
      const x2 = cx + Math.cos(a) * (r - 1.5);
      const y2 = cy + Math.sin(a) * (r - 1.5);
      s += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${long ? 1.8 : 1}"/>`;
    }
    return s;
  }

  function svgRound(opt) {
    const cx = 60, cy = 74, r = 42;
    let bezel = "";
    if (opt.bezel === "pepsi") {
      bezel = `<path d="M60 32 A42 42 0 0 1 60 116 L60 74 Z" fill="#8B1E1E"/>
        <path d="M60 32 A42 42 0 0 0 60 116 L60 74 Z" fill="#1E3A5F"/>
        <circle cx="60" cy="74" r="32" fill="#1B1814"/>`;
    } else {
      bezel = `<circle cx="${cx}" cy="${cy}" r="42" fill="${opt.bezel || INK}"/>
        <circle cx="${cx}" cy="${cy}" r="32" fill="${opt.wave ? "#0E2A36" : "#1B1814"}"/>
        ${opt.wave ? `<polygon points="60,36 63,42 57,42" fill="#F3EEE4"/>` : ""}`;
    }
    let wave = "";
    if (opt.wave) {
      wave = `<path d="M30 74 Q45 68 60 74 T90 74" fill="none" stroke="#9BB8C4" stroke-width=".7" opacity=".7"/>
        <path d="M30 80 Q45 74 60 80 T90 80" fill="none" stroke="#9BB8C4" stroke-width=".7" opacity=".5"/>
        <path d="M30 68 Q45 62 60 68 T90 68" fill="none" stroke="#9BB8C4" stroke-width=".7" opacity=".5"/>`;
    }
    const pips = opt.pip
      ? `<g fill="#F3EEE4">${[0,30,60,90,120,150,180,210,240,270,300,330].map((d,i)=>{
          const a = (d * Math.PI) / 180;
          const x = cx + Math.cos(a) * 37;
          const y = cy + Math.sin(a) * 37;
          return i % 3 === 0
            ? `<rect x="${x-1.2}" y="${y-2.2}" width="2.4" height="4.4" transform="rotate(${d} ${x} ${y})" fill="#F3EEE4"/>`
            : `<circle cx="${x}" cy="${y}" r="1.3"/>`;
        }).join("")}</g>`
      : "";
    const lume = opt.lume
      ? `<rect x="58.2" y="48" width="3.6" height="14" rx="1" fill="#E8D48A"/>
         <rect x="72" y="72.2" width="14" height="3.6" rx="1" fill="#E8D48A"/>`
      : hourMarks(cx, cy, 30, "#F3EEE4");
    const date = opt.lume
      ? `<rect x="82" y="69" width="10" height="10" fill="#F3EEE4"/><text x="87" y="77" text-anchor="middle" font-size="7" font-family="Newsreader, Georgia, serif" fill="${INK}">18</text>`
      : "";
    return svgWrap(`
      <rect x="58" y="20" width="4" height="10" fill="${INK}"/>
      <rect x="100" y="70" width="10" height="8" rx="1" fill="${INK}"/>
      ${bezel}${pips}${wave}${lume}${date}
      ${hands(cx, cy, 28, "#F3EEE4", 10, 8)}
      <circle cx="${cx}" cy="${cy}" r="42.6" fill="none" stroke="${INK}" stroke-width="1"/>
    `);
  }

  function svgChrono(opt) {
    const dial = opt.dial;
    const light = !!opt.light;
    const fg = light ? "#F3EEE4" : INK;
    const cx = 60, cy = 74;
    const subs = [
      [60, 56],
      [44, 80],
      [76, 80],
    ];
    return svgWrap(`
      <rect x="58" y="18" width="4" height="10" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="44" fill="${opt.bezel}" />
      <circle cx="${cx}" cy="${cy}" r="34" fill="${dial}"/>
      ${opt.tachy ? `<circle cx="${cx}" cy="${cy}" r="40" fill="none" stroke="${light ? "#F3EEE4" : GOLD}" stroke-width=".6" stroke-dasharray="1.5 2.2"/>` : ""}
      ${subs.map(([x,y]) => `<circle cx="${x}" cy="${y}" r="8.5" fill="none" stroke="${fg}" stroke-width=".8"/>
        <line x1="${x}" y1="${y-6}" x2="${x}" y2="${y-2}" stroke="${fg}" stroke-width=".6"/>`).join("")}
      ${hands(cx, cy, 30, fg, 10, 12)}
      <circle cx="${cx}" cy="${cy}" r="44.5" fill="none" stroke="${INK}" stroke-width="1"/>
    `);
  }

  function svgDatejust() {
    const cx = 60, cy = 74, r = 42;
    let flute = "";
    for (let i = 0; i < 36; i++) {
      const a1 = (i / 36) * Math.PI * 2;
      const a2 = ((i + 0.5) / 36) * Math.PI * 2;
      const x1 = cx + Math.cos(a1) * r;
      const y1 = cy + Math.sin(a1) * r;
      const x2 = cx + Math.cos(a2) * (r + 3.5);
      const y2 = cy + Math.sin(a2) * (r + 3.5);
      const a3 = ((i + 1) / 36) * Math.PI * 2;
      const x3 = cx + Math.cos(a3) * r;
      const y3 = cy + Math.sin(a3) * r;
      flute += `<path d="M${x1} ${y1} L${x2} ${y2} L${x3} ${y3}" fill="${i % 2 ? GOLD : "#8A7A3A"}"/>`;
    }
    return svgWrap(`
      <rect x="58" y="20" width="4" height="8" fill="${INK}"/>
      <rect x="102" y="70" width="10" height="8" rx="1" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="42" fill="${INK}"/>
      ${flute}
      <circle cx="${cx}" cy="${cy}" r="34" fill="#F7F1E6"/>
      ${hourMarks(cx, cy, 32, INK)}
      <rect x="84" y="69" width="10" height="10" fill="#F7F1E6" stroke="${INK}" stroke-width=".6"/>
      <circle cx="89" y="64" r="5.5" fill="none" stroke="${INK}" stroke-width=".7"/>
      ${hands(cx, cy, 28, INK, 2, 42)}
    `);
  }

  function svgAquaTerra() {
    const cx = 60, cy = 74;
    let teak = "";
    for (let i = 0; i < 9; i++) {
      const y = 50 + i * 5.4;
      teak += `<line x1="34" y1="${y}" x2="86" y2="${y}" stroke="#1B1814" stroke-width=".4" opacity=".25"/>`;
    }
    return svgWrap(`
      <rect x="58" y="20" width="4" height="10" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="42" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="34" fill="#F4EFE4"/>
      ${teak}
      ${hourMarks(cx, cy, 32, INK)}
      ${hands(cx, cy, 28, INK, 9, 14)}
    `);
  }

  function svgConstellation() {
    const cx = 60, cy = 74;
    const claws = [200, 230, 310, 340].map((d) => {
      const a = (d * Math.PI) / 180;
      const x = cx + Math.cos(a) * 44;
      const y = cy + Math.sin(a) * 44;
      return `<rect x="${x-2}" y="${y-5}" width="4" height="10" transform="rotate(${d+90} ${x} ${y})" fill="${INK}"/>`;
    }).join("");
    return svgWrap(`
      <rect x="58" y="22" width="4" height="8" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="40" fill="${INK}"/>
      <circle cx="${cx}" cy="${cy}" r="32" fill="#F7F1E6"/>
      ${claws}
      <polygon points="60,60 62.2,67 70,67.2 63.8,71.6 66.2,79 60,74.8 53.8,79 56.2,71.6 50,67.2 57.8,67" fill="${GOLD}"/>
      ${hands(cx, cy, 26, INK, 3, 20)}
    `);
  }

  function svgSantos() {
    return svgWrap(`
      <rect x="30" y="36" width="60" height="76" rx="10" fill="${INK}"/>
      <rect x="36" y="44" width="48" height="60" rx="6" fill="#F7F1E6"/>
      ${[[36,44],[78,44],[36,98],[78,98],[36,71],[84,71],[57,44],[57,104]].map(([x,y],i)=>
        `<circle cx="${i===4?36:i===5?84:x}" cy="${y}" r="2.1" fill="${GOLD}"/>`
      ).join("")}
      <line x1="60" y1="52" x2="60" y2="58" stroke="${INK}" stroke-width="1.4"/>
      <line x1="60" y1="90" x2="60" y2="96" stroke="${INK}" stroke-width="1.4"/>
      <line x1="44" y1="74" x2="50" y2="74" stroke="${INK}" stroke-width="1.4"/>
      <line x1="70" y1="74" x2="76" y2="74" stroke="${INK}" stroke-width="1.4"/>
      ${hands(60, 74, 22, INK, 10, 8)}
      <rect x="90" y="70" width="8" height="8" fill="${INK}"/>
    `);
  }

  function svgTank() {
    return svgWrap(`
      <rect x="38" y="30" width="44" height="88" fill="${INK}"/>
      <rect x="34" y="38" width="8" height="72" fill="${INK}"/>
      <rect x="78" y="38" width="8" height="72" fill="${INK}"/>
      <rect x="44" y="40" width="32" height="68" fill="#F7F1E6"/>
      <line x1="60" y1="46" x2="60" y2="52" stroke="${INK}" stroke-width="1.2"/>
      <line x1="60" y1="96" x2="60" y2="102" stroke="${INK}" stroke-width="1.2"/>
      ${hands(60, 74, 20, INK, 1, 18)}
    `);
  }

  function svgPanthere() {
    return svgWrap(`
      <rect x="34" y="42" width="52" height="64" rx="14" fill="${INK}"/>
      <rect x="40" y="48" width="40" height="52" rx="10" fill="#F7F1E6"/>
      ${[12,3,6,9].map((h) => {
        const a = (h / 12) * Math.PI * 2 - Math.PI / 2;
        const x = 60 + Math.cos(a) * 18;
        const y = 74 + Math.sin(a) * 18;
        return `<text x="${x}" y="${y+3}" text-anchor="middle" font-size="7" font-family="Newsreader, Georgia, serif" fill="${INK}">${h===0?12:h}</text>`;
      }).join("")}
      ${hands(60, 74, 16, INK, 10, 50)}
    `);
  }

  function svgBallon() {
    return svgWrap(`
      <rect x="58" y="24" width="4" height="8" fill="${INK}"/>
      <circle cx="60" cy="76" r="40" fill="${INK}"/>
      <circle cx="60" cy="76" r="33" fill="#F7F1E6"/>
      ${[12,1,2,3,4,5,6,7,8,9,10,11].map((h) => {
        const a = (h / 12) * Math.PI * 2 - Math.PI / 2;
        const x = 60 + Math.cos(a) * 24;
        const y = 76 + Math.sin(a) * 24;
        return `<text x="${x}" y="${y+3}" text-anchor="middle" font-size="7" font-family="Newsreader, Georgia, serif" fill="${INK}">${h}</text>`;
      }).join("")}
      ${hands(60, 76, 20, "#2A4A8A", 2, 12)}
    `);
  }

  function svgPanerai(ref) {
    const due = /01123/.test(ref);
    const fg = due ? INK : "#F3EEE4";
    const dial = due ? "#F4EFE4" : "#1B1814";
    return svgWrap(`
      <rect x="28" y="34" width="62" height="80" rx="22" fill="${INK}"/>
      <rect x="33" y="39" width="52" height="70" rx="18" fill="${dial}"/>
      <rect x="90" y="66" width="12" height="16" rx="1" fill="${INK}"/>
      <rect x="88" y="62" width="4" height="24" rx="1" fill="${INK}"/>
      <text x="59" y="58" text-anchor="middle" font-size="10" font-family="Newsreader, Georgia, serif" fill="${fg}">12</text>
      <text x="46" y="80" text-anchor="middle" font-size="10" font-family="Newsreader, Georgia, serif" fill="${fg}">9</text>
      <text x="59" y="100" text-anchor="middle" font-size="10" font-family="Newsreader, Georgia, serif" fill="${fg}">6</text>
      ${hands(59, 74, 22, fg, 10, 8)}
    `);
  }

  /* —— Cards & drawer —— */
  let DATA = null;
  let INDEX = null;
  let PHOTOS = {};
  let CREDITS = [];
  let charts = [];

  function photoPath(ref) {
    return "img/" + encodeURIComponent(ref) + ".webp";
  }

  function portrait(w) {
    if (PHOTOS[w.ref]) {
      return `<img src="${photoPath(w.ref)}" alt="${escapeHtml(w.brand + " " + w.model)}" width="800" height="800" loading="eager" decoding="async">`;
    }
    return illustrate(w);
  }

  function offerButtons(w, limit) {
    const all = rankedOffers(w.offers);
    const direct = all.filter((o) => !isSearch(o) && !/chrono24/i.test(o.seller));
    let shown = direct.slice(0, limit);
    if (!shown.length && all.length) shown = all.slice(0, 1);
    const rest = all.length - shown.length;
    const links = shown.map((o) => {
      const search = isSearch(o) || /chrono24/i.test(o.seller);
      const label = shortSeller(o.seller);
      const price = o.price_eur != null ? money(o.price_eur) : (search ? "pesquisa" : "");
      return `<a class="${search ? "search" : ""}" href="${o.url}" target="_blank" rel="noopener noreferrer" data-stop="1">
        <span class="seller">${escapeHtml(label)}</span>
        <span class="oprice">${price}</span>
      </a>`;
    }).join("");
    const more = rest > 0
      ? `<button class="more" type="button" data-open="${escapeHtml(w.ref)}">mais +${rest}</button>`
      : (all.length ? "" : `<span class="more">sem ofertas</span>`);
    return links + more;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function cardHTML(w) {
    const pill = `<span class="pill ${signalClass(w.signal)}">${escapeHtml(w.signal)}${w.premium_pct != null ? " · " + pct(w.premium_pct) : ""}</span>`;
    return `<article class="card" tabindex="0" role="button" data-ref="${escapeHtml(w.ref)}" aria-label="${escapeHtml(w.brand + " " + w.model)}">
      <div class="illu">${portrait(w)}</div>
      <p class="brand">${escapeHtml(w.brand)}</p>
      <h3 class="model">${escapeHtml(w.model)}</h3>
      <p class="ref">${escapeHtml(w.ref)}</p>
      <p class="price"><span class="price-label">Mercado</span>${money(w.market_eur)}</p>
      <p class="retail">Retalho PT <strong>${money(w.retail_pt_eur)}</strong></p>
      ${pill}
      <p class="onde-label">Onde comprar</p>
      <div class="offers">${offerButtons(w, 3)}</div>
    </article>`;
  }

  function filtered() {
    const brand = document.getElementById("f-brand").value;
    const gender = document.getElementById("f-gender").value;
    const signal = document.getElementById("f-signal").value;
    const sort = document.getElementById("f-sort").value;
    let list = DATA.watches.slice();
    if (brand) list = list.filter((w) => w.brand === brand);
    if (gender) list = list.filter((w) => w.gender === gender);
    if (signal) list = list.filter((w) => w.signal === signal);
    const key = sort === "price" ? "market_eur" : sort === "premium" ? "premium_pct" : null;
    const brandOrder = { Rolex: 0, Omega: 1, Cartier: 2, Panerai: 3 };
    const idx = Object.fromEntries(DATA.watches.map((w, i) => [w.ref, i]));
    list.sort((a, b) => {
      if (key) {
        const av = a[key], bv = b[key];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return av - bv;
      }
      const ba = brandOrder[a.brand] ?? 9;
      const bb = brandOrder[b.brand] ?? 9;
      return ba - bb || idx[a.ref] - idx[b.ref];
    });
    return list;
  }

  function renderGrid() {
    const list = filtered();
    const grid = document.getElementById("grid");
    const total = DATA.watches.length;
    document.getElementById("count").textContent =
      list.length === total ? `${total} referências` : `${list.length} de ${total}`;
    grid.innerHTML = list.length
      ? list.map(cardHTML).join("")
      : `<p class="empty-grid">Nenhum modelo com este filtro.</p>`;
  }

  function typeLabel(t) {
    return ({ AD: "AD", dealer: "dealer", marketplace: "mercado", CPO: "CPO" }[t] || t || "");
  }

  function openDrawer(ref) {
    const w = DATA.watches.find((x) => x.ref === ref);
    if (!w) return;
    const d = document.getElementById("drawer");
    const s = document.getElementById("scrim");
    const body = document.getElementById("drawer-body");
    const sales = w.demand && w.demand.sales_1y != null ? NUM.format(w.demand.sales_1y) : "—";
    const days = w.demand && w.demand.days_on_market != null ? NUM1.format(w.demand.days_on_market) : "—";
    const offers = rankedOffers(w.offers)
      .map((o) => {
        const search = /chrono24/i.test(o.seller);
        const flag = search ? `<span class="tag-search">pesquisa</span>` : "";
        const cond = o.condition ? escapeHtml(o.condition) : "";
        const seen = o.seen ? formatSeen(o.seen) : "";
        const meta = [typeLabel(o.type), o.country, cond, seen].filter(Boolean).join(" · ");
        return `<li>
          <a href="${o.url}" target="_blank" rel="noopener noreferrer">
            <div class="offer-top">
              <span class="offer-seller">${escapeHtml(shortSeller(o.seller))}${flag}</span>
              <span class="offer-price">${o.price_eur != null ? money(o.price_eur) : "abrir"}</span>
            </div>
            <p class="offer-meta">${meta}</p>
          </a>
        </li>`;
      })
      .join("");
    body.innerHTML = `
      <p class="brand">${escapeHtml(w.brand)}</p>
      <h2 class="model" id="drawer-title">${escapeHtml(w.model)}</h2>
      <div class="illu">${portrait(w)}</div>
      <p class="ref">${escapeHtml(w.ref)}</p>
      <p class="price"><span class="price-label">Mercado</span>${money(w.market_eur)}</p>
      <p class="retail">Retalho PT <strong>${money(w.retail_pt_eur)}</strong></p>
      <span class="pill ${signalClass(w.signal)}">${escapeHtml(w.signal)}${w.premium_pct != null ? " · " + pct(w.premium_pct) : ""}</span>
      ${w.blurb ? `<p class="blurb">${escapeHtml(w.blurb)}</p>` : ""}
      <dl class="stats">
        <div class="stat"><dt>Vendas a 1 ano</dt><dd>${sales}</dd></div>
        <div class="stat"><dt>Dias no mercado</dt><dd>${days}</dd></div>
      </dl>
      <p class="landed">Importação estimada <strong>${money(w.landed_import_eur)}</strong>
        <span> vs </span> dealer UE <strong>${money(w.dealer_eur)}</strong></p>
      <p class="onde-label">Onde comprar</p>
      <ul class="offer-list">${offers}</ul>
    `;
    d.hidden = false;
    s.hidden = false;
    document.body.style.overflow = "hidden";
    document.getElementById("drawer-close").focus();
  }

  function closeDrawer() {
    document.getElementById("drawer").hidden = true;
    document.getElementById("scrim").hidden = true;
    document.body.style.overflow = "";
  }

  function formatSeen(iso) {
    const [y, m, day] = iso.split("-").map(Number);
    const months = ["jan.","fev.","mar.","abr.","mai.","jun.","jul.","ago.","set.","out.","nov.","dez."];
    if (!y || !m) return iso;
    return `${day} ${months[m - 1]} ${y}`;
  }

  /* —— Charts —— */
  function chartDefaults() {
    if (!window.Chart) return;
    Chart.defaults.font.family = '"Instrument Sans", system-ui, sans-serif';
    Chart.defaults.font.size = 11;
    Chart.defaults.color = MUTED;
    Chart.defaults.borderColor = "rgba(27,24,20,.12)";
    Chart.defaults.animation = false;
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.backgroundColor = INK;
    Chart.defaults.plugins.tooltip.titleColor = "#F3EEE4";
    Chart.defaults.plugins.tooltip.bodyColor = "#F3EEE4";
    Chart.defaults.plugins.tooltip.cornerRadius = 0;
    Chart.defaults.plugins.tooltip.padding = 10;
  }

  function makeBar(id, labels, values, opt) {
    const ctx = document.getElementById(id);
    if (!ctx || !window.Chart) return;
    const colors = (values || []).map((v) => {
      if (opt && opt.signed) return v >= 0 ? UP : DOWN;
      return opt && opt.color ? opt.color : NAVY;
    });
    const ch = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, barPercentage: 0.62, categoryPercentage: 0.7 }],
      },
      options: {
        indexAxis: opt && opt.horizontal ? "y" : "x",
        maintainAspectRatio: false,
        responsive: true,
        scales: {
          x: {
            grid: { color: "rgba(27,24,20,.08)", drawBorder: false },
            ticks: {
              color: MUTED,
              maxRotation: 0,
              autoSkip: true,
              callback: function (value) {
                if (opt && opt.horizontal) {
                  if (opt.pct) return value;
                  if (opt.money || opt.xMoney) return NUM.format(value);
                  return value;
                }
                return this.getLabelForValue(value);
              },
            },
          },
          y: {
            grid: { color: opt && opt.horizontal ? "rgba(27,24,20,.08)" : "transparent", drawBorder: false },
            ticks: {
              color: MUTED,
              autoSkip: false,
              callback: function (value) {
                if (opt && opt.horizontal) return this.getLabelForValue(value);
                if (opt && opt.yMoney) return NUM.format(value);
                return value;
              },
            },
          },
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: (c) => {
                const v = c.raw;
                if (opt && opt.pct) return pct(v);
                if (opt && (opt.xMoney || opt.yMoney || opt.money)) return money(v);
                return opt && opt.unit ? NUM.format(v) + " " + opt.unit : String(v);
              },
            },
          },
        },
      },
    });
    charts.push(ch);
  }

  function renderCharts() {
    charts.forEach((c) => c.destroy());
    charts = [];
    const brands = DATA.aggregates.by_brand;
    const bLabels = brands.map((b) => b.brand);
    const srcBrand = "WatchCharts, 17 nov. 2026; prémio só vs retalho PT verificado. BCE 17 nov. 2026.";
    document.getElementById("cap-premium").textContent = srcBrand;
    document.getElementById("cap-median").textContent = srcBrand;
    document.getElementById("cap-sales").textContent = "WatchCharts, volume de vendas a 1 ano, 17 nov. 2026.";

    makeBar("chart-premium", bLabels, brands.map((b) => b.avg_premium_pct), { signed: true, pct: true });
    makeBar("chart-median", bLabels, brands.map((b) => b.median_market_eur), { color: NAVY, money: true, yMoney: true });
    makeBar("chart-sales", bLabels, brands.map((b) => b.total_sales_1y), { color: GOLD, money: false, yMoney: true, unit: "vendas" });

    const yearly = (INDEX.charts || []).find((c) => c.id === "wc-yearly");
    if (yearly) {
      document.getElementById("cap-yearly").innerHTML =
        `<a href="${yearly.source_url}" target="_blank" rel="noopener">${escapeHtml(yearly.source)}</a>`;
      makeBar("chart-yearly", yearly.labels, yearly.values, { signed: true, pct: true });
    }

    const rank = (DATA.aggregates.ranking_premium || []).filter((r) => r.premium_pct != null);
    const labels = rank.map((r) => r.ref);
    document.getElementById("cap-rank").textContent =
      "Prémio de mercado (WatchCharts) face ao retalho PT. Referências sem PVP PT omitidas.";
    makeBar("chart-rank", labels, rank.map((r) => r.premium_pct), { horizontal: true, signed: true, pct: true });

    const snaps = document.getElementById("snapshots");
    const wc = (INDEX.charts || []).find((c) => c.id === "wc-index-snapshot");
    const cp = (INDEX.charts || []).find((c) => c.id === "chronopulse");
    function chg(n) {
      if (n == null) return "—";
      return (n > 0 ? "+" : "") + NUM1.format(n) + " %";
    }
    let html = "";
    if (wc) {
      html += `<div class="snap">
        <p class="kicker">WatchCharts Overall</p>
        <p class="snap-val">${NUM.format(wc.value)}</p>
        <p class="snap-meta"><b>1A ${chg(wc.changes["1y"])}</b> · 1M ${chg(wc.changes["1m"])} · 5A ${chg(wc.changes["5y"])} · 13 nov. 2026</p>
      </div>`;
    }
    if (cp) {
      html += `<div class="snap">
        <p class="kicker">ChronoPulse</p>
        <p class="snap-val">${NUM.format(cp.value)}</p>
        <p class="snap-meta"><b>12M ${chg(cp.changes["12m"])}</b> · T3 ${chg(cp.changes.q3_2026)} · fecho set. 2026</p>
      </div>`;
    }
    snaps.innerHTML = html;
  }

  function renderFooter() {
    const src = DATA.sources || {};
    const updated = formatSeen(DATA.updated);
    const creditItems = CREDITS.map((c) => {
      const src = c.source_page
        ? `<a href="${c.source_page}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.source || "fonte")}</a>`
        : escapeHtml(c.source || "");
      return `<li>${escapeHtml(c.model)} — ${escapeHtml(c.credit)} · ${escapeHtml(c.licence)} · ${src}</li>`;
    }).join("");
    const creditBlock = CREDITS.length
      ? `<div class="credits">
        <h2>Créditos das imagens</h2>
        <ul>${creditItems}</ul>
      </div>`
      : "";
    document.getElementById("foot").innerHTML = `
      <div>
        <p><strong>Dados ${updated}</strong>, Europe/Lisbon. Não é aconselhamento financeiro.</p>
        <p>Mercado e procura: WatchCharts, 17 nov. 2026. Retalho: AD em Portugal. Ofertas: Watchfinder, Montredo, AD. Ligações Chrono24 são pesquisas, não anúncios.</p>
      </div>
      <div>
        <p>Edição 01 · G Watch Radar</p>
        <p>Porto</p>
      </div>
      ${creditBlock}`;
  }

  function fillBrandFilter() {
    const sel = document.getElementById("f-brand");
    const brands = [...new Set(DATA.watches.map((w) => w.brand))];
    brands.forEach((b) => {
      const o = document.createElement("option");
      o.value = b;
      o.textContent = b;
      sel.appendChild(o);
    });
  }

  function onGridClick(ev) {
    const stop = ev.target.closest("[data-stop]");
    if (stop) return;
    const more = ev.target.closest("[data-open]");
    if (more) {
      ev.preventDefault();
      openDrawer(more.getAttribute("data-open"));
      return;
    }
    const card = ev.target.closest(".card");
    if (card) openDrawer(card.getAttribute("data-ref"));
  }

  function onGridKey(ev) {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const card = ev.target.closest(".card");
    if (!card || ev.target !== card) return;
    ev.preventDefault();
    openDrawer(card.getAttribute("data-ref"));
  }

  async function init() {
    const [wRes, iRes, cRes] = await Promise.all([
      fetch("data/watches.json"),
      fetch("data/indices.json"),
      fetch("img/credits.json"),
    ]);
    if (!wRes.ok || !iRes.ok) throw new Error("Falha a ler os dados.");
    DATA = await wRes.json();
    INDEX = await iRes.json();
    if (cRes.ok) {
      const cred = await cRes.json();
      CREDITS = cred.images || [];
      CREDITS.forEach((c) => { if (c.ref) PHOTOS[c.ref] = true; });
    }
    fillBrandFilter();
    renderGrid();
    document.getElementById("filters").addEventListener("change", renderGrid);
    document.getElementById("grid").addEventListener("click", onGridClick);
    document.getElementById("grid").addEventListener("keydown", onGridKey);
    document.getElementById("drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("scrim").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDrawer();
    });
    const params = new URLSearchParams(location.search);
    const q = params.get("open");
    if (q) openDrawer(q);
    if (params.get("shot") === "mercado") {
      const modelos = document.getElementById("modelos");
      if (modelos) modelos.hidden = true;
    }
    await Promise.all(Array.from(document.querySelectorAll(".illu img")).map(function (img) {
      return img.decode ? img.decode().catch(function () {}) : Promise.resolve();
    }));
    chartDefaults();
    renderCharts();
    renderFooter();
  }

  init().catch((err) => {
    document.getElementById("grid").innerHTML =
      `<p class="empty-grid">Não foi possível carregar os dados.</p>`;
    console.error(err);
  });
})();
