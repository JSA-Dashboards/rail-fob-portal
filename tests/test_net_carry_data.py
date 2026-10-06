"""The Net Carry tab's data adapter: which corridors / dates can show a carry ladder, the bids as net_carry items
(an 'R' package, a missing bid, Palmetto's two-letter futures codes), the freight exclusion, who the comparison
starts with, and the futures-curve lookup (latest day on or before the as-of date).

    python tests/test_net_carry_data.py

Pure: no Snowflake, no Streamlit. The futures query runs against a throwaway in-memory SQLite — the SQL is the
same text the portal sends to Snowflake (only the placeholder differs, translated below).
"""
import os
import sqlite3
import sys
from datetime import date

try:                                    # check names use arrows / dashes; a cp1252 console would choke on them
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import net_carry as nc                 # noqa: E402  (vendored — the maths this adapter feeds)
import net_carry_compare as cmp_       # noqa: E402
import net_carry_data as nd            # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name, ("  -- " + str(detail)) if (detail and not cond) else ""))
    if not cond:
        FAILS.append(name)


def close(a, b, tol=1e-9):
    return a is not None and abs(a - b) <= tol


def R(src, market, day, period, fut, bid, offer=None, com="Corn", rail="CSX"):
    return {"source": src, "market": market, "date": day, "period": period, "period_order": 0, "futures": fut,
            "bid": bid, "offer": offer, "commodity": com, "rail": rail, "bid_raw": None, "offer_raw": None}


