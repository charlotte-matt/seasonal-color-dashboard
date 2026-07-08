# CLAUDE.md — Color_Analysis

Project reference for anyone (human or Claude) working on this repo. For the live
current-state snapshot and next steps, see [HANDOFF.md](HANDOFF.md).

## What this is

A **seasonal-color trend-validation dashboard** for a fashion/retail analyst. It answers
one question: **did the colors people searched for most actually sell at full price?**
It puts real **H&M sales** (vertical axis) against **Google Trends search interest**
(horizontal axis), season by season.

The deliverable is a self-contained dashboard (`dashboard/index.html`) that opens straight
from disk — plain SVG + vanilla JS, no build step, no dependencies, no internet.

## The most important caveat (read before touching metrics)

The public H&M data has **transactions only — no buy/inventory** (no "units received").
So we **cannot compute true sell-through** (sold ÷ received). Everything is measured as
**full-price SHARE of sales** = full-price units ÷ units *sold*. Denominators are always
*units that sold*, never *units bought*.

- Each transaction row = **one unit sold** (no quantity column).
- A sale is a **markdown** if its price is ≥ `--md-threshold` (default 12%) below that
  article's own peak price ever seen; otherwise **full price**.
- "Full-price share · seasonal colors" and "Markdown rate · seasonal colors" are scoped to
  **non-neutral (fashion) colors**, counted by item.

## Files

