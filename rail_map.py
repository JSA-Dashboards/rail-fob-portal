"""
Interactive rail map for the Map tab: Class I + CN, TPW, Iowa Interstate and Watco-operated lines (BTS NTAD rail network),
the navigable grain rivers highlighted, and markers for crush plants, ethanol / corn processors and the railroads' grain shippers.
Data files are built by build_rail_lines.py, build_waterways.py and build_map_points.py.
"""
import json
import os

import plotly.graph_objects as go
import streamlit as st

_DATA = os.path.join(os.path.dirname(__file__), "data")

# NTAD owner code -> (label, colour, width)
RAILROADS = {
    "CN": ("CN", "#d4272e", 1.6), "UP": ("UP", "#e8a317", 1.1), "BNSF": ("BNSF", "#f26b21", 1.1),
    "CPKC": ("CPKC", "#7a1f2b", 1.0), "CSXT": ("CSX", "#1f4e9c", 1.1), "NS": ("NS", "#2d2d2d", 1.1),
    "TPW": ("Toledo, Peoria & Western", "#0a9396", 2.4), "IAIS": ("Iowa Interstate", "#7b2cbf", 2.4),
    "WSOR": ("Watco: Wisconsin & Southern", "#2a9d8f", 2.2), "KO": ("Watco: Kansas & Oklahoma", "#8ab17d", 2.2),
}
DEFAULT_ON = ["CN", "TPW", "IAIS", "WSOR", "KO"]
# Grain rivers drawn as the highlighted system (NTAD river names)
GRAIN_RIVERS = ["MISSISSIPPI RIVER", "ILLINOIS RIVER", "OHIO RIVER", "MISSOURI RIVER", "ARKANSAS RIVER", "TENNESSEE RIVER",
                "CUMBERLAND RIVER", "KENTUCKY RIVER", "MONONGAHELA RIVER", "ALLEGHENY RIVER", "KANAWHA RIVER", "COLUMBIA RIVER",
                "SNAKE RIVER", "WHITE RIVER", "ATCHAFALAYA RIVER", "MINNESOTA RIVER", "GULF INTRACOASTAL WATERWAY"]
SHIPPER_COLORS = {"BNSF": "#f26b21", "CN": "#d4272e", "CSX": "#1f4e9c", "NS": "#2d2d2d"}


@st.cache_data(show_spinner=False)
def _load(name):
    with open(os.path.join(_DATA, name), encoding="utf8") as fh:
        return json.load(fh)


def _line_xy(paths):
    lon, lat = [], []
    for p in paths:
        for x, y in p:
            lon.append(x)
            lat.append(y)
        lon.append(None)
        lat.append(None)
    return lon, lat


def build_figure(rails, rivers, show_crush, show_ethanol, shipper_roads, height=720):
    fig = go.Figure()
    lines = _load("rail_lines.json")
    if rivers:
        water = _load("waterways.json")
        paths = [p for r in GRAIN_RIVERS for p in water.get(r, [])]
        lon, lat = _line_xy(paths)
        fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", line=dict(width=4, color="#4aa3ff"), name="Grain rivers",
                                    hoverinfo="skip", opacity=0.75))
    for code in rails:
        label, color, width = RAILROADS[code]
        lon, lat = _line_xy(lines.get(code, []))
        fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", line=dict(width=width, color=color), name=label, hoverinfo="skip"))
    pts = _load("map_points.json")
    for road in shipper_roads:
        rows = [r for r in pts["shipper"] if r["road"] == road]
        fig.add_trace(go.Scattermap(
            lon=[r["lon"] for r in rows], lat=[r["lat"] for r in rows], mode="markers",
            marker=dict(size=6, color=SHIPPER_COLORS[road]), name=f"{road} grain shippers ({len(rows)})",
            text=[f'{r["name"]}, {r["state"]}' + (" (shuttle)" if r.get("shuttle") else "") for r in rows], hoverinfo="text"))
    for flag, key, name, color in ((show_ethanol, "ethanol", "Ethanol / corn processing", "#2e9e4f"),
                                   (show_crush, "crush", "Crush plants", "#7b3fbf")):
        if flag:
            rows = pts[key]
            fig.add_trace(go.Scattermap(
                lon=[r["lon"] for r in rows], lat=[r["lat"] for r in rows], mode="markers",
                marker=dict(size=11, color=color), name=f"{name} ({len(rows)})",
                text=[f'{r["name"]} {r["state"]}'.strip() for r in rows], hoverinfo="text"))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=40.5, lon=-91), zoom=4.6), height=height,
                      margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.0, bgcolor="rgba(255,255,255,0.85)"))
    return fig


def render():
    st.markdown("### Rail Network Map")
    c1, c2, c3 = st.columns([3, 2, 2])
    rails = c1.multiselect("Railroads", list(RAILROADS), default=DEFAULT_ON, format_func=lambda k: RAILROADS[k][0], key="railmap_rails")
    with c2:
        rivers = st.checkbox("Highlight grain rivers", value=True, key="railmap_rivers")
        crush = st.checkbox("Crush plants", value=True, key="railmap_crush")
        ethanol = st.checkbox("Ethanol / corn processing", value=True, key="railmap_eth")
    shippers = c3.multiselect("Grain shippers by railroad", list(SHIPPER_COLORS), default=list(SHIPPER_COLORS), key="railmap_ship")
    st.plotly_chart(build_figure(rails, rivers, crush, ethanol, shippers), use_container_width=True, key="railmap_fig")
    st.caption("Rail lines: US DOT BTS North American Rail Network (NTAD); rivers: USACE navigable waterway network via BTS NTAD (2018). "
               "Shippers: BNSF and CN directories with coordinates; CSX and NS only where the station's city is geocoded. "
               "Crush / ethanol markers are the basis tracker's tagged plants. "
               "[CN GeoMapGuide](https://cnebusiness.geomapguide.ca/) · [TPW](https://www.gwrr.com/railroads/toledo-peoria-and-western-railway) · "
               "[Iowa Interstate](https://iaisrr.com/ship-with-iais/what-where-how/) · [Watco system map](https://www.watco.com/system-map/)")
