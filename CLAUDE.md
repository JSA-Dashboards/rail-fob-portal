# Rail FOB portal ("Rail Corridors")

Standalone Streamlit app over the basis tracker's archived rail corridor bids (`rail_fob`, sources `manual` + `palmetto`)
and the CSX / NS / BN / CN freight workbooks. `app.py` is the whole UI; `rail_data.py` / `river_data.py` read Snowflake
(`JSA.BASIS_TRACKER`, `RIVER_FOB.PUBLIC`) with key-pair auth.

- **Deploys from `requirements.txt`** (Streamlit Community Cloud). `environment.sis.yml` is the Streamlit-in-Snowflake
  package spec — a new dependency goes in BOTH.
- **Secrets:** `USE_SNOWFLAKE` + `SNOWFLAKE_*` arrive through `st.secrets`, which `app.py` bridges into the environment.
  The repo's `.env` only holds the retired Postgres URLs, so a local run against Snowflake needs the `SNOWFLAKE_*` variables
  in the process environment first (never commit them). With neither set the app shows a notice and stops.

## 💵 Net Carry tab (the last tab)

The basis tracker's Net Carry tab for rail corridors: each posted delivery's basis re-expressed against ONE futures
contract, interest charged from the carry-start month, net of interest, the top of net carry, the "Cash Fwd Curve"
chart, the **Return to Carry history** (what storing the corridor's grain from harvest has paid, crop year by crop year, from
the old rundown reports) and a side-by-side comparison of corridors. All values are cents/bu.

### Vendored from the basis tracker — never edit these copies

`net_carry.py`, `net_carry_chart.py`, `net_carry_compare.py`, `carry_rate.py`, `delivery_period.py`,
`data/fed_funds_dff.csv`, `tests/test_net_carry.py`, `tests/test_net_carry_chart.py` — and, for the Return to Carry
history, `return_to_carry.py`, `return_to_carry_data.py`, `return_to_carry_view.py`, `return_to_carry_block.py`,
`data/prime_rate.csv`, `data/rtc_futures_1996_2006.csv`, `data/rtc_futures_soy_2005_2007.csv` and the four
`tests/test_return_to_carry*.py` with their `tests/fixtures/rtc*.json`.
The tracker (`basis-tracker-streamlit`) is the source of truth: change the module THERE, then re-sync:

    python ../basis-tracker-streamlit/sync_carry_modules.py . --check     # lists files that differ (exit 1 if any)
    python ../basis-tracker-streamlit/sync_carry_modules.py .             # copies them over

The fed-funds and prime snapshots are refreshed in the tracker (`python carry_rate.py` there), then re-synced. Don't run it
here. Altair >= 5 is needed (ships with current Streamlit).

### Return to Carry history (added 2026-10-05; Kolten: "rail of course several are already created from the old reports")

`return_to_carry_block.render(...)` (vendored; shared with the tracker) draws, under the carry charts: the Interest switch (the tab's
fed funds + 2.25% by default, bank prime to tie out to the analyst's report), the report's **shipment-by-month table** (break-even
basis, current/best bid and return for each shipment month), the headline numbers, the season chart, the best-return-by-year bars and
the by-year table. The weekly series is the corridor's **Spot** bid in `rail_fob` (the old rundown reports: CSX Columbus and UP
Group 3 back to 1996-97, UP Interior IA from 2000, the Allen Stations / BN Hereford / BN PNW from 2004, NS Ft Wayne from 2006, CSX
Evansville from 2009) — or the nearest forward period
where the rundown stopped posting Spot — read with `return_to_carry_data.obs_from_rail`; the shipment table's forward bids
(`quotes_from_rail`) exist only for the periods posted since Aug 2026, so its Best-YTD fills in as 2026-27 goes. Futures come from
`net_carry_data.futures_history(root)` (one query of `FUTURES_PRICES` per commodity, over the analyst-sheet weeks in
`data/rtc_futures_*.csv`); prime from `data/prime_rate.csv`. Corn and soybeans only (wheat shows a message). The **View** (Net /
Gross) radio now sits above the history and drives it and the comparison. Corn 2007-08's Dec 2007 front contract (missing from the stored
futures) comes from the vendored `data/rtc_futures_1996_2006.csv`; the engine and its tests live in the tracker (`CLAUDE.md` there).

