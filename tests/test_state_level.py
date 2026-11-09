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
print("test_state_level: all ok")
