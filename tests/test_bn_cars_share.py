"""BN's secondary-market car value split (Kolten, 2026-11-02): over 0 it is full to PNW and half to Hereford; in the unders the opposite.
Run: python tests/test_bn_cars_share.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import freight_data as FD

assert FD.bn_cars_share("pnw", 450) == 1.0 and FD.bn_cars_share("hereford", 450) == 0.5
assert FD.bn_cars_share("pnw", -300) == 0.5 and FD.bn_cars_share("hereford", -300) == 1.0
assert FD.bn_cars_share("pnw", 0) == 1.0 and FD.bn_cars_share("hereford", 0) == 0.5          # 0 is not "in the unders"

def row():
    return {"pnw_rate": 5000, "pnw_miles": 1000, "herf_rate": 4000, "herf_miles": 800}

over = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": 400}])
assert over["pnw"]["jan"] == 5000 + 1000 * 0.5 + 400 and over["hereford"]["jan"] == 4000 + 800 * 0.5 + 200
under = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": -400}])
assert under["pnw"]["jan"] == 5000 + 1000 * 0.5 - 200 and under["hereford"]["jan"] == 4000 + 800 * 0.5 - 400
assert abs(under["pnw_cpb"]["jan"] - (5000 + 500 - 200) / 4000 * 100) < 1e-9
print("test_bn_cars_share: all ok")
