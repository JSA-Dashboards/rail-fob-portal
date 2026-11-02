"""BN's secondary-market car value split (Kolten, 2026-11-02): over 0 it is full to PNW and half to Hereford; in the unders half to PNW and full
to Hereford, except a small unders is zero for Hereford. Run: python tests/test_bn_cars_share.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import freight_data as FD

big = FD.BN_BIG_UNDERS
assert FD.bn_car_cost("pnw", 450) == 450 and FD.bn_car_cost("hereford", 450) == 225
assert FD.bn_car_cost("pnw", 0) == 0 and FD.bn_car_cost("hereford", 0) == 0                    # 0 is not "in the unders"
# small unders: half to PNW, zero to Hereford
assert FD.bn_car_cost("pnw", -100) == -50 and FD.bn_car_cost("hereford", -100) == 0
assert FD.bn_car_cost("hereford", -(big - 1)) == 0
# big unders: half to PNW, the full premium to Hereford
assert FD.bn_car_cost("pnw", -400) == -200 and FD.bn_car_cost("hereford", -400) == -400
assert FD.bn_car_cost("hereford", -big) == -big

def row():
    return {"pnw_rate": 5000, "pnw_miles": 1000, "herf_rate": 4000, "herf_miles": 800}

over = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": 400}])
assert over["pnw"]["jan"] == 5000 + 500 + 400 and over["hereford"]["jan"] == 4000 + 400 + 200
small = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": -100}])
assert small["pnw"]["jan"] == 5000 + 500 - 50 and small["hereford"]["jan"] == 4000 + 400
under = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": -400}])
assert under["pnw"]["jan"] == 5000 + 500 - 200 and under["hereford"]["jan"] == 4000 + 400 - 400
assert abs(under["pnw_cpb"]["jan"] - (5000 + 500 - 200) / 4000 * 100) < 1e-9
print("test_bn_cars_share: all ok")
