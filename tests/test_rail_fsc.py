"""Pure checks for rail_fsc (no network): every railroad's formula against the surcharges its page (or the USDA AMS
report) showed, from the EIA monthly-average diesel prices behind them. Run: python tests/test_rail_fsc.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bn_fsc as BNF
import rail_fsc as RF


def eq(got, want, what):
    assert abs(got - want) < 1e-9, f"{what}: got {got!r}, want {want!r}"


# EIA monthly averages of the weekly US on-highway diesel price (No 2), by SOURCE month — the surcharge is two months later
DIESEL = {"2026-04": 5.501, "2026-06": 5.024, "2026-07": 4.955, "2026-08": 5.462, "2026-09": 6.291}
LATER = {"2026-04": "2026-06", "2026-06": "2026-08", "2026-07": "2026-09", "2026-08": "2026-10", "2026-09": "2026-11"}

for rr, p in RF.PROGRAMS.items():
    for applies, want in p["published"].items():
        src = next(s for s, a in LATER.items() if a == applies) if applies in LATER.values() else None
        if src is None:       # a published month whose diesel month isn't in the fixture (BN's August)
            continue
        eq(RF.fsc(rr, DIESEL[src]), want, f"{rr} {applies} (diesel {src} {DIESEL[src]})")

# BN's generic program is the same formula bn_fsc.py was fitted with
for price in (4.955, 5.024, 5.462, 6.291, 6.252, 6.352, 3.25, 3.26):
    eq(RF.fsc("BN", price), BNF.fsc_from_diesel(price), f"BN generic vs bn_fsc at {price}")

# rounding details that distinguish the programs
eq(RF.fsc("UP", 2.30), 0.05, "UP pays its 5c base at the strike")
eq(RF.fsc("UP", 2.349), 0.05, "UP counts full steps only")
eq(RF.fsc("UP", 2.35), 0.06, "UP's first full step")
eq(RF.fsc("BN", 3.251), 0.01, "BN counts a started step")
eq(RF.fsc("NS", 6.299), RF.fsc("NS", 6.29), "NS cuts the diesel price to the cent")
eq(RF.fsc("CN", 6.291), 1.039, "CN, 160 steps of 0.6496c")
eq(RF.fsc("CN", 4.955), 0.695, "CN, 107 steps = 0.695072 (USDA Sep)")
eq(RF.fsc("UP", 1.0), 0.0, "under the strike")

# the month table works for another railroad
weekly = [("2026-08-03", 5.4), ("2026-08-10", 5.5), ("2026-09-07", 6.3), ("2026-09-14", 6.3), ("2026-10-05", 6.2), ("2026-10-26", 6.35)]
t = RF.table("UP", weekly, date(2026, 10, 28))
eq(t["oct"]["fsc"], RF.fsc("UP", 5.45), "UP Oct from Aug diesel")
assert t["oct"]["kind"] == "published" and t["jan"]["kind"] == "forecast"
assert "\\$2.30" in RF.equation("UP") and "5¢ plus" in RF.equation("UP")
assert "\\$3.749" in RF.equation("CSX")

print("test_rail_fsc: all ok")
