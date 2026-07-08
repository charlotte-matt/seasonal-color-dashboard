# HANDOFF — Color_Analysis (as of 2026-07-03)

Snapshot for picking this up in a fresh context window. For the stable reference (files,
commands, definitions), read [CLAUDE.md](CLAUDE.md) alongside this.

## Where things stand

A working seasonal-color trend-validation dashboard, **live on real data on both axes**:
- **Sales:** real H&M transactions (Kaggle), Sep 2018 – Sep 2020, all 31.8M rows, in `data/hm/`.
- **Forecast:** real **Google Trends momentum** search interest, **averaged across a
  12-garment basket** (dress, top, shirt, sweater, jeans, pants, skirt, coat, jacket, heels,
  sneakers, bag), in `data/hm_forecast.csv`. Re-fetched & rebuilt 2026-07-03.

`dashboard/data.js` currently holds the H&M + momentum build. Open `dashboard/index.html`
(or serve `dashboard/` on port 8765) to view. **No known bugs; no console errors.**

## What was built (chronological-ish)

1. Started as a synthetic demo (`generate_data.py`) → built the real H&M adapter
   (`build_hm_data.py`) and ran it on the downloaded Kaggle files.
2. Added the Google Trends forecast (`fetch_trends.py`) with two methods — `level`
   (popularity) and `momentum` (rising interest, now the default). Ran the A/B.
3. Rebuilt the dashboard into a **6-act story flow** with a self-explanatory pass
   (plain-language labels, source chips, hover definitions, auto-written takeaway).
4. Iterated heavily on **copy and KPIs** with the user (see "Decisions" below).
5. Applied an **H&M theme** (cool-neutral + red accent) and flipped the heatmap so
   dark = sold well.

## Decisions the user made (don't re-litigate)

- **Language:** dropped the word **"hype"** everywhere → **"search interest" / "interest"**.
  Renamed the flop verdict "Hype trap" → **"Overrated"**. Keep plain language; the user
  dislikes jargon and wants each number's source + meaning obvious.
- **Header:** title **"Seasonal Color — Search vs. Sales"** (user may still change the title
  — she's thinking about it, so *don't* change it unprompted). Kept the question
  "Did the most searched-for colors actually sell?". One short intro line naming both data
  sources. Old "H&M (Kaggle)…" banner removed.
- **Act 1 KPIs:** full-price share + markdown rate scoped to seasonal (non-neutral) colors,
  by item count; added "Items that were seasonal colors"; reworded revenue KPI. No ⓘ icons,
  no source chips in Act 1.
- **Act 2 KPIs (moved here from Act 1):** Forecast accuracy, Avg forecast error, Full-price
  rev · top-searched, Biggest surprise, Biggest miss. (Replaced the old Missed-opportunity /
  Wasted-interest pair.) No ⓘ icons on Act-2 KPI cards either (tables keep their ⓘ).
- **Trimmed** the duplicate accuracy headline out of Act 4 (accuracy lives in the Act 2 KPI).
- **Section 5:** deleted the Sell-Through Decay chart; heatmap now full width.
- **Theme:** implemented the "recommended starting point" — cool-neutral base, H&M red
  (`#e50010`) on section numbers / title underline / takeaway / negatives, black selected
  chips, muted green kept for positives, heatmap **deep red = sold well, pale = marked down**.

## Current SS19 numbers (sanity check for a fresh session)

