"""BN's secondary-market car value split (Kolten, 2026-11-02): at zero and over it is full to PNW and half to Hereford; under zero, half to PNW
and full to Hereford. Run: python tests/test_bn_cars_share.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import freight_data as FD

assert FD.bn_car_cost("pnw", 450) == 450 and FD.bn_car_cost("hereford", 450) == 225
assert FD.bn_car_cost("pnw", 0) == 0 and FD.bn_car_cost("hereford", 0) == 0                    # zero starts the "over" side
for under in (-1, -100, -400):
    assert FD.bn_car_cost("pnw", under) == under / 2 and FD.bn_car_cost("hereford", under) == under
assert not hasattr(FD, "BN_BIG_UNDERS")

def row():
    return {"pnw_rate": 5000, "pnw_miles": 1000, "herf_rate": 4000, "herf_miles": 800}

over = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": 400}])
assert over["pnw"]["jan"] == 5000 + 500 + 400 and over["hereford"]["jan"] == 4000 + 400 + 200
under = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": -400}])
assert under["pnw"]["jan"] == 5000 + 500 - 200 and under["hereford"]["jan"] == 4000 + 400 - 400
small = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.5, "cars": -100}])
assert small["pnw"]["jan"] == 5000 + 500 - 50 and small["hereford"]["jan"] == 4000 + 400 - 100
assert abs(under["pnw_cpb"]["jan"] - (5000 + 500 - 200) / 4000 * 100) < 1e-9
print("test_bn_cars_share: all ok")

# ---- BN COBO: tariff only (no car cost, no fuel surcharge), California = Hereford face + $960 (USDA AMS: Edison / Brunswick NE -> Hanford CA)
assert FD.BN_COBO_OVER_HEREFORD == 960 and "COBO" in FD.BN_DESTINATIONS
assert 4700 + FD.BN_COBO_OVER_HEREFORD == 5660 and 5360 + FD.BN_COBO_OVER_HEREFORD == 6320        # the two AMS lanes, Oct 2026
for cars in (400, -400, 0):
    cobo = FD.bn_build_row(row(), [{"key": "jan", "fsc_per_mile": 0.9, "cars": cars}, {"key": "feb", "fsc_per_mile": 0.5, "cars": 0}])
    assert cobo["cobo_rate"] == 4000 + 960 and abs(cobo["cobo_cpb"]["jan"] - 4960 / 4000 * 100) < 1e-9 and cobo["cobo_cpb"]["jan"] == cobo["cobo_cpb"]["feb"]
assert FD.bn_build_row({"pnw_rate": 5000, "pnw_miles": 1000, "herf_rate": None, "herf_miles": None}, [{"key": "jan", "fsc_per_mile": 0.5, "cars": 0}])["cobo_cpb"] == {}
print("test_bn_cobo: all ok")
