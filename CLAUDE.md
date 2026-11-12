# Rail FOB portal ("Rail Corridors")

Standalone Streamlit app over the basis tracker's archived rail corridor bids (`rail_fob`, sources `manual` + `palmetto`)
and the CSX / NS / BN / CN freight workbooks. `app.py` is the whole UI; `rail_data.py` / `river_data.py` read Snowflake
(`JSA.BASIS_TRACKER`, `RIVER_FOB.PUBLIC`) with key-pair auth.

- **Deploys from `requirements.txt`** (Streamlit Community Cloud). `environment.sis.yml` is the Streamlit-in-Snowflake
  package spec — a new dependency goes in BOTH.
- **Secrets:** `USE_SNOWFLAKE` + `SNOWFLAKE_*` arrive through `st.secrets`, which `app.py` bridges into the environment.
  The repo's `.env` only holds the retired Postgres URLs, so a local run against Snowflake needs the `SNOWFLAKE_*` variables
  in the process environment first (never commit them). With neither set the app shows a notice and stops.

## BN freight (re-seeded 2026-10-28; inputs fed in the app since the same day)

Freight is built the way Kolten's "Fob BN Corn Plus.xlsx" > "PNW Facing Corn Rates" tab (H16:Y100) builds it: `rate + miles x FSC + BN Cars`, Hereford
taking cars / 2, / 4000 bu/car for cents. `bn_freight_seed.json` holds the per-origin face rates and lane miles (13 origins; `source` lists the sheet's cells), the
`index_periods` the tab shows in "FOB by Origin" (Kolten's "FOB BN" sheet layout, 2026-10-28: one row per origin, PNW | Hereford under each period, the bid in a yellow row, a BN Car Val / FSC per Mi row, red parentheses for negatives, the better destination shaded — it replaced the state index) and runs bid inference on (Oct / Nov / Dec / JFM — `app.py`'s `_BN_TARGET_MONTHS` reads them, no code change
on a roll), and `defaults`: the inputs used until something is saved. The two inputs that move are **fed on the BN tab** (the "BN freight inputs" section at the bottom of the tab: shuttle quote editor, FSC grid, preview, Save). The saved quotes also show as a read-only bids/offers-style
"Secondary freight" sheet right under the delivered PNW / Hereford quotes, with the FSC as a quiet line below it (`_bn_secondary_table`):
the secondary-market **BN 110-car shuttle quotes** (bid / offer by shuttle period, the daily sheet Kolten gets) and the **FSC $/mile by month** (a 12-row Oct..Sep grid,
plus an optional per-month cars override). **FSC is a formula by default (`bn_fsc.py`, `tests/test_bn_fsc.py`):** 1 cent/mile for every 5 cents the monthly average of EIA's weekly US on-highway diesel, TWO months earlier, sits above a
$3.25 strike (each started step counts). Not from BNSF's rule text (Item 3377-Series — the grain price lists cite its $3.25 strike, the rule itself isn't public): it was fitted to the surcharges
Kolten has had and reproduces all four exactly (Aug .36, Sep .35, Oct .45, Nov .61; a one-month lag would not) — check each new month BN publishes against it. A month whose source month is
complete is "published", one whose source month is still open uses the average so far, and further out the latest weekly price is held flat (a stand-in for a diesel forecast). Needs the
`EIA_API_KEY` secret (the portal bridges it into the environment; weekly diesel cached 6 h); without it or if EIA is down the tab says so and uses the typed FSC. In the inputs the grid becomes an
**override** column in formula mode (`fsc_override`, wins over the formula); "Typed values" mode (`fsc_mode`) is the older typed-FSC grid. When there is no formula (or in typed mode):
A month with no FSC of its own takes the last entered month's, **held flat** (payload `hold_fsc`, default on, also for payloads saved before the option existed; the checkbox in the
inputs turns it off, and then a month with no FSC has no freight, its bids showing "—"). Typing a month replaces it and every later blank month follows.

`bn_inputs.py` (pure + the Snowflake IO; `tests/test_bn_inputs.py`): the BID is the premium; a month takes its own full-month quote, else the midpoint of its F/H and L/H
bids (lone half if only one), else the NARROWEST package covering it (Jan-Feb-Mar, April-May, April-July, ...); a quote with no bid ('-') doesn't count, so the month falls
through to a package or 0. Saves append one JSON row to `JSA.RAIL_FOB.BN_FREIGHT_INPUTS` (`bn_inputs_setup.sql` creates it — run once as ACCOUNTADMIN; its two GRANT lines are only for a portal role other than ACCOUNTADMIN; append-only, so a
save is a single INSERT with no DELETE-then-INSERT race, every change stays as history, `SYSDATE()` keeps it UTC); the tab reads the latest row (cached 60 s). Not on Snowflake, or the table
missing / unreadable: the tab runs on the seed's defaults, says so, and a Save holds for the session only ("Use saved values" drops it).

