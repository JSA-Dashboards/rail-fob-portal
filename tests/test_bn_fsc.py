"""Pure checks for bn_fsc (no network): the formula against the four surcharges BN has published, the open /
forecast months, and how bn_inputs uses it. Run: python tests/test_bn_fsc.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bn_fsc as F
import bn_inputs as BNI


def eq(got, want, what):
    assert got == want, f"{what}: got {got!r}, want {want!r}"


# EIA weekly US on-highway diesel (No 2), Mondays, Jun-Oct 2026
WEEKLY = [
    ('2026-06-01', 5.35),
    ('2026-06-08', 5.21),
    ('2026-06-15', 5.059),
    ('2026-06-22', 4.832),
    ('2026-06-29', 4.668),
    ('2026-07-06', 4.578),
    ('2026-07-13', 4.796),
    ('2026-07-20', 5.134),
    ('2026-07-27', 5.313),
    ('2026-08-03', 5.348),
    ('2026-08-10', 5.257),
    ('2026-08-17', 5.454),
    ('2026-08-24', 5.652),
    ('2026-08-31', 5.599),
    ('2026-09-07', 5.967),
    ('2026-09-14', 6.285),
    ('2026-09-21', 6.529),
    ('2026-09-28', 6.382),
    ('2026-10-05', 6.199),
    ('2026-10-12', 6.179),
    ('2026-10-19', 6.276),
    ('2026-10-26', 6.352),
]

# --- the formula reproduces every surcharge Kolten has had (the evidence it was built from)
eq(F.fsc_from_diesel(5.024), 0.36, "Aug: Jun diesel")
eq(F.fsc_from_diesel(4.955), 0.35, "Sep: Jul diesel")
eq(F.fsc_from_diesel(5.462), 0.45, "Oct: Aug diesel")
eq(F.fsc_from_diesel(6.291), 0.61, "Nov: Sep diesel")
eq(F.fsc_from_diesel(3.25), 0.0, "at the strike")
eq(F.fsc_from_diesel(3.30), 0.01, "one step started")
eq(F.fsc_from_diesel(3.35), 0.02, "an exact step is not rounded past")
eq(F.fsc_from_diesel(2.9), 0.0, "under the strike")

# --- the table as of Oct 28 2026 (latest week Oct 26)
t = F.auto_table(WEEKLY, date(2026, 10, 28))
eq([t[k]["fsc"] for k in ("oct", "nov")], [0.45, 0.61], "Oct / Nov from Aug / Sep diesel")
eq(t["oct"]["kind"], "published", "Oct is published")
eq(t["dec"]["kind"], "published", "Dec: Oct is complete once Oct 26 is in")
eq(t["dec"]["fsc"], 0.61, "Dec from Oct diesel 6.252")
eq(t["jan"]["kind"], "forecast", "Jan needs Nov diesel: not started")
eq(t["jan"]["fsc"], F.fsc_from_diesel(6.352), "forecast = latest week held flat")
eq(t["sep"]["fsc"], t["jan"]["fsc"], "every forecast month is the same steady number")
eq(F.auto_table(WEEKLY[:-2], date(2026, 10, 14))["dec"]["kind"], "open", "Oct still in progress -> average so far")
eq(F.auto_table([], date(2026, 10, 28)), {}, "no diesel, no table")
eq([k for k, _, _ in F.grid_months(date(2026, 10, 28))][:3], ["oct", "nov", "dec"], "grid order")
eq(F.grid_months(date(2026, 10, 28))[3][1:], (2027, 1), "Jan is next year")
eq(F.grid_months(date(2027, 2, 1))[0][1:], (2026, 10), "in Feb the grid still starts at last Oct")

# --- bn_inputs: formula by default, a typed override wins, no diesel falls back to typed + held flat
d = BNI.default_payload()
eq(d["fsc_mode"], "formula", "the defaults use the formula")
rows = BNI.month_rows(d, t)
eq([r["fsc"] for r in rows][:3], [0.45, 0.61, 0.61], "Oct / Nov / Dec from the formula, not the typed .55")
assert rows[0]["fsc_source"].startswith("formula: Aug diesel 5.462"), rows[0]["fsc_source"]
d2 = dict(d, months=[dict(m) for m in d["months"]])
d2["months"][2]["fsc_override"] = 0.55
r2 = BNI.month_rows(d2, t)
eq((r2[2]["fsc"], r2[2]["fsc_source"]), (0.55, "override"), "a typed override wins")
eq(r2[3]["fsc"], t["jan"]["fsc"], "other months stay on the formula")
r3 = BNI.month_rows(d, None)
eq([r["fsc"] for r in r3][:6], [0.45, 0.61, 0.55, 0.5, 0.5, 0.5], "no diesel -> the typed FSC")
eq(r3[6]["fsc_source"], "held flat from Mar", "...held flat after the last typed month")
eq(BNI.month_rows(dict(d, fsc_mode="typed"), t)[2]["fsc"], 0.55, "typed mode ignores the formula")
eq([w["key"] for w in BNI.effective_window(d, t)], [r["key"] for r in rows], "every month has an FSC")

print("test_bn_fsc: all ok")
