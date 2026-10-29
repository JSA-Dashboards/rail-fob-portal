"""
Static rail freight reference data — CSX + NS + BN origin spread tables.

Seeded from Kolten's "Rail Spreads.xlsx"
(`…\\Research Analyst\\Misc\\Rail Origins & Destinations\\`), CSX/NS/BN tabs,
via one-off extractions (CSX+NS: 2026-08-21; BN: 2026-08-25, re-seeded from
"Fob BN Corn Plus.xlsx" 2026-10-28).
`csx_freight_seed.json` / `ns_freight_seed.json` / `bn_freight_seed.json` are
committed snapshots — re-run the extraction and overwrite them if Kolten
sends an updated workbook; this module doesn't touch the source file at
runtime.

CSX/NS rows' `highlighted` flag comes straight from an "X"/"x" marker column
Kolten added to the workbook itself — not a hardcoded shortlist. BN's sheet
has no such marker (13 origins, no separate curated subset). BN's seed holds
the freight INPUTS (face rate, miles, FSC $/mile and BN Cars $/car per
period), not pasted totals — `load_bn()` rebuilds the totals.

CSX rates are $/car at the workbook's stated 3500 bu/car. NS rates are
already $/bu. BN rates are $/car at 4000 bu/car (confirmed by cross-checking
its own $/bu sub-table: $/car ÷ 4000 reproduces it exactly). All convert to
¢/bu for display, matching the bid side's units.
"""
import json
import os
import re

_DIR = os.path.dirname(__file__)

CSX_BU_PER_CAR = 3500

# CSX bid-market -> freight column(s) that net against it. Evansville has two
# published variants (by downstream market); AL/TN/KY/LA is the primary one,
# GA/FL is flagged when it differs (Kolten's call, 2026-08-21).
CSX_CORRIDORS = {
    "CSX Columbus":   {"field": "columbus", "market": "CSX Columbus"},
    "CSX Evansville": {"field": "eville_altkyla", "alt_field": "eville_gafl",
                        "market": "CSX Evansville"},
}

# NS has one bid market (Ft Wayne) with three published rate variants by
# downstream market — same "through rate" pattern as CSX's dual Evansville
# rate, just three-wide instead of two (Kolten confirmed, 2026-08-21).
NS_REGIONS = {
    "GA":        "ga",
    "NC/SC/VA":  "ncscva",
    "East":      "east",
}
NS_BID_MARKET = "NS Ft Wayne"
NS_BU_PER_CAR = 3500        # for the fuel surcharge's $/car -> ¢/bu (the same car the CSX workbook uses; NS's isn't stated)


def fsc_cpb(fsc_per_mile, miles, bu_per_car):
    """A $/car-mile fuel surcharge x extra rail miles, in ¢/bu."""
    return fsc_per_mile * miles / bu_per_car * 100

# BN publishes rates by delivery month rather than one flat number — a
# genuinely different shape from CSX/NS. The "Tarif + FSC + Cars" table is
# just a ROLLING ~4-month-ahead window (Kolten, 2026-08-25: "all it is is
# shows the 4 most nearby months") — its header months (and presumably the
# underlying numbers) change whenever Kolten updates the workbook, so
# `load_bn()` always reflects whatever's currently published rather than a
# fixed set. Months outside that window have no published rate at all.
#
# A period nets against the freight for its FIRST named month (Kolten's
# call): "Sep 25-Oct 5" -> Sep, "OCT-MAR" -> Oct, "LH OND" -> Oct (OND is a
# package meaning Oct/Nov/Dec), "JFM" -> Jan (a package meaning Jan/Feb/Mar)
# -> blank if Jan isn't in the current window. "IN TRANSIT"/"RETURN TRIP"
# name no month at all -> blank. This mirrors rail_corridors.py's
# package/month parsing conventions used elsewhere for CSX, but BN's own
# period labels (LH OND, SEP 25-OCT 5, RETURN TRIP...) needed slightly more
# tolerant parsing (a stripped qualifier prefix, packages matched mid-string)
# so it's kept separate rather than importing that module's stricter version.
BN_BU_PER_CAR = 4000
BN_DESTINATIONS = {
    "PNW":      {"field": "pnw", "market": "BN PNW"},
    "Hereford": {"field": "hereford", "market": "BN Hereford"},
}

