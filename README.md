# Seasonal Color — Search vs. Sales

**▶ Live dashboard: https://charlotte-matt.github.io/seasonal-color-dashboard/**

An interactive dashboard that answers one question a fashion buyer actually cares about:

> **Did the colors people searched for most actually sell at full price?**

It puts real **H&M sales** (vertical) against **Google Trends search interest** (horizontal),
season by season, so every color earns a verdict: **Validated** (searched & sold),
**Overrated** (searched but flopped at full price), **Sleeper** (quiet but sold),
**Niche** (quiet & modest), or **Core** (a neutral).

The dashboard is a single self-contained page — plain SVG + vanilla JS, **no build step, no
dependencies, no internet**. It reads an embedded `dashboard/data.js` and opens straight from
disk (that's exactly what the live link above serves).

The **same dashboard** can run on two data sources:

| Mode | Data | Notes |
|---|---|---|
| **B. Real H&M** (what's live) | `build_hm_data.py` (Kaggle public dataset) | Real apparel sales by color, 2018–2020. Full-price *share* of sales. |
| **A. Synthetic demo** | `generate_data.py` (seeded, made up) | Instant demo with true sell-through metrics, no download needed. |

Labels adapt automatically via a `meta` block in `data.js` (e.g. "full-price sell-through" →
"full-price share of sales" for H&M, since public data has no buy/inventory). Whichever script
you run **last** is what the dashboard shows.

---

## Where the search data comes from

The horizontal **"Search interest"** axis is real **Google Trends** data, pulled via the
unofficial `pytrends` library ([`fetch_trends.py`](fetch_trends.py)) — free, public search
data, cached locally so re-runs don't re-hit Google.

For every color it measures search interest across a **12-garment basket** (dress, top, shirt,
sweater, jeans, pants, skirt, coat, jacket, heels, sneakers, bag) in the **US**, over the
**6 months before each season** — a demand read *before* anything sold. The score is
**momentum**: a color's interest in that lead-up window ÷ its own long-run average, so it
captures *rising* interest rather than baseline popularity (which neutrals like black would
otherwise dominate), rescaled per season so the top fashion color = 100. The dashboard's
**Category filter recomputes it from just that category's garments** (e.g. Lower body → jeans,
pants, skirt), and the **"Most searched as"** column names each color's single top garment
(e.g. *taupe dress*, *khaki pants*, *yellow jacket*).

> **Honest caveat:** this is a rough, free proxy — Google Trends is a sampled, self-normalized
> index, not absolute search volume, and it turns out to be a *weak* predictor of full-price
> selling (≈68%). A serious color-trend forecast would use professional data (WGSN, runway
> tagging, Pantone), not public search.

---

## What's in the dashboard

It reads top-to-bottom as a **six-act story**. Everything — including the search axis —
recomputes live when you change the **Season / Category / Channel** filters. (There's no Region
filter: H&M customers are anonymized, so it's a single "All markets".)

| Act | Section | What it tells you |
|---|---|---|
| **1** | The season at a glance | Four sales KPIs — seasonal-color items sold at full price, seasonal items sold on discount, non-neutral share of items sold, and sales revenue from seasonal colors — with a one-line summary underneath. |
| **2** | Which colors were people searching for most? | The Google Trends explainer table (colors ranked by search interest, plus "Most searched as"), then six forecast KPIs: **forecast accuracy**, avg forecast error, full-price rev of the **most-searched** color, full-price rev of the **best-selling seasonal** color, and the biggest **surprise** / **miss** (searched rank → sold rank). |
| **3** | What actually sold? | Fashion-vs-neutral revenue split, then every color ranked by sales with a full-price vs. discounted bar. |
| **4** | Did search interest predict what sold? | A **predicted-vs-actual scatter** (what search predicted each color's full-price share would be, vs. what it actually sold, with a 45° perfect-forecast line), an **interest-rank → sales-rank bump chart**, and the full sortable **scorecard**. |
| **5** | Where did each color sell? | A full-width **Color × Category heatmap** — deep red = sold at full price, pale = marked down. A color can win in one category and die in another. |
| **6** | So what | Auto-written takeaways (buy deeper / pull back / how much to trust the search signal). |

Table columns carry an ⓘ hover definition; the two data sources — **H&M sales** (vertical) and
**Google Trends** (horizontal) — label the two axes.

---

## The headline finding

Neither Google Trends **popularity** nor **momentum** reliably predicts full-price selling in
this H&M data. Broadening momentum from dresses-only to the **12-garment basket** lifted SS19
forecast accuracy from ≈ 63% to **≈ 68%** — a real but still weak-to-mild link:

- The **most-searched color** (Mole/taupe) was the **biggest miss** — only ~1% of full-price sales.
- The **best-selling seasonal color** (Red) drove ~5% — and **neutrals carry the business**
  (Black alone is ~31% of full-price sales).
- Filtering by category shows search predicts some categories better than others (SS19: Shoes
  ≈ 61%, Lower body ≈ 48%, vs. 68% overall).

**Free search data is a weak color-trend forecast** — a serious version needs WGSN / runway-
tagging data. That's a legitimate proof-of-concept conclusion, not a failure.

---

## Quick start

```bash
# The live dashboard is already built. To rebuild locally:

# MODE B — real H&M data (see "Run it on real H&M data" below)
python3 make_hm_sample.py                       # schema-accurate mock, optional
python3 build_hm_data.py --data-dir data/hm_sample

# MODE A — synthetic demo (pure stdlib, no installs)
python3 generate_data.py

# Then open the dashboard (either mode):
open dashboard/index.html          # macOS — works straight from disk
# or serve it:  python3 -m http.server 8765 --directory dashboard
```

No build step, no dependencies, no internet — the dashboard reads an embedded
`dashboard/data.js` and renders everything with plain SVG.

---

## Run it on real H&M data

The [H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations)
dataset is ~31M real apparel transactions (Sep 2018 – Sep 2020) with a real
`perceived_colour_master_name` field — the closest public data to this use case. (The raw
files are **not** in this repo — the transactions CSV alone is 3.3 GB, over GitHub's limit.)

1. **Download** from Kaggle (free account + accept competition rules). You only need
   two files — skip the 25 GB of images:
   - `articles.csv`
   - `transactions_train.csv`  (~3.5 GB)
2. **Build** the dashboard data (streams the big file, no pandas needed):
   ```bash
   python3 build_hm_data.py --data-dir /path/to/h-and-m
   # quick first run on a subset:
   python3 build_hm_data.py --data-dir /path/to/h-and-m --sample-frac 0.1
   ```
3. **Open** `dashboard/index.html`.

**How H&M fields map in:**

| Dashboard field | H&M source |
|---|---|
| color family | `articles.perceived_colour_master_name` (already grouped) |
| category | `articles.product_group_name` (top 8 by volume kept) |
| channel | `transactions.sales_channel_id` → In-store / Online |
| full-price vs. markdown | price below the article's own peak price ever seen, by `--md-threshold` (default 12%) |
| revenue | Σ `price` (H&M prices are normalized → shown as an index) |
| search interest | `data/hm_forecast.csv` + `hm_forecast_detail.json` — Google Trends momentum via `fetch_trends.py` |

**Two honest caveats** (both handled by the dashboard's labels):
- **No "units received."** Public data has only transactions (each row = one unit *sold*), so
  the metric is **full-price *share* of sales** — full-price units ÷ units sold — not true
  sell-through (sold ÷ received).
- **No geography.** Customers are anonymized → a single "All markets" region (filter hidden).

### The forecast axis: real Google Trends (`fetch_trends.py`)

```bash
pip install pytrends
python3 fetch_trends.py                       # momentum (default), US, 12-garment basket
python3 fetch_trends.py --method level         # raw popularity, for A/B comparison
python3 build_hm_data.py --data-dir data/hm    # rebuild with whichever forecast you fetched
```

`fetch_trends.py` does the non-obvious work — fashion-qualified terms, a per-season lead-up
window, averaging **momentum across the garment basket**, ranking each color's top garment for
the "Most searched as" column, and caching every response to `data/trends_cache/`. It offers
two signals:

- **`--method momentum`** (default) — each color's interest in the season ÷ its own long-run
  average. Isolates *rising* interest from baseline popularity; scale-invariant, averaged over
  the 12-garment basket, and written per-garment to `hm_forecast_detail.json` so the dashboard
  can recompute it live for any Category subset.
- **`--method level`** — absolute search interest, anchor-batched and rescaled so all colors
  share one scale. This is pure popularity (dominated by neutrals); kept for A/B contrast.

Needs network on the first run (`pytrends` rate-limits with HTTP 429, but every response is
cached, so re-runs resume from disk).

---

## The synthetic data model (Mode A)

For a no-download demo, [`generate_data.py`](generate_data.py) fabricates a seeded, reproducible
dataset that has the buy/inventory the public H&M data lacks (so Mode A shows **true**
sell-through, not just full-price share):

- **5 seasons** (SS24 → SS26; SS26 is "in-season" with fewer weeks), **6 categories**,
  **3 regions**, **2 channels**.
- **18 color families** — 6 perennial neutrals (the baseline) + 12 fashion colors,
  each with a real hex and a per-season **forecast strength**.
- Demand is driven by forecast strength **imperfectly on purpose**: a few colors are engineered
  as **overrated bets** (loud forecast, weak sell-through — e.g. SS24 Peach Fuzz) and **sleeper
  hits** (quiet forecast, strong sell-through — e.g. SS24 Sage Green), so the story isn't a
  clean diagonal.
- A weekly simulation walks each style-color through launch → decay → markdown → clearance,
  producing full-price vs. markdown units, revenue, and returns.

### Outputs

| File | Grain | Use |
|---|---|---|
| `data/sales_skuweek.csv` | season × color × category × region × channel × **week** (~40k rows) | Drop into Excel / Power BI / Tableau for your own cuts. |
| `data/color_palette.csv` | one row per color | Reference: hex + forecast strength by season. |
| `dashboard/data.js` | pre-aggregated for the dashboard | Auto-generated; don't hand-edit. |

---

## Project files

| File | Role |
|---|---|
| [`dashboard/index.html`](dashboard/index.html) | The dashboard. Self-contained; reads `data.js`, adapts labels from its `meta` block. |
| [`dashboard/data.js`](dashboard/data.js) | Generated data payload (`window.COLOR_DATA`). **Whatever script ran last wins.** |
| [`build_hm_data.py`](build_hm_data.py) | Mode B — real H&M adapter (streams the Kaggle CSVs, two passes). |
| [`fetch_trends.py`](fetch_trends.py) | Google Trends fetcher → `data/hm_forecast.csv` + `hm_forecast_detail.json` (12-garment momentum, cached). |
| [`generate_data.py`](generate_data.py) | Mode A — synthetic data generator. |
| [`make_hm_sample.py`](make_hm_sample.py) | Schema-accurate mock of the H&M files for testing Mode B without the download. |
| [`hm_config.py`](hm_config.py) | Shared config: color→hex, core-neutral set, season logic, Pantone-anchored forecast fallback, color-name normalization. |
| `data/hm_forecast.csv` | Search interest per season × color — written by `fetch_trends.py`, read by `build_hm_data.py`. |
| `data/hm_forecast_detail.json` | Per-garment momentum + volume per color — powers the category-aware search axis. |
| `.github/workflows/pages.yml` | GitHub Actions workflow that deploys `dashboard/` to GitHub Pages on every push. |

## Deployment

The live site is served by **GitHub Pages** from the `dashboard/` folder via
`.github/workflows/pages.yml`. Any push to `main` redeploys automatically (~1 minute), so to
update the live dashboard: rebuild `data.js`, then `git commit` + `git push`.

## Plugging in any other data source

The dashboard only needs `dashboard/data.js` to expose `window.COLOR_DATA` with:

- `meta` — labels/flags (`metricLabel`, `hasReturns`, `hasRegion`, `moneyPrefix`, …),
- `records[]` at `season × color × category × region × channel` carrying
  `received, sold, sold_fp, sold_md, revenue, fp_revenue, returns, forecast, hex, is_core`,
- `forecastGarments` — per-garment momentum + volume (for the category-aware search axis),
- plus `seasons / categories / regions / channels / palette` lists.

`build_hm_data.py` is the worked example of producing this from raw transactions — copy its
shape for a Shopify export or your own warehouse. The two hard real-world steps are always the
same: **normalizing color names** ("Sangria"/"Wine" → `Burgundy`) and **attaching a search /
forecast signal** per color/season (Google Trends here, or Pantone/WGSN/runway).

---

## Ideas to extend

- **Professional trend data** (WGSN / runway tagging / Pantone) as the forecast axis — the free
  search proxy is demonstrably weak; this is the biggest lever on the headline finding.
- **Surface per-category accuracy** — the search axis is already category-aware, so accuracy
  varies by Category; expose an at-a-glance "accuracy by category" readout.
- **Forecast accuracy over time** — does search track sales better in some seasons than others?
- **Size-curve breakage** by color — did broken sizes kill an otherwise strong color early?
- **Buy-mix recommender** — given next season's signal, suggest the neutral-vs-fashion split and
  depth per color.
</content>
</invoke>