**Harvest basis (2026-10-06; Kolten: "add the ability to apply your own harvest basis into the models, but default to the calculated
method").** The block's **Harvest basis** switch — Calculated (default) or My own, a number in cents vs Dec / Jan — measures the crop year
being tracked: the shipment table, and the history when that year has weekly bids (the rundown's weekly Spot bids start the first
Wednesday of October); a what-if box applies it to every year. Vendored (see the tracker's `CLAUDE.md`). The call passes
`scope=corridor.key` so a number typed for one corridor never follows the user to another (the widget keys carry it); keep passing it.

### `net_carry_data.py` — the adapter (pure; `tests/test_net_carry_data.py`)

- **Catalog:** every (source, corridor, commodity) in the `rail_fob` rows, in `rail_corridors.CORRIDORS` order. The
  `* Freight` and `* Shuttle` markets are $/car freight, not bids, and are excluded. A posting date is offered only when
  the corridor posted 2+ priced periods that day — the weekly "Spot" history (1,400+ rows per corridor, back to 1996) has
  none, so it is counted, not listed.
- **Items:** one per BID (an offer-only row is not a bid to carry), the period label as archived, the basis untouched
  (never rolled or adjusted — see the rail-entry rule). Package rows (futures `R`, e.g. AMJJ) and anything that can't be
  dated are set aside by `net_carry` and named in a caption.
- **Futures codes are completed:** Palmetto's scrape and the manual rundowns before Sept 2026 store a two-letter code with
  no year (`CZ`, `SX`). `full_symbol` completes it from the posting date (the first contract of that month on or after the
  posting month). Without this `delivery_period.canonical` can't place the delivery and the whole ladder drops out. Rows
  whose futures is `None` (some CN / Palmetto postings) still can't be dated; a posting where that is every row says so.
- **Comparison:** same commodity only, each corridor's latest posting on/before the as-of date and within 10 days;
  defaults to the same railroad's other corridors (`net_carry_compare.rail_peers`); Palmetto's boards are pickable, not
  preselected (they are the same corridors posted a second way).

### Futures and interest

- **Futures:** the basis tracker's `FUTURES_PRICES` (`JSA.BASIS_TRACKER`; `date` TEXT, `symbol`, `price_cents`), read through
  `rail_data._rows`. The curve is the latest stored day ON OR BEFORE the posting date (the tracker uses the exact day, else
  today's live curve — this portal has no live curve) and the tab says when it isn't the posting's own day. The table has
  weekday gaps (the daily capture misses days, e.g. 2026-09-29/30 during the key-rotation outage; ZS reaches back to
  2006-11, ZC to 2007-01, ZW/KE to 2021-10), so about 15% of ladders read an earlier day's curve.
- **Python 3.11 (`environment.sis.yml`):** the vendored files must not use f-string constructs that need 3.12 (a backslash, a
  comment, a line break or the same quote inside a replacement field). `net_carry_compare.py` had one; fixed in the tracker
  2026-10-05, and the tracker's `tests/test_vendored_syntax.py` now scans every vendored file. `app.py` still guards the imports,
  so a runtime that can't load them costs only this tab (the Return to Carry history has its own guard).
- **Known quirks of the vendored maths** (fix them in the tracker, not here): `reference_symbol(..., "newcrop")` keeps the
  current year's Dec contract after it has expired in mid-December, so "Nearest new-crop" on a late-December posting
  references an unpriced contract and its rows fall back to raw basis (flagged `·`); an archived posting whose rows have no
  futures contract (a few CN / Palmetto days) can't be dated, so it has no ladder.
- **Interest:** `carry_rate.rate_for(posting date, fed funds)` = effective fed funds + 2.25% (the Cost of Carry sheet's),
  interest = reference board price x rate x actual days / 360 from the carry-start month. The rate box is keyed by the
  posting date so its default re-derives when the date changes.

### UI traps

- **Tab order:** the railroad logos on the CSX / NS / BN / CN tabs are CSS-keyed to position
  (`[role="tab"]:nth-of-type(2..5)`), so new tabs go at the END of `st.tabs`. The same selectors also land on the
  Shipments tab's nested sub-tabs 2-5 (they show the CSX / NS / BN / CN logos) — scope them if that ever matters.
- **`@st.fragment`:** the tab is a fragment, so a widget change reruns only this tab. A cold page load still runs every
  tab first, so Net Carry (last) fills in after the others, and Streamlit lazy-loads the Vega chart (a grey placeholder
  for a few seconds).
- **Widget keys** carry what their options depend on (`nc_date_<corridor>`, `nc_rate_<date>`, `nc_cmp_<corridor>_<date>`),
  or a stale value outlives its options.
- **Table copy / PNG** (`_table_actions`, html2canvas in an iframe that sees none of the page CSS): table rules live in
  `_TABLE_CSS`; avoid inset box-shadows (html2canvas fills the whole cell) and give vendored HTML a font stack.
  `st.components.v1.html`, which it uses, is deprecated in current Streamlit (the logs say "removed after 2026-06-01") —
  a future Cloud upgrade past its removal breaks the Copy / PNG buttons on EVERY table here, not just these.
- **`$` in captions** is read as math; escape it (`\$`, written `\\$` in a Python string) or use `&#36;`. Net Carry text is
  cents, so it has none.

### Checks

`python tests/test_net_carry.py`, `python tests/test_net_carry_chart.py`, `python tests/test_net_carry_data.py` and the four
`python tests/test_return_to_carry*.py` (all pure, no Snowflake). On real data: drive `app.py` with `streamlit.testing.v1.AppTest` and recompute a row from raw SQL; look at the
tab with headless Playwright at 1280 and 390 px (the chart legend clips on a phone if its entries run long).
