#!/usr/bin/env python3
"""Weekly updater for data/listings_history.json.

Loads the current live snapshot (data/watches.json offers with
kind=="listing" and price_eur not null, plus data/dealer_listings.json
"listings"), normalizes each listing URL by stripping a trailing "/", and
merges it into the existing data/listings_history.json: new URLs become new
history records, URLs already on file get last_seen bumped and a new
price_observations entry appended only if that exact (date, price_eur) pair
isn't already recorded. Never removes or rewrites past observations. Never
invents a date or price that isn't present in the source files.

Respects robots / no Chrono24 scrape, same as tools/refresh_trends_deals.py.

Weekly routine (Monday):

  python3 tools/update_listing_history.py
  python3 tools/update_listing_history.py --check-gone   # recommended: also
                                                            # re-verifies any
                                                            # listing that
                                                            # dropped out of
                                                            # the live snapshot

--check-gone issues one polite GET per URL (no retries, no concurrency) for
every currently "active" history listing that is no longer present in the
live snapshot. A 404 / other 4xx-5xx, or an obvious sold/unavailable marker
in the HTML, marks it status="gone" with gone_date/gone_http set. A clean
200 with no such marker is left "active" (absence of bad news isn't proof of
life, but we don't guess wrong either way). Any exception leaves status as
it was.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ_NAME = "Europe/Lisbon"
UA = "GWatchRadar/1.0 (+https://guguiomar.github.io/watch-dashboard/; weekly feed refresh)"

SOLD_MARKERS = (
    "sold out",
    "item sold",
    "watch sold",
    "already sold",
    "no longer available",
    "not available",
    "out of stock",
    "currently unavailable",
    "vendido",
    "esgotado",
    "indisponível",
    "indisponivel",
    "ausverkauft",
    "nicht verfügbar",
    "nicht mehr verfügbar",
    "vendu",
    "n'est plus disponible",
    "plus disponible",
)

CHRONO24_HOST = "chrono24"


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)}", file=sys.stderr)


def norm_url(u: str | None) -> str:
    return (u or "").rstrip("/")


def parse_orig_price_and_currency(price_text, currency_field, price_eur):
    """Return (price, currency) in the original currency, derived from
    price_text and/or an explicit currency field. Falls back to
    (price_eur, 'EUR') when nothing else can be determined."""
    if currency_field:
        currency_field = currency_field.upper()
    text = (price_text or "").strip()

    if text.startswith("£"):
        num = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return (float(num) if "." in num else int(num)), "GBP"
        except ValueError:
            pass
    if text.startswith("$"):
        num = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return (float(num) if "." in num else int(num)), "USD"
        except ValueError:
            pass
    if "CHF" in text:
        num = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return (float(num) if "." in num else int(num)), "CHF"
        except ValueError:
            pass
    if "€" in text or currency_field == "EUR":
        stripped = text.replace("€", "").strip()
        if "," in stripped:
            stripped = stripped.replace(".", "").replace(",", ".")
            try:
                val = float(stripped)
                return (int(val) if val == int(val) else val), "EUR"
            except ValueError:
                pass
        elif "." in stripped:
            try:
                return int(stripped.replace(".", "")), "EUR"
            except ValueError:
                pass
        else:
            try:
                return int(stripped), "EUR"
            except ValueError:
                pass

    return price_eur, (currency_field or "EUR")


def collect_live_listings():
    """Return {normalized_url: {ref, seller, country, type, seen, price_eur,
    price_text, currency}} from the current watches.json offers
    (kind=="listing", price_eur not null) and dealer_listings.json
    "listings" (kind=="listing")."""
    live = {}

    watches = load_json(DATA / "watches.json").get("watches") or []
    for w in watches:
        ref = w.get("ref")
        for o in w.get("offers") or []:
            if o.get("kind") != "listing" or o.get("price_eur") is None:
                continue
            url = norm_url(o.get("url"))
            if not url:
                continue
            live[url] = {
                "ref": ref,
                "seller": o.get("seller"),
                "country": o.get("country"),
                "type": o.get("type"),
                "seen": o.get("seen"),
                "price_eur": o.get("price_eur"),
                "price_text": o.get("price_text"),
                "currency": o.get("currency"),
            }

    dealer_listings = load_json(DATA / "dealer_listings.json").get("listings") or []
    for item in dealer_listings:
        if item.get("kind") != "listing":
            continue
        url = norm_url(item.get("url"))
        if not url:
            continue
        rec = live.setdefault(url, {})
        rec.setdefault("ref", item.get("ref"))
        rec.setdefault("seller", item.get("seller"))
        rec.setdefault("country", item.get("country"))
        rec.setdefault("type", item.get("type"))
        rec.setdefault("seen", item.get("seen"))
        rec.setdefault("price_eur", item.get("price_eur"))
        rec.setdefault("price_text", item.get("price_text"))
        rec.setdefault("currency", item.get("currency"))

    return live


def merge_into_history(history: dict, live: dict):
    listings = history.setdefault("listings", {})
    new_urls = 0
    updated_urls = 0

    for url, info in live.items():
        price, currency = parse_orig_price_and_currency(
            info.get("price_text"), info.get("currency"), info.get("price_eur")
        )
        seen = info.get("seen")
        obs = {
            "date": seen,
            "price": price,
            "currency": currency,
            "price_eur": info.get("price_eur"),
            "price_text": info.get("price_text"),
        }

        if url not in listings:
            listings[url] = {
                "ref": info.get("ref"),
                "seller": info.get("seller"),
                "country": info.get("country"),
                "type": info.get("type"),
                "kind": "listing",
                "first_seen": seen,
                "last_seen": seen,
                "status": "active",
                "gone_date": None,
                "gone_http": None,
                "price_observations": [obs] if seen else [],
            }
            new_urls += 1
            continue

        rec = listings[url]
        changed = False

        if seen:
            if not rec.get("first_seen") or seen < rec["first_seen"]:
                rec["first_seen"] = seen
                changed = True
            if not rec.get("last_seen") or seen > rec["last_seen"]:
                rec["last_seen"] = seen
                changed = True

        existing_pairs = {
            (o.get("date"), o.get("price_eur")) for o in rec.get("price_observations", [])
        }
        if seen and (seen, info.get("price_eur")) not in existing_pairs:
            rec.setdefault("price_observations", []).append(obs)
            changed = True

        # fill in any missing descriptive fields opportunistically
        for k in ("ref", "seller", "country", "type"):
            if not rec.get(k) and info.get(k):
                rec[k] = info.get(k)

        if changed:
            updated_urls += 1

    return new_urls, updated_urls


def fetch_url(url: str, timeout: int = 20):
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"})
    with urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read()


def check_gone_candidates(history: dict, live_urls: set):
    """For every status=='active' listing not present in the current live
    snapshot, politely fetch its URL once and decide whether to mark it
    gone. Returns the count newly marked gone."""
    listings = history.get("listings") or {}
    candidates = [
        url for url, rec in listings.items()
        if rec.get("status") == "active" and url not in live_urls
    ]

    newly_gone = 0
    for url in candidates:
        if CHRONO24_HOST in url.lower():
            continue  # never scrape Chrono24

        rec = listings[url]
        try:
            code, raw = fetch_url(url)
        except HTTPError as e:
            if e.code == 404 or e.code >= 400:
                rec["status"] = "gone"
                rec["gone_date"] = date.today().isoformat()
                rec["gone_http"] = e.code
                newly_gone += 1
            # other HTTPErrors (e.g. 3xx weirdness) -- leave as-is
            continue
        except (URLError, TimeoutError, OSError):
            # network error: no evidence either way, leave status as-is
            continue
        except Exception:
            continue

        try:
            if code == 404 or code >= 400:
                rec["status"] = "gone"
                rec["gone_date"] = date.today().isoformat()
                rec["gone_http"] = code
                newly_gone += 1
                continue
            html = raw.decode("utf-8", errors="ignore").lower()
            if any(marker in html for marker in SOLD_MARKERS):
                rec["status"] = "gone"
                rec["gone_date"] = date.today().isoformat()
                rec["gone_http"] = code
                newly_gone += 1
            # else: 200 and no sold marker -- leave status unchanged (active)
        except Exception:
            continue

    return newly_gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check-gone",
        action="store_true",
        help="Re-verify listings that dropped out of the live snapshot by fetching their URL once.",
    )
    args = ap.parse_args()

    history_path = DATA / "listings_history.json"
    history = load_json(history_path) if history_path.exists() else {
        "updated": None,
        "timezone": TZ_NAME,
        "note": "Histórico semeado apenas com datas realmente observadas nos ficheiros do Radar. Sem datas inventadas.",
        "listings": {},
    }

    live = collect_live_listings()
    new_urls, updated_urls = merge_into_history(history, live)

    newly_gone = 0
    if args.check_gone:
        newly_gone = check_gone_candidates(history, set(live.keys()))

    history["updated"] = date.today().isoformat()
    history["timezone"] = history.get("timezone") or TZ_NAME

    dump_json(history_path, history)

    total = len(history.get("listings") or {})
    print(f"total listings: {total}")
    print(f"new URLs added: {new_urls}")
    print(f"updated (last_seen/new observation): {updated_urls}")
    if args.check_gone:
        print(f"newly marked gone: {newly_gone}")


if __name__ == "__main__":
    main()