_BN_MONTH3 = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_BN_MONTH3_REV = {v: k for k, v in _BN_MONTH3.items()}
_BN_PACKAGES = {"jfm": 1, "fma": 2, "mam": 3, "amj": 4, "mjj": 5, "jja": 6,
                 "jas": 7, "aso": 8, "son": 9, "ond": 10, "ndj": 11, "djf": 12,
                 "amjj": 4, "am": 4, "jj": 6, "as": 8, "fm": 2}


def bn_period_first_month(period):
    """First named calendar month (1-12) in a period label, or None if it
    names no month at all (e.g. "In Transit", "Return Trip")."""
    p = re.sub(r"^\s*(FH|LH|MP|SPLIT|FULL)\b\s*", "", period.strip(), flags=re.I).lower()
    if p in _BN_PACKAGES:
        return _BN_PACKAGES[p]
    found = [(p.find(tok), m) for tok, m in _BN_MONTH3.items() if tok in p]
    if not found:
        return None
    found.sort()
    return found[0][1]


def bn_month_sort_key(month_key):
    """Calendar order for a seed-data month key (e.g. 'oct' -> 10), so
    callers can list an origin's published months in the right order
    regardless of which months are currently in the rolling window."""
    return _BN_MONTH3.get(month_key, 99)


def bn_freight_cpb(month_rates, period):
    """month_rates: whatever months are CURRENTLY published, e.g.
    {'aug':..,'sep':..,'oct':..,'nov':..} in ¢/bu (already converted) — the
    exact set rolls over time. Returns the rate for `period`'s first named
    month if that month is in the current window, else None. A legacy 'jj'
    key (if ever present again) covers both Jun and Jul."""
    m = bn_period_first_month(period)
    if m is None:
        return None
    key = _BN_MONTH3_REV[m]
    if key in month_rates:
        return month_rates[key]
    if m in (6, 7) and "jj" in month_rates:
        return month_rates["jj"]
    return None