Packages net on their FIRST named month (JFM -> Jan), so the grid's Feb/Mar only matter for periods that start there. The sheet's own Polo, IL PNW row (L49:N49) leaves the cars term
out; the seed doesn't carry that (the old totals-based seed did, which overstated Polo's PNW FOB and the IL row of the state index by 12.5 / 30 / 22.5 cents for Sep / Oct / Nov).
**Car value split (Kolten, 2026-11-02: "start at zero; if less than zero it's half PNW and full Hereford, if above zero full PNW and half Hereford"; `FD.bn_car_cost`, `tests/test_bn_cars_share.py`):** the secondary-market BN car value at zero or over is full price to PNW and HALF to Hereford for every origin; under zero it is the opposite — half to PNW, full to Hereford. No small / big unders distinction (the workbook's H16 note had one — Herf at face value in a small unders — and Kolten dropped it). All BN values = destination value − tariff − car cost − FSC/mile × miles, EXCEPT BN COBO: the buyer takes the car cost and FSC, so COBO's FOB = its bid − the TARIFF only. **BN COBO is a third destination (2026-11-02; `FD.BN_DESTINATIONS['COBO']`, `BN_COBO_OVER_HEREFORD`)**: it has its own lane, California (Kolten); the origin rates aren't in the price-list file I have, so the tariff comes from USDA AMS's AgTransport series (`3az4-jkr6`, BNSF corn): California is exactly **$960/car over Hereford** for both Edison NE → Hanford CA ($5,660 vs $4,700) and Brunswick NE → Hanford CA ($6,320 vs $5,360), every month Mar-Oct 2026 (both stepped +$200 in Oct), so COBO tariff = the origin's Hereford face rate + $960 (assumed to hold for every origin; AMS has only those two; the same every month — a later step isn't modelled), miles not needed. COBO appears as a third column in the BN FOB by State / Key Corridors / lookup tables (car-val/FSC row shows "—" under it) and in the State Summary. Garden City KS as a BN destination typically trades a 25¢ discount to Hereford on tariff, FSC calculated the same and car costs like Hereford — not modelled (no bid market for it).
The headline periods are Oct / Nov / Dec / JFM / AM / JJ (`index_periods`; edit it in the seed to roll them). A headline period the board didn't post as itself is filled
in app.py (`_bn_infer_quote`, a (bid, offer) pair from ONE posting; display only, the archive is untouched): Split <month> (treated as the full month — it wins over FH/LH, so a stray
LH Nov can't drag Nov down) > FH/LH average (or the lone half) > the containing package (AM and JJ from AMJJ) > for Oct/Nov/Dec the OND package, reverse-averaged against Oct. The
secondary freight sheet draws the shuttle quotes in the delivered board's grid format (periods across, bid with the offer in blue, BNSF / as-of chips).

## CN soybeans on the CN 105s Beans bids (2026-10-28)

With Soybeans picked on the CN tab, a "Soybean price" switch chooses what the freight comes off: the CN 105s Beans bids (default) or Soybeans CIF NOLA (the earlier netback, kept). The bean bids are the rail bid archive's market
`CN 105s Beans` (`JSA.BASIS_TRACKER.rail_fob`, posted as "CN YSB 105's (FOB Champ)", cents vs the futures tag on each period, forward periods since Aug 2026; read through the Bids tab's posting date like the BN tab). The bid is FOB
Champaign for a 105-car shuttle, so each origin's FOB = bid + freight(Champaign, IL, 105+ cars) − freight(origin, 105+ cars), like for like in car size and source and in soybean ¢/bu — only origins with a 105+ car rate appear.
`_cn_state_fob_table` and the by-origin table take a `base_fn(period, size, rate field)`, so the CIF path and the bid path share them. Corn still uses CIF NOLA only. "FOB Champaign" comes from the basis tracker's paste notes
(`rail_paste.py`); confirm with Kolten if the bid's reference origin is ever in doubt.

## FOB at any BN / CN location (2026-10-28) — `bn_locator.py`, `tests/test_bn_locator.py`

Under "FOB by Origin" on the BN tab, **FOB at Any BN Location** is a dropdown of every origin on the BNSF price list (197, plus the 13 seeded origins) that renders the same table for one origin (`_bn_fob_by_origin` with `legend=False`).
The freight sheet only has 13 origins with face rates and lane miles; for the rest: face rate = the price list's `DEST GRP 50 PNW` 286K / 5,001+ cu ft column **+ $200** (exact for all 7 seeded origins on the list); Hereford = the list's column + an
**adder** (the sheet's Hereford rates run $0–$200 over the list, varying by origin, so their average — $90 — is the editable default); **miles are estimated from the BNSF shippers directory's coordinates**:
miles = a + b × great-circle miles to a fixed point (PNW: Spokane; Hereford: a point in southern Kansas, since the lane runs through Kansas and a straight line to Hereford, TX fits far worse), constants fitted to the 13 seeded origins (`LANES`;
RMS ~65–70 miles ≈ 1¢/bu; the test refits it). Origins outside the fitted area (`CAL_BOX`, about MN/SD/NE/IA/IL) get a rougher-estimate warning; origins with no coordinates in the directory (24) show "—" until miles are typed; a typed mileage wins.
Seeded origins use the sheet's own rates and miles. `freight_data.bn_build_row` is the shared freight build (a lane with no rate or miles has no freight). The shippers directory abbreviates stations to 9 characters — `bn_locator._station_key`.
The CN tab has **FOB at Any CN Location** the same way (`_cn_location_lookup`): one tariff origin from a dropdown, all its volume tiers; CN's tariff rates are flat $/car; its fuel surcharge (below) is what needs miles.
29 of the CN shipper directory's 96 locations (e.g. Kankakee, Heyworth) have no rate of their own in the tariff and aren't offered.

## CN fuel surcharge (2026-10-28) — `cn_miles.py`, `rail_fsc.window`, `tests/test_cn_miles.py`

CN freight = tariff $/car + **CN 7403 fuel surcharge** ($/car-mile, `rail_fsc.PROGRAMS["CN"]`) × the origin's rail miles to the Gulf; ÷ bu/car for ¢/bu. The CN tab has an "Include CN fuel surcharge" checkbox (default on; off = the earlier tariff-only numbers).
That the surcharge is ADDED to the tariff comes from USDA AMS's Grain Transportation Report tables (Table 7, CN Gibson City, IL → Reserve, LA): Oct 22 2026 $3,011 tariff + $718 fuel; Sept 24 $2,791 + $605. $718 / the $0.825 USDA's dataset shows CN billed in Oct = **870 miles** (USDA's `route_mileage`; an earlier 983 from CN's page rate was wrong) —
the one real mileage there is (`ANCHOR_MILES`; CN's own Get Rail Miles tool needs an eBusiness login). The per-month $/mile is `rail_fsc.window("CN", weekly, today)`: CN-PUBLISHED values (`PROGRAMS["CN"]["published"]` — add each new month CN posts) win, else the formula on EIA diesel,
else the last published held flat. Periods map to a month by their first named month (`FD.bn_period_first_month`; "FM" → Feb was added).
**Miles are estimated** (`cn_miles.miles_to_gulf`): Champaign = USDA's 870 for Gibson City less ~33 = 837 (fixed, not editable); origins in IA/WI/MI/MN go via Chicago (1.0 × great-circle to Chicago + 136 + Champaign's); others sit on the Illinois Central line (Champaign's ± 1.10 × great-circle to Champaign, + north / − south).
The circuity factors are judgement — not fitted, there is one data point — roughly 10-15% of the distance from Champaign; local-move origins far south (New Orleans, Memphis) are the least reliable. Coordinates are Census TIGERweb centroids in `data/rail_directory/place_coords.json`
(now ~180 places: Census centroids, plus OpenStreetMap for hamlets Census lacks; also feeds BN and NS). `cn_miles.ALIASES` (Kolten, 2026-10-28): Coles + Dorans IL are measured from Mattoon, Clymers IN from Logansport (Rising Sun MS = OSM's Leflore Co. hamlet; Kolten wrote "Sidell", read as Sidon, same county). Cockrell, Green's Switch and Indian Oaks IL (no coordinates anywhere) are measured from Mattoon too (Kolten: "just use Mattoon as a reference"); the CN 105s corn bid is FOB Champaign (Kolten, 2026-10-29), and NS has NOT reissued its spreads (still the 2024-25 sheet).
**Against the CN 105s Beans bids (FOB Champaign) the Champaign mileage cancels** — FOB(origin) = bid + freight(Champaign) − freight(origin), so the fuel surcharge enters as FSC × (Champaign miles − origin miles) and only the DIFFERENCE in miles matters (Kolten's point); the absolute 837 only matters for the CIF NOLA netback or a typed mileage.
**Tariff level + real miles (2026-10-28, found in USDA AgTransport dataset `3az4-jkr6`, snapshot `data/usda_cn_tariff.json`; CN's own public price-documents pages need a visitor registration — name/company/email — so I did not use them)**: USDA's monthly series for CN Gibson City→Reserve (large car, 105+ unit train) shows (1) the seed (Supplement 41) is EXACTLY the Jun-Aug 2026 rate ($2,516 railroad / $2,136 private); (2) CN's tariff moves by month — Sep $2,791, Oct $3,011 (+$495), and October is a SEASONAL PEAK: Nov fell $220 in 2024 and $330 in 2025 ($2,681 Nov 2025-May 2026) — so the first flat-$495 version (pushed 7bfa0e4) overstated Nov+; (3) CN's route miles are 870 (not 983) and the surcharge CN billed is $0.825/mi in Oct (= 1.1298 × the $0.7303 on CN's page; `rail_fsc` CN per_step is now 0.6496¢, published Sep .695 / Oct .825 / Nov 1.039 = page .92 × 1.1298); Ida Grove IA→Convent is 1,376 and Minneapolis→New Orleans 1,277, both ≈ Champaign + 136 + great-circle to Chicago, so `C_CHICAGO` = 1.0 (was 1.25). Per-period tariff level: `FD.cn_tariff_level/cn_tariff_uplift(month, today)` — USDA's actual for months it has (Oct, Sep, Jun-Aug), else the same month a year earlier (Nov-May +$165); a flat $/car on every origin (USDA lists no other CN origin; assumed). Not editable on the tab (Kolten, 2026-10-28: "those are set — just use the USDA benchmark and adjust accordingly"): the Champaign-miles and tariff-level inputs were removed. Cancels against the Champaign bean bids. Still open: CN publishes the real Nov+ rates (a newer supplement); the raw tariff table at the bottom still shows the supplement's own rates.

## Railroad reference (2026-10-28) — `rail_reference.py`, `rail_fsc.py`, `data/rail_directory/`

Under each railroad tab (CSX, NS, BN, CN, and a UP tab after CN) `rail_reference.render(rr, weekly)` draws two kinds of collapsed expander. Each loads only when opened (`st.expander(on_change="rerun")` + `.open`; an
older Streamlit without it just loads them always).
- **Fuel surcharge** (`rail_fsc.PROGRAMS`): each railroad's mileage-based grain program on EIA diesel, two-month lag — BN strike 3.25 / 1¢ per 5¢ / round up (fitted); UP 2.30 / 5¢ / full steps + 5¢ base (UP's page);
  NS 2.50 / 4¢ / round up on diesel cut to the cent (NS's page, rounding inferred); CN 2.30 / 0.575¢ per 2.5¢ / round up (CN 7403, rounding inferred); CSX ~3.749 / 4¢ / round up (INFERRED — CSX's own page wasn't readable).
  The expander shows the equation, the next six months worked out from the EIA weekly diesel (the same feed and cache as the BN FSC), the railroad's published values beside them, and how sure each point is.
  `tests/test_rail_fsc.py` keeps every published value reproducible; check the next month each railroad publishes against it. Not verified: that grain shuttles move under the public UP / NS / CSX programs rather than a contract one.
- **Directories** — the six files in `JSA - Documents/Research Analyst/Misc/Rail Origins & Destinations` (BNSF Shippers, CSX Shippers, NS Grain Loaders, Map CN Origins, UP grain loaders PDF, BN Corn Shuttle Rates 2026), parsed ONCE into
  `data/rail_directory/*.json` (the extraction script wasn't kept; re-parse from the originals when they change). **The repo is public, so only business facility data is archived — BNSF's contact names, titles, emails, phones and faxes are not**
  (the originals on SharePoint are the full archive). The UP list is as issued Oct 2023 and the BN shuttle rates are BNSF price list PA-00055472-40 v86 (1/26/2026); the freight build's face rates are that list's third column (286K lb, 5,001+ cu ft) plus later increases (mostly $200/car on PNW).

**View-only build:** `RAIL_VIEW_ONLY` (a secret/env var, for a separate Cloud app nobody edits from) or `?view=1` on the URL hides the BN freight inputs section (the editors, Save) and the Shipments token / refresh box. The read-only
secondary-freight sheet stays. `?view=1` is only a convenience — anyone can drop it from the URL; the real separation is a second app with the secret.

**Delivered bid overrides:** BN freight inputs has a Hereford / PNW bid (and offer) grid per headline period that replaces what the board shows in FOB by Origin (underlined dotted). The seed's defaults — Hereford Oct +85, PNW Dec +100 (Kolten, 2026-10-28) —
apply until something is saved, then whatever is saved wins (`bn_inputs.bid_overrides`).

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

**Ship by (2026-10-12; Kolten: "limit how late the study goes ... a ground pile that at the latest has to ship by March ... default to best with
no limits").** The block's **Ship by** box — No limit (default) or the end of a month, November to June — stops the study there: the best
return, the by-year table, both charts and the shipment table read only the weeks / months up to it. Vendored (see the tracker's `CLAUDE.md`);
the call needs no new argument, and the choice (`nc_rtc_ship_by_corn`) follows the user from corridor to corridor.

**Harvest window (2026-10-12; Kolten: "we default to establishing corn basis as of Oct and for 7 weeks ... yes, add start week and number of
weeks").** The block's **Start week** / **Number of weeks** boxes choose which weekly bids the calculated harvest basis averages (since
2026-10-19, Kolten: "start with week zero as Sep 1": week 0 = the first Wednesday of September, so the report's window starts at week 4, or 5 when
September has five Wednesdays, and the default is that week and 7). A window is the same weeks, counted from September, in every crop year;
interest still starts at the report's third weekly bid, except that a window opening BEFORE the report's moves the purchase with it (its own
3rd bid), and the season chart starts in September (2026-10-19; own harvest basis = this year only, the every-year what-if is gone). Best
return is now the best LOCKABLE one (the nearby bid or a forward month sold ahead, on any day) with today's forward curve on the chart; the
corridors only archived forward periods from Aug 2026, so earlier years are the nearby bid's best (the tracker's `CLAUDE.md`). A September bid quoted off CU futures is rolled to Dec at the Dec - Sep
spread of the last trading day before first notice; the rail corridors tag their September bids Z, so nothing is rolled here. Vendored (see the
tracker's `CLAUDE.md`); the call needs no new argument, and the choice (`nc_rtc_win_corn_*`) follows the user from corridor to corridor.

### Estimated archive weeks are hidden (2026-10-22)

UP Allen Station's weekly Spot history before its actual bids (2023-05-31) was a formula, `Est Mexico Allen` / `Est Domestic Allen` = Group 3 + 20 / + 10, and carries `bid_raw = 'est'` in `rail_fob`
(994 weeks for each of `UP Illinois (Mex)` and `(Dom)`). Kolten: "hide data that is pure estimate at least for now" — keep / exclude / delete is still open. `rail_data.get_all` and `get_dates` leave those rows out
(`AND (bid_raw IS NULL OR bid_raw <> 'est')`; the desk's '?' stays), so the board's dates, Net Carry and Return to Carry see Allen from May 2023 only; the rows are still in the table and
`RAIL_SHOW_ESTIMATES=1` in the environment shows them again. The tracker does the same in `database.get_rail_fob*` (see its `CLAUDE.md`). Reboot after a push.

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
  (`[role="tab"]:nth-of-type(3..6)` since the State Summary became tab 2, 2026-10-28), so adding a tab before position 7 means
  shifting those four numbers. The same selectors also land on the Shipments tab's nested sub-tabs 3-6 (they show the CSX / NS / BN / CN
  logos) — scope them if that ever matters.
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

## CSX and NS lookups + NS fuel surcharge (2026-10-28)
- **FOB at Any CSX Location** / **FOB at Any NS Location** (`_csx_location_lookup`, `_ns_location_lookup`, selectboxes `csx_loc_pick` / `ns_loc_pick`) cover every origin in the seeds (196 CSX origin·train-type rows, 67 NS), not only the starred Highlighted ones — the freight spreads were already seeded, nothing typed.
  CSX shows a row per active corridor; NS a row per region. `_state_best_row` / `_fob_variant_rows` now accept freight as a callable(period) for freight that moves by period.
- **CSX fuel surcharge is noted, not included** (Kolten): a caption under the corridor table lists CSX's $/car-mile by bid period (`_fsc_by_period("CSX", ...)`; publication 8662, the formula is INFERRED — only June 2026's .44 is published, so with no EIA diesel feed it shows "—").
- **NS fuel surcharge is included** (checkbox `ns_fsc_on`, default on). The NS seed is a SPREAD to NS Ft Wayne (Ft Wayne = 0, origins nearer a region than Ft Wayne negative; $/bu to GA / NC-SC-VA / East), so the surcharge counts only on the extra rail miles vs Ft Wayne:
  `ns_miles.delta_miles` = 1.10 × (great-circle(origin, region town) − great-circle(Ft Wayne, region town)), towns Gainesville GA / Greensboro NC / Harrisburg PA; `FD.fsc_cpb(fsc, miles, 3800 bu)` (Kolten, 2026-11-02: bushels per car are CSX and NS 3800, BN and UP 4000, CN unchanged — its per-commodity car weights; the CSX workbook itself says 3500 and `CSX_BU_PER_CAR` is now 3800 on his say-so). The seed's spreads track that distance difference (R² 0.7-0.8 per region, `tests/test_ns_miles.py`),
  which is what confirms they are Ft Wayne spreads. Judgement: the region towns, the 1.10; NOT verified: that the workbook's spreads exclude NS's fuel surcharge (Kolten asked for it to be added, so assumed). WTNN borrows Jackson TN's coordinates (the West Tennessee Railroad is based there). Dyer OH borrows Fostoria's coordinates (same spreads).
  Periods naming no month (Spot) take the current month's surcharge; months after the published ones use the formula on EIA diesel (needs EIA_API_KEY) else NS's last published value held flat.
  Highlighted Origins' NS row is now the cheapest-freight region per period (it was one fixed region before — with the surcharge the best region can change by period).
- **CSX tables are in the BN layout (2026-10-28, Kolten: "make the CSX table like BN comparing the two different corridors by state vs key corridors")**: `_csx_fob_by_corridor` — Columbus | Evansville side by side under each bid period, the bid / offer in a yellow row, CSX's fuel surcharge $/mi beneath it (noted, not included), negatives in red parentheses, the better corridor shaded. Used for **FOB by State** (best origin in each state, per corridor), **Key Corridors — Highlighted Origins** (the starred rows) and **FOB at Any CSX Location**. NS keeps its region layout. Row labels for CSX rows with no buying station use the origin group (Rule 11 origins show e.g. "IL CHICAGO - EXP Rule 11").

## Audit of the NS / CSX / CN freight (2026-10-28, after "IL NS FOB index is wrong, IL can't be above IN")
- **Seeds vs `Rail Spreads.xlsx`** (`Research Analyst/Misc/Rail Origins & Destinations`; the file is locked for reading in place — `cp` it to the scratchpad first): NS 67/67 rows identical; CSX 199/200 (the workbook now stars MI ITHACA / Zeeland Farms — seed flag updated); CN seed = Supplement 41 (effective Jun 23 2026, EXPIRES Aug 31 2026 — matches USDA's Jun-Aug rate).
- **Vintage is the real accuracy risk**: the NS tab says "Effective 2024-10-01" (two years old); CSX "2025-2026, 10/01/2025 Effective"; CN's supplement has expired. Bids are live, freight is not. Ask Kolten for the current NS / CSX / CN freight.
- **IL above IN on the NS state index** was Browns, IL: its GA spread is -2.03¢ in the workbook itself (every other IL origin is +6 to +7.5), it is not 105-car eligible, not starred, and not in NS's grain loader directory; the NS fuel surcharge then credits it for ~137 fewer miles to GA. The state index now defaults to **105-car-eligible origins only** (checkbox `ns_idx_105`; IL then comes from Sidney, IL -5.6 vs IN +3.4 at the Nov surcharge). TN showed "—" because WTNN had no coordinates; WTNN = West Tennessee Railroad, based in Jackson TN, so `ns_miles.SIBLING` borrows Jackson's. `C_RAIL` for NS is 1.10 now (was 1.25; CN's USDA-checked routes run 1.0-1.1).
- Not verified: that NS's workbook spreads exclude NS's fuel surcharge (the credit for origins nearer a region than Ft Wayne depends on it); a long strip like "Jan July" takes its FIRST month's surcharge only; BN seed was checked against "Fob BN Corn Plus.xlsx" at build, not again.
- **New files checked (2026-10-28, from Kolten's Downloads)**: `2026-27_CSXT-Grain-Origin-Spreads.pdf` (released 07/31/2026, effective 10/01/2026): all 177 rows I could parse (83 train buying stations + 94 less-than-train) are IDENTICAL to the seed (so the CSX seed is current for 2026-27; the PDF's WILLARD column, NE/NY/PA, isn't used — no bid corridor for it). `Ft Wayne Origin Spreads .xlsx` (sheet "24-25", effective 10/1/2024): 67/67 rows identical to the NS seed — it is the same sheet as `Rail Spreads.xlsx`'s NS tab, not a newer one; only NS/Kolten can say whether NS's spreads were reissued for 25-26 / 26-27.
- **BN tab in the CSX layout (2026-10-28, Kolten: "make the BN table with all the locations the same as CSX, key corridors listed with highlighted origins")**: **FOB by State — PNW vs Hereford** (`_bn_fob_by_origin(by_state=True)`: best FOB among ALL BNSF locations — the sheet's 13 + the price list's ~180 with estimated miles, `_bn_all_rows`), then **Key Corridors — Highlighted Origins** (the sheet's 13 origins, the old "FOB by Origin"), then **FOB at Any BN Location**. The old "BN Origins" block further down is unchanged.

## State Summary tab (2026-10-28, Kolten: "a summary page with state-indexed FOB values compared across all rail corridors, like the BN table, several delivery periods")
- Second tab, "📊 State Summary" (`_summary_tab`, a fragment; behind Bids, with the logo CSS shifted to tabs 3-6). It shows the NEXT FIVE WHOLE MONTHS (Nov, Dec, Jan, Feb, Mar on 10-28; checkbox `sum_cur` adds the current month), one table each: states down, corridors across — CSX Columbus, CSX Evansville, NS Ft Wayne, BN PNW, BN Hereford, CN — a yellow bid row, the best corridor per state shaded and named in a Best column.
- `_summary_corridors` builds each corridor's STATE INDEX (best origin in the state) from the same freight / fuel surcharge / bids as its own tab: CSX no FSC; NS 105-car origins, cheapest of its 3 regions, with FSC; BN every location (the sheet's 13 + price list, estimated miles), headline periods only (AMJJ→AM); CN = the **CN 105s corn bid (FOB Champaign; market `CN 105s`, the corn twin of `CN 105s Beans`)** carried to each origin: bid + freight(Champaign) − freight(origin), 105+ car, large railroad car, USDA tariff level + FSC on estimated miles. A radio (`sum_cn_src`, 2026-10-29, Kolten: "CN should be able to use the CN 105s bids") switches it to the CIF NOLA corn netback; with no CN 105s bids posted it falls back to CIF NOLA on its own (noted), and with neither CN is left out. UP is one column (see the UP tab section below).
- Verified with a stubbed AppTest (`scratchpad/test_summary.py`), not in a browser.
- Each corridor's bid is resolved to the WHOLE month by `_month_quote`: the plain month, else Split <month>, else FH/LH averaged, else the narrowest posted package covering it (`FD.period_months`: JFM = Jan-Mar, AMJJ = Apr-Jul, "Jan July" = Jan-Jul, FM = Feb-Mar); a bid not posted as the month itself is starred (*). BN's Oct/Nov/Dec keep the BN tab's own inference and typed bids. Freight and fuel surcharge use that month.

## UP tab (2026-11-02, Kolten's description of how UP origins trade) — `up_spreads.py`, `tests/test_up_spreads.py`
- UP origins trade as a DISCOUNT to a base: Group 3 (North Bend, NE; market `UP Group 3`) or Interior IA (Joice, IA; `UP Interior IA`), which typically trades 8¢ under Group 3. So FOB(origin) = base bid − discount (the discount is the freight spread, like CSX / NS). Named: Brewster + Heron Lake MN 3 off both (mostly Group 3), Savage MN 12 off G3 / 7 off IIA, Sloan IA 3 off G3, Randolph 8 / Hope 7 / Welcome 6 MN off IIA. An origin with one stated side takes the other through the 8¢ († = derived). Other IA origins are par to IIA, other NE origins par to G3 (a small discount isn't stated, so par); MN / SD origins have no rule beyond the named ones.
- Allen Station IL is posted as its own bids (`UP Illinois (Mex)` / `(Dom)`) and is already FOB; typically 20¢ better than IIA to Mexico, about 30¢ domestic — the tab prints the actual spread beside that (the old archive estimate was Group 3 + 20 / + 10, not the same relation).
- Tab sections (BN layout, `_csx_fob_by_corridor(..., title="FOB UP")`, no fuel surcharge row): raw UP bids; **FOB by State — Group 3 vs Interior IA** (NE / IA / MN best origin per base); **Key Corridors — Named Origins**; Allen Station Mexico vs Domestic; **FOB at Any UP Location** (the 142 origins on UP's 2023 shuttle list + the named ones; IA / NE take the par rule, others say there is no stated rule). The State Summary has one UP column (best of the two bases; IL = Allen's better market). The UP fuel surcharge isn't in the freight (the spreads are paper spreads); the reference expander is unchanged.

## Check against LIVE data before pushing (learned 2026-11-02)
A `return` that slid into an `else:` crashed the State Summary only when CN 105s bids were posted — the stubbed AppTests never hit that branch, and the exception stopped the page so the UP tab (and every tab after the Summary) never rendered. Before a push that touches several tabs, run the app on live Snowflake data, read-only, with the basis tracker's `.env` Snowflake settings (set USE_SNOWFLAKE and the SNOWFLAKE_* variables in the process environment, private key path made absolute, `BASIS_DATABASE_URL=""`), then `AppTest.from_file("app.py")`, `.run()` and check `at.exception` — see `scratchpad/test_live_up.py`.

## State Summary: core states + whole numbers (2026-11-02)
- **Core shipping states with a toggle** (Kolten: "a sub set of states that can then be expanded on a toggle ... the core shipping states"): the State Summary opens on `_CORE_STATES` = IA, IL, IN, MI, MN, ND, NE, OH, SD (my pick of the main rail-loading states, plus ND and MI that Kolten asked for — edit the constant) and the toggle `sum_all_states` ("Show all states", off by default) shows every state any corridor has an origin in.
- **State ETHANOL INDEX column (Kolten: "get this from the Basis Tracker on the summary page")**: `ethanol_index.py` (+ `tests/test_ethanol_index.py`) — the average corn basis (¢ vs futures, the same unit as the corridors' bids) of the tracker's `Corn Processing` plants (its ethanol plants and corn processors, ~130 on live data) by state and delivery month, from each plant's LATEST snapshot in the last 10 days (`snapshots` + `snapshot_rows` + `location_meta` in JSA.BASIS_TRACKER; forward bids only, corn only, a plant's bids for a month averaged before the state average). It is a BENCHMARK column on the Summary (`benchmark: True`): shown beside the corridors but never shaded or named as the best. Needs Snowflake (`RD._use_snowflake()`); without it the column is just absent. The tracker has no named "state ethanol index" — this is my reading of it (state average of its Corn Processing plants); confirm that is the one he means.
- **Whole numbers, every FOB tab (Kolten: "use the whole number no decimals ... same on every tab")**: `_rnd` (halves away from zero) is used by `_fob_cell`, `_fob_cell_int`, `_bn_fob_cell` (BN / CSX / UP / Summary tables), the NS state index and best-freight text, the expanded freight tables, the BN freight build and the CN freight cells. Bids (which can be half-points), FSC $/mile and $/car rates keep their own formats; Net Carry is untouched (its cents are small).
- **UP logo**: `assets/up_logo.svg` (a hand-drawn SVG of the shield from the image Kolten attached — blue top with UNION PACIFIC, red / white stripes) on tab 7 via `UP_LOGO_URI` / `UP_LOGO_RULE`, like the other four carriers.
- **Ethanol index on the BN tab (Kolten, 2026-11-02: "add a column for the state ethanol index to the BN tab"; he confirmed it is the state average of the tracker's Corn Processing plants)**: `_bn_fob_by_origin(..., eth=_ethanol_index())` adds one grey-italic "Ethanol" column per headline period in the FOB by State, Key Corridors and FOB at Any BN Location tables (the row's state; a period reads the index at its FIRST month, like the BN freight); checkbox `bn_f_eth` (default on) turns it off. A benchmark: never shaded; the car-val row and bid row show "—" / "plant avg" under it.
- **Tighter State Summary headers (Kolten, 2026-11-02)**: columns are now CSX COL, CSX Eville, NS, BN PNW, BN Hereford, UP, CN 105s (CN CIF NOLA when the radio / fallback is on), Ethanol Index, Best. **BN COBO is not on the Summary** (it stays on the BN tab).
- **Front month (Kolten, 2026-11-02: "November as the front month and then the 4 months to follow"; 2026-11-03: "always show the nearest month ... don't even make it an option")**: the State Summary ALWAYS starts on the current month and shows it plus the next four (Nov, Dec, Jan, Feb, Mar in November). There is no toggle for it (the old `sum_cur` checkbox was removed).
- **CP PNW dropped from the Bids tab's BN Western Rail section (Kolten, 2026-11-02)**: `rail_corridors.MANUAL_SECTIONS` no longer lists `BN PNW CP` (displayed "CP PNW"); it stays in `CORRIDORS` so Net Carry and the archive still know it. NB `rail_corridors.py` is a hand-copied registry from the basis tracker — the tracker's own Rail FOB tab still shows it.

## CN tariff for every origin (2026-11-02, Kolten: "just focus on the CN" -> "tariff for every origin")
- **Second USDA origin checks the flat-step assumption**: AgTransport `3az4-jkr6` also publishes CN **Ida Grove, IA -> Convent, LA** (soybeans, 105-car unit): the seed's Ida Grove 105+ rates ($3,704 railroad / $3,269 private, large car) are EXACTLY USDA's Jun-Aug 2026 Ida Grove rates (so Supplement 41 = the Jun-Aug level for both lanes), and since then both origins took the same step in every month — Sep 2026 +$275, Nov-May +$165 (Nov 2025-May 2026) — EXCEPT Oct 2026, when Gibson City stepped +$495 on the seed and Ida Grove only +$275 (Oct 2025 both +$440 over Sep). So the per-month flat $/car step (`FD.cn_tariff_uplift`) is applied to every origin; the one known miss is the Oct step. `tests/test_cn_miles.py` keeps that check (snapshot `data/usda_cn_tariff.json` has the Ida Grove series under `other_lanes`).
- **Live refresh**: `usda_cn.py` overlays the committed Gibson City series with USDA's live API (public, no key; `USDA_APP_TOKEN` is sent if set, cached 6 h, any failure falls back to the snapshot; `USDA_CN_LIVE=0` = snapshot only, as the unit tests do), so USDA's actual Nov / Dec rates replace last year's stand-ins when it publishes them (mid-month). `FD.cn_usda_series()` goes through it.
- Still not available: CN's own current supplement (public price documents need a visitor registration) — the real per-origin rates would replace the step model; the raw tariff table at the bottom of the CN tab still shows the supplement's own (Jun-Aug) rates.

## Disclaimer (2026-11-02, Kolten: "add disclaimer to bottom of each page on dashboard")
`_render_disclaimer()` draws JSA's standard compliance disclaimer (the River FOB Portal's wording, which is also the tracker emails' signature text; the year is the calendar year) as the LAST thing on the page, after all the tab blocks — so it sits at the bottom whichever tab is open — and on the not-configured notice page too. It is identical in the view-only build. No wording was supplied, so the existing standard text was reused; change it in `_render_disclaimer`.
- **Tab order (2026-11-02, Kolten: "move Shipments to the right of Map")**: Bids, State Summary, CSX, NS, BN, CN, UP, Map, Shipments, References, Net Carry. The carrier logos stay on tabs 3-7 (CSX / NS / BN / CN / UP), which this move doesn't touch.

## State Level tab (2026-11-03, Kolten: "a new tab called state level ... like the state summary but you filter a specific state ... rail corridors and ethanol plants along with river locations to compare")
- Third tab, "📍 State Level" (`_state_level_tab`, a fragment). Layout CHOSEN by Kolten from his "FOB Central IL Corn" sheet image (he first wrote it the other way round — columns = corridors — then picked the sheet's layout): rows grouped **River / Processor / East Rail / West Rail**, columns = the next 8 delivery months (current month first, labelled Spot, 1 Mon ... 7 Mon). A State selectbox (`sl_state`, default IL) filters it; multiselects pick which **ethanol plants** and **river terminals** in the state to show (defaults: the 5 each with the most forward months; keys carry the state).
- Rail rows reuse `_summary_corridors` (the State Summary's numbers: the state's best origin on that corridor after freight, CN on the CN 105s bid): East Rail = CN 105s (Champaign), CSX COL (Columbus), CSX Eville (Evansville), NS (Ft Wayne); West Rail = UP, BN PNW, BN Hereford. Processor rows = the state's Ethanol Index plus the selected plants; River rows = the selected terminals. Plants / terminals come from the tracker's latest corn bids (`ethanol_index.LOC_SQL` / `location_series`, facility types `Corn Processing` and `River Terminal`, last 10 days; a plant bid is delivered, a river bid is at the terminal).
- Shading (the sheet's colours): the best two and worst two RAIL rows per month green / red (rankings leave the river out, like the sheet). NOT applied: the sheet's spreads / adjustments (37c truck freight + 4c margin to bring STL to a Central IL FOB, Havana margins, Decatur +5 over Ft Wayne) — the river and plant rows are as posted; ask Kolten for his rules if they should be applied.
- Tab order is now Bids, State Summary, State Level, CSX, NS, BN, CN, UP, Map, Shipments, References, Net Carry; the carrier logos moved to tabs 4-8 (CSS `nth-of-type`, `UP_LOGO_RULE` = 8).

## Bid side only; one-sided offer postings stay blank (2026-11-09, Kolten)
- Kolten reported the State Level numbers looked like they came off the OFFER side. Every rail FOB in the portal is bid - freight (checked on live data: CSX COL IL Nov = bid 30 - 12.8 = 17; the offer would be 27) — nothing used the offer. What he then asked for: **a month whose own postings (the plain month, Split / FH / LH / MP of it) carry an offer but NO bid is left BLANK** — not filled from a covering package. `_offer_only_month` is checked in `_month_quote` (State Summary / State Level) and in `_bn_infer_quote` (BN tab headline periods and the Summary's BN Oct / Nov / Dec). e.g. UP Group 3 Jan (offer only) no longer takes the JFM bid; BN PNW FH / LH Dec (offers only) don't fill Dec (a typed BN bid override still does). A month whose own postings include any bid is unchanged.

## State Level: Illinois cleaned up (2026-11-09, Kolten: "clean up the lists for the State level tables, start with IL")
- **IL has no pickers any more**: River rows = INDEXES (`state_level.py`, `tests/test_state_level.py`) — **Zone 2, Zone 3, Zone 5 and STL** — each the simple average of its terminals' corn bids for the month (a terminal's own bids averaged first), from the Basis Tracker's latest bids; Processor = the state **Ethanol Index** only (no individual plants); the seven rail rows as before. Zones are the tracker's own `location_meta.delivery_zone` tags (IL: Zone 1, 2, 3, 5): Zone 2 = CGB River Landing, CHS Morris, CHS Seneca; Zone 3 = CGB Hennepin, CHS Ottawa River Mkt, CHS Peru Marketstreet, Cargill Lacon, Cargill Spring Valley South; Zone 5 = CHS Havana/Beardstown, Cargill Beardstown / Havana / Meredosia (the tracker's Zone 5 also holds the St. Louis-area terminals, which are pulled OUT into STL). **STL** = Bunge Fairmont City, CGB Cahokia, CHS Cahokia, Cargill East St. Louis and ADM Sauget (untagged) — `STL_TERMINALS`. The ADM terminals (Hennepin, Lacon, Havana, Morris, Ottawa, Spring Valley, Creve Coeur ...) carry no zone in the tracker, so they are in NO group — tag them in `location_meta` (or extend `state_level.py`) to include them. Zone 1 (Chicago) and Zone 4 (Peoria) aren't shown (not asked for).
- Other states still show the plant / river-terminal pickers until each gets the same treatment (Kolten: "lets start with IL").

## State Level rail rows = the state's AVERAGE freight spread (2026-11-09, Kolten)
- Kolten: "on the State Level for the rail, can we do what the average freight spread is for the state from each rail corridor?" The State Level rail rows are now **bid less the AVERAGE freight across the corridor's origins in the state** (`_pick(vals, "avg")`; each corridor's `fob(state, m, mode)` takes mode "best" — the State Summary and the UP / BN / CSX tabs, unchanged — or "avg"), and a new **Spread** column shows that average spread at the front month (average FOB - bid; negative = freight against the bid, relative to Champaign for CN), like the sheet's Spread column (CN 0, CSX -13, NS -8, UP 0, BN Hereford -116 there). NS averages each origin's cheapest region; UP averages each origin's better base (named origins at their stated discounts + the unnamed par ones); BN / CSX / CN average over all their origins in the state (CSX every seeded row, BN every location incl. estimated miles, CN the 105+ car tier). `bidnum(state, m)` on each corridor gives the bid the spread is measured from.
- **Illinois (same day, Kolten)**: the UP row is **Allen Station, Mexico values** (`UP Illinois (Mex)`; this also changes the State Summary's IL UP number, which used the better of Mexico / domestic), and the **BN PNW row is dropped** ("it will never make sense").

## State Level: Indiana (2026-11-10, Kolten: "for IN use Evansville and Louisville for river values, their state ethanol index levels, NS, CSX COL & Eville, and CN rail values")
- Indiana is cleaned up like Illinois (no pickers): **River = Evansville and Louisville indexes**, Processor = the state Ethanol Index only, rail = CN 105s, CSX COL, CSX Eville, NS (UP and BN have no Indiana origins). `state_level.IN_GROUPS`: **Evansville** = ADM's four Evansville, IN terminals (`Evansville, IN ...`) plus ADM Mt. Vernon, IN (Kolten, 11-10: "add ADM Mt Vernon into the avg"; Newburgh and Rockport stay out); **Louisville** = CGB Louisville (KY) and CGB Jeffersonville (IN, across the river) — the tracker types both as COUNTRY ELEVATORS (it has no Louisville river terminal) and the Louisville one is in Kentucky, so they are read by name (`EXTRA_SQL`, `IN_EXTRA_LOCATIONS`). On 11-10 only ONE of the two had forward corn bids, so "Louisville index" shows "Avg of 1 terminal" and gaps — Kolten: "keep Louisville as 1". ADM Mt. Vernon / Newburgh / Rockport (Indiana river terminals) are not shown. `SL.RIVER_ORDER` lists the cleaned states (IL, IN); `river_index(rows, state)`.

## State Level: Iowa, Ohio, Nebraska (2026-11-10, Kolten) — and the generalisation
- `state_level.NAMED_GROUPS` now drives the cleaned-up states' river rows by exact `(provider, location)` (read by name with a LEFT JOIN — `named_sql` — because the tracker leaves many of these untyped, in a neighbouring state, or without a `location_meta` row at all); IL stays zone-based. `RIVER_ORDER` lists the cleaned states (IL, IN, IA, OH, NE); the rail rows per state are `app._SL_RAIL_BY_STATE`, looked up by corridor label from `_summary_corridors(..., state_level=True)` (which, for the State Level only, also builds `UP Interior IA` / `UP Group 3` as separate corridors and `BN COBO`; the State Summary is unchanged).
- **IA** (his list: "state ethanol index value, Dubuque River Value, UP Interior, UP Group 3, CN, NS, BN PNW & BN Hereford, BN COBO might make sense as well?"): river = **Dubuque** = ADM "East Dubuque, ADM Grain" (the ONLY Dubuque location the tracker carries; it is on the Illinois bank and has no `location_meta` row, so it shows "Avg of 1 terminal" with gaps); rail rows = CN 105s, NS (East Rail) then UP Interior IA, UP Group 3, BN PNW, BN Hereford, BN COBO. COBO was included on his "might make sense" — drop it from `_SL_RAIL_BY_STATE` if not.
- **OH** ("state ethanol index, Toledo, Cincinnati for river/export bids, CSX Eville, CSX COL, NS"): river = **Toledo** (ADM Toledo export terminal + Andersons Toledo Edwin Dr and Kuhlman Dr) and **Cincinnati** (Cargill Kellogg, Cargill River Road); rail = CSX Eville, CSX COL, NS (three rows, so the shading is best / worst one).
- **NE** ("state ethanol index, UP Interior, UP Group 3, BN PNW & BN Hereford, BN COBO"): no river rows; rail = UP Interior IA, UP Group 3, BN PNW, BN Hereford, BN COBO.

## State Level: Kansas and Nebraska sub-indexes (2026-11-10, Kolten)
- **Nebraska (revised)**: the state Ethanol Index plus **Eastern NE index** and **Central NE index** (the state's plants split by longitude: Eastern >= -97.7 = York, Fairmont, Columbus, Fremont, Blair, Jackson, Adams; Central -100.5 to -97.7 = Plainview, Aurora, Central City, Wood River, Ravenna, Ord, Atkinson, Minden; the two West plants — Bridgeport, Madrid — are in the state index only); rail = UP Group 3, UP Interior IA, BN Hereford, BN PNW (BN COBO dropped from NE).
- **Kansas**: the state Ethanol Index plus **Northeast KS index** (lon >= -98.9: Lyons, Colwich, Garnett) and **Southwest KS index** (lon < -98.9: only Oakley — the tracker holds just four Kansas plants, East KS Agri-Energy Garnett has no bids, so each sub-index is one or two plants and Oakley is really north-west); a **Garden City region** row (`state_level.REGION`: every non-ethanol Kansas location of any type within 60 miles of Garden City — Garden City Coop's elevators, ADM Leoti / Copeland / Plains, Bartlett Scott City / Healy ... ~16 with bids; forward months are sparse); rail = UP Group 3, UP Interior IA, BN Hereford, BN PNW. **BN PNW has no Kansas origins, so its row is skipped** (any corridor with no value for the state shows no row). **The Kansas UP rows rest on an ASSUMPTION**: `up_spreads.GENERIC["KS"]` = par to Group 3 (no Kansas spread was ever stated) — it is identical to Nebraska's generic rule, so the KS UP numbers equal NE's; confirm or give the real Kansas discount. (`GENERIC` also feeds the UP tab's "FOB at Any UP Location", where KS origins now take it.)
- Mechanics: `ethanol_subindex(rows, state)` / `region_index(rows, state)` read lat / lon (`LOC_SQL` and `named_sql` now select them); the Kansas pull is `ALL_SQL` (every type, one state); `_SL_RAIL_BY_STATE` has IL, IN, IA, OH, NE, KS. The other states still show the plant / river-terminal pickers.

## UP split: Group 3 and Interior IA separate (2026-11-10, Kolten: "Show Group 3 and Iowa interior both separate")
- **State Summary**: the single UP column is now **UP G3**, **UP IIA** and **UP Allen** (IL only: Allen Station's own Mexico bids; blank for a month with no Mexico posting, e.g. Nov 2026). Each column = the state's best origin on that base (bid - discount); the Best column picks across all of them.
- **State Level**: every state with UP origins (NE, IA, MN, KS) shows two rows, **UP Group 3** and **UP Interior IA** (average freight spread, like the other rail rows); the default rows include both; IL keeps one **UP Allen** row. KS is State Level only (par to Group 3 is still an assumption). The old combined "UP" corridor (best of the two bases) is gone.

## State Level: Minnesota (2026-11-10, Kolten: "MN Ethanol index, Winona river, Cities River, BN PNW, BN Hereford, UP Group 3, UP Interior IA")
- River rows (`NAMED_GROUPS['MN']`): **Winona index** = ADM Winona + CHS Winona; **Twin Cities index** = ADM St. Paul (Elevator D) + CGB / CHS / Cargill Savage. Processor = the MN state Ethanol Index. Rail = BN PNW, BN Hereford, UP Group 3, UP Interior IA (`_SL_RAIL_BY_STATE['MN']`). Scoular Winona is not in Winona: the tracker types it KS / Rail Terminal and it posts only an in-store corn bid.
- Fix found on the way: CHS labels its grain `Yellow Corn`, and `location_series` / `state_index` only accepted grains starting with `corn`, so CHS bids were silently dropped everywhere (CHS Savage / Winona / Cahokia ...). `ethanol_index._is_corn` now accepts both.

## State Level: Iowa Eastern / Western ethanol indexes (2026-11-11, Kolten: "index IA ethanol by region, Eastern Iowa vs Western IA")
- `ETHANOL_SUBINDEX['IA']`: **Eastern IA index** (lon >= -93.6) and **Western IA index** (lon < -93.6, the Des Moines meridian; Jewell -93.64 falls west, Hanlontown -93.38 / Iowa Falls / Mason City east). Live 11-11: 17 eastern + 18 western plants (the tracker's Corn Processing set, so it includes non-ethanol processors such as GPC Washington, CHS Nestle Davenport, ADM / Cargill Cedar Rapids and Clinton, the same set the state Ethanol Index uses). `_state_location_rows` adds the plants to IA's named-group pull (`named_sql` carries no plants).

## State Level: South Dakota (2026-11-11, Kolten: "BN Hereford & PNW, UP Group 3 & Interior IA, Eastern Ethanol and western ethanol")
- Rows: the state Ethanol Index, **Eastern SD index** (lon >= -97.5: Watertown, Chancellor, Wentworth, Marion, Rosholt, Big Stone City, Hudson = 7 plants) and **Western SD index** (lon < -97.5: Scotland, Mitchell, Groton, Aberdeen, Mina, Onida = 6), then BN Hereford, BN PNW, UP Group 3, UP Interior IA. No river rows.
- **ASSUMPTION**: no SD UP origin discount was stated, so `up_spreads.GENERIC['SD'] = Interior IA, par` (Group 3 comes through the 8c paper spread, i.e. 8c under). SD UP rows are State Level only (not on the State Summary), like Kansas. Replace when Kolten gives the real SD spreads.

## State Level: North Dakota (2026-11-11, Kolten: "do the same with ND")
- Same layout as SD: state Ethanol Index, **Eastern ND index** (lon >= -97.5, the Red River Valley: Hankinson, Wahpeton) and **Western ND index** (Dakota Spirit / Spiritwood, Blue Flint / Underwood; the tracker holds only four ND plants, and Dakota Spirit posts Jan / Feb only), then BN Hereford, BN PNW, UP Group 3, UP Interior IA. No river rows.
- **ASSUMPTION**: `up_spreads.GENERIC['ND']` = par to Interior IA, like SD (no ND spread stated); ND UP rows are State Level only.