# ── a small archive, in the shape rail_data.get_all() returns (dates are 'YYYY-MM-DD' strings) ──────────
ROWS = [
    # CSX Columbus, Fri 2026-10-02 — the live rundown's shape: a package ('R'), an offer-only row, a bid per period
    R("manual", "CSX Columbus", "2026-10-02", "FH Oct", "ZCZ26", -10, -2),
    R("manual", "CSX Columbus", "2026-10-02", "Nov", "ZCZ26", 16, 23),
    R("manual", "CSX Columbus", "2026-10-02", "FH Dec", "ZCH27", 8, 13),
    R("manual", "CSX Columbus", "2026-10-02", "Dec", "ZCH27", 14, 18),
    R("manual", "CSX Columbus", "2026-10-02", "JFM", "ZCH27", 17, 20),
    R("manual", "CSX Columbus", "2026-10-02", "AMJJ", "R", 20),                 # a package spanning months
    R("manual", "CSX Columbus", "2026-10-02", "LH Nov", "ZCZ26", None, 5),      # offer only: no bid to carry
    # an earlier day with a ladder, and the weekly spot history that came before the forward rundowns
    R("manual", "CSX Columbus", "2026-09-29", "Nov", "ZCZ26", 12),
    R("manual", "CSX Columbus", "2026-09-29", "Dec", "ZCH27", 9),
    R("manual", "CSX Columbus", "2026-06-17", "Spot", "ZCN26", 42),
    R("manual", "CSX Columbus", "2026-06-10", "Spot", "ZCN26", 40),
    # the same corridor's soybeans (a second commodity)
    R("manual", "CSX Columbus", "2026-10-02", "Nov", "ZSX26", 10, com="Soybeans"),
    R("manual", "CSX Columbus", "2026-10-02", "Jan", "ZSF27", 14, com="Soybeans"),
    # freight lines — $/car, not bids
    R("manual", "CSX Freight", "2026-10-02", "Spot", None, 1500),
    R("manual", "CSX Freight", "2026-10-02", "Return Trip", None, 1400),
    R("manual", "UP Freight", "2026-10-02", "Spot", None, 3000),
    R("manual", "BN 110 Shuttle", "2026-10-02", "Oct", None, 4000),
    # other corridors the comparison can use
    R("manual", "CSX Evansville", "2026-10-01", "Nov", "ZCZ26", 20),
    R("manual", "CSX Evansville", "2026-10-01", "Dec", "ZCH27", 12),
    R("manual", "NS Ft Wayne", "2026-10-02", "Nov", "ZCZ26", 13, rail="NS"),
    R("manual", "NS Ft Wayne", "2026-10-02", "Dec", "ZCH27", 5, rail="NS"),
    R("manual", "BN Hereford", "2026-10-02", "Nov", "ZCZ26", 110, rail="BNSF"),
    R("manual", "BN Hereford", "2026-10-02", "Dec", "ZCH27", 120, rail="BNSF"),
    R("manual", "UP Group 3", "2026-09-15", "Nov", "ZCZ26", -10, rail="UP"),      # 17 days before 10-02: too old
    R("manual", "UP Group 3", "2026-09-15", "Dec", "ZCH27", 0, rail="UP"),
    R("manual", "CN 105s Beans", "2026-10-02", "Oct", "ZSX26", 1, rail="CN", com="Soybeans"),
    R("manual", "CN 105s Beans", "2026-10-02", "Dec", "ZSF27", 7, rail="CN", com="Soybeans"),
    R("manual", "BN COBO Buyers", "2026-09-02", "Oct", "ZCZ26", 100, rail="BNSF"),   # one period: never a ladder
    R("manual", "BN COBO Buyers", "2026-10-02", "Oct", "ZCZ26", None, 90, rail="BNSF"),  # offer only
    R("manual", "Some New Corridor", "2026-10-02", "Nov", "ZCZ26", 1, rail="XX"),
    R("manual", "Some New Corridor", "2026-10-02", "Dec", "ZCH27", 2, rail="XX"),
    # Palmetto's scrape: two-letter futures codes, ALL-CAPS month names
    R("palmetto", "COL, OH Beans 90's", "2026-10-02", "OCTOBER", "SX", -25, com="Soybeans"),
    R("palmetto", "COL, OH Beans 90's", "2026-10-02", "NOVEMBER", "SX", 0, com="Soybeans"),
    R("palmetto", "COL, OH Beans 90's", "2026-10-02", "December", "SF", 15, com="Soybeans"),
    R("palmetto", "EVILLE, Corn- 90's", "2026-10-02", "October", "CZ", -14),
    R("palmetto", "EVILLE, Corn- 90's", "2026-10-02", "December", "CH", 10),
]
ASOF = date(2026, 10, 2)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("net_carry_data: which markets are bids")
check("the freight-rate lines are not FOB bids",
      not any(nd.is_bid_market(m) for m in ("BN Freight", "UP Freight", "CPKC Freight", "CSX Freight", "UP 110 Shuttle", "BN 110 Shuttle")))
check("corridors (and Palmetto's boards) are",
      all(nd.is_bid_market(m) for m in ("CSX Columbus", "CN 25's", "CN 105s Beans", "COL, OH Beans 90's", "BN PNW CP")))

print("net_carry_data: futures codes")
check("Palmetto's two-letter code gets the year from the posting date (the first such contract on/after the posting month)",
      nd.full_symbol("SX", date(2026, 10, 2)) == "ZSX26" and nd.full_symbol("SF", date(2026, 10, 2)) == "ZSF27"
      and nd.full_symbol("CZ", date(2023, 11, 7)) == "ZCZ23" and nd.full_symbol("CH", date(2023, 11, 7)) == "ZCH24")
check("the posting's own month counts (Sep corn posted in Sep is this year's)", nd.full_symbol("CU", date(2026, 9, 10)) == "ZCU26")
check("an earlier month than the posting rolls to NEXT year (Jul corn posted in Oct)", nd.full_symbol("CN", date(2026, 10, 2)) == "ZCN27")
check("a full symbol, an 'R' package and a note pass through; blank -> None",
      nd.full_symbol("ZCZ26", ASOF) == "ZCZ26" and nd.full_symbol("zcz26", ASOF) == "ZCZ26" and nd.full_symbol("R", ASOF) == "R"
      and nd.full_symbol("", ASOF) is None and nd.full_symbol(None, ASOF) is None and nd.full_symbol("NoBN", ASOF) == "NOBN")
