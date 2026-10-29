"""cn_miles + the CN fuel surcharge window: the one real mileage ties to USDA's published surcharge dollars, estimates
have the right sign and size, and rail_fsc.window prefers published values. Run: python tests/test_cn_miles.py"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cn_miles as CM
import freight_data as FD
import rail_fsc as RF

# ---- USDA GTR: CN Gibson City -> Reserve, LA fuel surcharge per car = $605 (Sept) and $718 (Oct) at CN's bulk $/mile
pub = RF.PROGRAMS["CN"]["published"]
assert round(CM.ANCHOR_MILES * pub["2026-09"]) == 605 and round(CM.ANCHOR_MILES * pub["2026-10"]) == 718

# ---- every tariff origin gets miles unless it has no coordinates (a handful of sidings)
rows = {(r["origin"], r["state"]) for r in FD.load_cn()}
res = {k: CM.miles_to_gulf(*k) for k in rows}
missing = [k for k, (m, _) in res.items() if m is None]
assert len(missing) <= 20 and all(res[k][1].startswith("no coordinates") for k in missing), missing
assert res[("GIBSON CITY", "IL")][0] == 983 and res[("CHAMPAIGN", "IL")][0] == CM.CHAMPAIGN_MILES

# ---- signs and rough size: north of Champaign is farther from the Gulf, south is nearer; Chicago routing for IA/WI/MI/MN
assert CM.delta_miles("ALDEN", "IA") > 300 and CM.delta_miles("HINTON", "IA") > CM.delta_miles("ALDEN", "IA")
assert CM.delta_miles("SAGINAW", "MI") > 300
assert CM.delta_miles("MEMPHIS", "TN") < -300 and CM.delta_miles("MOUND CITY", "IL") < -150
assert 100 < CM.delta_miles("CHICAGO", "IL") < 160          # Chicago is ~136 rail miles from Champaign

# ---- champaign_miles moves the absolute figure, not the difference between two estimated origins
a = CM.miles_to_gulf("ALDEN", "IA", 900)[0] - CM.miles_to_gulf("PEORIA", "IL", 900)[0]
b = CM.miles_to_gulf("ALDEN", "IA", 1000)[0] - CM.miles_to_gulf("PEORIA", "IL", 1000)[0]
assert a == b

# ---- rail_fsc.window: published months win; no diesel data holds the last published value flat
w = RF.window("CN", [], date(2026, 10, 28))
assert w["oct"] == {"fsc": 0.7303, "kind": "published"} and w["nov"]["fsc"] == 0.92
assert w["dec"] == {"fsc": 0.92, "kind": "held"} and w["sep"]["kind"] == "held"
w2 = RF.window("CN", [("2026-10-12", 5.5), ("2026-10-19", 5.5), ("2026-10-26", 5.5)], date(2026, 10, 28))
assert w2["oct"]["kind"] == "published" and w2["dec"]["kind"] == "formula"
assert FD.bn_period_first_month("FM") == 2 and FD.bn_period_first_month("AMJJ") == 4
assert abs(FD.cn_freight_cpb(3000, "Small", "Corn", 600) - 3600 / FD.CN_BU_PER_CAR["Corn"]["Small"] * 100) < 1e-9
print("test_cn_miles: all ok")