Full-price share (seasonal) 67.3% · Markdown 32.7% · Items seasonal 23.4% · Revenue seasonal
22.4% · Forecast accuracy **68%** (was 63% dress-only — the 12-garment basket lifted it) ·
Avg forecast error ±5 pts · Most-searched color **Mole/taupe** = only ~1% of full-price
sales · Biggest surprise **Yellow** (searched #7 → sold #2) · Biggest miss **Mole** (#1 → #5).

## Changes this session (2026-07-03)

- **Act 1 KPIs** retitled + captions removed; the bottom sentence now describes those four
  sales KPIs (no forecast talk).
- **Act 2 KPIs:** removed the "Interest × Sales" source chips + most captions; "Forecast
  accuracy" shows just the % (no "mild positive link" wording); "Full-price rev · top-searched"
  → **"Full-price rev · most-searched color"** = the single #1-searched color's full-price
  revenue + its share (re-added a one-line color-naming sub).
- **Act 4:** replaced the Trend-Validation Quadrant with a **predicted-vs-actual scatter**
  (45° perfect-forecast line; `renderQuadrant()` rewritten, new `.dash` legend key, desc
  updated in `applyLabels`). Section-4 caption reworded; bump-chart caption deleted.
- **Forecast:** `fetch_trends.py` now averages momentum across `DEFAULT_GARMENTS` (12) via
  `--garments`; per-garment volume floor + per-term error resilience. Re-ran + rebuilt `data.js`.
- **Added a 6th Act-2 KPI:** "Full-price rev · best-selling seasonal color" (top non-neutral
  seller by full-price revenue = **Red, 5%**) sitting next to "· most-searched color"
  (**Mole, 1%**) — the search-vs-sales contrast in one pair, both scoped to seasonal colors.
- **"Searched as" → "Most searched as":** column now shows each color's single top garment by
  volume (taupe dress, khaki pants, yellow jacket…) via new `compute_top_garment()` in
  `fetch_trends.py` (anchor-batched level compare). Interest score is still the basket average
  (ⓘ tooltip says so). Re-fetched (only ~54 new batch requests) + rebuilt.
- **Category-aware forecast (built):** the search axis now responds to the **Category** filter.
  `fetch_trends.py` writes per-garment momentum + volume + core to `data/hm_forecast_detail.json`;
  `build_hm_data.py` embeds it as `forecastGarments`; the dashboard `computeForecast()` +
  `CAT_GARMENTS` map (in `index.html`, called from `byColor()`) re-averages momentum over the
  selected categories' garments, re-normalizes, and re-picks "Most searched as". All categories =
  the blend = the CSV values (default unchanged); unmapped categories fall back to the blend with a
  note. New insight: SS19 accuracy by category — Shoes ≈ 61%, Lower body ≈ 48%, overall 68%.

## Open items / candidate next steps (nothing committed)

- **Title** — user is still deciding; leave as-is until she says.
- **In-page A/B toggle** — switch forecast method (popularity ↔ momentum ↔ Pantone) live in
  the browser, instead of re-running `fetch_trends.py`. Offered, not built.
- **Theme dials** offered: soften heatmap reds, swap green positives to neutral, flatter cards.
- **Predicted-vs-actual scatter:** mid-band colors (Orange/Mole/Khaki/Red/Green) still cluster
  because they genuinely all sold ~68–70% — labels crowd there. Could add leader lines or only
  label the big bubbles. Offered, not built.
- **Most-searched-color KPI** is now the single #1 color (noisier than the old top-third) —
  can revert to top-third / show both. Avg-error still uses a within-season linear fit.
- **Category-aware forecast — DONE** (see Changes this session). Possible follow-ups: surface the
  per-category accuracy somewhere (it's currently only visible by filtering); refine the
  `CAT_GARMENTS` map; decide whether narrow-category (few-garment) noise needs a floor/warning.
- **Trim unused:** `D.curves` (weekly decay data) is still generated but unused since the
  decay chart was removed.
- Bigger: replace Google Trends with WGSN/runway data for a real forecast signal.

## Gotchas for the next session

- `data.js` is generated; a rebuild overwrites it. Keep `build_hm_data.py` in sync with any
  direct `data.js` patch.
- Preview caches `data.js` hard — cache-bust before reload.
- `fetch_trends.py` needs network (run with sandbox disabled); it's cached in
  `data/trends_cache/`, so re-runs are cheap.
- When editing `index.html`, its strings are full of unicode punctuation — match exactly.
  Don't rename the internal `.tag.hype` / `cls:'hype'` (label shows "Overrated").