check("ALL-CAPS full month names fold to one spelling; codes meant to be capitals do not",
      nd.tidy_label("OCTOBER") == "October" and nd.tidy_label("October") == "October" and nd.tidy_label("JFM") == "JFM"
      and nd.tidy_label("OCT/NOV") == "OCT/NOV" and nd.tidy_label("  FH   Dec ") == "FH Dec")

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("net_carry_data: one corridor's posting as net_carry items")
items = nd.corridor_items(ROWS, "manual", "CSX Columbus", "Corn", "2026-10-02")
check("one item per BID: the offer-only row is left out, the 'R' package is kept",
      [i["delivery"] for i in items] == ["FH Oct", "Nov", "FH Dec", "Dec", "JFM", "AMJJ"], items)
check("the shape net_carry takes: delivery label, futures symbol, basis in cents as posted",
      items[0] == {"delivery": "FH Oct", "futures": "ZCZ26", "basis": -10} and items[-1] == {"delivery": "AMJJ", "futures": "R", "basis": 20})
check("another day / commodity / corridor / source never leaks in",
      nd.corridor_items(ROWS, "manual", "CSX Columbus", "Soybeans", "2026-10-02") == [
          {"delivery": "Nov", "futures": "ZSX26", "basis": 10}, {"delivery": "Jan", "futures": "ZSF27", "basis": 14}]
      and [i["delivery"] for i in nd.corridor_items(ROWS, "manual", "CSX Columbus", "Corn", "2026-09-29")] == ["Nov", "Dec"]
      and nd.corridor_items(ROWS, "palmetto", "CSX Columbus", "Corn", "2026-10-02") == []
      and nd.corridor_items(ROWS, "manual", "NOPE", "Corn", "2026-10-02") == [])
check("a missing commodity means corn (the archive's older rows have none)",
      nd.corridor_items([R("manual", "X", "2026-10-02", "Nov", "ZCZ26", 1, com=None)], "manual", "X", "Corn", "2026-10-02")[0]["basis"] == 1)
pal = nd.corridor_items(ROWS, "palmetto", "COL, OH Beans 90's", "Soybeans", "2026-10-02")
check("Palmetto's rows come out with full symbols and one spelling per month",
      pal == [{"delivery": "October", "futures": "ZSX26", "basis": -25}, {"delivery": "November", "futures": "ZSX26", "basis": 0},
              {"delivery": "December", "futures": "ZSF27", "basis": 15}], pal)
raw_pal = [{"delivery": "October", "futures": "SX", "basis": -25}, {"delivery": "December", "futures": "SF", "basis": 15}]
rows0, meta0 = nc.compute_net_carry(raw_pal, "ZSX26", {"ZSX26": 1284.0, "ZSF27": 1300.75}, 10, 0.06)
check("WHY the codes are completed: net_carry cannot place a delivery whose futures has no year — the whole ladder drops out",
      rows0 == [] and meta0["skipped"] == ["October", "December"], (len(rows0), meta0["skipped"]))

print("net_carry_data: the items through the vendored maths (hand-checked)")
CURVE = {"ZCZ26": 500.0, "ZCH27": 515.0}
RATE = 0.06
rows_, meta_ = nc.compute_net_carry(items, "ZCZ26", CURVE, 10, RATE)
by = {r.delivery: r for r in rows_}
check("the package has no single delivery month: set aside, not on the ladder", meta_["skipped"] == ["AMJJ"] and "AMJJ" not in by, meta_["skipped"])
check("anchor = the October delivery in the posting; interest is 0 there", meta_["anchor_ym"] == (2026, 10) and by["FH Oct"].interest == 0.0)
check("Nov: bid 16 vs ZCZ26 (the reference) — interest 500 x 6% x 31/360, net = 16 - that",
      close(by["Nov"].basis_ref, 16) and close(by["Nov"].interest, 500 * 0.06 * 31 / 360) and close(by["Nov"].net, 16 - 500 * 0.06 * 31 / 360), by["Nov"])
