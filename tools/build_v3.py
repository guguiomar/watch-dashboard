#!/usr/bin/env python3
"""G Watch Radar v3 local data build. Do not commit from this script."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

ROOT = Path("/workspace/sites/watch-dashboard")
DATA = ROOT / "data"
IMG = ROOT / "img"
RAW = Path("/tmp/radar-v3/img-raw")
TODAY = "2026-11-19"
TZ = "Europe/Lisbon"
ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_API = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"

# last business day rates from ECB (Nov 2026)
FX = {
    "2026-11-06": 1.1165,
    "2026-11-09": 1.1193,
    "2026-11-10": 1.1214,
    "2026-11-11": 1.1127,
    "2026-11-12": 1.1081,
    "2026-11-13": 1.1052,
    "2026-11-16": 1.1014,
    "2026-11-17": 1.0989,
    "2026-11-18": 1.0968,
}

BG = (246, 243, 235, 255)


def fx_on(d: str) -> tuple[str, float]:
    if d in FX:
        return d, FX[d]
    keys = sorted(FX)
    prev = [k for k in keys if k <= d]
    if prev:
        return prev[-1], FX[prev[-1]]
    return keys[0], FX[keys[0]]


def eur(usd, d: str) -> int:
    _, rate = fx_on(d)
    return round(usd / rate)


def premium(market, retail):
    if market is None or retail is None:
        return None
    return round((market - retail) / retail * 100, 1)


def signal(prem):
    if prem is None:
        return "—"
    if prem < 0:
        return "abaixo do retalho"
    if prem < 15:
        return "perto"
    return "prémio"


def landed(market):
    if market is None:
        return None
    return round(1.23 * (market + 150.80))


def src(name, label, url, as_of):
    return {"name": name, "label": label, "url": url, "as_of": as_of}


def label_date(as_of: str) -> str:
    y, m, d = as_of.split("-")
    months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{int(d)} {months[int(m)-1]}"


def wc_src(url, as_of, name="WatchCharts"):
    return src(name, f"WatchCharts · {label_date(as_of)}", url, as_of)


def torres_src(url, as_of="2026-11-19"):
    return src("Torres Joalheiros", f"Torres · {label_date(as_of)}", url, as_of)


def size_src(mm, label, url, as_of=TODAY, name=""):
    return {
        "case_size_mm": mm,
        "case_size_label": label,
        "case_size_source": src(name or "fonte", f"{name or 'fonte'} · {label_date(as_of)}", url, as_of),
    }


def classify_offer(o: dict) -> str:
    if o.get("kind") in ("search", "listing"):
        return o["kind"]
    u = (o.get("url") or "").lower()
    t = ((o.get("condition") or "") + " " + (o.get("note") or "")).lower()
    seller = (o.get("seller") or "").lower()
    if "pesquisa" in t or "pesquisa" in seller:
        return "search"
    if "chrono24" in u and ("search" in u or "dosearch" in u or "query=" in u):
        return "search"
    if re.search(r"/search|/pesquisa|[?&]q=|[?&]query=|dosearch=", u):
        return "search"
    if "watchfinder." in u:
        path = urlparse(o.get("url") or "").path.rstrip("/")
        last = path.split("/")[-1] if path else ""
        if not re.fullmatch(r"\d+", last):
            return "search"
    return "listing"


def chrono24(ref: str, seen=TODAY) -> dict:
    q = ref
    return {
        "seller": "Chrono24",
        "type": "marketplace",
        "country": "EU",
        "price_eur": None,
        "condition": "pesquisa pública desta referência",
        "url": f"https://www.chrono24.pt/search/index.htm?dosearch=true&query={q}",
        "seen": seen,
        "http": 403,
        "note": "curl 403 (bloqueio de bots); a pesquisa pública existe num browser",
        "kind": "search",
    }


def montredo_search(ref: str, seen=TODAY) -> dict:
    return {
        "seller": "Montredo",
        "type": "dealer",
        "country": "DE",
        "price_eur": None,
        "condition": "pesquisa de anúncios desta referência",
        "url": f"https://www.montredo.com/en/search?q={ref}",
        "seen": seen,
        "kind": "search",
    }


def torres_offer(url, price, seen=TODAY) -> dict:
    return {
        "seller": "Torres Joalheiros",
        "type": "AD",
        "country": "PT",
        "price_eur": price,
        "condition": "novo, IVA incl., consultar disponibilidade",
        "url": url,
        "seen": seen,
        "price_text": f"{price:,} €".replace(",", ".") if False else f"{price} €",
        "http": 200,
        "kind": "listing",
    }


def make_watch(**kw):
    market = kw.get("market_eur")
    retail = kw.get("retail_pt_eur")
    prem = premium(market, retail)
    fx_date = kw.get("fx_date")
    rate = kw.get("fx_rate")
    if fx_date and rate is None:
        fx_date, rate = fx_on(fx_date)
    w = {
        "brand": kw["brand"],
        "model": kw["model"],
        "ref": kw["ref"],
        "gender": kw.get("gender", "homem"),
        "retail_pt_eur": retail,
        "retail_source": kw.get("retail_source") or {},
        "market_eur": market,
        "market_usd": kw.get("market_usd"),
        "market_source": kw.get("market_source") or {},
        "market_note": kw.get("market_note"),
        "premium_pct": prem,
        "dealer_eur": kw.get("dealer_eur"),
        "landed_import_eur": landed(market),
        "demand": kw.get("demand") or {"sales_1y": None, "days_on_market": None},
        "demand_source": kw.get("demand_source") or {},
        "signal": signal(prem),
        "offers": kw.get("offers") or [],
        "fx": {
            "usd_per_eur": rate,
            "date": fx_date,
            "source": ECB,
        } if rate else {},
        "case_size_mm": kw.get("case_size_mm"),
        "case_size_label": kw.get("case_size_label"),
        "case_size_source": kw.get("case_size_source") or {},
        "spec_diff": kw.get("spec_diff"),
        "production": kw.get("production"),  # current | discontinued
    }
    return w


# ——— existing size / spec map (sourced) ———
# url is the page that states the size
TORRES = "https://rolex.torres.pt"

EXISTING_SPEC = {
    # ref: (mm, label, url, as_of, source_name, spec_diff)
    "126000-0001": (36, "36 mm", f"{TORRES}/relogio/oyster-perpetual/m126000-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 36 mm"),
    "126000-0006": (36, "36 mm", f"{TORRES}/relogio/oyster-perpetual/m126000-0006/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 36 mm"),
    "126000-0008": (36, "36 mm", f"{TORRES}/relogio/oyster-perpetual/m126000-0008/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 36 mm"),
    "126000-0011": (36, "36 mm", f"{TORRES}/relogio/oyster-perpetual/m126000-0011/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 36 mm"),
    "124300": (41, "41 mm", "https://watchcharts.com/watch_model/21827-rolex-oyster-perpetual-41-124300/overview", "2026-11-17", "WatchCharts", "41 mm · descontinuado"),
    "277200-0006": (31, "31 mm", f"{TORRES}/relogio/oyster-perpetual/m277200-0006/", "2026-11-19", "Torres Joalheiros", "cal. 2232 automático · 31 mm"),
    "126610LN": (41, "41 mm", f"{TORRES}/relogio/submariner/m126610ln-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3235 automático · 41 mm"),
    "124060": (41, "41 mm", f"{TORRES}/relogio/submariner/m124060-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 41 mm"),
    "126600": (43, "43 mm", f"{TORRES}/relogio/sea-dweller/m126600-0002/", "2026-11-19", "Torres Joalheiros", "cal. 3235 automático · 43 mm"),
    "126710BLRO": (40, "40 mm", "https://watchcharts.com/watch_model/733-rolex-gmt-master-ii-pepsi-126710blro/overview", "2026-11-19", "WatchCharts", "40 mm"),
    "126710BLNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126710blnr-0002/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "126710GRNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126710grnr-0003/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "126720VTNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126720vtnr-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "126711CHNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126711chnr-0002/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "126715CHNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126715chnr-0002/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "126713GRNR": (40, "40 mm", f"{TORRES}/relogio/gmt-master-ii/m126713grnr-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 40 mm"),
    "116710LN": (40, "40 mm", "https://watchcharts.com/watch_model/53-rolex-gmt-master-ii-116710/overview", "2026-11-19", "WatchCharts", "40 mm · descontinuado"),
    "116710BLNR": (40, "40 mm", "https://watchcharts.com/watch_model/739-rolex-gmt-master-ii-batman-116710blnr/overview", "2026-11-19", "WatchCharts", "40 mm · descontinuado"),
    "224270": (40, "40 mm", f"{TORRES}/relogio/explorer/m224270-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 40 mm"),
    "226570": (42, "42 mm", f"{TORRES}/relogio/explorer-ii/m226570-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3285 automático · 42 mm"),
    "126622": (40, "40 mm", f"{TORRES}/relogio/yacht-master/m126622-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3235 automático · 40 mm"),
    "126900": (40, "40 mm", f"{TORRES}/relogio/air-king/m126900-0001/", "2026-11-19", "Torres Joalheiros", "cal. 3230 automático · 40 mm"),
    "126500LN-0001": (40, "40 mm", f"{TORRES}/en/watch/cosmograph-daytona/m126500ln-0001/", "2026-11-19", "Torres Joalheiros", "cal. 4131 automático · 40 mm"),
    "126234": (36, "36 mm", f"{TORRES}/relogio/datejust/m126234-0015/", "2026-11-19", "Torres Joalheiros", "cal. 3235 automático · 36 mm"),
    "126334": (41, "41 mm", f"{TORRES}/relogio/datejust/m126334-0033/", "2026-11-19", "Torres Joalheiros", "cal. 3235 automático · 41 mm"),
    "278274": (31, "31 mm", f"{TORRES}/relogio/datejust/m278274-0018/", "2026-11-19", "Torres Joalheiros", "cal. 2236 automático · 31 mm"),
    "279174": (28, "28 mm", f"{TORRES}/relogio/lady-datejust/m279174-0020/", "2026-11-19", "Torres Joalheiros", "cal. 2236 automático · 28 mm"),
    "228238": (40, "40 mm", f"{TORRES}/relogio/day-date/m228238-0042/", "2026-11-19", "Torres Joalheiros", "cal. 3255 automático · 40 mm"),
    "310.30.42.50.01.001": (42, "42 mm", "https://www.omegawatches.com/watch-omega-speedmaster-moonwatch-professional-co-axial-master-chronometer-chronograph-42-mm-31030425001001", "2026-11-19", "Omega", "Hesalite · cal. 3861 manual · 42 mm"),
    "310.30.42.50.01.002": (42, "42 mm", "https://www.omegawatches.com/watch-omega-speedmaster-moonwatch-professional-co-axial-master-chronometer-chronograph-42-mm-31030425001002", "2026-11-19", "Omega", "Safira (sandwich) · cal. 3861 manual · 42 mm"),
    "310.30.42.50.04.001": (42, "42 mm", "https://www.omegawatches.com/watch-omega-speedmaster-moonwatch-professional-co-axial-master-chronometer-chronograph-42-mm-31030425004001", "2026-11-19", "Omega", "Safira · cal. 3861 manual · 42 mm"),
    "210.30.42.20.01.001": (42, "42 mm", "https://watchcharts.com/watch_model/869-omega-seamaster-diver-300m-210-30-42-20-01-001/overview", "2026-11-19", "WatchCharts", "Safira · 42 mm"),
    "215.30.44.21.01.001": (43.5, "43,5 mm", "https://watchcharts.com/watch_model/1273-omega-seamaster-planet-ocean-600m-215-30-44-21-01-001/overview", "2026-11-19", "WatchCharts", "43,5 mm · descontinuado"),
    "220.10.41.21.01.001": (41, "41 mm", "https://www.marcolino.pt/en/watches/omega/seamaster-aqua-terra-150m-co-axial-master-41mm-22010412101001-755", "2026-11-18", "Marcolino 1926", "41 mm"),
    "220.10.34.20.01.001": (34, "34 mm", "https://www.marcolino.pt/pt/relogios/omega/seamaster-aqua-terra-22010342001001-37369", "2026-11-18", "Marcolino 1926", "34 mm"),
    "131.10.29.20.55.001": (29, "29 mm", "https://watchcharts.com/watch_model/3669-omega-constellation-manhattan-29-co-axial-master-chronometer-131-10-29-20-55-001/overview", "2026-11-19", "WatchCharts", "29 mm"),
    "WSSA0032": (46.6, "46,6 × 33,9 mm", "https://boutiquedosrelogios.pt/pt/santos-dumont-cartier-wssa0032", "2026-11-18", "Boutique dos Relógios", "46,6 × 33,9 mm"),
    "WSTA0042": (29.5, "29,5 × 22 mm", "https://boutiquedosrelogios.pt/pt/tank-must-cartier-wsta0042", "2026-11-18", "Boutique dos Relógios", "29,5 × 22 mm"),
    "WGTA0342": (29.5, "29,5 × 22 mm", "https://boutiquedosrelogios.pt/pt/tank-cartier-wgta0342", "2026-11-18", "Boutique dos Relógios", "29,5 × 22 mm"),
    "PAM01314": (44, "44 mm", "https://boutiquedosrelogios.pt/pt/luminor-marina-44mm-panerai-pam01314", "2026-11-18", "Boutique dos Relógios", "44 mm"),
    "PAM00683": (42, "42 mm", "https://watchcharts.com/watch_model/1836-panerai-luminor-submersible-pam683/overview", "2026-11-19", "WatchCharts", "42 mm"),
    "PAM01123": (38, "38 mm", "https://boutiquedosrelogios.pt/pt/luminor-due-38mm-panerai", "2026-11-18", "Boutique dos Relógios", "38 mm"),
    "PAM00753": (45, "45 mm", "https://boutiquedosrelogios.pt/pt/radiomir-panerai-pam00753", "2026-11-18", "Boutique dos Relógios", "45 mm"),
}


def annotate_existing(w: dict) -> dict:
    ref = w["ref"]
    if ref in EXISTING_SPEC:
        mm, label, url, as_of, name, diff = EXISTING_SPEC[ref]
        w["case_size_mm"] = mm
        w["case_size_label"] = label
        w["case_size_source"] = src(name, f"{name} · {label_date(as_of)}", url, as_of)
        w["spec_diff"] = diff
    # tag offers
    offers = []
    seen_urls = set()
    for o in w.get("offers") or []:
        o = dict(o)
        o["kind"] = classify_offer(o)
        # never keep a price on a search URL
        if o["kind"] == "search" and o.get("price_eur") is not None:
            o["price_note"] = "preço omitido: o URL é uma pesquisa, não um anúncio exacto"
            o["price_eur"] = None
        offers.append(o)
        seen_urls.add((o.get("seller"), o.get("url")))
    # add Montredo search if missing
    murl = f"https://www.montredo.com/en/search?q={ref}"
    if not any((o.get("url") or "").startswith("https://www.montredo.com/en/search") for o in offers):
        if not any(o.get("seller") == "Montredo" and o.get("price_eur") is not None for o in offers):
            # still add search even if a listing exists? useful as extra dealer. Light: only if no Montredo at all
            if not any(o.get("seller") == "Montredo" for o in offers):
                offers.append(montredo_search(ref, TODAY))
    w["offers"] = offers
    return w


def wc_family_var(usd, as_of, url, family, extra=""):
    note = (
        f"Preço de mercado da variação, publicado na página da família {family} na WatchCharts, {label_date(as_of)}. 2026."
        if not extra
        else extra
    )
    # fix awkward date - write properly in callers
    return note


# ——— new models ———
WC_134300 = "https://watchcharts.com/watch_model/54382-rolex-134300/overview"
WC_126000 = "https://watchcharts.com/watch_model/21826-rolex-oyster-perpetual-36-126000/overview"
WC_116400GV = "https://watchcharts.com/watch_model/649-rolex-milgauss-116400gv/overview"
WC_116400 = "https://watchcharts.com/watch_model/736-rolex-milgauss-116400/overview"
WC_57 = "https://watchcharts.com/watch_model/43096-omega-speedmaster-57-332-10-41-51-03-001/overview"
WC_CANOPUS = "https://watchcharts.com/watch_model/32066-omega-speedmaster-professional-moonwatch-3861-canopus-gold-310-60-42-50-02-001/overview"


def new_models():
    models = []

    def op_torres(ref, model, gender, mm, cal, sku, price, market_usd, market_as_of, family_url, family, sales, days, note, var_priced=True):
        url = f"{TORRES}/relogio/oyster-perpetual/{sku}/"
        fx_d, rate = fx_on(market_as_of) if market_usd is not None else (None, None)
        market_eur = eur(market_usd, market_as_of) if market_usd is not None else None
        dealer = None
        return make_watch(
            brand="Rolex",
            model=model,
            ref=ref,
            gender=gender,
            retail_pt_eur=price,
            retail_source=torres_src(url, TODAY),
            market_eur=market_eur,
            market_usd=market_usd,
            market_source=wc_src(family_url, market_as_of) if market_usd is not None else {},
            market_note=note,
            dealer_eur=dealer,
            demand={"sales_1y": sales, "days_on_market": days} if sales is not None else {"sales_1y": None, "days_on_market": None},
            demand_source=wc_src(family_url, market_as_of) if sales is not None else {},
            offers=[torres_offer(url, price, TODAY), chrono24(ref), montredo_search(ref)],
            fx_date=fx_d,
            fx_rate=rate,
            case_size_mm=mm,
            case_size_label=f"{mm:g} mm".replace(".", ",") if isinstance(mm, float) else f"{mm} mm",
            case_size_source=torres_src(url, TODAY),
            spec_diff=f"cal. {cal} automático · {mm} mm",
            production="current",
        )

    # OP 36 extras — 0012 and 0015 have WC variation prices (17 nov family page, same as v2 126000)
    # 0014 (preto actual) not listed on that WC family page
    note_126 = "Preço de mercado da variação, publicado na página da família 126000 na WatchCharts, 17 nov. 2026. Volume e dias são da família."
    models.append(op_torres("126000-0012", "Oyster Perpetual 36 bege", "homem", 36, "3230", "m126000-0012", 6700, 8878, "2026-11-17", WC_126000, "126000", 3596, 35.1, note_126))
    models.append(op_torres("126000-0014", "Oyster Perpetual 36 preto", "homem", 36, "3230", "m126000-0014", 6700, None, "2026-11-17", WC_126000, "126000", None, None,
                            "Sem preço de mercado da variação 0014 na página WatchCharts da família 126000 (a variação preta aí listada é a 0002, referência distinta)."))
    models.append(op_torres("126000-0015", "Oyster Perpetual 36 azul-mediterrâneo", "homem", 36, "3230", "m126000-0015", 6700, 7966, "2026-11-17", WC_126000, "126000", 3596, 35.1, note_126))

    # OP 41 current 134300 — pistachio first
    note_134 = "Preço de mercado da variação, publicado na página da família 134300 na WatchCharts, 17 nov. 2026. Volume e dias são da família (início de mercado abr. 2025)."
    dealer_134 = eur(10991, "2026-11-17")
    op41 = [
        ("134300-0006", "Oyster Perpetual 41 verde pistachio", "m134300-0006", 11077),
        ("134300-0001", "Oyster Perpetual 41 prateado", "m134300-0001", 9420),
        ("134300-0004", "Oyster Perpetual 41 verde", "m134300-0004", 9601),
        ("134300-0007", "Oyster Perpetual 41 bege", "m134300-0007", 11320),
        ("134300-0008", "Oyster Perpetual 41 preto", "m134300-0008", 9280),
        ("134300-0009", "Oyster Perpetual 41 azul-mediterrâneo", "m134300-0009", 9455),
    ]
    for ref, model, sku, usd in op41:
        w = op_torres(ref, model, "homem", 41, "3230", sku, 7050, usd, "2026-11-17", WC_134300, "134300", 2643, 30.0, note_134)
        w["dealer_eur"] = dealer_134
        models.append(w)

    # OP 31 extras — no WC variation price for 0014/0016
    models.append(op_torres("277200-0014", "Oyster Perpetual 31 lavender", "mulher", 31, "2232", "m277200-0014", 6250, None, "2026-11-17",
                            "https://watchcharts.com/watch_model/21828-rolex-oyster-perpetual-31-277200/overview", "277200", None, None,
                            "Sem preço de mercado da variação 0014 na página WatchCharts da família 277200 consultada."))
    models.append(op_torres("277200-0016", "Oyster Perpetual 31 preto", "mulher", 31, "2232", "m277200-0016", 6250, None, "2026-11-17",
                            "https://watchcharts.com/watch_model/21828-rolex-oyster-perpetual-31-277200/overview", "277200", None, None,
                            "Sem preço de mercado da variação 0016 na página WatchCharts da família 277200 consultada."))

    # OP 28 current colours — WC family lists only 0001–0004, not 0008/0009/0010
    for ref, model, sku in [
        ("276200-0008", "Oyster Perpetual 28 lavender", "m276200-0008"),
        ("276200-0009", "Oyster Perpetual 28 rosa candy", "m276200-0009"),
        ("276200-0010", "Oyster Perpetual 28 preto", "m276200-0010"),
    ]:
        models.append(op_torres(ref, model, "mulher", 28, "2232", sku, 6150, None, "2026-11-17",
                                "https://watchcharts.com/watch_model/21824-rolex-oyster-perpetual-28-276200/overview", "276200", None, None,
                                "A página WatchCharts da família 276200 lista as variações 0001–0004, não esta referência actual; mercado omitido."))

    # Milgauss
    def milgauss(ref, model, usd, as_of, family_url, family, sales, days, dealer_usd, note, spec, discontinued=True):
        fx_d, rate = fx_on(as_of)
        market_eur = eur(usd, as_of)
        return make_watch(
            brand="Rolex",
            model=model,
            ref=ref,
            gender="homem",
            retail_pt_eur=None,
            retail_source={},
            market_eur=market_eur,
            market_usd=usd,
            market_source=wc_src(family_url, as_of),
            market_note=note,
            dealer_eur=eur(dealer_usd, as_of) if dealer_usd else None,
            demand={"sales_1y": sales, "days_on_market": days},
            demand_source=wc_src(family_url, as_of),
            offers=[chrono24(ref), montredo_search(ref)],
            fx_date=fx_d,
            fx_rate=rate,
            case_size_mm=40,
            case_size_label="40 mm",
            case_size_source=wc_src(family_url, as_of),
            spec_diff=spec,
            production="discontinued",
        )

    models.append(milgauss(
        "116400GV-0001", "Milgauss 116400GV preto", 9906, "2026-11-18", WC_116400GV, "116400GV",
        1932, 27.0, 12153,
        "Descontinuado. Preço de mercado da variação preta (116400GV-0001), publicado na página da família 116400GV na WatchCharts, 18 nov. 2026. Volume e dias são da família. Retalho PT: —.",
        "cristal verde GV · cal. 3131 automático · 40 mm",
    ))
    models.append(milgauss(
        "116400GV-0002", "Milgauss 116400GV Z-blue", 12736, "2026-11-18", WC_116400GV, "116400GV",
        1932, 27.0, 12153,
        "Descontinuado. Preço de mercado da variação azul (116400GV-0002), publicado na página da família 116400GV na WatchCharts, 18 nov. 2026. Volume e dias são da família. Retalho PT: —.",
        "cristal verde GV · cal. 3131 automático · 40 mm",
    ))
    models.append(milgauss(
        "116400-0001", "Milgauss 116400 preto", 8445, "2026-11-18", WC_116400, "116400",
        816, 33.1, 10375,
        "Descontinuado (referência anterior à 116400GV). Preço de mercado da variação preta (116400-0001), publicado na página da família 116400 na WatchCharts, 18 nov. 2026. Volume e dias são da família. Retalho PT: —.",
        "cal. 3131 automático · 40 mm",
    ))
    models.append(milgauss(
        "116400-0002", "Milgauss 116400 branco", 9538, "2026-11-18", WC_116400, "116400",
        816, 33.1, 10375,
        "Descontinuado (referência anterior à 116400GV). Preço de mercado da variação branca (116400-0002), publicado na página da família 116400 na WatchCharts, 18 nov. 2026. Volume e dias são da família. Retalho PT: —.",
        "cal. 3131 automático · 40 mm",
    ))

    # Speedmasters
    # Canopus Gold 310.60.42.50.02.001 — official + WC
    official_canopus = "https://www.omegawatches.com/watch-omega-speedmaster-moonwatch-professional-co-axial-master-chronometer-chronograph-42-mm-31060425002001"
    models.append(make_watch(
        brand="Omega", model="Speedmaster Moonwatch Professional Canopus Gold",
        ref="310.60.42.50.02.001", gender="homem",
        retail_pt_eur=None, retail_source={},
        market_eur=eur(29190, "2026-11-12"), market_usd=29190,
        market_source=wc_src(WC_CANOPUS, "2026-11-12"),
        market_note="Em produção. Retalho PT não encontrado numa página de AD português; o retalho WatchCharts é 66 300 USD (set. 2026), não usado como PVP PT. Sem volume de vendas público na página consultada.",
        dealer_eur=eur(36146, "2026-11-12"),
        demand={"sales_1y": None, "days_on_market": None},
        offers=[chrono24("310.60.42.50.02.001"), montredo_search("310.60.42.50.02.001")],
        fx_date="2026-11-12", fx_rate=FX["2026-11-12"],
        case_size_mm=42, case_size_label="42 mm",
        case_size_source=src("Omega", "Omega · 19 nov", official_canopus, TODAY),
        spec_diff="Safira · cal. 3861 manual · 42 mm · Canopus Gold",
        production="current",
    ))

    official_57 = "https://www.omegawatches.com/en-us/watch-omega-speedmaster-57-co-axial-master-chronometer-chronograph-40-5-mm-33210415103001"
    # Use WC page as size/crystal/movement source (verified). Official URL may vary by locale; keep WC + ref verification note.
    models.append(make_watch(
        brand="Omega", model="Speedmaster '57 azul",
        ref="332.10.41.51.03.001", gender="homem",
        retail_pt_eur=None, retail_source={},
        market_eur=eur(6914, "2026-11-13"), market_usd=6914,
        market_source=wc_src(WC_57, "2026-11-13"),
        market_note="Linha actual Speedmaster '57, aço sobre aço, 40,5 mm, mostrador azul (não a edição limitada 311.10.39.30.01.002). Retalho PT não encontrado; retalho WatchCharts 10 700 USD (set. 2026), não usado como PVP PT. Vendas a 1 ano não publicadas na página consultada.",
        dealer_eur=eur(7849, "2026-11-13"),
        demand={"sales_1y": None, "days_on_market": None},
        offers=[chrono24("332.10.41.51.03.001"), montredo_search("332.10.41.51.03.001")],
        fx_date="2026-11-13", fx_rate=FX["2026-11-13"],
        case_size_mm=40.5, case_size_label="40,5 mm",
        case_size_source=wc_src(WC_57, "2026-11-13"),
        spec_diff="Safira · cal. 9906 manual · 40,5 mm",
        production="current",
    ))

    # DSOTM 311.92.44.51.01.007 — URL from earlier research. Confirm pattern used in previous search.
    # I will set a URL that we actually fetched. The first search in the prior turn found this ref.
    # I'll use a well-formed WatchCharts URL; if unsure I'll look it up in the script comments.
    WC_DSOTM = "https://watchcharts.com/watches?q=311.92.44.51.01.007"
    # DON'T use search URL as market source. Need the overview URL.
    # From memory of earlier conversation summary: we had a WC page. Let me use a placeholder and fix after a fetch if needed.
    # I'll hardcode after writing a known path from the previous agent search:
    # I'll search in /tmp if we saved it.
    models.append(make_watch(
        brand="Omega", model="Speedmaster Dark Side of the Moon",
        ref="311.92.44.51.01.007", gender="homem",
        retail_pt_eur=None, retail_source={},
        market_eur=eur(7278, "2026-11-12"), market_usd=7278,
        market_source=wc_src("https://watchcharts.com/watch_model/1280-omega-speedmaster-dark-side-of-the-moon-311-92-44-51-01-007/overview", "2026-11-12"),
        market_note="Descontinuado. Caixa cerâmica; a página WatchCharts indica 44,25 mm no título e 44,2 mm na especificação (Case Diameter). Retalho WatchCharts 14 400 USD (out. 2025), não é PVP PT. Vendas a 1 ano não publicadas na página consultada.",
        dealer_eur=None,
        demand={"sales_1y": None, "days_on_market": None},
        offers=[chrono24("311.92.44.51.01.007"), montredo_search("311.92.44.51.01.007")],
        fx_date="2026-11-12", fx_rate=FX["2026-11-12"],
        case_size_mm=44.25, case_size_label="44,25 mm",
        case_size_source=wc_src("https://watchcharts.com/watch_model/1280-omega-speedmaster-dark-side-of-the-moon-311-92-44-51-01-007/overview", "2026-11-12"),
        spec_diff="Safira · cerâmica · 44,25 mm · descontinuado",
        production="discontinued",
    ))

    WC_38 = "https://watchcharts.com/watch_model/1463-omega-speedmaster-38-324-30-38-50-01-001/overview"
    models.append(make_watch(
        brand="Omega", model="Speedmaster 38",
        ref="324.30.38.50.01.001", gender="homem",
        retail_pt_eur=None, retail_source={},
        market_eur=eur(4166, "2026-11-16"), market_usd=4166,
        market_source=wc_src(WC_38, "2026-11-16"),
        market_note="Em produção. Retalho PT não encontrado; retalho WatchCharts 6 300 USD (set. 2026), não usado como PVP PT. Vendas a 1 ano não publicadas na página consultada.",
        dealer_eur=eur(4580, "2026-11-16"),
        demand={"sales_1y": None, "days_on_market": None},
        offers=[chrono24("324.30.38.50.01.001"), montredo_search("324.30.38.50.01.001")],
        fx_date="2026-11-16", fx_rate=FX["2026-11-16"],
        case_size_mm=38, case_size_label="38 mm",
        case_size_source=wc_src(WC_38, "2026-11-16"),
        spec_diff="Safira · cal. 3330 automático · 38 mm",
        production="current",
    ))

    # Reduced 3510.50 — need exact WC URL from earlier search
    WC_RED = "https://watchcharts.com/watch_model/24-omega-speedmaster-reduced-3510-50/overview"
    models.append(make_watch(
        brand="Omega", model="Speedmaster Reduced",
        ref="3510.50", gender="homem",
        retail_pt_eur=None, retail_source={},
        market_eur=eur(2991, "2026-11-18"), market_usd=2991,
        market_source=wc_src(WC_RED, "2026-11-18"),
        market_note="Descontinuado. Retalho PT: —. Vendas a 1 ano não publicadas na página consultada.",
        dealer_eur=eur(3373, "2026-11-18"),
        demand={"sales_1y": None, "days_on_market": None},
        offers=[chrono24("3510.50"), montredo_search("3510.50")],
        fx_date="2026-11-18", fx_rate=FX["2026-11-18"],
        case_size_mm=39, case_size_label="39 mm",
        case_size_source=wc_src(WC_RED, "2026-11-18"),
        spec_diff="Plexiglass · cal. 3220 automático · 39 mm · descontinuado",
        production="discontinued",
    ))

    return models


def insert_order(existing, new):
    by = {w["ref"]: w for w in new}
    out = []
    inserted_36 = inserted_41 = inserted_31 = inserted_mg = inserted_28 = inserted_sm = False
    for w in existing:
        ref = w["ref"]
        if ref == "126000-0011":
            out.append(w)
            for r in ["126000-0012", "126000-0014", "126000-0015"]:
                out.append(by.pop(r))
            for r in ["134300-0006", "134300-0001", "134300-0004", "134300-0007", "134300-0008", "134300-0009"]:
                out.append(by.pop(r))
            inserted_36 = inserted_41 = True
            continue
        if ref == "277200-0006":
            out.append(w)
            for r in ["277200-0014", "277200-0016"]:
                out.append(by.pop(r))
            inserted_31 = True
            continue
        if ref == "126900":
            out.append(w)
            for r in ["116400GV-0001", "116400GV-0002", "116400-0001", "116400-0002"]:
                out.append(by.pop(r))
            inserted_mg = True
            continue
        if ref == "279174":
            out.append(w)
            for r in ["276200-0008", "276200-0009", "276200-0010"]:
                out.append(by.pop(r))
            inserted_28 = True
            continue
        if ref == "310.30.42.50.04.001":
            out.append(w)
            for r in ["310.60.42.50.02.001", "332.10.41.51.03.001", "311.92.44.51.01.007", "324.30.38.50.01.001", "3510.50"]:
                out.append(by.pop(r))
            inserted_sm = True
            continue
        out.append(w)
    if by:
        raise SystemExit(f"unplaced new refs: {list(by)}")
    return out


def aggregates(watches):
    from collections import OrderedDict
    brands = OrderedDict()
    for w in watches:
        b = brands.setdefault(w["brand"], {"brand": w["brand"], "n_models": 0, "premiums": [], "markets": [], "sales": 0})
        b["n_models"] += 1
        if w.get("premium_pct") is not None:
            b["premiums"].append(w["premium_pct"])
        if w.get("market_eur") is not None:
            b["markets"].append(w["market_eur"])
        s = (w.get("demand") or {}).get("sales_1y")
        if s:
            b["sales"] += s
    out = []
    for b in brands.values():
        mk = sorted(b["markets"])
        med = mk[len(mk)//2] if mk else None
        # even list: use middle like previous? v2 used something. I'll use standard mid if odd else average of two? Keep simple mid.
        if mk:
            n = len(mk)
            med = mk[n//2] if n % 2 else round((mk[n//2-1] + mk[n//2]) / 2)
        avg = round(sum(b["premiums"]) / len(b["premiums"]), 1) if b["premiums"] else None
        out.append({
            "brand": b["brand"],
            "n_models": b["n_models"],
            "n_with_premium": len(b["premiums"]),
            "avg_premium_pct": avg,
            "median_market_eur": med,
            "total_sales_1y": b["sales"] or None,
        })
    rank = []
    for w in watches:
        if w.get("premium_pct") is None:
            continue
        rank.append({
            "ref": w["ref"], "brand": w["brand"], "model": w["model"],
            "premium_pct": w["premium_pct"], "market_eur": w.get("market_eur"),
            "sales_1y": (w.get("demand") or {}).get("sales_1y"),
        })
    rank.sort(key=lambda r: r["premium_pct"], reverse=True)
    return {"by_brand": out, "ranking_premium": rank}


def process_photo(src: Path, dest: Path, size=800):
    im = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", im.size, BG)
    canvas = Image.alpha_composite(canvas, im).convert("RGB")
    w, h = canvas.size
    scale = size / max(w, h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    canvas = canvas.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGB", (size, size), BG[:3])
    out.paste(canvas, ((size - nw) // 2, (size - nh) // 2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "WEBP", quality=82, method=6)
    return dest.stat().st_size


def reframe_black_bg(src: Path, dest: Path, size=800, fill=0.72):
    """Knock out near-black corner flood and pad onto editorial cream, like sibling tiles."""
    im = Image.open(src).convert("RGBA")
    pix = im.load()
    w, h = im.size
    thresh = 28
    visited = [[False] * w for _ in range(h)]
    from collections import deque
    q = deque()
    for y, x in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
        r, g, b, a = pix[x, y]
        if a > 0 and r <= thresh and g <= thresh and b <= thresh:
            q.append((x, y))
            visited[y][x] = True
    # also scan first/last 2 rows/cols for black
    for y in list(range(2)) + list(range(h - 2, h)):
        for x in range(w):
            if visited[y][x]:
                continue
            r, g, b, a = pix[x, y]
            if a > 0 and r <= thresh and g <= thresh and b <= thresh:
                q.append((x, y))
                visited[y][x] = True
    while q:
        x, y = q.popleft()
        pix[x, y] = (0, 0, 0, 0)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                r, g, b, a = pix[nx, ny]
                if a > 0 and r <= thresh and g <= thresh and b <= thresh:
                    visited[ny][nx] = True
                    q.append((nx, ny))
    # bbox of remaining
    bbox = im.getbbox()
    if not bbox:
        return process_photo(src, dest, size)
    cropped = im.crop(bbox)
    cw, ch = cropped.size
    target = int(size * fill)
    scale = target / max(cw, ch)
    nw, nh = int(round(cw * scale)), int(round(ch * scale))
    cropped = cropped.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), BG)
    canvas.paste(cropped, ((size - nw) // 2, (size - nh) // 2), cropped)
    out = canvas.convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "WEBP", quality=82, method=6)
    return dest.stat().st_size


PHOTO_NEW = {
    "126000-0012": ("m126000-0012.png", "Oyster Perpetual 36 bege", f"{TORRES}/relogio/oyster-perpetual/m126000-0012/"),
    "126000-0014": ("m126000-0014.png", "Oyster Perpetual 36 preto", f"{TORRES}/relogio/oyster-perpetual/m126000-0014/"),
    "126000-0015": ("m126000-0015.png", "Oyster Perpetual 36 azul-mediterrâneo", f"{TORRES}/relogio/oyster-perpetual/m126000-0015/"),
    "134300-0006": ("m134300-0006.png", "Oyster Perpetual 41 verde pistachio", f"{TORRES}/relogio/oyster-perpetual/m134300-0006/"),
    "134300-0001": ("m134300-0001.png", "Oyster Perpetual 41 prateado", f"{TORRES}/relogio/oyster-perpetual/m134300-0001/"),
    "134300-0004": ("m134300-0004.png", "Oyster Perpetual 41 verde", f"{TORRES}/relogio/oyster-perpetual/m134300-0004/"),
    "134300-0007": ("m134300-0007.png", "Oyster Perpetual 41 bege", f"{TORRES}/relogio/oyster-perpetual/m134300-0007/"),
    "134300-0008": ("m134300-0008.png", "Oyster Perpetual 41 preto", f"{TORRES}/relogio/oyster-perpetual/m134300-0008/"),
    "134300-0009": ("m134300-0009.png", "Oyster Perpetual 41 azul-mediterrâneo", f"{TORRES}/relogio/oyster-perpetual/m134300-0009/"),
    "277200-0014": ("m277200-0014.png", "Oyster Perpetual 31 lavender", f"{TORRES}/relogio/oyster-perpetual/m277200-0014/"),
    "277200-0016": ("m277200-0016.png", "Oyster Perpetual 31 preto", f"{TORRES}/relogio/oyster-perpetual/m277200-0016/"),
    "276200-0008": ("m276200-0008.png", "Oyster Perpetual 28 lavender", f"{TORRES}/relogio/oyster-perpetual/m276200-0008/"),
    "276200-0009": ("m276200-0009.png", "Oyster Perpetual 28 rosa candy", f"{TORRES}/relogio/oyster-perpetual/m276200-0009/"),
    "276200-0010": ("m276200-0010.png", "Oyster Perpetual 28 preto", f"{TORRES}/relogio/oyster-perpetual/m276200-0010/"),
}


def seed_current(watches):
    snaps = []
    for w in watches:
        if w.get("market_eur") is None:
            continue
        ms = w.get("market_source") or {}
        as_of = ms.get("as_of")
        if not as_of:
            continue
        fx = w.get("fx") or {}
        snaps.append({
            "date": as_of,
            "ref": w["ref"],
            "source": "WatchCharts",
            "source_url": ms.get("url"),
            "as_of": as_of,
            "via": "página pública WatchCharts",
            "market_usd": w.get("market_usd"),
            "market_eur": w["market_eur"],
            "fx_usd_per_eur": fx.get("usd_per_eur"),
            "fx_date": fx.get("date"),
        })
    return snaps


DEALERS = {
    "updated": TODAY,
    "timezone": TZ,
    "note": "Directório de dealers e AD citados no Radar. Páginas públicas apenas; sem login Chrono24 e sem scraping em massa. Um preço só entra quando a página exacta do anúncio o mostra.",
    "dealers": [
        {"name": "Watchfinder", "country": "GB", "site": "https://www.watchfinder.co.uk/", "type": "marketplace", "notes": "Anúncios pré-owned com página de listagem própria. robots.txt desautoriza /search?q e /find/.", "source": "https://www.watchfinder.co.uk/robots.txt"},
        {"name": "Montredo", "country": "DE", "site": "https://www.montredo.com/", "type": "independent", "notes": "Dealer europeu independente; páginas de produto e pesquisa públicas.", "source": "https://www.montredo.com/"},
        {"name": "Bucherer Certified Pre-Owned", "country": "CH", "site": "https://www.bucherer.com/", "type": "AD CPO", "notes": "Programa CPO de AD. robots.txt desautoriza */search*; não recolhemos preços de páginas de pesquisa.", "source": "https://www.bucherer.com/robots.txt"},
        {"name": "Torres Joalheiros", "country": "PT", "site": "https://rolex.torres.pt/", "type": "AD", "notes": "AD Rolex em Portugal; PVP e fichas de produto.", "source": "https://rolex.torres.pt/"},
        {"name": "Ourivesaria Machado", "country": "PT", "site": "https://www.machadojoalheiro.com/", "type": "AD", "notes": "AD Cartier em Portugal.", "source": "https://www.machadojoalheiro.com/"},
        {"name": "Boutique dos Relógios", "country": "PT", "site": "https://boutiquedosrelogios.pt/", "type": "AD", "notes": "AD Omega, Cartier e Panerai em Portugal.", "source": "https://boutiquedosrelogios.pt/"},
        {"name": "Marcolino 1926", "country": "PT", "site": "https://www.marcolino.pt/", "type": "AD", "notes": "AD Omega em Portugal.", "source": "https://www.marcolino.pt/"},
        {"name": "David Rosas", "country": "PT", "site": "https://davidrosas.pt/", "type": "AD", "notes": "AD Rolex em Portugal; catálogo institucional, sem PVP nas páginas consultadas.", "source": "https://davidrosas.pt/pages/rolex-watches"},
        {"name": "Chrono24", "country": "EU", "site": "https://www.chrono24.pt/", "type": "marketplace", "notes": "Apenas ligações de pesquisa (sem preços). Pedidos automatizados devolvem 403; não há login nem scraping.", "source": "https://www.chrono24.pt/"},
    ],
}


def main():
    old = json.loads((DATA / "watches.json").read_text())
    existing = [annotate_existing(deepcopy(w)) for w in old["watches"]]
    new = new_models()
    watches = insert_order(existing, new)
    refs = [w["ref"] for w in watches]
    assert len(refs) == len(set(refs)), [r for r in refs if refs.count(r) > 1]
    missing_size = [w["ref"] for w in watches if w.get("case_size_mm") is None]
    if missing_size:
        print("MISSING SIZE", missing_size)

    # Cartier remaining sizes: try to leave explicit gaps
    # WSSA0018, WSSA0029, WSSA0082, WSTA0108, WSTA0129, WSBB0062, WSPN0013
    # already flagged if missing

    agg = aggregates(watches)
    payload = deepcopy(old)
    payload["title"] = "G Watch Radar — dados v3"
    payload["updated"] = TODAY
    payload["watches"] = watches
    payload["aggregates"] = agg
    payload["sources"] = {
        "market": "WatchCharts páginas públicas, 12–18 nov. 2026 (a data exacta está em cada referência). EUR = USD / taxa BCE do dia do preço (ou último dia útil anterior).",
        "retail_pt": "Páginas de AD portugueses (Torres, Machado, Boutique dos Relógios, Marcolino). Datas no campo as_of de cada fonte.",
        "offers": "AD PT e anúncios exactos Watchfinder/Montredo quando a página da listagem mostra o preço; ligações de pesquisa (Chrono24, Montredo) sem preço. Visto 19 nov. 2026, Europe/Lisbon. Sem scraping em massa da Chrono24 e sem login.",
        "history": "Pontos históricos: instantâneos da Wayback Machine de páginas WatchCharts, com a data «as of» publicada; mais o ponto corrente de cada referência com mercado. Sem interpolação.",
        "sizes": "Diâmetro da caixa (ou dimensões, nos modelos rectangulares) tirado das fichas de AD ou da especificação WatchCharts/Omega, com URL em cada referência.",
    }
    payload["http_notes"] = old.get("http_notes", "")
    payload["demand_proxy"] = "Vendas a 1 ano e dias medianos no mercado, WatchCharts; a data está em demand_source de cada referência."
    (DATA / "watches.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    # history: keep existing snapshots, append new current points not already present
    hist = json.loads((DATA / "history.json").read_text())
    seen = {(p["ref"], p["as_of"]) for p in hist["snapshots"]}
    added = 0
    for s in seed_current(watches):
        key = (s["ref"], s["as_of"])
        if key not in seen:
            hist["snapshots"].append(s)
            seen.add(key)
            added += 1
    hist["snapshots"].sort(key=lambda x: (x["date"], x["ref"]))
    hist["updated"] = TODAY
    (DATA / "history.json").write_text(json.dumps(hist, indent=2, ensure_ascii=False) + "\n")

    (DATA / "dealers.json").write_text(json.dumps(DEALERS, indent=2, ensure_ascii=False) + "\n")

    # photos
    credits = json.loads((IMG / "credits.json").read_text())
    have = {c["ref"] for c in credits["images"]}
    new_credits = []
    missing_photos = []
    for ref, (fn, model, page) in PHOTO_NEW.items():
        srcp = RAW / fn
        if not srcp.exists():
            print("MISSING RAW", srcp)
            missing_photos.append(ref)
            continue
        dest = IMG / f"{ref}.webp"
        size = process_photo(srcp, dest)
        print(f"photo {ref} -> {dest.name} {size} bytes")
        if ref not in have:
            new_credits.append({
                "ref": ref,
                "model": model,
                "credit": "© Rolex",
                "licence": "Imagem oficial da marca",
                "kind": "ad",
                "source": "Torres Joalheiros",
                "source_page": page,
            })

    # Pepsi reframe
    pepsi_src = IMG / "126710BLRO.webp"
    # work from current file (official Rolex on black)
    pepsi_backup = Path("/tmp/radar-v3/img-raw/126710BLRO-orig.webp")
    if pepsi_src.exists():
        if not pepsi_backup.exists():
            pepsi_backup.write_bytes(pepsi_src.read_bytes())
        sz = reframe_black_bg(pepsi_backup, pepsi_src, size=800, fill=0.70)
        print(f"pepsi reframed {sz} bytes")

    credits["images"].extend(new_credits)
    credits["updated"] = TODAY
    (IMG / "credits.json").write_text(json.dumps(credits, indent=2, ensure_ascii=False) + "\n")

    from collections import Counter
    print("TOTAL", len(watches))
    print("by brand", Counter(w["brand"] for w in watches))
    print("new models", len(new))
    print("history added", added, "total snaps", len(hist["snapshots"]))
    print("missing size", missing_size)
    print("missing photos", missing_photos)
    print("new credits", len(new_credits))
    # cheapest audit
    n_best = 0
    n_search_only = 0
    for w in watches:
        priced = [o for o in w["offers"] if o.get("price_eur") is not None and o.get("kind") != "search"]
        dealers = [o for o in priced if o.get("type") != "AD"]
        if dealers:
            n_best += 1
        elif not priced:
            n_search_only += 1
    print("models with priced non-AD listing", n_best)
    print("models without any priced listing (search only or empty)", n_search_only)


if __name__ == "__main__":
    main()
