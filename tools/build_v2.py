#!/usr/bin/env python3
"""Build watches.json v2, history.json, process new photos, update credits.
Never invent prices; missing stays None. Do not commit/push.
"""
from __future__ import annotations

import json
import math
import statistics
from copy import deepcopy
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path("/workspace/sites/watch-dashboard")
DATA = ROOT / "data"
IMG = ROOT / "img"
RAW = Path("/tmp/radar-v2/img-raw")

FX = {
    "2022-10-20": 0.9811,
    "2022-10-24": 0.9851,
    "2022-11-09": 1.0039,
    "2023-03-10": 1.0586,
    "2023-05-18": 1.0813,  # AT41 already in EUR
    "2023-12-03": 1.0875,  # ECB 2023-12-01
    "2023-12-15": 1.0946,
    "2025-03-09": 1.0857,  # ECB 2025-03-07
    "2025-03-17": 1.0903,
    "2025-04-10": 1.1082,
    "2025-04-15": 1.1324,
    "2025-07-14": 1.1690,
    "2025-08-02": 1.1404,  # ECB 2025-08-01
    "2025-11-04": 1.1491,
    "2026-01-06": 1.1707,
    "2026-10-17": 1.1253,  # ECB 2026-10-16
    "2026-11-13": 1.1052,
    "2026-11-16": 1.1014,
    "2026-11-17": 1.0989,
    "2026-11-18": 1.0968,
}
FX_USED = {
    "2023-12-03": "2023-12-01",
    "2025-03-09": "2025-03-07",
    "2025-08-02": "2025-08-01",
    "2026-10-17": "2026-10-16",
}

def eur_from_usd(usd, as_of):
    fx = FX[as_of]
    return int(round(usd / fx)), fx, FX_USED.get(as_of, as_of)

def landed(market_eur):
    if market_eur is None:
        return None
    return int(round(1.23 * (market_eur + 150.80)))

def premium(market, retail):
    if market is None or retail is None or retail == 0:
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

def wc(name, url, as_of="2026-11-17"):
    d, m = as_of.split("-")[2], int(as_of.split("-")[1])
    months = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
    label = f"WatchCharts · {int(d)} {months[m-1]}"
    return {"name": "WatchCharts", "label": label, "url": url, "as_of": as_of}

def retail_src(name, url, as_of="2026-11-18", short=None):
    d, m = as_of.split("-")[2], int(as_of.split("-")[1])
    months = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
    short = short or name.split()[0]
    return {"name": name, "label": f"{short} · {int(d)} {months[m-1]}", "url": url, "as_of": as_of}

def offer_ad(seller, country, price, url, condition, http=200):
    text = None
    if price is not None:
        text = f"{price:,.0f} €".replace(",", ".") + ""
        # 11300 -> 11.300 €
        s = f"{int(price):,}".replace(",", ".")
        text = f"{s} €"
    return {
        "seller": seller,
        "type": "AD",
        "country": country,
        "price_eur": price,
        "condition": condition,
        "url": url,
        "seen": "2026-11-18",
        "price_text": text,
        "http": http,
    }

def offer_c24(q):
    return {
        "seller": "Chrono24",
        "type": "marketplace",
        "country": "EU",
        "price_eur": None,
        "condition": "pesquisa pública desta referência",
        "url": f"https://www.chrono24.pt/search/index.htm?dosearch=true&query={q}",
        "seen": "2026-11-18",
        "http": 403,
        "note": "curl 403 (bloqueio de bots); a pesquisa pública existe num browser",
    }