def _load(name):
    with open(os.path.join(_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def load_csx():
    """[{state, origin_group, train_type, buying_station, highlighted,
         columbus, eville_gafl, eville_altkyla,      <- $/car
         columbus_cpb, eville_gafl_cpb, eville_altkyla_cpb}]  <- ¢/bu"""
    rows = _load("csx_freight_seed.json")
    for r in rows:
        for f in ("columbus", "eville_gafl", "eville_altkyla"):
            r[f"{f}_cpb"] = r[f] / CSX_BU_PER_CAR * 100
    return rows


def load_ns():
    """[{origin, state, highlighted, flag_105,
         ga, ncscva, east,               <- $/bu
         ga_cpb, ncscva_cpb, east_cpb}]  <- ¢/bu"""
    rows = _load("ns_freight_seed.json")
    for r in rows:
        for f in ("ga", "ncscva", "east"):
            r[f"{f}_cpb"] = r[f] * 100
    return rows


def load_bn_seed():
    """The raw BN seed: {source, index_periods, defaults, origins}. `defaults` are the
    shuttle quotes and monthly FSC used until inputs are saved (see bn_inputs.py)."""
    return _load("bn_freight_seed.json")


def load_bn_index_periods():
    """The bid periods the BN tab's FOB Index by State shows, and the ones that get
    FH/LH/Split/OND bid inference: Oct / Nov / Dec / JFM as of 2026-10-28."""
    return load_bn_seed()["index_periods"]


def load_bn(window):
    """[{origin, state, pnw_rate, pnw_miles, herf_rate, herf_miles,
         pnw: {<month key>: $/car}, hereford: {<month key>: $/car},
         pnw_cpb: {...: ¢/bu}, hereford_cpb: {...: ¢/bu}}]
    window = [{key, fsc_per_mile, cars}] — one entry per month with an FSC
    (bn_inputs.effective_window). Freight is built the way the workbook builds
    it (Kolten's "PNW Facing Corn Rates" tab, 2026-10-28): face rate + lane
    miles x that month's fuel surcharge $/mile + the month's BN Cars
    (secondary-market) premium in $/car — PNW takes all of it, Hereford half."""
    rows = load_bn_seed()["origins"]
    for r in rows:
        bn_build_row(r, window)
    return rows


def bn_build_row(r, window):
    """Adds pnw / hereford ($/car by month key) and pnw_cpb / hereford_cpb (¢/bu) to one origin dict that carries
    pnw_rate, pnw_miles, herf_rate, herf_miles. A lane whose rate or miles is None (no list rate, or miles not known yet)
    gets empty dicts, so its FOB shows "—". Shared by the freight sheet's 13 origins and bn_locator's lookup."""
    for lane, rate, miles, share in (("pnw", "pnw_rate", "pnw_miles", 1), ("hereford", "herf_rate", "herf_miles", 0.5)):
        ok = r.get(rate) is not None and r.get(miles) is not None
        r[lane] = {w["key"]: r[rate] + r[miles] * w["fsc_per_mile"] + w["cars"] * share for w in window} if ok else {}
        r[f"{lane}_cpb"] = {m: v / BN_BU_PER_CAR * 100 for m, v in r[lane].items()}
    return r


# CN's sheet is a straight copy of its published Gulf Export tariff (CN
# 004050-A8), not a hand-built spread table like the others. All 187 rows go
# to one destination ("Gulf Exports Group"); rate_a-d are the tariff's own
# rate-column definitions (car size × railway- vs shipper-supplied
# equipment), and multiple rows per origin are different volume/condition
# tiers keyed by `notes` (see CN_NOTES below) — e.g. note "4" = 105+ car
# blocks, matching the existing "CN 105s" bid market; note "1" = 25-49 cars,
# matching "CN 25's". Kolten (2026-08-26): upload the raw rates only for
# now — no bu/car figure or FOB netback logic yet; he's still sorting out
# the basis side, which will reference Corn CIF NOLA from the River FOB
# Portal rather than a rail_fob bid market like CSX/NS/BN use.
CN_NOTES = {
    "1": "Car blocks of 25 to 49 cars",
    "2": "Excludes reciprocal switch at origin",
    "3": "Car blocks of 50 to 104 cars",
    "4": "Car blocks of 105 cars or greater",
    "5": "Not subject to AAR Rule 11 billing at origin",
    "6": "USD, collect (invoiced by destination carrier)",
    "7": "Subject to AAR Rule 11 billing at origin",
    "8": "Includes reciprocal switch at origin, up to $139/car",
    "9": "Car blocks of 50 to 84 cars",
    "10": "Car blocks of 85 cars or more",
}
# Kolten's relabeling (2026-08-26): the tariff's own "A/B/C/D" + cubic-foot/
# supplied-by jargon becomes two independent filterable dimensions —
# car SIZE (Small ≤5149 ft³ vs Large >5149 ft³) and car SOURCE (Railroad-
# supplied vs Private/shipper-supplied) — since that's what a shipper
# actually chooses between, not the tariff's letter codes.
CN_SIZES = {"Small": "≤5149 ft³", "Large": ">5149 ft³"}
CN_SOURCES = {"Railroad": "railway-supplied equipment", "Private": "shipper-supplied equipment"}
CN_RATE_FIELD = {
    ("Small", "Railroad"): "rate_a",
    ("Large", "Railroad"): "rate_b",
    ("Small", "Private"):  "rate_c",
    ("Large", "Private"):  "rate_d",
}

# The real reason an origin has multiple rows: every row goes to the SAME
# destination (all 187 are "Gulf Exports Group" — confirmed, not a filter
# worth having) but at a different shipment-volume tier. Kolten's follow-up
# (2026-08-26): only 3 tiers matter for filtering/highlighting, not 5 — codes
# 3 ("50-104 cars", 41 rows) and 9 ("50-84 cars", 1 row) never both appear on
# the same origin, so they're folded into one mid tier (labeled by the
# dominant code, 3); same for 4 ("105+", 52 rows) and 10 ("85+", 1 row).
CN_VOLUME_TIERS = {
    "1":  "25-49 cars",
    "3":  "50-104 cars",
    "9":  "50-104 cars",
    "4":  "105+ cars",
    "10": "105+ cars",
}
CN_VOLUME_TIER_ORDER = ["25-49 cars", "50-104 cars", "105+ cars"]


def cn_volume_tier(notes):
    """The volume-tier label for a row's `notes` string, or None if it
    carries none of the tier codes."""
    if not notes:
        return None
    codes = notes.split("-")
    for code in codes:
        if code in CN_VOLUME_TIERS:
            return CN_VOLUME_TIERS[code]
    return None


def cn_has_reciprocal_switch(notes):
    """True if this row's rate INCLUDES a reciprocal switch at origin (note
    code 8, up to $139/car) — the exception worth flagging. Code 2 (excludes
    reciprocal switch) is the default on nearly every row and isn't worth
    calling out. Informational only — Kolten asked for this as a note, not
    another filter."""
    return bool(notes) and "8" in notes.split("-")


def load_cn():
    """[{origin, state, destination, rate_a, rate_b, rate_c, rate_d, notes,
         tier, switch}] — $/car rates only; convert to ¢/bu via
    cn_freight_cpb(rate, size, commodity), since the bu/car denominator
    depends on which commodity's filling the car (see CN_BU_PER_CAR)."""
    rows = _load("cn_freight_seed.json")
    for r in rows:
        r["tier"] = cn_volume_tier(r["notes"])
        r["switch"] = cn_has_reciprocal_switch(r["notes"])
    return rows


# Bushels/car for CN's two size classes, by commodity. Corn confirmed with
# Kolten (2026-08-26): weight-based hopper-car capacity (Soy Transportation
# Coalition — 100-ton/4750 ft³ and 110-ton/5750 ft³ reference cars, net
# payload ÷ corn's 56 lb/bu) rather than a naive volumetric conversion, since
# grain shipments are weight-limited, not volume-limited. Soybeans derived
# from that SAME net payload (the car's weight limit doesn't change by
# commodity) ÷ soybeans' 60 lb/bu — i.e. corn bu/car × 56/60 — rather than a
# separately-sourced figure (Kolten's call, 2026-08-26). Depends only on car
# SIZE, not source — a railroad- vs private-supplied car of the same size
# class holds the same number of bushels.
CN_BU_PER_CAR = {
    "Corn":     {"Small": 3570, "Large": 3930},
    "Soybeans": {"Small": 3332, "Large": 3668},
}
CN_COMMODITIES = ["Corn", "Soybeans"]
CN_LB_PER_BU = {"Corn": 56, "Soybeans": 60}


# USDA AMS Grain Transportation Report 10-22-26, Table 7: CN Gibson City, IL -> Reserve, LA, large covered hopper (C-114), 90+ car
# shuttle, tariff per car. The seed (Supplement 41) is the same $495/car lower for BOTH car sources (Large 105+: $2,516 / $2,136), so
# CN's rates read as one flat step up since the supplement (Kolten, 2026-10-28: "CN raised rates this year starting in Oct. Use USDA
# numbers"); applied to every origin as a uniform $/car — USDA lists no other CN origin to check that against.
CN_USDA = {"origin": ("GIBSON CITY", "IL"), "tier": "105+ cars", "Railroad": 3011, "Private": 2631,
           "source": "USDA AMS Grain Transportation Report 10-22-26, Table 7"}


def cn_usda_uplift():
    """$/car that CN's tariff stands above the seed at the USDA origin (the large-car columns, rate_b railroad / rate_d private)."""
    r = next(r for r in load_cn() if (r["origin"], r["state"]) == CN_USDA["origin"] and r["tier"] == CN_USDA["tier"])
    gaps = {CN_USDA["Railroad"] - r["rate_b"], CN_USDA["Private"] - r["rate_d"]}
    return gaps.pop() if len(gaps) == 1 else round(sum(gaps) / len(gaps))


def cn_freight_cpb(rate, size, commodity="Corn", extra=0.0):
    """$/car -> ¢/bu for CN's freight, given a car size and commodity. `extra` is more $/car on top of the tariff rate
    (the fuel surcharge: $/mile x miles, cn_miles.py)."""
    return (rate + extra) / CN_BU_PER_CAR[commodity][size] * 100
