"""ns_miles: the NS seed is a spread to Ft Wayne, so the estimated extra miles to each region must have the right sign and track
the seed's spreads. Run: python tests/test_ns_miles.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import freight_data as FD
import ns_miles as NSM

rows = FD.load_ns()
# Ft Wayne is the zero; New Haven (Ft Wayne's suburb) is ~0
assert all(NSM.delta_miles("FT WAYNE", "IN", f) == 0 for f in NSM.DEST)
assert all(abs(NSM.delta_miles("NEW HAVEN", "IN", f)) < 15 for f in NSM.DEST)
# west of Ft Wayne = farther from every region; south-west (Anderson IN) is nearer GA; Toledo is nearer the East
assert NSM.delta_miles("DES MOINES", "IA", "ga") > 100 and NSM.delta_miles("DES MOINES", "IA", "east") > 400
assert NSM.delta_miles("ANDERSON", "IN", "ga") < 0 and NSM.delta_miles("TOLEDO", "OH", "east") < 0
# Dyer OH has no coordinates of its own and borrows Fostoria's (same spreads)
assert NSM.delta_miles("DYER", "OH", "ga") == NSM.delta_miles("FOSTORIA", "OH", "ga") is not None
# only a station we cannot place lacks miles
missing = [(r["origin"], r["state"]) for r in rows if NSM.delta_miles(r["origin"], r["state"], "ga") is None]
assert missing == [("WTNN", "TN")], missing
# the seed's spreads track the miles difference (that is the check that they are spreads to Ft Wayne)
for f in NSM.DEST:
    pts = [(NSM.delta_miles(r["origin"], r["state"], f), r[f] * 3500) for r in rows if NSM.delta_miles(r["origin"], r["state"], f) is not None]
    n = len(pts)
    mx, my = sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    r2 = sxy ** 2 / (sum((x - mx) ** 2 for x, _ in pts) * sum((y - my) ** 2 for _, y in pts))
    assert sxy > 0 and r2 > 0.5, (f, r2)
assert abs(FD.fsc_cpb(0.95, 350, 3500) - 9.5) < 1e-9
print("test_ns_miles: all ok")
