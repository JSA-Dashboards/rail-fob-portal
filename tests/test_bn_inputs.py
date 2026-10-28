"""Pure checks for bn_inputs (no Snowflake): shuttle-label parsing, the quote -> month rule,
and the freight it feeds. Run: python tests/test_bn_inputs.py"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bn_inputs as BNI
import freight_data as FD


def eq(got, want, what):
    assert got == want, f"{what}: got {got!r}, want {want!r}"


# --- labels exactly as the 2026-10-28 sheet writes them
for label, months, kind in [
    ("Return Trip", [], "none"),
    ("F/H November", [11], "fh"),
    ("L/H November", [11], "lh"),
    ("F/H December", [12], "fh"),
    ("December", [12], "full"),
    ("Jan, Feb, Mar 2027", [1, 2, 3], "package"),
    ("April May 2027", [4, 5], "package"),
    ("April - July", [4, 5, 6, 7], "package"),
    ("April - September 2027", [4, 5, 6, 7, 8, 9], "package"),
    ("JFM", [1, 2, 3], "package"),
    ("AMJJ", [4, 5, 6, 7], "package"),
    ("Dec-Feb", [12, 1, 2], "package"),
    ("LH Dec", [12], "lh"),
]:
    eq(BNI.period_months(label), (months, kind), label)

# --- the sheet's quotes -> BN Cars by month (the BID; full month > halves > narrowest package)
d = BNI.default_payload()
cars = BNI.cars_by_month(d["quotes"])
eq(cars.get(10), None, "Oct has no quote")
eq(cars.get(11), None, "Nov: both halves have no bid, no package covers it")
eq(cars[12][0], 0.0, "Dec: the full-month bid (0) wins over F/H Dec 25")
eq([cars[m][0] for m in (1, 2, 3)], [450.0] * 3, "Jan-Mar")
eq([cars[m][0] for m in (4, 5)], [100.0] * 2, "Apr-May: the April-May package")
eq([cars[m][0] for m in (6, 7)], [100.0] * 2, "Jun-Jul: April-July is the narrowest covering it")
eq([cars[m][0] for m in (8, 9)], [0.0] * 2, "Aug-Sep: April-September")

# F/H + L/H midpoint only when both are bid; a lone half stands; no full month beats a package
q = [{"period": "F/H Nov", "bid": 10}, {"period": "L/H Nov", "bid": 30}, {"period": "Nov-Dec", "bid": 99}]
eq(BNI.cars_by_month(q)[11][0], 20.0, "midpoint of two halves beats the package")
eq(BNI.cars_by_month(q)[12][0], 99.0, "Dec only has the package")
eq(BNI.cars_by_month([{"period": "L/H Nov", "bid": 30}])[11][0], 30.0, "lone half")

# --- rows / window: a month with no FSC has no freight; an override beats the quote
rows = BNI.month_rows(d)
eq([r["key"] for r in rows], ["oct", "nov", "dec", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep"], "crop-year order")
win = BNI.effective_window(d)
eq([w["key"] for w in win], ["oct", "nov", "dec", "jan", "feb", "mar"], "months with an FSC")
eq([w["cars"] for w in win], [0.0, 0.0, 0.0, 450.0, 450.0, 450.0], "cars per month")
d2 = json.loads(json.dumps(d))
d2["months"][0]["cars_override"] = 250
d2["months"][6]["fsc"] = 0.5   # Apr gets an FSC -> it joins the window with its package value
w2 = BNI.effective_window(d2)
eq(w2[0]["cars"], 250.0, "override wins")
eq([w["key"] for w in w2][-1], "apr", "Apr joins once it has an FSC")
eq(w2[-1]["cars"], 100.0, "Apr's value comes from the April-May package")

# --- the freight it feeds: Breckenridge PNW, rate 5590 / 1579 miles
r = FD.load_bn(win)[0]
eq(r["origin"], "Breckenridge, MN", "first origin")
eq(round(r["pnw"]["oct"], 2), 6300.55, "PNW Oct = 5590 + 1579 x .45 + 0")
eq(round(r["pnw"]["jan"], 2), round(5590 + 1579 * 0.50 + 450, 2), "PNW Jan")
eq(round(r["hereford"]["jan"], 2), round(6040 + 1203 * 0.50 + 225, 2), "Hereford Jan takes half the cars")
assert "apr" not in r["pnw"], "no FSC, no freight"

# --- problems() warns, never raises
assert BNI.problems({"quotes": [{"period": "Weekly special", "bid": 1}], "months": [{"key": "oct", "fsc": 9}]})
eq(BNI.problems(d), [], "the defaults are clean")

print("test_bn_inputs: all ok")
