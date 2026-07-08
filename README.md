# Seasonal Color — Trend Validation

An interactive dashboard for answering one question a fashion buyer actually cares about:

> **Did the colors the trend industry told us to buy actually sell at full price?**

It plots **forecast strength** (how hard Pantone / WGSN / runway pushed a color in a
given season) against **real full-price sell-through**, so every color lands in one of
four buckets: **Validated Trends**, **Hype Traps**, **Sleeper Hits**, or **Niche**.

The **same dashboard** runs on two data sources — pick one:

| Mode | Data | When |
|---|---|---|
| **A. Synthetic demo** | `generate_data.py` (made up, seeded) | Instant demo, full sell-through metrics |
| **B. Real H&M data** | `build_hm_data.py` (Kaggle public dataset) | Real apparel sales by color, 2018–2020 |

The dashboard adapts its labels automatically via a `meta` block in `data.js`
(e.g. "full-price sell-through" → "full-price share of sales" for H&M, since public
data has no buy/inventory). Whichever script you run **last** is what the dashboard shows.

---

## Quick start

```bash
# MODE A — synthetic demo (pure stdlib, no installs)
python3 generate_data.py

# MODE B — real H&M data (see "Run it on real H&M data" below)
python3 make_hm_sample.py                       # test data, optional
python3 build_hm_data.py --data-dir data/hm_sample

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
`perceived_colour_master_name` field — the closest public data to this use case.

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
| week (decay) | `transactions.t_dat` − article's first-sale date |
| full-price vs. markdown | price below the style's peak price by `--md-threshold` (default 12%) |
| revenue | Σ `price` (H&M prices are normalized → shown as an index) |
| forecast strength | `data/hm_forecast.csv` — Google Trends (via `fetch_trends.py`) or Pantone-anchored seed |

**Two honest caveats** (both handled by the dashboard's labels):
- **No "units received."** Public data has no buy/inventory, so the metric is
  **full-price *share* of sales** (+ velocity), not true sell-through.
- **No geography.** Customers are anonymized → a single "All markets" region (filter hidden).

### The forecast axis: real Google Trends (`fetch_trends.py`)

The X-axis (forecast strength) can be either hand-typed Pantone placeholders **or**
real Google Trends search interest. To use real data:

```bash
pip install pytrends
python3 fetch_trends.py                       # momentum (default), US, "<color> dress"
python3 fetch_trends.py --method level         # popularity, for A/B comparison
python3 build_hm_data.py --data-dir data/hm    # rebuild with whichever forecast you fetched
```

`fetch_trends.py` does the non-obvious work (fashion-qualified terms, a lead-up window
per season, caching to `data/trends_cache/`, backup to `hm_forecast.backup.csv`) and
offers two signals:

- **`--method level`** — absolute search interest. Anchor-batched + rescaled (Trends
  normalizes each query to its own peak and caps at 5 terms) so all colors share one scale.
- **`--method momentum`** (default) — each color's interest in the season ÷ its own
  long-run average. Isolates *rising* interest from baseline popularity, and is
  scale-invariant (each color compared only to itself, so no anchor needed).

> **What the A/B showed — and it's the real finding:** **neither** signal predicts
> full-price performance on the H&M data.
> - *Level* is pure popularity: Black/White/Blue dominate, **Red is the top fashion
>   color every season**, Pantone's Ultra Violet lands near the bottom, and the
>   **Validated Trends** quadrant is nearly empty — the best sellers (Yellow, Metal,
>   Green) are low-search **Sleeper Hits**.
> - *Momentum* gives a lively, season-varying forecast and does populate the quadrant,
>   but the hyped colors split ~evenly into Validated and Hype traps, so **forecasted
>   colors still land ≈ 0 to −5 pts vs. the core-neutral baseline** every season.
>
> **Conclusion:** free Google-Trends search interest — however you slice it — is a weak
> proxy for fashion *color* trends and does not forecast sell-through here. A serious
> forecast axis needs WGSN / runway-tagging data. (Caveats: momentum also conflates
> seasonality with novelty; US + "dress" is womenswear-biased; H&M is neutral-heavy fast
> fashion.)

---

## What's in the dashboard

It reads top-to-bottom as a six-act story; everything recomputes live when you change
the season / category / channel filters.

| Act | Section | What it tells you |
|---|---|---|
| **1** | KPIs + verdict | Full-price share, seasonal-color revenue share, markdown rate, **forecast accuracy** (rank correlation of hype vs. sales), plus **missed-opportunity** and **wasted-hype** $ (index). A one-line auto-written verdict sits underneath. |
| **2** | Forecast explainer | The colors ranked by search **hype**, with the exact search term used and the method — so the forecast numbers are transparent. |
| **3** | Sales breakdown | Fashion-vs-neutral revenue split, then every color ranked by sales with a full-price vs. discounted bar. |
| **4** | Did hype predict sales? | The **quadrant** (hype × full-price selling) beside a **hype-rank → sales-rank bump chart** (flat lines = forecast held; crossings = it didn't), plus the full sortable **scorecard** table. |
| **5** | Where & when | Color × category heatmap and the week-by-week sell-through decay curve. |
| **6** | So what | Auto-written recommendations (buy deeper / pull back / how much to trust the hype). |

Every metric carries a source chip (`H&M sales` / `Google Trends` / `Hype × Sales`) and an
ⓘ hover definition.

---

## The synthetic data model (Mode A)

Everything is produced by [`generate_data.py`](generate_data.py) (seeded, reproducible).

- **5 seasons** (SS24 → SS26; SS26 is "in-season" with fewer weeks), **6 categories**,
  **3 regions**, **2 channels**.
- **18 color families** — 6 perennial neutrals (the baseline) + 12 fashion colors,
  each with a real hex and a per-season **forecast strength**.
- Demand is driven by forecast strength **imperfectly on purpose**. A few colors are
  engineered as **hype traps** (loud forecast, weak sell-through — e.g. SS24 Peach Fuzz)
  and **sleeper hits** (quiet forecast, strong sell-through — e.g. SS24 Sage Green), so
  the quadrant has a real story rather than a clean diagonal.
- A weekly simulation walks each style-color through launch → decay → markdown →
  end-of-season clearance, producing full-price vs. markdown units, revenue, and returns.

### Outputs

| File | Grain | Use |
|---|---|---|
| `data/sales_skuweek.csv` | season × color × category × region × channel × **week** (~40k rows) | Drop into Excel / Power BI / Tableau for your own cuts. |
| `data/color_palette.csv` | one row per color | Reference: hex + forecast strength by season. |
| `dashboard/data.js` | pre-aggregated for the dashboard | Auto-generated; don't hand-edit. |

### Key metrics

- **Full-price sell-through** = full-price units ÷ units received (the margin-healthy demand signal).
- **vs. baseline** = a color's full-price sell-through minus the received-weighted average of the core neutrals.
- **Forecast hit rate** = share of hyped colors (forecast ≥ 55) that beat the baseline.
- **Markdown rate** = markdown units ÷ total units sold.
- **Return rate** = returns ÷ units sold (higher online; higher for whites & saturated brights).

---

## Project files

| File | Role |
|---|---|
| [`dashboard/index.html`](dashboard/index.html) | The dashboard. Self-contained; reads `data.js`, adapts labels from its `meta` block. |
| [`dashboard/data.js`](dashboard/data.js) | Generated data payload. **Whatever script ran last wins.** |
| [`generate_data.py`](generate_data.py) | Mode A — synthetic data generator. |
| [`build_hm_data.py`](build_hm_data.py) | Mode B — real H&M adapter (streams the Kaggle CSVs). |
| [`make_hm_sample.py`](make_hm_sample.py) | Schema-accurate mock of the H&M files for testing Mode B without the download. |
| [`fetch_trends.py`](fetch_trends.py) | Pull real Google Trends search interest → `data/hm_forecast.csv` (anchor-batched, cached). |
| [`hm_config.py`](hm_config.py) | Shared config: color→hex, core set, seasons, Pantone-anchored forecast. |
| `data/hm_forecast.csv` | Forecast strengths (Mode B) — written by `fetch_trends.py`, read by `build_hm_data.py`. |

## Plugging in any other data source

The dashboard only needs `dashboard/data.js` to expose `window.COLOR_DATA` with:

- `meta` — labels/flags (`metricLabel`, `hasReturns`, `hasRegion`, `moneyPrefix`, …),
- `records[]` at `season × color × category × region × channel` carrying
  `received, sold, sold_fp, sold_md, revenue, fp_revenue, returns, forecast, hex, is_core`,
- `curves[season][bucket][]` = cumulative full-price curve by week,
- plus `seasons / categories / regions / channels / palette` lists.

`build_hm_data.py` is the worked example of producing this from raw transactions —
copy its shape for a Shopify export or your own warehouse. The two hard real-world
steps are always the same: **normalizing color names** ("Sangria"/"Wine" → `Burgundy`)
and **attaching a forecast strength** per color/season (Pantone/WGSN/runway or a
search-trend proxy like Google Trends).

---

## Ideas to extend

- **Forecast accuracy over time** — does the brand's buying team get better at picking winners season over season?
- **Search/social signal** as the forecast axis instead of (or alongside) Pantone — Google Trends or runway mention counts.
- **Size-curve breakage** by color — did broken sizes kill an otherwise strong color early?
- **Buy-mix recommender** — given next season's forecast, suggest the neutral-vs-fashion split and depth per color.
- **Regional climate splits** — brights vs. neutrals by market temperature.
