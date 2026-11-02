"""up_spreads: the stated UP origin spreads, and the 8c paper spread filling the side that isn't stated. Run: python tests/test_up_spreads.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import up_spreads as US

by = {o["name"]: o for o in US.origin_spreads()}
# stated sides stay as stated
assert (by["Brewster, MN"]["g3"], by["Brewster, MN"]["iia"]) == (3, 3) and (by["Savage, MN"]["g3"], by["Savage, MN"]["iia"]) == (12, 7)
# the missing side comes through Interior IA's 8c discount to Group 3
assert (by["Randolph, MN"]["g3"], by["Randolph, MN"]["iia"], by["Randolph, MN"]["g3_derived"]) == (16, 8, True)
assert (by["Welcome, MN"]["g3"], by["Hope, MN"]["g3"]) == (14, 15)
assert (by["Sloan, IA"]["g3"], by["Sloan, IA"]["iia"], by["Sloan, IA"]["iia_derived"]) == (3, -5, True)      # 5c over Interior IA
assert (by["Joice, IA"]["g3"], by["North Bend, NE"]["iia"]) == (8, -8)                                           # the bases themselves
# FOB = base bid - discount; Savage trades Group 3 (12 off) rather than Interior IA (7 off, which is 15 off Group 3)
g3, iia = 60.0, 52.0
sav = by["Savage, MN"]
assert US.fob(sav, "Group 3", g3) == 48 and US.fob(sav, "Interior IA", iia) == 45 and US.fob(sav, "Group 3", None) is None
# Brewster: 3 off Group 3 beats 3 off Interior IA by the paper spread
bw = by["Brewster, MN"]
assert US.fob(bw, "Group 3", g3) - US.fob(bw, "Interior IA", iia) == 8
# unnamed origins are par to their state's base; no stated rule elsewhere
assert US.generic_spreads("IA")["iia"] == 0 and US.generic_spreads("IA")["g3"] == 8
assert US.generic_spreads("NE")["g3"] == 0 and US.generic_spreads("NE")["iia"] == -8
assert US.generic_spreads("MN") is None and US.generic_spreads("SD") is None
print("test_up_spreads: all ok")