check("Dec: bid 14 vs ZCH27 — basis REF = 14 + (515 - 500) = 29; interest 500 x 6% x 61/360; net = 29 - 5.0833",
      close(by["Dec"].credit, 15) and close(by["Dec"].basis_ref, 29) and close(by["Dec"].interest, 500 * 0.06 * 61 / 360)
      and close(by["Dec"].net, 29 - 500 * 0.06 * 61 / 360), by["Dec"])
check("JFM sits on March (its futures month): 151 days from Oct 1; 17 + 15 - 500 x 6% x 151/360",
      by["JFM"].ym == (2027, 3) and by["JFM"].days == 151 and close(by["JFM"].net, 32 - 500 * 0.06 * 151 / 360), by["JFM"])
pts = nc.monthly_carry(rows_)
top = nc.top_of_net_carry(pts, meta_["anchor_ym"])
check("the top of net carry is Dec 26 and equals the highest Net of Interest in the table from the carry start",
      top["label"] == "Dec 26" and close(top["net"], max(r.net for r in rows_ if r.ym >= meta_["anchor_ym"]))
      and close(top["net"], 29 - 500 * 0.06 * 61 / 360), top)
check("...and its table row is the Dec slot (the one the tab tags)", rows_[top["row"]].delivery == "Dec")

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("net_carry_data: the corridor catalog")
cat = nd.build_catalog(ROWS)
keys = [c.key for c in cat]
check("freight lines are not in the catalog at all", not any("Freight" in k or "Shuttle" in k for k in keys), keys)
check("a corridor whose only bid-bearing day has one period has no ladder date; one with no bid is not listed",
      next(c for c in cat if c.market == "BN COBO Buyers").dates == () and sum(c.market == "BN COBO Buyers" for c in cat) == 1)
check("the portal's corridor order first (CSX, NS, UP, BN, CN as rail_corridors lists them), then what the registry doesn't know, alphabetical",
      [c.market for c in cat] == ["CSX Columbus", "CSX Columbus", "CSX Evansville", "NS Ft Wayne", "UP Group 3", "BN Hereford",
                                  "BN COBO Buyers", "CN 105s Beans", "COL, OH Beans 90's", "EVILLE, Corn- 90's", "Some New Corridor"],
      [c.market for c in cat])
csx = {c.commodity: c for c in cat if c.market == "CSX Columbus"}
check("a corridor with two commodities gets the commodity in its label; keys are unique",
      csx["Corn"].label == "CSX Columbus · Corn" and csx["Soybeans"].label == "CSX Columbus · Soybeans" and len(set(keys)) == len(keys), [c.label for c in cat])
check("ladder dates = posting days with 2+ priced periods, newest first; every bid day is in `posted`",
      csx["Corn"].dates == ("2026-10-02", "2026-09-29") and csx["Corn"].posted == ("2026-10-02", "2026-09-29", "2026-06-17", "2026-06-10"), csx["Corn"])
check("the weekly spot postings are counted, not offered", csx["Corn"].spot_only == 2)
pal_b = next(c for c in cat if c.source == "palmetto" and c.commodity == "Soybeans")
check("Palmetto's board is labelled as such and keeps its carrier", pal_b.label == "COL, OH Beans 90's (Palmetto)" and pal_b.rail == "CSX" and pal_b.dates == ("2026-10-02",))
check("the portal's own display names are used (CP PNW, Allen Station)",
      nd.corridor_label("manual", "BN PNW CP") == "CP PNW" and nd.corridor_label("manual", "UP Illinois (Dom)") == "Allen Station (Dom)"
      and nd.corridor_label("manual", "CSX Columbus") == "CSX Columbus")

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("net_carry_data: who the comparison offers and starts with")
main = csx["Corn"]
opts = nd.compare_options(cat, main, ASOF)
om = [c.market for c in opts]
check("same commodity only, never the corridor itself", all(c.commodity == "Corn" for c in opts) and main.key not in {c.key for c in opts}, om)
check("a corridor whose last posting is older than 10 days is not offered (UP Group 3 posted 17 days earlier)", "UP Group 3" not in om, om)
check("soybean corridors are not offered against a corn one; Palmetto's corn board is", "CN 105s Beans" not in om and "EVILLE, Corn- 90's" in om, om)
check("a posting AFTER the as-of date does not count", "CSX Evansville" in [c.market for c in nd.compare_options(cat, main, date(2026, 10, 1))]
      and "NS Ft Wayne" not in [c.market for c in nd.compare_options(cat, main, date(2026, 10, 1))])
