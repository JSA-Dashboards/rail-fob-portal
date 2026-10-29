"""bn_locator: the mileage estimate stays calibrated on the freight sheet's 13 origins, the price-list rates tie to the
sheet's, and a looked-up origin builds the same freight as the sheet's own. Run: python tests/test_bn_locator.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bn_locator as BL
import freight_data as FD

seed = FD.load_bn_seed()["origins"]
opts = BL.origins(seed)

# ---- every seeded origin is offered, with the sheet's own rates and miles
for o in seed:
    r = opts[BL.norm(o["origin"])]
    assert r["seeded"] and r["pnw_rate"] == o["pnw_rate"] and r["herf_miles"] == o["herf_miles"], o["origin"]
assert len(opts) > 150, len(opts)

# ---- the price list + $200 reproduces the sheet's PNW face rate for every seeded origin that is on the list
listed = BL.list_rates(BL._load("bn_shuttle_rates.json"))
checked = 0
for o in seed:
    lr = listed.get(BL.norm(o["origin"]), {})
    if "pnw" in lr:
        assert lr["pnw"] + BL.PNW_ADDER == o["pnw_rate"], (o["origin"], lr["pnw"], o["pnw_rate"])
        checked += 1
assert checked >= 7, checked
adder = BL.hereford_adder(seed, listed)
assert 0 <= adder <= 200, adder

# ---- the estimate is calibrated: on the 13 seeded origins, within ~100 miles RMS and nobody off by more than 200
coords = BL.station_coords(BL._load("bnsf_shippers.json")["rows"])
for lane, field in (("pnw", "pnw_miles"), ("hereford", "herf_miles")):
    errs = []
    for o in seed:
        city, st = BL._split(o["origin"])
        xy = coords[(BL._station_key(city), st)]
        errs.append(BL.estimate_miles(lane, *xy) - o[field])
    rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5
    assert rmse < 100 and max(abs(e) for e in errs) < 200, (lane, rmse, errs)

# ---- an unseeded origin: price-list rate + adder, estimated miles, flagged when outside the calibration box
holyoke = opts["HOLYOKE, CO"]
assert not holyoke["seeded"] and holyoke["pnw_rate"] == listed["HOLYOKE, CO"]["pnw"] + 200
assert holyoke["herf_rate"] == listed["HOLYOKE, CO"]["hereford"] + adder
assert holyoke["coords"] and holyoke["pnw_miles"] and holyoke["herf_miles"]
assert any(r["off_box"] for r in opts.values()) and any(r["coords"] is None and not r["seeded"] for r in opts.values())

# ---- build_row: same formula as load_bn, and a lane with no miles / rate has no freight
window = [{"key": "dec", "fsc_per_mile": 0.55, "cars": 100.0}]
row = FD.bn_build_row({"pnw_rate": 5870, "pnw_miles": 2103, "herf_rate": 4620, "herf_miles": 1064}, window)
assert abs(row["pnw"]["dec"] - (5870 + 2103 * 0.55 + 100)) < 1e-9
assert abs(row["hereford"]["dec"] - (4620 + 1064 * 0.55 + 50)) < 1e-9
assert abs(row["pnw_cpb"]["dec"] - row["pnw"]["dec"] / 4000 * 100) < 1e-9
none = FD.bn_build_row({"pnw_rate": 5000, "pnw_miles": None, "herf_rate": None, "herf_miles": 900}, window)
assert none["pnw"] == {} and none["hereford"] == {} and FD.bn_freight_cpb(none["pnw_cpb"], "Dec") is None
sheet = {r["origin"]: r for r in FD.load_bn(window)}
assert abs(sheet["Polo, IL"]["pnw"]["dec"] - row["pnw"]["dec"]) < 1e-9

assert BL.norm("Council Bluffs, IA +") == "COUNCIL BLUFFS, IA"
print("test_bn_locator: all ok")
