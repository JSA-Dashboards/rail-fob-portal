"""
Builds data/map_points.json for the Map tab: the ethanol / corn processing plant list (PRX Corn Plant List) and the crush plant
list (Crush Plant Data), placed by city from the Census gazetteer, plus the railroads' grain shipper directories (the rows with
coordinates).
    python build_map_points.py
"""
import io
import json
import math
import os
import re
import zipfile

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "data", "rail_directory")
MISC = r"C:\Users\KoltenPostin\John Stewart and Associates\JSA - Documents\Research Analyst\Misc"
ETHANOL_XLSX = os.path.join(MISC, "Ethanol", "PRX Corn Plant List - All.xlsx")
CRUSH_XLSX = os.path.join(MISC, "Crush", "Crush Plant Data.xlsx")
GAZ_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_place_national.zip"
_SUFFIX = re.compile(r"\s+(city|town|village|CDP|borough|municipality|township)$", re.I)


def _norm(s):
    s = re.sub(r"^(saint|st\.?)\s+", "st ", str(s).strip().lower())
    return re.sub(r"[^a-z0-9 ]", "", s.replace("-", " "))


# places the gazetteer lacks (unincorporated / hyphenated), approximate town centres
EXTRA = {("IA", "jewell"): (42.31, -93.64), ("IN", "clymers"): (40.745, -86.374), ("IN", "harrisville"): (40.175, -84.93),
         ("IN", "indianapolis"): (39.768, -86.158), ("KS", "campus"): (38.87, -100.8), ("MI", "riga"): (41.8, -83.77),
         ("MI", "woodbury"): (42.6, -85.1), ("VA", "elliston lafayette"): (37.13, -80.2), ("IN", "mt vernon"): (37.93, -87.9),
         ("MO", "n kansas city"): (39.14, -94.57)}


def _gazetteer():
    """{(ST, normalised place name): (lat, lon)} from the Census gazetteer (public domain); the bigger place wins a name clash."""
    z = zipfile.ZipFile(io.BytesIO(requests.get(GAZ_URL, timeout=120).content))
    g = pd.read_csv(z.open(z.namelist()[0]), sep="\t", encoding="latin1")
    g.columns = [c.strip() for c in g.columns]
    g = g.sort_values("ALAND_SQMI")
    out = {(r.USPS, _norm(_SUFFIX.sub("", r.NAME))): (r.INTPTLAT, r.INTPTLONG) for r in g.itertuples()}
    for k, v in EXTRA.items():
        out.setdefault(k, v)
    return out


def _num(v, div):
    try:
        x = round(float(v) / div, 1)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def _add(out, gaz, miss, name, st, city, status, **extra):
    if pd.isna(city) or pd.isna(st):
        return
    p = gaz.get((str(st).strip(), _norm(city)))
    if not p:
        miss.append(f"{name} ({city}, {st})")
        return
    out.append({"name": str(name).strip(), "state": str(st).strip(), "city": str(city).strip(),
                "status": "" if pd.isna(status) else str(status).strip(),
                "lat": round(p[0], 4), "lon": round(p[1], 4), **{k: v for k, v in extra.items() if v is not None}})


def _load(path):
    with open(path, encoding="utf8") as fh:
        return json.load(fh)


def main():
    pts = {"crush": [], "ethanol": [], "shipper": []}
    gaz = _gazetteer()
    miss = []
    eth = pd.read_excel(ETHANOL_XLSX, header=1)
    for _, r in eth.iterrows():
        _add(pts["ethanol"], gaz, miss, r["COMPANY"], r["ST"], r["CITY"], r.get("STATUS"),
             cls=None if pd.isna(r.get("CLASS")) else str(r["CLASS"]), mgy=_num(r.get("Ethanol (Gallons)"), 1e6))
    cr = pd.read_excel(CRUSH_XLSX, sheet_name=0)
    for _, r in cr.iterrows():
        _add(pts["crush"], gaz, miss, r["COMPANY"], r["ST"], r["CITY"], r.get("STATUS"), mbu=_num(r.get("ANNUAL CAPACITY"), 1e6))
    place = _load(os.path.join(DIR, "place_coords.json"))["rows"]
    for r in _load(os.path.join(DIR, "bnsf_shippers.json"))["rows"]:
        if r.get("lat") is not None and r.get("state") not in ("AB", "SK", "MB", "BC"):
            pts["shipper"].append({"name": r["name"], "state": r["state"], "road": "BNSF", "lat": round(r["lat"], 4),
                                   "lon": round(r["lon"], 4), "shuttle": bool(r.get("shuttle"))})
    for r in _load(os.path.join(DIR, "cn_origins.json"))["rows"]:
        if r.get("lat") is None:
            continue
        pts["shipper"].append({"name": r["name"], "state": r["state"], "road": "CN", "lat": round(r["lat"], 4), "lon": round(r["lon"], 4)})
    for road, f in (("CSX", "csx_shippers"), ("NS", "ns_loaders")):
        for r in _load(os.path.join(DIR, f + ".json"))["rows"]:
            p = gaz.get((r["state"], _norm(r["city"]))) or place.get(f'{r["city"].upper()}|{r["state"]}')
            if p:
                pts["shipper"].append({"name": r["name"], "state": r["state"], "road": road, "lat": round(p[0], 4), "lon": round(p[1], 4)})
    with open(os.path.join(HERE, "data", "map_points.json"), "w") as fh:
        json.dump(pts, fh, separators=(",", ":"))
    print({k: len(v) for k, v in pts.items()})
    print("no coordinates:", miss)


if __name__ == "__main__":
    main()
