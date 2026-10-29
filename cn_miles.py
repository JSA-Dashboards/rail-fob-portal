"""
Rail miles to the Gulf for the CN fuel surcharge (Kolten, 2026-10-28: "check on CN FSC ... I believe it should be added").

CN's fuel surcharge (tariff CN 7403, rail_fsc.PROGRAMS["CN"]) is $/car-MILE, so it needs each origin's miles to the Gulf
Exports Group, which CN gives only through its Get Rail Miles tool (an eBusiness login). What can be checked:

  * USDA AMS's Grain Transportation Report tables list CN Gibson City, IL -> Reserve, LA with its fuel surcharge per car:
    $605 in the Sept 24 report (CN's Sept bulk surcharge $0.6153/mi) and $718 in the Oct 22 report ($0.7303/mi) — both
    exactly 983 miles. That is the one real mileage here (ANCHOR_MILES), and it confirms the surcharge is ADDED to the
    tariff rate (Gibson City: $3,011 tariff + $718 fuel = $3,729 in October).
  * Everything else is estimated from the origin's place coordinates (data/rail_directory/place_coords.json, Census
    centroids). Champaign is taken as ~Gibson City's 983 (35 miles apart on the same line). Origins in IA / WI / MI / MN
    reach the Gulf through Chicago, so their miles = 1.25 x the great-circle miles to Chicago + 136 (Chicago-Champaign) +
    Champaign's; the rest sit on or near the Illinois Central line, so miles = Champaign's +/- 1.10 x the great-circle
    miles to Champaign (+ north of it, - south). The circuity factors are judgement, not fitted — only one real mileage
    exists — so treat an estimate as good to roughly 10-15% of the distance from Champaign, and prefer a typed figure.

Against a bid FOB Champaign the Champaign figure cancels: FOB(origin) = bid + freight(Champaign) - freight(origin), so the
fuel surcharge only enters as FSC x (Champaign miles - origin miles), which needs just the distance difference, not
anybody's absolute miles.

Pure functions; no Streamlit.
"""
import bn_locator as BL

ANCHOR = ("GIBSON CITY", "IL")
ANCHOR_MILES = 983                         # USDA GTR: $718 / $0.7303 (Oct) = $605 / $0.6153 (Sep) = 983
CHAMPAIGN_MILES = ANCHOR_MILES             # Champaign is ~35 miles from Gibson City on the same line
CHICAGO = (41.8781, -87.6298)
CHICAGO_TO_CHAMPAIGN = 136                 # rail miles, Illinois Central main line
VIA_CHICAGO = {"IA", "WI", "MI", "MN"}
C_CHICAGO = 1.25
C_DIRECT = 1.10
EST_NOTE = "estimated from the town's coordinates"

# Sidings that load at / are served from a town (Kolten, 2026-10-28): measured from that town.
ALIASES = {("COLES", "IL"): ("MATTOON", "IL"), ("DORANS", "IL"): ("MATTOON", "IL"), ("CLYMERS", "IN"): ("LOGANSPORT", "IN")}


def coords(origin, state):
    origin, state = ALIASES.get((origin.upper(), state), (origin.upper(), state))
    return BL.place_coords().get(f"{origin}|{state}")


def delta_miles(origin, state):
    """Estimated miles from Champaign to the origin, along the way to the Gulf: positive = farther from the Gulf than
    Champaign. None when the origin has no coordinates."""
    xy = coords(origin, state)
    champ = coords("CHAMPAIGN", "IL")
    if xy is None or champ is None:
        return None
    if state in VIA_CHICAGO:
        return round(C_CHICAGO * BL.haversine(xy, CHICAGO) + CHICAGO_TO_CHAMPAIGN)
    d = C_DIRECT * BL.haversine(xy, champ)
    return round(d if xy[0] >= champ[0] else -d)


def miles_to_gulf(origin, state, champaign_miles=CHAMPAIGN_MILES):
    """(miles, note): the origin's rail miles to the Gulf Exports Group, or (None, why)."""
    if (origin.upper(), state) == ANCHOR:
        return ANCHOR_MILES, "USDA tariff table (Sept / Oct 2026)"
    if (origin.upper(), state) == ("CHAMPAIGN", "IL"):
        return champaign_miles, "taken as about Gibson City's"
    d = delta_miles(origin, state)
    if d is None:
        return None, "no coordinates for this station"
    alias = ALIASES.get((origin.upper(), state))
    return champaign_miles + d, (f"measured from {alias[0].title()}, {alias[1]}" if alias else EST_NOTE)