| File | Role |
|---|---|
| `dashboard/index.html` | The dashboard. ~590 lines, self-contained. Reads `data.js`. |
| `dashboard/data.js` | Generated data payload (`window.COLOR_DATA`). **Whatever script ran last wins.** Currently H&M + momentum forecast. |
| `build_hm_data.py` | **Mode B** — real H&M adapter. Streams `data/hm/*.csv` (two passes, `csv.reader`), writes `data.js`. |
| `fetch_trends.py` | Google Trends fetcher → `data/hm_forecast.csv`. Methods: `level` / `momentum` (default). Needs network. |
| `generate_data.py` | **Mode A** — synthetic data generator (stdlib, seeded). |
| `make_hm_sample.py` | Schema-accurate mock of the H&M files for testing Mode B without the 3.2 GB download. |
| `hm_config.py` | Shared config: color→hex, core-neutral set, season logic, Pantone-anchored forecast fallback, `NAME_NORMALIZE` (e.g. "Lilac Purple"→"Purple"). |
| `data/hm/` | Real H&M CSVs: `articles.csv` (34 MB), `transactions_train.csv` (3.2 GB, 31.8M rows). |
| `data/hm_forecast.csv` | Current forecast (Google Trends momentum). `.backup.csv` = previous. |
| `data/hm_forecast_detail.json` | Per-garment momentum + volume per color (+ core set) — powers the category-aware forecast. Written by `fetch_trends.py`, embedded into `data.js` as `forecastGarments`. |
| `data/trends_cache/` | Cached Trends responses (so re-runs don't re-hit Google). |
| `data/hm_sample/` | Mock H&M files. |
| `data/sales_skuweek.csv`, `data/color_palette.csv` | Synthetic (Mode A) outputs. |
| `README.md` | User-facing project docs. |
| `.claude/launch.json` | Preview server config (python http.server, port 8765). |

## How to run

```bash
# Preview the dashboard (or just open dashboard/index.html from disk)
python3 -m http.server 8765 --directory dashboard   # then open http://localhost:8765

# Rebuild dashboard data from the real H&M files (~3 min, 31.8M rows)
python3 build_hm_data.py --data-dir data/hm

# Refresh the Google Trends forecast, then rebuild (fetch NEEDS network — run with the
# sandbox disabled; pytrends rate-limits, but responses are cached)
pip install pytrends
python3 fetch_trends.py --method momentum        # or --method level (popularity, for A/B)
python3 build_hm_data.py --data-dir data/hm

# Synthetic demo instead of real data
python3 generate_data.py
```

## Dashboard structure (six numbered "acts")

1. **The season at a glance** — 4 sales KPIs, titles reworded and captions removed
   ("Seasonal-color items sold at full price", "Seasonal-items sold on discount",
   "Non-neutral items sold", "Sales revenue from seasonal color items") + a bottom sentence
   that now **describes those four KPIs** (no forecast talk — that lives in Act 2).
2. **Which colors were people searching for most?** — Google Trends explainer table (colors
   ranked by search interest + "Most searched as" top garment), then 6 forecast KPIs: Forecast
   accuracy, Avg forecast error, Full-price rev · most-searched color, **Full-price rev ·
   best-selling seasonal color** (top non-neutral seller by full-price revenue — the foil to
   most-searched), Biggest surprise, Biggest miss. (KPI cards carry no source chips, mostly no
   captions.)
3. **What actually sold?** — fashion-vs-neutral revenue split + ranked full-price/markdown
   bars per color.
4. **Did search interest predict what sold?** — a **predicted-vs-actual scatter** (x = the
   full-price share search predicted via a within-season linear fit, y = actual, with a 45°
   perfect-forecast line; `renderQuadrant()` still, id `#quadrant`) + an interest-rank→sales-rank
   bump chart + the full sortable scorecard table.
5. **Where did each color sell?** — full-width Color × Category heatmap.
6. **So what — the takeaways** — auto-written recommendations.

Filters (Season / Category / Channel) recompute everything live — including the search axis:
the forecast is **category-aware** (see Key definitions). There is no Region filter
(H&M customers are anonymized → single "All markets").

## Key definitions (as coded)

- **Search interest / forecast (0–100):** Google Trends **momentum** — a color's interest
  in the season's lead-up window ÷ its own long-run average, normalized per season so the
  top *fashion* color = 100. Momentum is **averaged across a 12-garment basket** (dress, top,
  shirt, sweater, jeans, pants, skirt, coat, jacket, heels, sneakers, bag — `DEFAULT_GARMENTS`
  in `fetch_trends.py`, `--garments` to change), US market, 6-month lead window, so the signal
  represents color demand across the assortment, not one silhouette. The interest score is the
  basket average, but the **"Most searched as"** column shows each color's single top garment by
  volume (e.g. "taupe dress", "khaki pants", "yellow jacket") — ranked by `compute_top_garment()`
  (anchor-batched level comparison, since momentum series are self-normalized and not comparable
  across garments). (`level` mode = raw popularity, single qualifier, for A/B.)
- **Category-aware forecast:** the interest is not a fixed per-color number — it recomputes from
  the garments of the selected **Category** filter. `fetch_trends.py` writes per-garment momentum
  + volume to `data/hm_forecast_detail.json`; the dashboard (`computeForecast()` + `CAT_GARMENTS`
  map in `index.html`) averages momentum over the active garments and re-normalizes per season, and
  re-picks each color's "Most searched as" from those garments. Filter to Lower body → the interest
  column re-ranks and "taupe dress" becomes "taupe pants"; **all categories = the full-basket blend
  = the CSV values** (default view unchanged). Unmapped categories (Underwear/Swimwear/Socks) have
  no garment terms → they fall back to the blend with a note. SS19 accuracy shifts by category
  (Shoes ≈ 61%, Lower body ≈ 48% vs 68% overall) — search predicts some categories better.
- **Forecast accuracy:** Spearman rank correlation of interest vs. full-price share across
  fashion colors, rescaled to 0–100% (50% = chance). `accDesc()` words it: ≥72 "tracked
  well", ≥57 "mild positive link", ≥45 "coin flip", else "ran backwards". **60–65% is weak.**
- **Verdicts:** Validated (high interest & sold), **Overrated** (high interest & flopped —
  CSS class is still `.tag.hype`), Sleeper (quiet & sold), Niche (quiet & modest), Core (neutral).
- **Core neutrals:** Black, White, Grey, Beige, Blue, Brown (the baseline "just buy black").

## Theme (H&M)

Cool-neutral base with H&M red as a **sparing** accent:
- `--bg #f6f6f6` · `--panel #fff` · `--ink #111` · `--muted #767676` · `--line #ececec`
- `--brand`/`--bad` **`#e50010`** (H&M red) — used on section-number circles, the title
  underline, takeaway bold, negatives, the "Overrated" tag.
- Selected filter chips = **black** (`--accent #111`). Green kept for positives/"Validated";
  slate blue `#3a5a8c` for "Sleeper"; grey combo chips.
- Heatmap is monochrome: **deep red = sold full price, pale = marked down.**

## Conventions & gotchas

- **`data.js` is generated** — don't hand-edit it as the source of truth. When a small
  change was patched directly into `data.js` (meta labels, banner note), the matching change
  was also made in `build_hm_data.py` so a rebuild stays consistent.
- **Preview caching:** when verifying in the Claude preview, `data.js` caches hard. Cache-bust
  with `await fetch('data.js',{cache:'reload'})` before `location.reload()`.
- **Editing index.html:** it has many `’ — · × ↑ →` unicode chars; match them exactly in Edit
  calls. CSS class names `.tag.hype` / `cls:'hype'` are internal — do **not** rename them even
  though the visible label is "Overrated".
- **fetch_trends caching** uses `hashlib` keys (stable across runs); `hash()` would not be.
- **Unused-but-harmless:** the weekly decay curves (`D.curves`) are still generated but the
  decay chart was removed — safe to ignore or strip later.

## Headline finding

Neither Google Trends **popularity** nor **momentum** reliably predicts full-price selling
in this H&M data. Broadening momentum from dresses-only to the **12-garment basket** lifted
SS19 accuracy from ≈ 63% to **≈ 68%** — a real but still weak-to-mild link (the #1-searched
color, Mole/taupe, was the biggest miss at ~1% of full-price sales; neutrals carry the
business). **Free search data is a weak color-trend forecast** — a serious version needs
WGSN / runway-tagging data. This is a legitimate proof-of-concept conclusion, not a failure.
