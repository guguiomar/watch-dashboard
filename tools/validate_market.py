#!/usr/bin/env python3
"""Validate WatchCharts market prices against real active listings.

A market estimate is 'validado' only if at least one real, active listing
confirms it. Confirmation requires all of:

  - exact reference (and, for Rolex, a matching bracelet — 'match', not
    'unknown' or 'mismatch')
  - own product-page URL (not a search results page)
  - visible asking price
  - seen within the last 14 days
  - listing comparable price in [market × 0.85, market × 1.15]

Comparable price (stated choice): the listing's own asking price in EUR —
the EU EUR price when the seller is in the EU, or the raw asking price
converted to EUR (existing ECB/FX conversion already stored as price_eur)
when the seller is extra-EU. Import costs, IVA on import and portes are
excluded, because WatchCharts is a secondary-market (private-sale)
estimate, not a Portugal landed consumer price. Official AD / new PVP
listings are also excluded: a retail price does not confirm a secondary
market number.

If none confirms: status 'não validado'. The weekly routine (and the UI)
must not treat an unvalidated market as a baseline for Comprar / Perto
or for %-vs-market badges.

Usage (from the repo root):

  python3 tools/validate_market.py

Also invoked at the end of tools/refresh_trends_deals.py, so the weekly
refresh already applies the rule. This command can be run on its own
after listings or history have been updated:

  python3 tools/update_listing_history.py --check-gone
  python3 tools/validate_market.py

Never invents prices. Never scrapes Chrono24.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ_NAME = "Europe/Lisbon"
WINDOW_DAYS = 14
TOLERANCE = 0.15
NON_EU = {"GB", "UK", "US", "CH", "JP", "HK", "SG", "AE"}
TODAY = date.today()


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)}", file=sys.stderr)


def norm_url(u: str | None) -> str:
    return (u or "").rstrip("/")


def parse_iso(d: str | None):
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


def is_search(o: dict) -> bool:
    if not o:
        return True
    if o.get("kind") == "search":
        return True
    if o.get("kind") == "listing":
        # still reject search-shaped URLs
        pass
    u = (o.get("url") or "").lower()
    text = " ".join(
        str(o.get(k) or "") for k in ("condition", "note", "seller")
    ).lower()
    if "pesquisa" in text:
        return True
    if re.search(r"/search|/pesquisa|[?&]q=|[?&]query=|dosearch=", u):
        return True
    if "chrono24" in (o.get("seller") or "").lower() and re.search(
        r"search|dosearch|query=", u
    ):
        return True
    if "watchfinder." in u and not re.search(r"/\d+/?(\?|$)", u.split("?")[0]):
        return True
    return False


def is_priced_listing(o: dict) -> bool:
    return bool(
        o
        and o.get("price_eur") is not None
        and o.get("url")
        and not is_search(o)
    )


def comparable_eur(o: dict):
    """Asking price in EUR, never landed / import cost."""
    if not o or o.get("price_eur") is None:
        return None
    try:
        return float(o["price_eur"])
    except (TypeError, ValueError):
        return None


def rolex_bracelet_ok(watch: dict, o: dict, *, require_match: bool) -> bool:
    """For confirmation, Rolex needs an explicit match. For the cheapest
    listing reference, only a known mismatch is excluded."""
    if (watch.get("brand") or "") != "Rolex":
        return True
    bm = o.get("bracelet_match")
    if require_match:
        return bm == "match"
    return bm != "mismatch"


def within_window(seen: str | None, as_of: date) -> bool:
    d = parse_iso(seen)
    if d is None:
        return False
    return (as_of - d).days <= WINDOW_DAYS and d <= as_of + timedelta(days=0)


def in_band(price: float, market: float) -> bool:
    if market is None or market <= 0 or price is None:
        return False
    lo = market * (1 - TOLERANCE)
    hi = market * (1 + TOLERANCE)
    return lo <= price <= hi


def last_price_from_history(entry: dict):
    obs = entry.get("price_observations") or []
    if not obs:
        return None, None, None
    # latest by date, then last in list
    def key(o):
        return o.get("date") or ""

    latest = sorted(obs, key=key)[-1]
    return latest.get("price_eur"), latest.get("price_text"), latest.get("date")


def collect_listings(watches, dealer_listings, history):
    """Deduped exact listings keyed by URL. Richer records win."""
    by_url = {}

    def merge(rec, src):
        url = norm_url(rec.get("url"))
        if not url:
            return
        rec = dict(rec)
        rec["url"] = url
        rec["_src"] = src
        prev = by_url.get(url)
        if not prev:
            by_url[url] = rec
            return
        # fill gaps; prefer explicit bracelet_match and newer seen
        for k, v in rec.items():
            if k.startswith("_"):
                continue
            if v in (None, "", []) and prev.get(k) not in (None, "", []):
                continue
            if k == "bracelet_match":
                rank = {"match": 3, "mismatch": 2, "unknown": 1}
                if rank.get(v, 0) >= rank.get(prev.get(k), 0):
                    prev[k] = v
                    if rec.get("bracelet"):
                        prev["bracelet"] = rec.get("bracelet")
                continue
            if k in ("seen", "last_seen"):
                if v and (not prev.get(k) or v > prev[k]):
                    prev[k] = v
                continue
            if prev.get(k) in (None, "", []) and v not in (None, "", []):
                prev[k] = v

    for w in watches:
        for o in w.get("offers") or []:
            item = dict(o)
            item["ref"] = w["ref"]
            merge(item, "offers")

    for L in dealer_listings or []:
        merge(dict(L), "dealer_listings")

    for url, e in (history or {}).items():
        price, text, obs_date = last_price_from_history(e)
        item = {
            "url": url,
            "ref": e.get("ref"),
            "seller": e.get("seller"),
            "country": e.get("country"),
            "type": e.get("type"),
            "kind": e.get("kind") or "listing",
            "price_eur": price,
            "price_text": text,
            "seen": e.get("last_seen") or obs_date,
            "last_seen": e.get("last_seen") or obs_date,
            "status": e.get("status"),
            "condition": e.get("condition"),
            "bracelet": e.get("bracelet"),
            "bracelet_match": e.get("bracelet_match"),
        }
        merge(item, "history")

    return list(by_url.values())


def listing_seen(o: dict) -> str | None:
    return o.get("last_seen") or o.get("seen")


def is_active(o: dict) -> bool:
    st = (o.get("status") or "active").lower()
    return st not in {"gone", "sold", "inactive", "removed"}


def candidate_ok(watch: dict, o: dict, as_of: date, *, for_confirm: bool) -> bool:
    if not is_priced_listing(o):
        return False
    if not is_active(o):
        return False
    if not within_window(listing_seen(o), as_of):
        return False
    if o.get("ref") and o.get("ref") != watch.get("ref"):
        return False
    if for_confirm and (o.get("type") or "") == "AD":
        return False
    if not rolex_bracelet_ok(watch, o, require_match=for_confirm):
        return False
    if comparable_eur(o) is None:
        return False
    return True


def summarize_listing(o: dict, market=None) -> dict:
    price = comparable_eur(o)
    rec = {
        "seller": o.get("seller"),
        "country": o.get("country"),
        "type": o.get("type"),
        "price_eur": o.get("price_eur"),
        "price_text": o.get("price_text"),
        "url": o.get("url"),
        "seen": listing_seen(o),
        "condition": o.get("condition"),
        "bracelet": o.get("bracelet"),
        "bracelet_match": o.get("bracelet_match"),
    }
    if market and price is not None and market:
        rec["ratio"] = round(price / market, 3)
        rec["delta_pct"] = round(100.0 * (price - market) / market, 1)
    return rec


def validate_watch(watch: dict, listings: list, as_of: date) -> dict:
    market = watch.get("market_eur")
    ref_listings = [o for o in listings if o.get("ref") == watch["ref"]]
    confirm_pool = [
        o for o in ref_listings if candidate_ok(watch, o, as_of, for_confirm=True)
    ]
    display_pool = [
        o for o in ref_listings if candidate_ok(watch, o, as_of, for_confirm=False)
    ]
    # cheapest real listing: prefer non-AD eligible, else any eligible incl. AD
    non_ad = [o for o in display_pool if (o.get("type") or "") != "AD"]
    cheap_pool = non_ad or display_pool
    cheap_pool = sorted(cheap_pool, key=lambda o: comparable_eur(o))
    cheapest = summarize_listing(cheap_pool[0], market) if cheap_pool else None

    if market is None:
        return {
            "status": "sem mercado",
            "confirmed_by": 0,
            "confirming": [],
            "cheapest_listing": cheapest,
            "band_lo_eur": None,
            "band_hi_eur": None,
            "tolerance": TOLERANCE,
            "comparable": (
                "preço do anúncio em EUR (preço UE, ou câmbio do preço "
                "pedido extra-UE; sem custo de importação)"
            ),
            "as_of": as_of.isoformat(),
            "unvalidated_reason": "sem preço de mercado WatchCharts",
        }

    lo = round(market * (1 - TOLERANCE), 2)
    hi = round(market * (1 + TOLERANCE), 2)
    confirming = []
    for o in confirm_pool:
        price = comparable_eur(o)
        if in_band(price, market):
            confirming.append(summarize_listing(o, market))
    confirming.sort(key=lambda r: r.get("price_eur") or 0)

    if confirming:
        return {
            "status": "validado",
            "confirmed_by": len(confirming),
            "confirming": confirming,
            "cheapest_listing": cheapest,
            "band_lo_eur": lo,
            "band_hi_eur": hi,
            "tolerance": TOLERANCE,
            "comparable": (
                "preço do anúncio em EUR (preço UE, ou câmbio do preço "
                "pedido extra-UE; sem custo de importação)"
            ),
            "as_of": as_of.isoformat(),
            "unvalidated_reason": None,
        }

    if not confirm_pool and not display_pool:
        reason = "sem anúncios exactos com preço visível nos últimos 14 dias"
    elif not confirm_pool:
        reason = (
            "nenhum anúncio de dealer/mercado com pulseira confirmada "
            "nos últimos 14 dias"
        )
    else:
        reason = (
            "nenhum anúncio exacto confirma o mercado no intervalo ±15 %"
        )
    return {
        "status": "não validado",
        "confirmed_by": 0,
        "confirming": [],
        "cheapest_listing": cheapest,
        "band_lo_eur": lo,
        "band_hi_eur": hi,
        "tolerance": TOLERANCE,
        "comparable": (
            "preço do anúncio em EUR (preço UE, ou câmbio do preço "
            "pedido extra-UE; sem custo de importação)"
        ),
        "as_of": as_of.isoformat(),
        "unvalidated_reason": reason,
    }


def apply_curated_updates(watches_doc, listings_doc, history_doc, as_of: date):
    """Idempotent data fixes and newly verified listings (22 Nov 2026).

    Bracelet fields on three Watchfinder Datejust offers are taken from the
    condition text already recorded in watches.json (not invented). New
    WSSA0018 Montredo and HORANDO prices were read from the product pages
    on 22 Nov 2026. Watchfinder UK WSSA0018 was re-checked the same day
    (£7,995, InStock, Unworn).
    """
    as_of_s = as_of.isoformat()
    watches = {w["ref"]: w for w in watches_doc["watches"]}

    def offer_by_url(w, url):
        u = norm_url(url)
        for o in w.get("offers") or []:
            if norm_url(o.get("url")) == u:
                return o
        return None

    # Bracelet from already-recorded condition text
    bracelet_fixes = [
        (
            "126334",
            "https://www.watchfinder.co.uk/watches/rolex/datejust-41/126334/453530",
            "Oyster",
            "match",
        ),
        (
            "278274",
            "https://www.watchfinder.co.uk/watches/rolex/datejust-lady-31/278274/448820",
            "Jubilee",
            "match",
        ),
        (
            "279174",
            "https://www.watchfinder.co.uk/watches/rolex/datejust-lady-28/279174/434799",
            "Oyster",
            "match",
        ),
        (
            "279174",
            "https://www.watchfinder.co.uk/watches/rolex/datejust-lady-28/279174/426275",
            "Jubilee",
            "mismatch",
        ),
    ]
    for ref, url, bracelet, match in bracelet_fixes:
        w = watches[ref]
        o = offer_by_url(w, url)
        if o:
            o["bracelet"] = bracelet
            o["bracelet_match"] = match

    # Re-verified Watchfinder UK WSSA0018 (still £7,995 InStock, Unworn)
    w18 = watches["WSSA0018"]
    wf = offer_by_url(
        w18,
        "https://www.watchfinder.co.uk/watches/cartier/santos-de-cartier/wssa0018/445096",
    )
    if wf:
        wf["seen"] = as_of_s
        wf["http"] = 200
        wf["price_eur"] = 9597
        wf["price_text"] = "£7,995"
        wf["condition"] = "unworn, caixa e papéis, 2026"

    montredo = {
        "seller": "Montredo",
        "type": "dealer",
        "country": "DE",
        "price_eur": 8370,
        "price_text": "8.370 €",
        "currency": "EUR",
        "condition": "novo, nunca usado",
        "url": "https://www.montredo.com/products/cartier-santos-automatic-silvery-opaline-39-8-x-47-5mm-2-49964",
        "seen": as_of_s,
        "http": 200,
        "kind": "listing",
        "import_flag": False,
        "source": "página de produto Montredo, 22 nov 2026 (InStock, 8.370 €, regular 9.000 €)",
    }
    horando = {
        "seller": "HORANDO",
        "type": "dealer",
        "country": "DE",
        "price_eur": 9000,
        "price_text": "9.000 €",
        "currency": "EUR",
        "condition": "novo, caixa e papéis, 2026; prazo de entrega 4–6 semanas",
        "url": "https://www.horando.de/en/products/cartier-santos-de-cartier-wssa0018",
        "seen": as_of_s,
        "http": 200,
        "kind": "listing",
        "import_flag": False,
        "source": "página de produto HORANDO, 22 nov 2026 (InStock, 9.000 €, NewCondition)",
    }

    # Replace Montredo search offer with the exact listing; keep Chrono24 search
    offers = w18.setdefault("offers", [])
    replaced = False
    for i, o in enumerate(offers):
        if (o.get("seller") or "").startswith("Montredo"):
            offers[i] = montredo
            replaced = True
            break
    if not replaced:
        # insert after Watchfinder, before search links
        offers.append(montredo)
    if not offer_by_url(w18, horando["url"]):
        # insert after Montredo
        idx = next(
            (i for i, o in enumerate(offers) if o.get("seller") == "Montredo"),
            len(offers) - 1,
        )
        offers.insert(idx + 1, horando)

    # dealer_listings.json upserts
    def upsert_listing(item):
        rec = {
            "ref": "WSSA0018",
            "seller": item["seller"],
            "type": item["type"],
            "country": item["country"],
            "price_eur": item["price_eur"],
            "price_text": item["price_text"],
            "currency": item.get("currency") or "EUR",
            "condition": item["condition"],
            "url": item["url"],
            "seen": item["seen"],
            "http": item.get("http") or 200,
            "kind": "listing",
            "import_flag": False,
            "variant_note": "Santos de Cartier grande / 39,8 mm, aço, cadran opalino",
            "source": item.get("source"),
        }
        listings = listings_doc.setdefault("listings", [])
        for i, L in enumerate(listings):
            if norm_url(L.get("url")) == norm_url(rec["url"]):
                listings[i] = {**L, **rec}
                return
        listings.append(rec)

    upsert_listing(montredo)
    upsert_listing(horando)
    listings_doc["updated"] = as_of_s
    listings_doc["timezone"] = TZ_NAME

    # listings_history.json — reuse the merge used by the weekly updater
    sys.path.insert(0, str(ROOT / "tools"))
    from update_listing_history import collect_live_listings, merge_into_history

    # Ensure current watches/listings are on disk before collect? We'll merge
    # a hand-built live dict so we don't depend on a half-written file.
    live = {}
    for w in watches_doc["watches"]:
        for o in w.get("offers") or []:
            if o.get("kind") != "listing" or o.get("price_eur") is None:
                continue
            url = norm_url(o.get("url"))
            if not url:
                continue
            live[url] = {
                "ref": w["ref"],
                "seller": o.get("seller"),
                "country": o.get("country"),
                "type": o.get("type"),
                "seen": o.get("seen"),
                "price_eur": o.get("price_eur"),
                "price_text": o.get("price_text"),
                "currency": o.get("currency"),
            }
    for item in listings_doc.get("listings") or []:
        if item.get("kind") != "listing":
            continue
        url = norm_url(item.get("url"))
        if not url:
            continue
        rec = live.setdefault(url, {})
        for k in ("ref", "seller", "country", "type", "seen", "price_eur", "price_text", "currency"):
            if not rec.get(k) and item.get(k) is not None:
                rec[k] = item.get(k)
    added, updated = merge_into_history(history_doc, live)
    history_doc["updated"] = as_of_s
    history_doc["timezone"] = TZ_NAME
    return added, updated


def patch_deals(deals: dict, by_ref: dict) -> dict:
    """Unvalidated (or missing) market cannot create Comprar / Perto vs-market."""
    def patch(e):
        st = (by_ref.get(e.get("ref")) or {}).get("status")
        e["market_validated"] = st == "validado"
        if st != "validado":
            if e.get("qualifies"):
                e["disqualified_reason"] = e.get("reason")
            e["qualifies"] = False
            e["reason"] = None
            e["unvalidated_market"] = True
        return e

    evaluated = [patch(dict(e)) for e in (deals.get("evaluated") or [])]
    deals["evaluated"] = evaluated
    deals["deals"] = [e for e in evaluated if e.get("qualifies")]
    deals["deal_count"] = len(deals["deals"])
    deals["evaluated_count"] = len(evaluated)
    deals["updated"] = deals.get("updated") or TODAY.isoformat()
    th = deals.setdefault("thresholds", {})
    th["market_validation"] = {
        "tolerance": TOLERANCE,
        "window_days": WINDOW_DAYS,
        "comparable": (
            "preço do anúncio em EUR (preço UE, ou câmbio do preço pedido "
            "extra-UE; sem custo de importação)"
        ),
        "ad_excluded": True,
        "rolex_bracelet": "só anúncios com bracelet_match == match",
        "rule": (
            "O mercado WatchCharts só entra na lógica Comprar/Perto e nos "
            "selos % vs mercado quando está validado por pelo menos um "
            "anúncio exacto no intervalo ±15 %."
        ),
    }
    note = deals.get("note") or ""
    extra = (
        " Um preço de mercado só é usado para Comprar/Perto se estiver "
        "validado por pelo menos um anúncio exacto no intervalo ±15 % "
        "(preço pedido em EUR, sem custo de importação; AD excluídos; "
        "pulseira correspondente nos Rolex)."
    )
    if "validado por pelo menos um anúncio" not in note:
        deals["note"] = (note + extra).strip()
    return deals


def run(as_of: date, apply_curated: bool = True):
    watches_doc = load_json(DATA / "watches.json")
    listings_doc = load_json(DATA / "dealer_listings.json")
    history_doc = load_json(DATA / "listings_history.json")

    if apply_curated:
        added, updated = apply_curated_updates(
            watches_doc, listings_doc, history_doc, as_of
        )
        print(f"history merge: +{added} new URLs, {updated} updated", file=sys.stderr)
        dump_json(DATA / "dealer_listings.json", listings_doc)
        dump_json(DATA / "listings_history.json", history_doc)

    listings = collect_listings(
        watches_doc["watches"],
        listings_doc.get("listings") or [],
        history_doc.get("listings") or {},
    )

    by_ref = {}
    for w in watches_doc["watches"]:
        rec = validate_watch(w, listings, as_of)
        w["market_validation"] = rec
        by_ref[w["ref"]] = rec

    # Keep a compact catalogue note
    sources = watches_doc.setdefault("sources", {})
    sources["market_validation"] = (
        "Um preço WatchCharts só é «validado» se pelo menos um anúncio "
        "exacto activo (ficha própria, preço visível, visto nos últimos "
        "14 dias; pulseira correspondente nos Rolex; excluídos AD/PVP) "
        "estiver entre 85 % e 115 % do mercado. Comparável: preço do "
        "anúncio em EUR (preço UE ou câmbio do preço pedido extra-UE), "
        "sem IVA de importação nem portes."
    )

    dump_json(DATA / "watches.json", watches_doc)

    counts = {"validado": [], "não validado": [], "sem mercado": []}
    for w in watches_doc["watches"]:
        counts[w["market_validation"]["status"]].append(w["ref"])

    summary = {
        "updated": as_of.isoformat(),
        "timezone": TZ_NAME,
        "rule": {
            "tolerance": TOLERANCE,
            "band": "market × 0.85 a market × 1.15",
            "window_days": WINDOW_DAYS,
            "comparable": (
                "preço do anúncio em EUR (preço UE, ou câmbio do preço "
                "pedido extra-UE; sem custo de importação)"
            ),
            "ad_excluded": True,
            "rolex_bracelet_required": True,
            "search_pages_excluded": True,
        },
        "counts": {k: len(v) for k, v in counts.items()},
        "validado": counts["validado"],
        "nao_validado": counts["não validado"],
        "sem_mercado": counts["sem mercado"],
        "models": {
            w["ref"]: {
                "brand": w["brand"],
                "model": w.get("model"),
                "market_eur": w.get("market_eur"),
                **w["market_validation"],
            }
            for w in watches_doc["watches"]
        },
        "command": "python3 tools/validate_market.py",
    }
    dump_json(DATA / "market_validation.json", summary)

    deals_path = DATA / "deals.json"
    if deals_path.exists():
        deals = load_json(deals_path)
        patch_deals(deals, by_ref)
        dump_json(deals_path, deals)

    print(
        f"validado {len(counts['validado'])} / "
        f"não validado {len(counts['não validado'])} / "
        f"sem mercado {len(counts['sem mercado'])}  "
        f"(total {len(watches_doc['watches'])})"
    )
    print("validado:", ", ".join(counts["validado"]) or "—")
    print("não validado:", ", ".join(counts["não validado"]) or "—")
    print("sem mercado:", ", ".join(counts["sem mercado"]) or "—")
    return summary, by_ref


def hook_from_refresh(watches_list, deals, as_of: date | None = None):
    """Apply validation onto an in-memory watches list and deals dict.

    Used by refresh_trends_deals.py after compute_deals. Persists
    market_validation onto data/watches.json and writes the summary
    plus the patched deals.json (caller may also dump deals).
    """
    as_of = as_of or date.today()
    watches_doc = load_json(DATA / "watches.json")
    # prefer the in-memory list (same refs) if provided
    if watches_list:
        by_mem = {w["ref"]: w for w in watches_list}
        for w in watches_doc["watches"]:
            mem = by_mem.get(w["ref"])
            if mem is not None:
                # keep validation off the refresh-only copy; use disk+mem offers
                w["offers"] = mem.get("offers", w.get("offers"))
    listings_doc = load_json(DATA / "dealer_listings.json")
    history_doc = load_json(DATA / "listings_history.json")
    listings = collect_listings(
        watches_doc["watches"],
        listings_doc.get("listings") or [],
        history_doc.get("listings") or {},
    )
    by_ref = {}
    for w in watches_doc["watches"]:
        rec = validate_watch(w, listings, as_of)
        w["market_validation"] = rec
        by_ref[w["ref"]] = rec
        mem = next((x for x in (watches_list or []) if x["ref"] == w["ref"]), None)
        if mem is not None:
            mem["market_validation"] = rec
    dump_json(DATA / "watches.json", watches_doc)
    patch_deals(deals, by_ref)
    return by_ref


def main():
    global TODAY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today in Europe/Lisbon)")
    ap.add_argument("--skip-curated", action="store_true", help="do not upsert the 22 Nov verified listings / bracelet fixes")
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    TODAY = as_of
    run(as_of, apply_curated=not args.skip_curated)


if __name__ == "__main__":
    main()