check("latest_posting is the vendored pick_latest rule (newest on/before the as-of date, within 10 days)",
      all(nd.latest_posting(c, a) == cmp_.pick_latest(sorted(date.fromisoformat(d) for d in c.posted), a, 10)
          for c in cat for a in (date(2026, 9, 1), date(2026, 9, 29), date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 12), date(2026, 10, 13), date(2026, 11, 30))))
peers = nd.default_peers(main, opts)
check("defaults: the same railroad's other corridor first, then padded alphabetically; Palmetto's boards are not defaults",
      [c.market for c in peers] == ["CSX Evansville", "BN Hereford", "NS Ft Wayne"], [c.market for c in peers])
check("fewer candidates than asked -> just those", len(nd.default_peers(main, opts[:1], 3)) == 1 and nd.default_peers(main, [], 3) == [])

print("net_carry_data: comparison columns")
ev = next(c for c in opts if c.market == "CSX Evansville")
up3 = next(c for c in cat if c.market == "UP Group 3")
ents = nd.comparison_entries(ROWS, main, items, ASOF, [ev, up3])
check("main first, flagged, on its own posting; the picked after it",
      [e.name for e in ents] == ["CSX Columbus · Corn", "CSX Evansville", "UP Group 3"] and ents[0].is_main and ents[0].quote_date == ASOF and not ents[1].is_main)
check("a picked corridor is read on its latest posting on/before the as-of date (Evansville: 10-01, a day earlier)",
      ents[1].quote_date == date(2026, 10, 1) and [i["delivery"] for i in ents[1].items] == ["Nov", "Dec"])
check("one that has gone quiet is a 'no recent quote' column, not an error", ents[2].items == [] and ents[2].quote_date is None)
res = cmp_.build_comparison(ents, "ZCZ26", CURVE, 10, meta_["anchor_ym"], RATE, "net", ASOF)
c_main, c_ev, c_up = res["columns"]
check("the main column is exactly the main table (same numbers)", all(close(c_main["points"][p["ym"]]["value"], p["net"]) for p in pts))
check("Evansville Nov re-based to ZCZ26 on the SAME interest clock: 20 - 500 x 6% x 31/360", close(c_ev["points"][(2026, 11)]["value"], 20 - 500 * 0.06 * 31 / 360), c_ev["points"])
check("its column is flagged as one day older than the as-of date; the quiet one has no data", c_ev["stale"] and c_up["no_data"])
check("the comparison's top for the main corridor is the same Dec 26 the ladder names", c_main["top"]["label"] == "Dec 26" and close(c_main["top"]["net"], top["net"]))

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("net_carry_data: the futures curve — the latest day on or before the as-of date")
db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE futures_prices (date TEXT NOT NULL, symbol TEXT NOT NULL, price_cents REAL, captured_at TEXT)")
db.executemany("INSERT INTO futures_prices (date, symbol, price_cents) VALUES (?,?,?)", [
    ("2026-09-30", "ZCZ26", 495.0),
    ("2026-10-01", "ZCZ26", 498.5), ("2026-10-01", "ZCH27", 512.0),
    ("2026-10-02", "ZCZ26", 502.25), ("2026-10-02", "ZCH27", 516.75), ("2026-10-02", "ZSX26", 1284.0), ("2026-10-02", "ZCK27", None),
    ("2026-10-05", "ZCZ26", 510.0),
])
CALLS = []


