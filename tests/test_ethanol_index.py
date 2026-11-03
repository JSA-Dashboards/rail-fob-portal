"""ethanol_index: plants' latest corn bids averaged by state and delivery month. Run: python tests/test_ethanol_index.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ethanol_index as EI

def R(prov, loc, st, grain, month, fut, basis, spot=0):
    return {"provider": prov, "location": loc, "state": st, "grain": grain, "delivery_month": month, "futures_symbol": fut,
            "basis_cents": basis, "is_spot": spot}

rows = [R("A", "Plant 1", "IL", "Corn", "Nov 2026", "ZCZ26", 0), R("B", "Plant 2", "IL", "Corn", "Nov 2026", "ZCZ26", -10),
        R("B", "Plant 2", "IL", "Corn", "Nov 2026", "ZCZ26", -20),            # a second bid for the same plant and month: averaged first
        R("C", "Plant 3", "IA", "Corn", "Dec 2026", "ZCZ26", -20),
        R("A", "Plant 1", "IL", "Corn", "Spot", "ZCZ26", 50, spot=1),         # spot is not a forward month
        R("D", "Plant 4", "IL", "Soybeans", "Nov 2026", "ZSF27", 99)]         # not corn
idx = EI.state_index(rows)
assert idx["IL"][(2026, 11)] == ((0 + (-15)) / 2, 2), idx["IL"]                # plants: 0 and (-10, -20 -> -15)
assert idx["IA"][(2026, 12)] == (-20, 1) and set(idx) == {"IL", "IA"}
today = date(2026, 11, 2)
assert EI.lookup(idx, "IL", 11, today) == (-7.5, 2) and EI.lookup(idx, "IA", 12, today) == (-20, 1)
assert EI.lookup(idx, "IL", 12, today) is None and EI.lookup(idx, "TX", 11, today) is None
assert EI.lookup({"IL": {(2027, 1): (5, 3)}}, "IL", 1, today) == (5, 3)       # January means next year's
print("test_ethanol_index: all ok")

# ---- per-location series (State Level tab)
def L(ft, prov, loc, grain, month, fut, basis, spot=0):
    return {"facility_type": ft, "provider": prov, "location": loc, "grain": grain, "delivery_month": month, "futures_symbol": fut,
            "basis_cents": basis, "is_spot": spot}

ser = EI.location_series([L("River Terminal", "ADM", "Havana, IL", "Corn", "Nov 2026", "ZCZ26", 10), L("River Terminal", "ADM", "Havana, IL", "Corn", "Nov 2026", "ZCZ26", 20),
                          L("Corn Processing", "ADM", "Decatur", "Corn", "Dec 2026", "ZCZ26", -5), L("Corn Processing", "ADM", "Decatur", "Soybeans", "Dec 2026", "ZSF27", 99),
                          L("Corn Processing", "ADM", "Decatur", "Corn", "Spot", "ZCZ26", 50, spot=1)])
assert ser[("River Terminal", "ADM", "Havana, IL")] == {(2026, 11): 15.0} and ser[("Corn Processing", "ADM", "Decatur")] == {(2026, 12): -5}
print("test_location_series: all ok")
