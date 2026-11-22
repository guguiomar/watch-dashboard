#!/usr/bin/env python3
"""Weekly refresh of trends.json, deals.json and social.json (X counts optional).

Respects robots / no Chrono24 scrape. Never invents prices.
Run from the repo root or any cwd; paths are relative to this file's parent.

  python3 tools/refresh_trends_deals.py
  python3 tools/refresh_trends_deals.py --skip-feeds   # reuse last trends items if fetch fails
  python3 tools/refresh_trends_deals.py --x-counts /path/to/counts.json

After listings have been rechecked, also update the listing history
and re-validate market prices against real listings:

  python3 tools/update_listing_history.py --check-gone
  python3 tools/validate_market.py

validate_market.py also runs at the end of this script, so a plain

  python3 tools/refresh_trends_deals.py

already applies the ±15 % confirmation rule (market is 'validado' only
when at least one exact active listing, matching Rolex bracelet, own
page URL, visible price, seen in the last 14 days, sits within
market × 0.85–1.15; comparable = asking EUR, no import costs; AD
excluded). Standalone command for the weekly routine:

  python3 tools/validate_market.py


X (Twitter) is not called from this script: the Monday routine may not have
the X tools. Pass a counts JSON produced by Grok Bot, or leave social.json
counts in place and only refresh Instagram metadata / timestamps.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import email.utils
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ_NAME = "Europe/Lisbon"
UA = "GWatchRadar/1.0 (+https://guguiomar.github.io/watch-dashboard/; weekly feed refresh)"
TODAY = date(2026, 11, 19)  # overwritten at runtime
MARKET_GAP = 0.05  # listing must be >= 5% below WatchCharts market
RETAIL_MARGIN = 0.05  # hard-to-get: listing <= PT retail + 5%
LANDED = lambda p: round(1.23 * (p + 150.80), 2)
NON_EU = {"GB", "UK", "US", "CH", "JP", "HK", "SG", "AE"}

FEEDS = [
    {"id": "hodinkee", "name": "Hodinkee", "url": "https://www.hodinkee.com/articles/rss.xml", "lang": "en"},
    {"id": "fratello", "name": "Fratello", "url": "https://www.fratellowatches.com/feed/", "lang": "en"},
    {"id": "monochrome", "name": "Monochrome Watches", "url": "https://monochrome-watches.com/feed/", "lang": "en"},
    {"id": "revolution", "name": "Revolution", "url": "https://revolutionwatch.com/feed/", "lang": "en"},
    {"id": "revolution-latam", "name": "Revolution México / LATAM", "url": "https://www.revolution.watch/feed/", "lang": "es"},
    {"id": "time-tide", "name": "Time+Tide", "url": "https://timeandtidewatches.com/feed/", "lang": "en"},
    {"id": "watchpro", "name": "WatchPro", "url": "https://www.watchpro.com/feed/", "lang": "en"},
    {"id": "watchonista", "name": "Watchonista", "url": "https://www.watchonista.com/feed/", "lang": "en"},
]

INSTAGRAM = {
    "note": "Apenas ligações públicas. Sem login, sem recolha de publicações, sem scraping.",
    "hashtags": [
        {"label": "#rolex", "url": "https://www.instagram.com/explore/tags/rolex/"},
        {"label": "#omegawatches", "url": "https://www.instagram.com/explore/tags/omegawatches/"},
        {"label": "#speedmaster", "url": "https://www.instagram.com/explore/tags/speedmaster/"},
        {"label": "#cartier", "url": "https://www.instagram.com/explore/tags/cartier/"},
        {"label": "#panerai", "url": "https://www.instagram.com/explore/tags/panerai/"},
        {"label": "#gmtmaster", "url": "https://www.instagram.com/explore/tags/gmtmaster/"},
    ],
    "accounts": [
        {"label": "@rolex", "url": "https://www.instagram.com/rolex/", "kind": "oficial"},
        {"label": "@omega", "url": "https://www.instagram.com/omega/", "kind": "oficial"},
        {"label": "@cartier", "url": "https://www.instagram.com/cartier/", "kind": "oficial"},
        {"label": "@panerai", "url": "https://www.instagram.com/panerai/", "kind": "oficial"},
        {"label": "@hodinkee", "url": "https://www.instagram.com/hodinkee/", "kind": "revista"},
        {"label": "@fratellowatches", "url": "https://www.instagram.com/fratellowatches/", "kind": "revista"},
        {"label": "@monochromewatches", "url": "https://www.instagram.com/monochromewatches/", "kind": "revista"},
        {"label": "@revolutionwatch", "url": "https://www.instagram.com/revolutionwatch/", "kind": "revista"},
        {"label": "@timeandtidewatches", "url": "https://www.instagram.com/timeandtidewatches/", "kind": "revista"},
    ],
}

X_QUERY_SPEC = {
    "note": "Usar as ferramentas públicas X (get_posts_counts_recent para totais de 7 dias; search_posts_all com start_time ~30 dias, max_results=25, sort_order=relevancy) para preencher posts. Respeitar 30/min e 1000/dia. Não tratar a pesquisa de 30 dias (máx. 25) como um total.",
    "counts_api": "get_posts_counts_recent",
    "search_api": "search_posts_all",
    "search_start_time": "2026-10-20T00:00:00Z",
    "max_results": 25,
    "queries": [
        "Rolex",
        "\"Omega Speedmaster\"",
        "\"Omega watch\" OR \"Omega watches\" OR \"Omega Speedmaster\" OR \"Omega Seamaster\" OR @omega",
        "Cartier",
        "Panerai",
        "\"Rolex Pepsi\" OR 126710BLRO OR \"GMT Pepsi\"",
        "\"Rolex Batman\" OR 126710BLNR",
        "\"Bruce Wayne\" Rolex OR 126710GRNR",
        "Rolex Submariner",
        "Rolex Daytona",
        "Rolex Explorer",
        "Rolex \"Yacht-Master\" OR \"Yacht Master\"",
        "Rolex \"Air-King\" OR \"Air King\"",
        "Milgauss",
        "Rolex Datejust",
        "Rolex \"Day-Date\" OR DayDate",
        "\"Oyster Perpetual\"",
        "pistachio Rolex OR pistache Rolex OR \"134300-0006\"",
        "Omega (\"Dark Side of the Moon\" OR DSOTM)",
        "\"Speedmaster '57\" OR \"Speedmaster 57\" OR \"Speedmaster Broad Arrow\"",
        "\"Cartier Santos\"",
        "\"Cartier Tank\"",
        "\"Ballon Bleu\"",
        "Panerai Luminor OR PAM01314 OR PAM01123",
        "\"Root Beer\" Rolex OR 126711CHNR OR 126715CHNR",
    ],
    "do_not_use": [
        "Omega (isolado — demasiado genérico)",
        "\"Dark Side of the Moon\" OR DSOTM (sem Omega — colide com Pink Floyd)",
        "\"Omega Speedmaster\" OR Moonwatch (Moonwatch demasiado genérico; o pico de 19 nov manteve-se mesmo só com \"Omega Speedmaster\")",
    ],
}


def now_lisbon():
    # Box clock is Europe/Lisbon
    return datetime.now().astimezone()


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)}", file=sys.stderr)


def fetch_url(url: str, timeout=25):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read()


def local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1].lower() if "}" in tag else tag.lower()


def parse_date(text: str | None):
    if not text:
        return None
    text = text.strip()
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            if fmt.endswith("Z"):
                dt = datetime.strptime(text[:19] + "Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            elif fmt.endswith("%z"):
                dt = datetime.strptime(text.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            else:
                dt = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def text_of(el) -> str:
    if el is None:
        return ""
    bits = [el.text or ""]
    for c in el:
        bits.append(text_of(c))
        bits.append(c.tail or "")
    return unescape(re.sub(r"<[^>]+>", " ", "".join(bits)))


def parse_feed(xml_bytes: bytes):
    items = []
    try:
        blob = xml_bytes.lstrip()
        if b'<?xml' in blob[:200] and not blob.startswith(b'<?xml'):
            blob = blob[blob.find(b'<?xml'):]
        root = ET.fromstring(blob)
    except ET.ParseError:
        return items, "xml-parse-error"
    # RSS items
    for it in root.iter():
        if local_tag(it.tag) != "item":
            continue
        fields = {local_tag(c.tag): c for c in list(it)}
        def first(*keys):
            for k in keys:
                if k in fields:
                    return fields[k]
            return None
        title = text_of(first("title")).strip()
        link_el = first("link")
        link = (text_of(link_el) or (link_el.get("href") if link_el is not None else "")).strip()
        if not link:
            guid = first("guid")
            link = text_of(guid).strip() if guid is not None else ""
        pub = text_of(first("pubdate", "published", "date"))
        summary = text_of(first("description", "summary", "content"))
        items.append({"title": title, "url": link, "date_raw": pub, "dt": parse_date(pub), "summary": re.sub(r"\s+", " ", summary)[:400]})
    # Atom entries
    if not items:
        for it in root.iter():
            if local_tag(it.tag) != "entry":
                continue
            fields = {local_tag(c.tag): c for c in list(it)}
            title = text_of(fields.get("title")).strip()
            link = ""
            for c in list(it):
                if local_tag(c.tag) == "link":
                    href = c.get("href") or text_of(c)
                    if href and (c.get("rel") in (None, "alternate") or not link):
                        link = href
            pub = text_of(fields.get("updated") or fields.get("published"))
            summary = text_of(fields.get("summary") or fields.get("content"))
            items.append({"title": title, "url": link, "date_raw": pub, "dt": parse_date(pub), "summary": re.sub(r"\s+", " ", summary)[:400]})
    return items, ("ok" if items else "empty")


def fetch_feeds():
    statuses = []
    collected = []
    for spec in FEEDS:
        entry = {"id": spec["id"], "name": spec["name"], "url": spec["url"], "lang": spec["lang"], "ok": False, "items": 0, "error": None}
        try:
            code, raw = fetch_url(spec["url"])
            if code != 200:
                entry["error"] = f"http {code}"
                statuses.append(entry)
                continue
            # WatchPro often returns a Cloudflare HTML challenge
            head = raw[:200].lstrip().lower()
            if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
                entry["error"] = "html-not-feed"
                statuses.append(entry)
                continue
            items, st = parse_feed(raw)
            if st == "xml-parse-error":
                entry["error"] = st
                statuses.append(entry)
                continue
            entry["ok"] = True
            entry["items"] = len(items)
            if st == "empty":
                entry["error"] = "empty-feed"
            for it in items:
                collected.append({
                    "title": it["title"],
                    "url": it["url"],
                    "source": spec["name"],
                    "source_id": spec["id"],
                    "lang": spec["lang"],
                    "date": it["dt"].astimezone().strftime("%Y-%m-%d") if it["dt"] else None,
                    "date_iso": it["dt"].astimezone().isoformat(timespec="seconds") if it["dt"] else None,
                    "summary": it["summary"],
                })
            statuses.append(entry)
        except HTTPError as e:
            entry["error"] = f"http {e.code}"
            statuses.append(entry)
        except URLError as e:
            entry["error"] = f"url {e.reason}"
            statuses.append(entry)
        except Exception as e:
            entry["error"] = type(e).__name__ + ": " + str(e)[:160]
            statuses.append(entry)
    return statuses, collected


def brand_aliases(brand: str):
    b = brand.lower()
    return [brand, b]


def model_tokens(w):
    toks = [w["ref"], w["ref"].replace(".", ""), w["ref"].replace("-", "")]
    model = w.get("model") or ""
    # keep distinctive multi-word pieces
    toks.append(model)
    for extra in (w.get("nickname"), w.get("spec_diff")):
        if extra:
            toks.append(str(extra))
    return [t for t in toks if t and len(str(t)) >= 3]


def match_item(item, watches):
    hay = f"{item.get('title','')} {item.get('summary','')}".lower()
    brands = sorted({w["brand"] for w in watches})
    hit_brands = [b for b in brands if re.search(r"\b" + re.escape(b.lower()) + r"\b", hay)]
    hit_refs = []
    hit_models = []
    for w in watches:
        ref = w["ref"]
        variants = {ref.lower(), ref.replace(".", "").lower(), ref.replace("-", "").lower()}
        if any(v and v in hay.replace(" ", "").replace(".", "").replace("-", "") or v in hay for v in variants):
            # tighter: ref or compacted ref in compacted hay
            compact = re.sub(r"[\s.\-/]", "", hay)
            cref = re.sub(r"[\s.\-/]", "", ref.lower())
            if cref and cref in compact:
                hit_refs.append(ref)
                continue
        model = (w.get("model") or "").lower()
        if w["brand"] in hit_brands and model and len(model) >= 5:
            # require brand + a distinctive model phrase
            # strip generic words
            core = model
            for g in ("de cartier", "watch", "professional"):
                core = core.replace(g, " ")
            core = re.sub(r"\s+", " ", core).strip()
            if len(core) >= 5 and core in hay:
                hit_models.append(ref)
    return sorted(set(hit_brands)), sorted(set(hit_refs)), sorted(set(hit_models))


def build_trends(watches, history, feed_status, items):
    today = date.today()
    d30 = today - timedelta(days=30)
    d90 = today - timedelta(days=90)

    def in_window(it, start):
        if not it.get("date"):
            return False
        try:
            d = date.fromisoformat(it["date"][:10])
        except ValueError:
            return False
        return start <= d <= today

    enriched = []
    for it in items:
        brands, refs, models = match_item(it, watches)
        rec = dict(it)
        rec["matched_brands"] = brands
        rec["matched_refs"] = sorted(set(refs + models))
        enriched.append(rec)

    brand_buzz = []
    for b in sorted({w["brand"] for w in watches}):
        m30 = [it for it in enriched if b in it["matched_brands"] and in_window(it, d30)]
        m90 = [it for it in enriched if b in it["matched_brands"] and in_window(it, d90)]
        latest = sorted(m90, key=lambda x: x.get("date") or "", reverse=True)[:5]
        brand_buzz.append({
            "brand": b,
            "magazine_30d": len(m30),
            "magazine_90d": len(m90),
            "window_note": "Contagens na janela do feed obtido (tipicamente as últimas 6–30 entradas), não um arquivo completo de 90 dias.",
            "headlines": [{"title": h["title"], "url": h["url"], "source": h["source"], "date": h["date"]} for h in latest],
        })

    # model buzz
    model_buzz = []
    by_ref = {w["ref"]: w for w in watches}
    for w in watches:
        ref = w["ref"]
        m30 = [it for it in enriched if ref in it["matched_refs"] and in_window(it, d30)]
        m90 = [it for it in enriched if ref in it["matched_refs"] and in_window(it, d90)]
        # also family mention: brand+model phrase already in matched_refs
        latest = sorted(m90, key=lambda x: x.get("date") or "", reverse=True)[:4]
        model_buzz.append({
            "ref": ref,
            "brand": w["brand"],
            "model": w.get("model"),
            "magazine_30d": len(m30),
            "magazine_90d": len(m90),
            "headlines": [{"title": h["title"], "url": h["url"], "source": h["source"], "date": h["date"]} for h in latest],
        })

    # price movement from history first-to-last sourced points
    snaps = history.get("snapshots") or []
    by = defaultdict(list)
    for s in snaps:
        if s.get("ref") and s.get("market_eur") is not None:
            by[s["ref"]].append(s)
    price_move = {}
    for ref, pts in by.items():
        pts = sorted(pts, key=lambda p: p.get("date") or p.get("as_of") or "")
        a, b = pts[0], pts[-1]
        if a is b or (a.get("date") == b.get("date") and a.get("market_eur") == b.get("market_eur")):
            if len(pts) < 2:
                continue
        if len(pts) < 2:
            continue
        first, last = pts[0], pts[-1]
        if first["market_eur"] and last["market_eur"] is not None:
            ch = last["market_eur"] - first["market_eur"]
            pct = round(100.0 * ch / first["market_eur"], 1) if first["market_eur"] else None
            price_move[ref] = {
                "from_eur": first["market_eur"],
                "to_eur": last["market_eur"],
                "from_date": first.get("date") or first.get("as_of"),
                "to_date": last.get("date") or last.get("as_of"),
                "change_eur": ch,
                "change_pct": pct,
                "direction": "up" if ch > 0 else ("down" if ch < 0 else "flat"),
                "n_points": len(pts),
                "source_first": first.get("source_url") or first.get("source"),
                "source_last": last.get("source_url") or last.get("source"),
            }

    failed = [s for s in feed_status if not s["ok"] or s.get("error")]
    return {
        "updated": date.today().isoformat(),
        "timezone": TZ_NAME,
        "note": "Itens de RSS/Atom públicos. As janelas de 30 e 90 dias referem-se apenas ao que o feed devolveu nesta recolha (muitas vezes as últimas 6–30 peças). WatchPro e feeds vazios ficam em feeds_failed. Não inventámos títulos nem datas.",
        "feeds": feed_status,
        "feeds_failed": failed,
        "items": enriched,
        "brand_buzz": brand_buzz,
        "model_buzz": model_buzz,
        "price_move": price_move,
    }


def compute_deals(watches, listings, dealers):
    dealer_by_name = {d["name"]: d for d in dealers.get("dealers") or []}
    # gather priced non-AD listings from watches + extra file
    pool = []
    for w in watches:
        for o in w.get("offers") or []:
            if o.get("kind") != "listing" or o.get("price_eur") is None:
                continue
            if o.get("type") == "AD":
                continue
            pool.append({"watch": w, "offer": o})
    # listings file may already be merged; skip dups
    seen = {(p["offer"].get("url") or "").rstrip("/") for p in pool}
    by_ref = {w["ref"]: w for w in watches}
    for L in listings:
        if (L.get("url") or "").rstrip("/") in seen:
            continue
        w = by_ref.get(L["ref"])
        if not w:
            continue
        pool.append({"watch": w, "offer": L})

    evaluated = []
    deals = []
    for p in pool:
        w, o = p["watch"], p["offer"]
        country = (o.get("country") or "").upper()
        import_flag = bool(o.get("import_flag")) or country in NON_EU
        price = o["price_eur"]
        compare = LANDED(price) if import_flag else price
        compare_label = "landed_eur" if import_flag else "listing_eur"
        market = w.get("market_eur")
        retail = w.get("retail_pt_eur")
        gap_mkt = None
        if market:
            gap_mkt = round(100.0 * (compare - market) / market, 1)
        gap_retail = None
        if retail:
            gap_retail = round(100.0 * (compare - retail) / retail, 1)
        hard = (w.get("signal") == "prémio") or (w.get("premium_pct") is not None and w["premium_pct"] >= 15)
        reason = None
        if market is not None and compare <= market * (1 - MARKET_GAP):
            reason = "market"
        elif hard and retail is not None and compare <= retail * (1 + RETAIL_MARGIN):
            reason = "retail_allocated"

        bracelet_match = o.get("bracelet_match")
        bracelet_mismatch = None
        caveat = "Verificar condição e papéis no anúncio: o Radar não confirma o estado da peça."
        if bracelet_match == "mismatch":
            bracelet_mismatch = True
            reason = None  # never qualify a deal across mismatched bracelets
            model_bracelet = w.get("bracelet") or "?"
            caveat += " Pulseira diferente da configuração PVP (" + model_bracelet + "); não comparável."
        elif bracelet_match == "unknown":
            bracelet_mismatch = None
            caveat += " Pulseira não confirmada no anúncio; pode não corresponder à configuração PVP."

        rec = {
            "ref": w["ref"],
            "brand": w["brand"],
            "model": w.get("model"),
            "seller": o.get("seller"),
            "country": o.get("country"),
            "url": o.get("url"),
            "listing_eur": price,
            "compare_eur": compare,
            "compare_as": compare_label,
            "import_flag": import_flag,
            "seen": o.get("seen"),
            "market_eur": market,
            "market_source": w.get("market_source"),
            "retail_pt_eur": retail,
            "retail_source": w.get("retail_source"),
            "gap_vs_market_pct": gap_mkt,
            "gap_vs_retail_pct": gap_retail,
            "hard_to_get": hard,
            "qualifies": reason is not None,
            "reason": reason,
            "photo": w.get("image") or w.get("photo") or w.get("img"),
            "bracelet_mismatch": bracelet_mismatch,
            "caveat": caveat,
        }
        evaluated.append(rec)
        if reason:
            deals.append(rec)

    deals.sort(key=lambda d: (d.get("gap_vs_market_pct") is None, d.get("gap_vs_market_pct") if d.get("gap_vs_market_pct") is not None else 99))
    return {
        "updated": date.today().isoformat(),
        "timezone": TZ_NAME,
        "note": "Uma oportunidade é um anúncio exacto, com preço e URL de ficha (não pesquisa, não AD), cujo preço comparável (landed se a origem for extra-UE) está pelo menos 5 % abaixo da estimativa WatchCharts de mercado, ou — só para modelos a prémio / com prémio ≥ 15 % — no máximo 5 % acima do PVP PT. O limiar de 5 % abaixo do mercado justifica-se porque o número WatchCharts é uma estimativa de venda entre particulares e os dealers costumam pedir esse valor ou mais; um desconto de 5 % ou superior face a essa estimativa pública não se explica só por câmbio ou arredondamento. Sempre com fontes e datas. Se nenhum anúncio cumprir o limiar, a lista fica vazia — não inventamos ofertas.",
        "thresholds": {
            "market_discount_pct": 5,
            "allocated_retail_margin_pct": 5,
            "allocated_rule": "signal == prémio ou premium_pct >= 15, e retail_pt_eur sourced",
            "landed_formula": "1.23 × (preço + 150.80 €) para GB/US/CH e outros extra-UE",
            "landed_formula_source": "mesmo critério já usado no Radar para custo de importação para PT",
        },
        "evaluated_count": len(evaluated),
        "deal_count": len(deals),
        "deals": deals,
        "evaluated": evaluated,
    }


def load_watches():
    return load_json(DATA / "watches.json")["watches"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x-counts", default=str(Path("/tmp/radar-v4/social/counts.json")))
    ap.add_argument("--skip-feeds", action="store_true")
    args = ap.parse_args()

    watches = load_watches()
    history = load_json(DATA / "history.json")
    dealers = load_json(DATA / "dealers.json")
    listings = load_json(DATA / "dealer_listings.json").get("listings") or []

    if args.skip_feeds:
        prev = load_json(DATA / "trends.json") if (DATA / "trends.json").exists() else None
        feed_status = (prev or {}).get("feeds") or []
        items = (prev or {}).get("items") or []
    else:
        feed_status, items = fetch_feeds()

    trends = build_trends(watches, history, feed_status, items)
    prev_trends = load_json(DATA / "trends.json") if (DATA / "trends.json").exists() else {}
    prev_by_url = {(it.get("url") or "").rstrip("/"): it for it in (prev_trends.get("items") or [])}
    for it in trends.get("items") or []:
        old = prev_by_url.get((it.get("url") or "").rstrip("/"), {})
        for k in ("image", "image_url", "image_original", "image_credit"):
            if not it.get(k) and old.get(k):
                it[k] = old[k]
    if prev_trends.get("headlines_featured"):
        trends["headlines_featured"] = prev_trends["headlines_featured"]
    dump_json(DATA / "trends.json", trends)

    deals = compute_deals(watches, listings, dealers)
    from validate_market import hook_from_refresh
    hook_from_refresh(watches, deals)
    dump_json(DATA / "deals.json", deals)

    # social.json
    social = {
        "updated": date.today().isoformat(),
        "timezone": TZ_NAME,
        "note": "Contagens X: API get_posts_counts_recent (janela de 7 dias, totais exactos da API). As pesquisas de 30 dias, quando existirem, estão limitadas a 25 resultados e não são um total. Consultas ruidosas (Omega isolado; Dark Side of the Moon sem Omega) ficam registadas mas não entram no buzz apresentado. Instagram: só ligações, sem recolha.",
        "x": {
            "as_of": None,
            "window": "7d",
            "api": "get_posts_counts_recent",
            "queries": [],
            "posts": [],
            "spec": X_QUERY_SPEC,
        },
        "instagram": INSTAGRAM,
    }
    counts_path = Path(args.x_counts)
    prev_social = load_json(DATA / "social.json") if (DATA / "social.json").exists() else {}
    if counts_path.exists():
        counts = load_json(counts_path)
        social["x"]["as_of"] = counts.get("as_of_lisbon") or counts.get("as_of")
        social["x"]["queries"] = counts.get("queries") or []
        # keep daily series / posts if the incoming counts file omits them
        prev_q = {(q.get("id") or q.get("query")): q for q in ((prev_social.get("x") or {}).get("queries") or [])}
        for q in social["x"]["queries"]:
            old = prev_q.get(q.get("id")) or prev_q.get(q.get("query")) or {}
            if not q.get("daily") and old.get("daily"):
                q["daily"] = old["daily"]
                if old.get("daily_note") and not q.get("daily_note"):
                    q["daily_note"] = old["daily_note"]
        if not social["x"].get("posts"):
            social["x"]["posts"] = (prev_social.get("x") or {}).get("posts") or []
            social["x"]["posts_note"] = (prev_social.get("x") or {}).get("posts_note") or social["x"].get("posts_note")
    elif (DATA / "social.json").exists():
        old = load_json(DATA / "social.json")
        social["x"]["as_of"] = (old.get("x") or {}).get("as_of")
        social["x"]["queries"] = (old.get("x") or {}).get("queries") or []
        social["x"]["posts"] = (old.get("x") or {}).get("posts") or []
        social["note"] += " Contagens X reutilizadas do ficheiro anterior (a rotina não chamou a API X)."
    dump_json(DATA / "social.json", social)

    print("feeds ok", [s["id"] for s in feed_status if s["ok"] and not s.get("error")])
    print("feeds failed", [(s["id"], s.get("error")) for s in feed_status if not s["ok"] or s.get("error")])
    print("items", len(items), "deals", deals["deal_count"], "evaluated", deals["evaluated_count"])


if __name__ == "__main__":
    main()
