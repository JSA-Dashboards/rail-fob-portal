"""state_level: the Illinois river indexes (Zone 2 / 3 / 5 from the tracker's tags, STL pulled out of Zone 5). Run: python tests/test_state_level.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import state_level as SL

def R(prov, loc, zone, month, basis, ft="River Terminal", fut="ZCZ26", grain="Corn"):
    return {"provider": prov, "location": loc, "facility_type": ft, "delivery_zone": zone, "grain": grain, "delivery_month": month,
            "futures_symbol": fut, "basis_cents": basis, "is_spot": 0}

rows = [R("CHS", "Seneca", "Zone 2", "Nov 2026", 10), R("CGB", "CGB - River Landing", "Zone 2", "Nov 2026", 20),
        R("CGB", "CGB HENNEPIN", "Zone 3", "Nov 2026", 5), R("ADM", "Lacon, IL", None, "Nov 2026", 99),                     # ADM is untagged: in no group
        R("Cargill", "Havana", "Zone 5", "Nov 2026", 30), R("CHS", "Havana/Beardstown", "Zone 5", "Nov 2026", 40),
        R("CHS", "CHS Cahokia", "Zone 5", "Nov 2026", -10), R("ADM", "Sauget, IL", None, "Nov 2026", -20),                     # STL: out of Zone 5, plus untagged Sauget
        R("CHS", "CHS Cahokia", "Zone 5", "Nov 2026", -30),                                                                     # a second bid, averaged first
        R("Cargill", "Havana", "Zone 5", "Dec 2026", 50),
        R("X", "Some Plant", None, "Nov 2026", 7, ft="Corn Processing"),                                                        # not a river terminal
        R("CHS", "Seneca", "Zone 2", "Nov 2026", 77, grain="Soybeans")]                                                         # not corn
idx = SL.river_index(rows)
assert set(idx) == {"Zone 2", "Zone 3", "Zone 5", "STL"}
assert idx["Zone 2"][(2026, 11)] == (15.0, 2) and idx["Zone 3"][(2026, 11)] == (5.0, 1)
assert idx["Zone 5"][(2026, 11)] == (35.0, 2) and idx["Zone 5"][(2026, 12)] == (50.0, 1)        # Havana + Havana/Beardstown, no Cahokia
assert idx["STL"][(2026, 11)] == ((-20 + -20) / 2, 2)                                            # Cahokia (-10, -30 -> -20) and Sauget -20
assert SL.group_of("Bunge", "Fairmont City", "Zone 5") == "STL" and SL.group_of("CHS", "Peru Marketstreet", "Zone 3") == "Zone 3"
assert SL.group_of("ADM", "Havana, IL", None) is None and SL.group_of("X", "Y", "Zone 1") is None
# ---- named-group states: IN (Evansville incl. Mt. Vernon, Louisville), IA (Dubuque), OH (Toledo, Cincinnati); NE has no river rows
inrows = [R("ADM", "Evansville, IN (1st Ave.)", None, "Nov 2026", 10, ft=None), R("ADM", "Evansville, IN (Broadway)", None, "Nov 2026", 20, ft=None),
          R("ADM", "Mt. Vernon, IN (Elevator)", None, "Nov 2026", 30, ft=None),                       # Mt. Vernon is in the Evansville average
          R("ADM", "Rockport, IN", None, "Nov 2026", 99, ft=None),                                      # a river terminal, but not shown for Indiana
          R("CGB", "CGB LOUISVILLE", None, "Nov 2026", -10, ft="Country Elevator"), R("CGB", "CGB JEFFERSONVILLE", None, "Nov 2026", -30, ft="Country Elevator"),
          R("CGB", "Some Other Elevator", None, "Nov 2026", 55, ft="Country Elevator")]
iidx = SL.river_index(inrows, "IN")
assert set(iidx) == {"Evansville", "Louisville"} and SL.RIVER_ORDER["IN"] == ("Evansville", "Louisville")
assert iidx["Evansville"][(2026, 11)] == (20.0, 3) and iidx["Louisville"][(2026, 11)] == (-20.0, 2)
assert SL.group_of_named("IN", "ADM", "Rockport, IN") is None and SL.group_of_named("IN", "CGB", "CGB LOUISVILLE") == "Louisville"
iarows = [R("ADM", "East Dubuque, ADM Grain", None, "Nov 2026", 5, ft=None), R("ADM", "Burlington, IA", None, "Nov 2026", 40, ft="River Terminal")]
assert SL.river_index(iarows, "IA") == {"Dubuque": {(2026, 11): (5.0, 1)}}
ohrows = [R("ADM", "Toledo, OH", None, "Nov 2026", 10, ft="Export Terminal"), R("Andersons", "Toledo - Edwin Dr", None, "Nov 2026", 20, ft=None),
          R("Andersons", "Toledo - Kuhlman Dr", None, "Nov 2026", 30, ft=None), R("Cargill", "Cincinnati Kellogg", None, "Nov 2026", -5, ft=None),
          R("Mennel", "Mennel Milling Toledo", None, "Nov 2026", 77, ft="Wheat Milling")]
oidx = SL.river_index(ohrows, "OH")
assert oidx["Toledo"][(2026, 11)] == (20.0, 3) and oidx["Cincinnati"][(2026, 11)] == (-5.0, 1) and SL.RIVER_ORDER["OH"] == ("Toledo", "Cincinnati")
assert SL.RIVER_ORDER["NE"] == () and SL.river_index([], "NE") == {} and SL.named_members("NE") == []
sql, params = SL.named_sql("OH")
assert sql.count("%s") == len(params) + 1 and params[0] == "ADM|Toledo, OH" and "LEFT JOIN" in sql      # the params, then `since`
# ---- ethanol sub-indexes (NE Eastern / Central, KS Northeast / Southwest) and the Garden City region
def P(prov, loc, lat, lon, month, basis, ft="Corn Processing"):
    r = R(prov, loc, None, month, basis, ft=ft)
    r["lat"], r["lon"] = lat, lon
    return r

nerows = [P("GPRE", "York", 40.87, -97.60, "Nov 2026", -20), P("ADM", "Columbus", 41.43, -97.36, "Nov 2026", -10),      # Eastern (lon >= -97.7)
          P("KAAPA", "Aurora", 40.87, -98.05, "Nov 2026", -30), P("KAAPA", "Minden", 40.48, -99.07, "Nov 2026", -40),   # Central
          P("CHS", "Bridgeport", 41.64, -103.08, "Nov 2026", -60),                                                     # West: in no sub-index
          P("X", "No coords", None, None, "Nov 2026", 5)]
sub = SL.ethanol_subindex(nerows, "NE")
assert set(sub) == {"Eastern NE index", "Central NE index"}
assert sub["Eastern NE index"][(2026, 11)] == (-15.0, 2) and sub["Central NE index"][(2026, 11)] == (-35.0, 2)
ksrows = [P("Western Plains", "Oakley", 39.13, -100.86, "Dec 2026", -5), P("Kansas Ethanol", "Lyons", 38.35, -98.20, "Dec 2026", 40),
          P("Cardinal", "Colwich", 37.78, -97.54, "Dec 2026", 50)]
ksub = SL.ethanol_subindex(ksrows, "KS")
assert ksub["Southwest KS index"][(2026, 12)] == (-5.0, 1) and ksub["Northeast KS index"][(2026, 12)] == (45.0, 2)
assert SL.ethanol_subindex(ksrows, "IL") == {}
regrows = [P("Garden City Coop", "Garden City, KS", 37.94, -101.26, "Nov 2026", 10, ft="Country Elevator"),         # inside 60 miles
           P("Garden City Coop", "Lakin, KS", 37.94, -101.26, "Nov 2026", 20, ft="Country Elevator"),
           P("X", "Wichita elevator", 37.69, -97.34, "Nov 2026", 99, ft="Country Elevator"),                          # far away
           P("Western Plains", "Oakley", 39.13, -100.86, "Nov 2026", 77)]                                           # a plant: not in the region
label, ridx = SL.region_index(regrows, "KS")
assert label == "Garden City region" and ridx == {(2026, 11): (15.0, 2)} and SL.region_index(regrows, "IL") is None
print("test_state_level: all ok")