def fake_rows(sql, params):
    """The portal's rail_data._rows contract: (sql with %s placeholders, params) -> [dict]."""
    CALLS.append((sql, params))
    cur = db.execute(sql.replace("%s", "?"), params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


cv, day = nd.futures_curve(date(2026, 10, 2), fake_rows)
check("an as-of date WITH a stored curve reads exactly that day", day == date(2026, 10, 2) and cv == {"ZCZ26": 502.25, "ZCH27": 516.75, "ZSX26": 1284.0}, (day, cv))
check("a NULL price is skipped, never read as zero", "ZCK27" not in cv)
cv2, day2 = nd.futures_curve(date(2026, 10, 3), fake_rows)
check("a Saturday reads Friday's curve (latest day on or before)", day2 == date(2026, 10, 2) and cv2 == cv, (day2, cv2))
check("a Sunday too", nd.futures_curve(date(2026, 10, 4), fake_rows)[1] == date(2026, 10, 2))
cv3, day3 = nd.futures_curve(date(2026, 10, 5), fake_rows)
check("a day with its own curve gets it, not the previous day's symbols mixed in", day3 == date(2026, 10, 5) and cv3 == {"ZCZ26": 510.0}, cv3)
check("a day after the archive's last stored day reads the last one", nd.futures_curve(date(2026, 12, 25), fake_rows)[1] == date(2026, 10, 5))
check("a date before the archive starts -> an empty curve and no day (the tab says so instead of raising)",
      nd.futures_curve(date(2026, 9, 29), fake_rows) == ({}, None))
check("one query per lookup; the date is a bound parameter, not pasted into the SQL",
      len(CALLS) == 6 and [p for _, p in CALLS] == [("2026-10-02",), ("2026-10-03",), ("2026-10-04",), ("2026-10-05",), ("2026-12-25",), ("2026-09-29",)]
      and all("2026" not in s and s.count("%s") == 1 for s, _ in CALLS), [p for _, p in CALLS])
check("rail_data is not imported until a lookup needs its connection", "rail_data" not in sys.modules)

print("net_carry_data: the whole futures history of a commodity (Return to Carry)")
db.execute("INSERT INTO futures_prices (date, symbol, price_cents) VALUES ('2026-10-06', 'ZSF27', 1301.5)")
CALLS.clear()
fh = nd.futures_history("ZC", fake_rows)
check("one query, the root a bound LIKE parameter and the start date another (nothing pasted into the SQL)",
      len(CALLS) == 1 and CALLS[0][1] == ("ZC%", "2004-01-01") and "ZC" not in CALLS[0][0] and CALLS[0][0].count("%s") == 2, CALLS)
check("every stored corn contract of every day, as {date: {symbol: cents}}, a NULL price skipped; soybeans are not in it",
      fh[date(2026, 10, 2)] == {"ZCZ26": 502.25, "ZCH27": 516.75} and fh[date(2026, 9, 30)] == {"ZCZ26": 495.0} and fh[date(2026, 10, 5)] == {"ZCZ26": 510.0}
      and not any(s.startswith("ZS") for px in fh.values() for s in px) and "ZCK27" not in fh[date(2026, 10, 2)])
check("the analyst-sheet weeks before the settlement archive are underneath (corn from 1996), the stored settlements on top",
      min(fh) < date(2006, 1, 1) and all(s.startswith("ZC") for px in fh.values() for s in px))
fs = nd.futures_history("ZS", fake_rows)
check("soybeans: the sheet weeks from 2005 and the stored settlements, ZS contracts only", min(fs) < date(2007, 1, 1) and fs[date(2026, 10, 6)] == {"ZSF27": 1301.5}
      and fs[date(2026, 10, 2)] == {"ZSX26": 1284.0})

print("\n" + ("ALL PASS" if not FAILS else "FAILURES: %s" % FAILS))
sys.exit(1 if FAILS else 0)