def mk(brand, model, ref, gender, usd, wc_url, retail, retail_source,
       sales, days, dealer_usd=None, as_of="2026-11-17",
       note=None, blurb=None, offers=None, discontinued=False):
    market_eur, fx, fx_date = (None, None, None)
    if usd is not None:
        market_eur, fx, fx_date = eur_from_usd(usd, as_of)
    dealer_eur = None
    if dealer_usd is not None:
        dealer_eur, _, _ = eur_from_usd(dealer_usd, as_of)
    prem = premium(market_eur, retail)
    src = wc(model, wc_url, as_of) if wc_url else None
    rec = {
        "brand": brand,
        "model": model,
        "ref": ref,
        "gender": gender,
        "retail_pt_eur": retail,
        "retail_source": retail_source,
        "market_eur": market_eur,
        "market_usd": usd,
        "market_source": src,
        "market_note": note,
        "premium_pct": prem,
        "dealer_eur": dealer_eur,
        "landed_import_eur": landed(market_eur),
        "demand": {"sales_1y": sales, "days_on_market": days},
        "demand_source": src,
        "signal": signal(prem),
        "blurb": blurb,
        "discontinued": bool(discontinued),
        "offers": offers or [],
        "fx": {"usd_per_eur": fx, "date": fx_date, "source": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"} if fx else None,
    }
    # drop null fx
    if rec["fx"] is None:
        del rec["fx"]
    if not rec["market_note"]:
        rec.pop("market_note")
    if not rec["blurb"]:
        rec.pop("blurb")
    if not rec["discontinued"]:
        rec.pop("discontinued")
    return rec

# ——— New models ———
TORRES = "https://rolex.torres.pt/relogio"
COND = "novo, IVA incl., consultar disponibilidade"

# WC URLs
U = {
    "126000": "https://watchcharts.com/watch_model/21826-rolex-oyster-perpetual-36-126000/overview",
    "124300": "https://watchcharts.com/watch_model/21827-rolex-oyster-perpetual-41-124300/overview",
    "224270": "https://watchcharts.com/watch_model/46434-rolex-explorer-224270/overview",
    "226570": "https://watchcharts.com/watch_model/33628-rolex-explorer-ii-226570/overview",
    "126710BLNR": "https://watchcharts.com/watch_model/1525-rolex-gmt-master-ii-batgirl-126710blnr/overview",
    "126710GRNR": "https://watchcharts.com/watch_model/49351-rolex-gmt-master-ii-bruce-wayne-126710grnr/overview",
    "126720": "https://watchcharts.com/watch_model/36317-rolex-gmt-master-ii-sprite-126720/overview",
    "126711CHNR": "https://watchcharts.com/watch_model/756-rolex-gmt-master-ii-root-beer-126711chnr/overview",
    "126715": "https://watchcharts.com/watch_model/1555-rolex-gmt-master-ii-126715/overview",
    "126713": "https://watchcharts.com/watch_model/46435-rolex-gmt-master-ii-126713/overview",
    "116710": "https://watchcharts.com/watch_model/53-rolex-gmt-master-ii-116710/overview",
    "116710BLNR": "https://watchcharts.com/watch_model/739-rolex-gmt-master-ii-batman-116710blnr/overview",
    "124060": "https://watchcharts.com/watch_model/21813-rolex-submariner-124060/overview",
    "126600": "https://watchcharts.com/watch_model/1300-rolex-sea-dweller-126600/overview",
    "126622": "https://watchcharts.com/watch_model/1156-rolex-yacht-master-126622/overview",
    "126900": "https://watchcharts.com/watch_model/36316-rolex-air-king-126900/overview",
    "228238": "https://watchcharts.com/watch_model/659-rolex-day-date-40-228238/overview",
    "126234": "https://watchcharts.com/watch_model/15369-rolex-datejust-36-126234/overview",
    "277200": "https://watchcharts.com/watch_model/21823-rolex-oyster-perpetual-31-277200/overview",
    "sapph": "https://watchcharts.com/watch_model/30921-omega-speedmaster-professional-moonwatch-310-30-42-50-01-002/overview",
    "white": "https://watchcharts.com/watch_model/49294-omega-speedmaster-moonwatch-professional-42-mm-steel-on-steel-310-30-42-50-04-001/overview",
    "po": "https://watchcharts.com/watch_model/1273-omega-seamaster-planet-ocean-600m-215-30-44-21-01-001/overview",
    "wsta0108": "https://watchcharts.com/watch_model/54227-cartier-tank-must-wsta0108/overview",
    "wsta0042": "https://watchcharts.com/watch_model/33567-cartier-tank-must-small-wsta0042/overview",
    "wssa0032": "https://watchcharts.com/watch_model/43697-cartier-santos-dumont-extra-large-wssa0032/overview",
    "wgta0342": "https://watchcharts.com/watch_model/52200-cartier-tank-louis-cartier-wgta0342/overview",
}

def t_off(path, price):
    url = f"{TORRES}/{path}/"
    return [
        offer_ad("Torres Joalheiros", "PT", price, url, COND),
        offer_c24(path.split("/")[-1].replace("m", "").replace("-", "").upper() if False else path.split("/")[-1].upper().lstrip("M")),
    ]

NEW = []

# OP 36 key dials (prices from family page variation list, 17 nov 2026)
op36_note = "Preço de mercado da variação, publicado na página da família 126000 na WatchCharts, 17 nov. 2026. Volume e dias são da família."
for ref, model, usd, path in [
    ("126000-0001", "Oyster Perpetual 36 prateado", 8064, "oyster-perpetual/m126000-0001"),
    ("126000-0006", "Oyster Perpetual 36 azul-turquesa", 14107, "oyster-perpetual/m126000-0006"),
    ("126000-0008", "Oyster Perpetual 36 rosa candy", 9746, "oyster-perpetual/m126000-0008"),
    ("126000-0011", "Oyster Perpetual 36 verde pistachio", 9568, "oyster-perpetual/m126000-0011"),
]:
    url = f"{TORRES}/{path}/"
    q = ref
    NEW.append(mk("Rolex", model, ref, "homem" if "turquesa" in model or "prateado" in model or "pistachio" in model else "homem",
                  usd, U["126000"], 6700, retail_src("Torres Joalheiros", url, short="Torres"),
                  3596, 35.1, dealer_usd=None, note=op36_note,
                  offers=[offer_ad("Torres Joalheiros", "PT", 6700, url, COND), offer_c24(q)]))

NEW.append(mk("Rolex", "Oyster Perpetual 41", "124300", "homem",
              8820, U["124300"], None, None,
              2595, None, 9640, note="Família 124300 (descontinuada). Os mostradores variam bastante no secundário ( WatchCharts, 17 nov. 2026).",
              discontinued=True, offers=[offer_c24("124300")]))

NEW.append(mk("Rolex", "Explorer 40", "224270", "homem",
              8628, U["224270"], 8350, retail_src("Torres Joalheiros", f"{TORRES}/explorer/m224270-0001/", short="Torres"),
              1751, 15.0, 9782,
              offers=[offer_ad("Torres Joalheiros", "PT", 8350, f"{TORRES}/explorer/m224270-0001/", COND), offer_c24("224270")]))

NEW.append(mk("Rolex", "Explorer II", "226570", "homem",
              10592, U["226570"], 10600, retail_src("Torres Joalheiros", f"{TORRES}/explorer-ii/m226570-0001/", short="Torres"),
              2514, 25.0, 11744,
              note="Preço de mercado da família 226570; o retalho e a fotografia são da configuração 0001 (mostrador branco).",
              offers=[offer_ad("Torres Joalheiros", "PT", 10600, f"{TORRES}/explorer-ii/m226570-0001/", COND), offer_c24("226570")]))

NEW.append(mk("Rolex", "GMT-Master II Batman", "126710BLNR", "homem",
              17222, U["126710BLNR"], 11950, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126710blnr-0002/", short="Torres"),
              5617, 20.0, 18902,
              note="Preço de mercado da família 126710BLNR; retalho e fotografia da configuração 0002 (bracelete Jubilee).",
              offers=[offer_ad("Torres Joalheiros", "PT", 11950, f"{TORRES}/gmt-master-ii/m126710blnr-0002/", COND), offer_c24("126710BLNR")]))

NEW.append(mk("Rolex", "GMT-Master II Bruce Wayne", "126710GRNR", "homem",
              20313, U["126710GRNR"], 11950, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126710grnr-0003/", short="Torres"),
              2989, 15.0, 22148,
              note="Preço de mercado da família 126710GRNR; retalho e fotografia da configuração 0003.",
              offers=[offer_ad("Torres Joalheiros", "PT", 11950, f"{TORRES}/gmt-master-ii/m126710grnr-0003/", COND), offer_c24("126710GRNR")]))

NEW.append(mk("Rolex", "GMT-Master II Sprite", "126720VTNR", "homem",
              16084, U["126720"], 12250, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126720vtnr-0001/", short="Torres"),
              3055, 24.1, 17831,
              note="Página WatchCharts da família 126720; retalho e fotografia da configuração 0001.",
              offers=[offer_ad("Torres Joalheiros", "PT", 12250, f"{TORRES}/gmt-master-ii/m126720vtnr-0001/", COND), offer_c24("126720VTNR")]))

NEW.append(mk("Rolex", "GMT-Master II Root Beer", "126711CHNR", "homem",
              18653, U["126711CHNR"], 20000, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126711chnr-0002/", short="Torres"),
              2587, 20.0, 20901,
              offers=[offer_ad("Torres Joalheiros", "PT", 20000, f"{TORRES}/gmt-master-ii/m126711chnr-0002/", COND), offer_c24("126711CHNR")]))

NEW.append(mk("Rolex", "GMT-Master II Root Beer Everose", "126715CHNR", "homem",
              38375, U["126715"], 57300, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126715chnr-0002/", short="Torres"),
              820, 29.0, 42994, as_of="2026-11-16",
              note="Preço de mercado da família 126715, 16 nov. 2026; retalho e fotografia da configuração 0002 (mostrador olho de ferro).",
              offers=[offer_ad("Torres Joalheiros", "PT", 57300, f"{TORRES}/gmt-master-ii/m126715chnr-0002/", COND), offer_c24("126715CHNR")]))

NEW.append(mk("Rolex", "GMT-Master II Rolesor amarelo", "126713GRNR", "homem",
              20694, U["126713"], 20300, retail_src("Torres Joalheiros", f"{TORRES}/gmt-master-ii/m126713grnr-0001/", short="Torres"),
              1476, 20.0, 22814, as_of="2026-11-13",
              note="Página WatchCharts da família 126713, 13 nov. 2026; retalho e fotografia da configuração 0001 (GRNR).",
              offers=[offer_ad("Torres Joalheiros", "PT", 20300, f"{TORRES}/gmt-master-ii/m126713grnr-0001/", COND), offer_c24("126713GRNR")]))

NEW.append(mk("Rolex", "GMT-Master II 116710LN", "116710LN", "homem",
              11971, U["116710"], None, None,
              2874, 22.0, 13511,
              note="Página WatchCharts titulada 116710; os anúncios visíveis são da variante LN ( luneta preta).",
              discontinued=True, offers=[offer_c24("116710LN")]))

NEW.append(mk("Rolex", "GMT-Master II Batman 116710BLNR", "116710BLNR", "homem",
              14136, U["116710BLNR"], None, None,
              1880, 22.0, 16010, discontinued=True, offers=[offer_c24("116710BLNR")]))

NEW.append(mk("Rolex", "Submariner sem data", "124060", "homem",
              12271, U["124060"], 10050, retail_src("Torres Joalheiros", f"{TORRES}/submariner/m124060-0001/", short="Torres"),
              3360, 16.2, 13527,
              offers=[offer_ad("Torres Joalheiros", "PT", 10050, f"{TORRES}/submariner/m124060-0001/", COND), offer_c24("124060")]))

NEW.append(mk("Rolex", "Sea-Dweller", "126600", "homem",
              11692, U["126600"], 14450, retail_src("Torres Joalheiros", f"{TORRES}/sea-dweller/m126600-0002/", short="Torres"),
              2422, 23.1, 13008,
              note="Preço de mercado da família 126600; retalho e fotografia da configuração 0002.",
              offers=[offer_ad("Torres Joalheiros", "PT", 14450, f"{TORRES}/sea-dweller/m126600-0002/", COND), offer_c24("126600")]))

NEW.append(mk("Rolex", "Yacht-Master 40", "126622", "homem",
              13870, U["126622"], 13150, retail_src("Torres Joalheiros", f"{TORRES}/yacht-master/m126622-0001/", short="Torres"),
              2084, 25.0, 15283,
              note="Preço de mercado da família 126622; retalho e fotografia da configuração 0001 (mostrador cor de ardósia).",
              offers=[offer_ad("Torres Joalheiros", "PT", 13150, f"{TORRES}/yacht-master/m126622-0001/", COND), offer_c24("126622")]))

NEW.append(mk("Rolex", "Air-King", "126900", "homem",
              8243, U["126900"], 8100, retail_src("Torres Joalheiros", f"{TORRES}/air-king/m126900-0001/", short="Torres"),
              1541, 20.0, 9155,
              offers=[offer_ad("Torres Joalheiros", "PT", 8100, f"{TORRES}/air-king/m126900-0001/", COND), offer_c24("126900")]))

NEW.append(mk("Rolex", "Day-Date 40", "228238", "homem",
              50770, U["228238"], 50200, retail_src("Torres Joalheiros", f"{TORRES}/day-date/m228238-0042/", short="Torres"),
              1301, 39.0, 55587,
              note="Preço de mercado da família 228238; retalho e fotografia da configuração 0042 (mostrador branco, sem diamantes).",
              offers=[offer_ad("Torres Joalheiros", "PT", 50200, f"{TORRES}/day-date/m228238-0042/", COND), offer_c24("228238")]))

NEW.append(mk("Rolex", "Datejust 36", "126234", "homem",
              12523, U["126234"], 10100, retail_src("Torres Joalheiros", f"{TORRES}/datejust/m126234-0015/", short="Torres"),
              4992, 34.3, 13714,
              note="Preço de mercado da família 126234 (vários mostradores); retalho e fotografia da configuração 0015 (mostrador preto vivo).",
              offers=[offer_ad("Torres Joalheiros", "PT", 10100, f"{TORRES}/datejust/m126234-0015/", COND), offer_c24("126234")]))

NEW.append(mk("Rolex", "Oyster Perpetual 31 verde", "277200-0006", "mulher",
              8159, U["277200"], 6250, retail_src("Torres Joalheiros", f"{TORRES}/oyster-perpetual/m277200-0006/", short="Torres"),
              1502, 42.2, None,
              note="Preço de mercado da variação 0006, publicado na página da família 277200. Volume e dias são da família.",
              offers=[offer_ad("Torres Joalheiros", "PT", 6250, f"{TORRES}/oyster-perpetual/m277200-0006/", COND), offer_c24("277200-0006")]))

# Omega
NEW.append(mk("Omega", "Speedmaster Moonwatch Professional (safira)", "310.30.42.50.01.002", "homem",
              6556, U["sapph"], None, None,
              1995, 16.0, 7225,
              offers=[offer_c24("310.30.42.50.01.002")]))

NEW.append(mk("Omega", "Speedmaster Moonwatch Professional branco", "310.30.42.50.04.001", "homem",
              7512, U["white"], None, None,
              1375, 16.0, 8084,
              offers=[offer_c24("310.30.42.50.04.001")]))

NEW.append(mk("Omega", "Seamaster Planet Ocean 600M 43,5 mm", "215.30.44.21.01.001", "homem",
              4123, U["po"], None, None,
              461, 28.0, 4764, discontinued=True,
              note="Modelo descontinuado na WatchCharts (retalho EUA referido a out. 2025).",
              offers=[offer_c24("215.30.44.21.01.001")]))

# Cartier
NEW.append(mk("Cartier", "Tank Must pequeno", "WSTA0042", "mulher",
              2884, U["wsta0042"], 3800, retail_src("Boutique dos Relógios", "https://boutiquedosrelogios.pt/pt/tank-must-cartier-wsta0042", short="BdR"),
              None, None, None, discontinued=True,
              offers=[offer_ad("Boutique dos Relógios", "PT", 3800, "https://boutiquedosrelogios.pt/pt/tank-must-cartier-wsta0042", COND), offer_c24("WSTA0042")]))

NEW.append(mk("Cartier", "Tank Must grande", "WSTA0108", "homem",
              3640, U["wsta0108"], None, None,
              42, 38.5, 4024,
              offers=[offer_c24("WSTA0108")]))

NEW.append(mk("Cartier", "Santos-Dumont extra-grande", "WSSA0032", "homem",
              5756, U["wssa0032"], 7900, retail_src("Boutique dos Relógios", "https://boutiquedosrelogios.pt/pt/santos-dumont-cartier-wssa0032", short="BdR"),
              258, 35.0, 6561,
              offers=[offer_ad("Boutique dos Relógios", "PT", 7900, "https://boutiquedosrelogios.pt/pt/santos-dumont-cartier-wssa0032", COND), offer_c24("WSSA0032")]))

NEW.append(mk("Cartier", "Tank Louis Cartier pequeno", "WGTA0342", "mulher",
              8626, U["wgta0342"], 12500, retail_src("Boutique dos Relógios", "https://boutiquedosrelogios.pt/pt/tank-cartier-wgta0342", short="BdR"),
              None, None, None, as_of="2026-10-17",
              offers=[offer_ad("Boutique dos Relógios", "PT", 12500, "https://boutiquedosrelogios.pt/pt/tank-cartier-wgta0342", COND), offer_c24("WGTA0342")]))

# Panerai Radiomir — retail only
NEW.append({
    "brand": "Panerai",
    "model": "Radiomir Logo 45 mm",
    "ref": "PAM00753",
    "gender": "homem",
    "retail_pt_eur": 5000,
    "retail_source": retail_src("Boutique dos Relógios", "https://boutiquedosrelogios.pt/pt/radiomir-panerai-pam00753", short="BdR"),
    "market_eur": None,
    "market_source": None,
    "premium_pct": None,
    "dealer_eur": None,
    "landed_import_eur": None,
    "demand": {"sales_1y": None, "days_on_market": None},
    "signal": "—",
    "blurb": "Preço de mercado público não encontrado nesta ronda; mantém-se em —.",
    "offers": [
        offer_ad("Boutique dos Relógios", "PT", 5000, "https://boutiquedosrelogios.pt/pt/radiomir-panerai-pam00753", COND),
        offer_c24("PAM00753"),
    ],
})

# ——— Existing watches: attach sources, keep numbers ———
existing_src = {
    "126610LN": ("https://watchcharts.com/watch_model/21817-rolex-submariner-date-126610/overview", "https://rolex.torres.pt/relogio/submariner/m126610ln-0001/", "A página WatchCharts é da família 126610, não só da variante LN."),
    "126710BLRO": ("https://watchcharts.com/watch_model/733-rolex-gmt-master-ii-pepsi-126710blro/overview", None, None),
    "126500LN-0001": ("https://watchcharts.com/watch_variation/1456-rolex-cosmograph-daytona-126500ln-0001/overview", "https://rolex.torres.pt/en/watch/cosmograph-daytona/m126500ln-0001/", None),
    "126334": ("https://watchcharts.com/watch_model/727-rolex-datejust-41-126334/overview", "https://rolex.torres.pt/relogio/datejust/m126334-0033/", None),
    "310.30.42.50.01.001": ("https://watchcharts.com/watch_model/30920-omega-speedmaster-professional-moonwatch-310-30-42-50-01-001/overview", "https://www.marcolino.pt/en/watches/omega/moonwatch-professional-co-axial-master-chronometer-chrono-31030425001001-8015", None),
    "210.30.42.20.01.001": ("https://watchcharts.com/watch_model/869-omega-seamaster-diver-300m-210-30-42-20-01-001/overview", "https://www.marcolino.pt/en/watches/omega/seamaster-diver-300m-co-axial-master-21030422001001-767", None),
    "220.10.41.21.01.001": ("https://watchcharts.com/watch_model/1251-omega-seamaster-aqua-terra-150m-220-10-41-21-01-001/overview", "https://www.marcolino.pt/en/watches/omega/seamaster-aqua-terra-150m-co-axial-master-41mm-22010412101001-755", None),
    "WSSA0029": ("https://watchcharts.com/watch_model/35440-cartier-santos-medium-wssa0029/overview", "https://www.machadojoalheiro.com/shop/catalogue/cartier-santos-medio-modelo_4237/?r=105", None),
    "WSSA0018": ("https://watchcharts.com/watch_model/35441-cartier-santos-large-wssa0018/overview", "https://www.machadojoalheiro.com/shop/catalogue/cartier-santos-grande-modelo_4230/", None),
    "WSBB0062": ("https://watchcharts.com/watch_model/43726-cartier-ballon-bleu-wsbb0062/overview", None, None),
    "PAM01314": ("https://watchcharts.com/watch_model/30905-panerai-luminor-marina-pam01314/overview", "https://boutiquedosrelogios.pt/pt/luminor-marina-44mm-panerai-pam01314", None),
    "PAM00683": ("https://watchcharts.com/watch_model/1836-panerai-luminor-submersible-pam683/overview", None, None),
    "279174": ("https://watchcharts.com/watch_model/15339-rolex-lady-datejust-279174/overview", "https://rolex.torres.pt/relogio/lady-datejust/m279174-0020/", None),
    "278274": ("https://watchcharts.com/watch_model/21829-rolex-datejust-31-278274/overview", "https://rolex.torres.pt/relogio/datejust/m278274-0018/", None),
    "131.10.29.20.55.001": ("https://watchcharts.com/watch_model/3669-omega-constellation-manhattan-29-co-axial-master-chronometer-131-10-29-20-55-001/overview", None, None),
    "220.10.34.20.01.001": (None, "https://www.marcolino.pt/pt/relogios/omega/seamaster-aqua-terra-22010342001001-37369", None),
    "WSPN0013": ("https://watchcharts.com/watch_model/49273-cartier-panthere-wspn0013/overview", "https://boutiquedosrelogios.pt/pt/rel-gio-panth-re-de-cartier-cartier-wspn0013", None),
    "WSSA0082": ("https://watchcharts.com/watch_model/54521-cartier-santos-wssa0082/overview", "https://www.machadojoalheiro.com/shop/catalogue/cartier-santos-pequeno-modelo_8443/", None),
    "WSTA0129": ("https://watchcharts.com/watch_model/52225-cartier-tank-francaise-wsta0129/overview", "https://boutiquedosrelogios.pt/pt/rel-gio-tank-fran-aise-cartier-wsta0129", None),
    "PAM01123": ("https://watchcharts.com/watch_model/35072-panerai-luminor-due-38-automatic-stainless-steel-pam01123/overview", "https://boutiquedosrelogios.pt/pt/luminor-due-38mm-panerai", None),
}

RETAIL_NAME = {
    "Torres": "Torres Joalheiros",
    "Marcolino": "Marcolino 1926",
    "Machado": "Machado Joalheiro",
    "Boutique": "Boutique dos Relógios",
}

def retail_name_from_url(url):
    if not url:
        return None
    if "torres" in url:
        return "Torres Joalheiros", "Torres"
    if "marcolino" in url:
        return "Marcolino 1926", "Marcolino"
    if "machado" in url:
        return "Machado Joalheiro", "Machado"
    if "boutiquedosrelogios" in url:
        return "Boutique dos Relógios", "BdR"
    return "AD PT", "AD"

def attach_sources(w):
    w = deepcopy(w)
    wc_url, retail_url, note = existing_src[w["ref"]]
    if wc_url and w.get("market_eur") is not None:
        w["market_source"] = wc("WatchCharts", wc_url, "2026-11-17")
        w["market_source"]["name"] = "WatchCharts"
        w["demand_source"] = w["market_source"]
    else:
        w["market_source"] = None
    if note:
        w["market_note"] = note
    if retail_url and w.get("retail_pt_eur") is not None:
        name, short = retail_name_from_url(retail_url)
        w["retail_source"] = retail_src(name, retail_url, short=short)
    else:
        w["retail_source"] = None
    return w

# ——— History snapshots ———
# (date as_of, ref, usd or eur, currency, source_url, via)
WB = "https://web.archive.org/web"

def hist_point(as_of, ref, amount, currency, url, via):
    rec = {
        "date": as_of,
        "ref": ref,
        "source": "WatchCharts",
        "source_url": url,
        "as_of": as_of,
        "via": via,
    }
    if currency == "USD":
        market_eur, fx, fx_date = eur_from_usd(amount, as_of)
        rec.update({"market_usd": amount, "market_eur": market_eur, "fx_usd_per_eur": fx, "fx_date": fx_date})
    else:
        rec.update({"market_usd": None, "market_eur": amount, "currency": "EUR", "fx_usd_per_eur": FX.get(as_of), "fx_date": FX_USED.get(as_of, as_of)})
    return rec

HISTORY_POINTS = [
    # Pepsi
    hist_point("2025-03-09", "126710BLRO", 19286, "USD",
               f"{WB}/20250310041941/https://watchcharts.com/watch_model/733-rolex-gmt-master-ii-pepsi-126710blro/overview",
               "Wayback Machine"),
    hist_point("2026-01-06", "126710BLRO", 20057, "USD",
               f"{WB}/20260109173639/https://watchcharts.com/watch_model/733-rolex-gmt-master-ii-pepsi-126710blro/overview",
               "Wayback Machine"),
    # 126610
    hist_point("2022-10-20", "126610LN", 14807, "EUR",
               f"{WB}/20221022022350/https://watchcharts.com/watch_model/21817-rolex-submariner-date-126610/overview",
               "Wayback Machine"),
    hist_point("2022-11-09", "126610LN", 14196, "USD",
               f"{WB}/20221111021320/https://watchcharts.com/watch_model/21817-rolex-submariner-date-126610/overview",
               "Wayback Machine"),
    hist_point("2025-03-17", "126610LN", 12852, "USD",
               f"{WB}/20250318201524/https://watchcharts.com/watch_model/21817-rolex-submariner-date-126610/overview",
               "Wayback Machine"),
    hist_point("2025-08-02", "126610LN", 12875, "USD",
               f"{WB}/20250803132610/https://watchcharts.com/watch_model/21817-rolex-submariner-date-126610/overview",
               "Wayback Machine"),
    # 226570
    hist_point("2022-10-24", "226570", 12324, "USD",
               f"{WB}/20221027140110/https://watchcharts.com/watch_model/33628-rolex-explorer-ii-226570/overview",
               "Wayback Machine"),
    hist_point("2025-04-10", "226570", 10175, "USD",
               f"{WB}/20250412014438/https://watchcharts.com/watch_model/33628-rolex-explorer-ii-226570/overview",
               "Wayback Machine"),
    # 126711CHNR
    hist_point("2025-04-15", "126711CHNR", 17763, "USD",
               f"{WB}/20250416065705/https://watchcharts.com/watch_model/756-rolex-gmt-master-ii-root-beer-126711chnr/overview",
               "Wayback Machine"),
    hist_point("2025-11-04", "126711CHNR", 18101, "USD",
               f"{WB}/20251105203020/https://watchcharts.com/watch_model/756-rolex-gmt-master-ii-root-beer-126711chnr/overview",
               "Wayback Machine"),
    # two-point series
    hist_point("2023-12-15", "126334", 12591, "USD",
               f"{WB}/20231217001214/https://watchcharts.com/watch_model/727-rolex-datejust-41-126334/overview",
               "Wayback Machine"),
    hist_point("2023-12-03", "278274", 10265, "USD",
               f"{WB}/20231206192044/https://watchcharts.com/watch_model/21829-rolex-datejust-31-278274/overview",
               "Wayback Machine"),
    hist_point("2023-03-10", "228238", 41973, "USD",
               f"{WB}/20230311175052/https://watchcharts.com/watch_model/659-rolex-day-date-40-228238/overview",
               "Wayback Machine"),
    hist_point("2023-05-18", "220.10.41.21.01.001", 3604, "EUR",
               f"{WB}/20230521064620/https://watchcharts.com/watch_model/1251-omega-seamaster-aqua-terra-150m-220-10-41-21-01-001/overview",
               "Wayback Machine"),
    hist_point("2025-07-14", "116710BLNR", 13721, "USD",
               f"{WB}/20250715160614/https://watchcharts.com/watch_model/739-rolex-gmt-master-ii-batman-116710blnr/overview",
               "Wayback Machine"),
]

def seed_current(watches):
    seeds = []
    for w in watches:
        src = w.get("market_source") or {}
        if w.get("market_eur") is None or not src:
            continue
        as_of = src.get("as_of") or "2026-11-17"
        rec = {
            "date": as_of,
            "ref": w["ref"],
            "market_eur": w["market_eur"],
            "market_usd": w.get("market_usd"),
            "source": "WatchCharts",
            "source_url": src.get("url"),
            "as_of": as_of,
            "via": "página pública",
        }
        if w.get("fx"):
            rec["fx_usd_per_eur"] = w["fx"]["usd_per_eur"]
            rec["fx_date"] = w["fx"]["date"]
        elif as_of in FX:
            rec["fx_usd_per_eur"] = FX[as_of]
            rec["fx_date"] = FX_USED.get(as_of, as_of)
        else:
            rec["fx_usd_per_eur"] = 1.0989
            rec["fx_date"] = "2026-11-17"
        seeds.append(rec)
    return seeds

def aggregates(watches):
    by = {}
    for w in watches:
        b = by.setdefault(w["brand"], {"brand": w["brand"], "premiums": [], "markets": [], "sales": 0, "n": 0, "n_prem": 0})
        b["n"] += 1
        if w.get("premium_pct") is not None:
            b["premiums"].append(w["premium_pct"])
            b["n_prem"] += 1
        if w.get("market_eur") is not None:
            b["markets"].append(w["market_eur"])
        s = (w.get("demand") or {}).get("sales_1y")
        if s:
            b["sales"] += s
    order = ["Rolex", "Omega", "Cartier", "Panerai"]
    out = []
    for brand in order:
        b = by[brand]
        med = int(round(statistics.median(b["markets"]))) if b["markets"] else None
        avg = round(sum(b["premiums"]) / len(b["premiums"]), 1) if b["premiums"] else None
        out.append({
            "brand": brand,
            "n_models": b["n"],
            "n_with_premium": b["n_prem"],
            "avg_premium_pct": avg,
            "median_market_eur": med,
            "total_sales_1y": b["sales"] or None,
        })
    rank = []
    for w in watches:
        if w.get("premium_pct") is None:
            continue
        rank.append({
            "ref": w["ref"],
            "brand": w["brand"],
            "model": w["model"],
            "premium_pct": w["premium_pct"],
            "market_eur": w.get("market_eur"),
            "sales_1y": (w.get("demand") or {}).get("sales_1y"),
        })
    rank.sort(key=lambda r: r["premium_pct"], reverse=True)
    return {"by_brand": out, "ranking_premium": rank}

# ——— Images ———
PHOTO_MAP = {
    "126000-0001": ("m126000-0001.png", "Oyster Perpetual 36 prateado", "https://rolex.torres.pt/relogio/oyster-perpetual/m126000-0001/"),
    "126000-0006": ("m126000-0006.png", "Oyster Perpetual 36 azul-turquesa", "https://rolex.torres.pt/relogio/oyster-perpetual/m126000-0006/"),
    "126000-0008": ("m126000-0008.png", "Oyster Perpetual 36 rosa candy", "https://rolex.torres.pt/relogio/oyster-perpetual/m126000-0008/"),
    "126000-0011": ("m126000-0011.png", "Oyster Perpetual 36 verde pistachio", "https://rolex.torres.pt/relogio/oyster-perpetual/m126000-0011/"),
    "224270": ("m224270-0001.png", "Explorer 40", "https://rolex.torres.pt/relogio/explorer/m224270-0001/"),
    "226570": ("m226570-0001.png", "Explorer II", "https://rolex.torres.pt/relogio/explorer-ii/m226570-0001/"),
    "126710BLNR": ("m126710blnr-0002.png", "GMT-Master II Batman", "https://rolex.torres.pt/relogio/gmt-master-ii/m126710blnr-0002/"),
    "126710GRNR": ("m126710grnr-0003.png", "GMT-Master II Bruce Wayne", "https://rolex.torres.pt/relogio/gmt-master-ii/m126710grnr-0003/"),
    "126720VTNR": ("m126720vtnr-0001.png", "GMT-Master II Sprite", "https://rolex.torres.pt/relogio/gmt-master-ii/m126720vtnr-0001/"),
    "126711CHNR": ("m126711chnr-0002.png", "GMT-Master II Root Beer", "https://rolex.torres.pt/relogio/gmt-master-ii/m126711chnr-0002/"),
    "126715CHNR": ("m126715chnr-0002.png", "GMT-Master II Root Beer Everose", "https://rolex.torres.pt/relogio/gmt-master-ii/m126715chnr-0002/"),
    "126713GRNR": ("m126713grnr-0001.png", "GMT-Master II Rolesor amarelo", "https://rolex.torres.pt/relogio/gmt-master-ii/m126713grnr-0001/"),
    "124060": ("m124060-0001.png", "Submariner sem data", "https://rolex.torres.pt/relogio/submariner/m124060-0001/"),
    "126600": ("m126600-0002.png", "Sea-Dweller", "https://rolex.torres.pt/relogio/sea-dweller/m126600-0002/"),
    "126622": ("m126622-0001.png", "Yacht-Master 40", "https://rolex.torres.pt/relogio/yacht-master/m126622-0001/"),
    "126900": ("m126900-0001.png", "Air-King", "https://rolex.torres.pt/relogio/air-king/m126900-0001/"),
    "228238": ("m228238-0042.png", "Day-Date 40", "https://rolex.torres.pt/relogio/day-date/m228238-0042/"),
    "126234": ("m126234-0015.png", "Datejust 36", "https://rolex.torres.pt/relogio/datejust/m126234-0015/"),
    "277200-0006": ("m277200-0006.png", "Oyster Perpetual 31 verde", "https://rolex.torres.pt/relogio/oyster-perpetual/m277200-0006/"),
    "WSTA0042": ("WSTA0042.png", "Tank Must pequeno", "https://boutiquedosrelogios.pt/pt/tank-must-cartier-wsta0042"),
    "WSSA0032": ("WSSA0032.png", "Santos-Dumont extra-grande", "https://boutiquedosrelogios.pt/pt/santos-dumont-cartier-wssa0032"),
    "WGTA0342": ("WGTA0342.png", "Tank Louis Cartier pequeno", "https://boutiquedosrelogios.pt/pt/tank-cartier-wgta0342"),
    "PAM00753": ("PAM00753.png", "Radiomir Logo 45 mm", "https://boutiquedosrelogios.pt/pt/radiomir-panerai-pam00753"),
}

BG = (246, 243, 235, 255)  # #F6F3EB

def process_photo(src: Path, dest: Path, size=800):
    im = Image.open(src)
    im = im.convert("RGBA")
    # composite on editorial tile colour
    canvas = Image.new("RGBA", im.size, BG)
    canvas = Image.alpha_composite(canvas, im)
    canvas = canvas.convert("RGB")
    w, h = canvas.size
    scale = size / max(w, h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    canvas = canvas.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGB", (size, size), BG[:3])
    out.paste(canvas, ((size - nw) // 2, (size - nh) // 2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "WEBP", quality=82, method=6)
    return dest.stat().st_size

def main():
    old = json.loads((DATA / "watches.json").read_text())
    old_by = {w["ref"]: attach_sources(w) for w in old["watches"]}

    # order: existing first in original order, then new
    watches = [old_by[w["ref"]] for w in old["watches"]] + NEW
    # verify unique refs
    refs = [w["ref"] for w in watches]
    assert len(refs) == len(set(refs)), [r for r in refs if refs.count(r) > 1]

    agg = aggregates(watches)

    payload = deepcopy(old)
    payload["title"] = "G Watch Radar — dados v2"
    payload["updated"] = "2026-11-18"
    payload["watches"] = watches
    payload["aggregates"] = agg
    payload["sources"] = {
        "market": "WatchCharts páginas públicas, 13–17 nov. 2026 (a data exacta está em cada referência). EUR = USD / taxa BCE do dia do preço (ou último dia útil anterior).",
        "retail_pt": "Páginas de AD portugueses (Torres, Machado, Boutique dos Relógios, Marcolino), 18 nov. 2026.",
        "offers": "AD PT e ligações de pesquisa Chrono24; visto 18 nov. 2026, Europe/Lisbon. Sem scraping em massa da Chrono24.",
        "history": "Pontos históricos: instantâneos da Wayback Machine de páginas WatchCharts, com a data «as of» publicada em cada página. Sem interpolação.",
    }
    payload["http_notes"] = old.get("http_notes", "")
    (DATA / "watches.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    seeds = seed_current(watches)
    # merge history: historical first, then current if not already same date+ref
    seen = {(p["ref"], p["as_of"]) for p in HISTORY_POINTS}
    snaps = list(HISTORY_POINTS)
    for s in seeds:
        key = (s["ref"], s["as_of"])
        if key not in seen:
            snaps.append(s)
            seen.add(key)
    snaps.sort(key=lambda x: (x["date"], x["ref"]))
    history = {
        "updated": "2026-11-18",
        "timezone": "Europe/Lisbon",
        "note": "Registo append-only de preços de mercado públicos. Cada ponto tem fonte e data. Não interpolámos nem inventámos valores.",
        "fx_source": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
        "snapshots": snaps,
    }
    (DATA / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")

    # photos
    credits = json.loads((IMG / "credits.json").read_text())
    have = {c["ref"] for c in credits["images"]}
    new_credits = []
    missing_photos = []
    for w in NEW:
        ref = w["ref"]
        if ref not in PHOTO_MAP:
            missing_photos.append(ref)
            continue
        fn, model, page = PHOTO_MAP[ref]
        src = RAW / fn
        if not src.exists():
            print("MISSING RAW", src)
            missing_photos.append(ref)
            continue
        dest = IMG / f"{ref}.webp"
        size = process_photo(src, dest)
        print(f"photo {ref} -> {dest.name} {size} bytes")
        if ref not in have:
            brand = "Rolex" if page.startswith("https://rolex.torres") else (
                "Cartier" if "cartier" in page or "WST" in ref or "WSS" in ref or "WGT" in ref else "Panerai"
            )
            source = "Torres Joalheiros" if "torres" in page else "Boutique dos Relógios"
            new_credits.append({
                "ref": ref,
                "model": model,
                "credit": f"© {brand}",
                "licence": "Imagem oficial da marca",
                "kind": "ad",
                "source": source,
                "source_page": page,
            })
    credits["images"].extend(new_credits)
    credits["updated"] = "2026-11-18"
    (IMG / "credits.json").write_text(json.dumps(credits, indent=2, ensure_ascii=False) + "\n")

    # coverage report
    from collections import Counter
    counts = Counter(p["ref"] for p in snaps)
    ge3 = [r for r, n in counts.items() if n >= 3]
    ge2 = [r for r, n in counts.items() if n >= 2]
    print("TOTAL", len(watches))
    print("by brand", Counter(w["brand"] for w in watches))
    print("history unique refs", len(counts), ">=3", ge3, ">=2", ge2)
    print("missing photos", missing_photos)
    print("new credits", len(new_credits))

if __name__ == "__main__":
    main()
