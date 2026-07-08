"""
Adapter: turn the real H&M Kaggle dataset into the dashboard's data.js.

Download from Kaggle (competition: h-and-m-personalized-fashion-recommendations)
and point --data-dir at the folder holding:
    articles.csv
    transactions_train.csv      (~3.5GB / 31M rows - streamed, not loaded into RAM)

What it computes per (season x color x category x channel):
    units sold, full-price vs markdown units, revenue, full-price share.
Markdown is detected from price drops: a sale below a color-style's reference
(peak) price by more than --md-threshold counts as a markdown.

Because public transaction data has no buy/inventory, there is NO "units received"
denominator - so the metric is full-price SHARE of sales (and velocity), not true
sell-through. The dashboard relabels itself accordingly via the meta block.

Usage:
    python3 make_hm_sample.py                       # create test data first
    python3 build_hm_data.py --data-dir data/hm_sample
    # then, for real:
    python3 build_hm_data.py --data-dir /path/to/h-and-m --md-threshold 0.10
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys

import hm_config as C

HERE = os.path.dirname(os.path.abspath(__file__))
csv.field_size_limit(10_000_000)


def load_articles(path):
    """article_id -> (color, category, is_core). Skips excluded/odd colors."""
    amap = {}
    cats = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            color = C.normalize_color(row.get("perceived_colour_master_name"))
            if C.is_excluded(color):
                continue
            cat = (row.get("product_group_name") or "Unknown").strip()
            amap[row["article_id"]] = (color, cat, C.is_core(color))
            cats[cat] = cats.get(cat, 0) + 1
    return amap, cats


def first_pass(tx_path, amap, sample_frac, max_rows):
    """Per article: reference (peak) price and first-sale date.
    Also returns the latest date in the file (to flag a truncated last season)."""
    ref_price, first_date = {}, {}
    max_date = ""
    n = 0
    with open(tx_path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        i_a, i_p, i_d = header.index("article_id"), header.index("price"), header.index("t_dat")
        for row in r:
            n += 1
            if max_rows and n > max_rows:
                break
            if row[i_d] > max_date:
                max_date = row[i_d]
            a = row[i_a]
            if sample_frac < 1.0 and (hash(a) % 1000) / 1000.0 >= sample_frac:
                continue
            if a not in amap:
                continue
            try:
                p = float(row[i_p])
            except ValueError:
                continue
            d = row[i_d]
            cur = ref_price.get(a)
            if cur is None or p > cur:
                ref_price[a] = p
            fd = first_date.get(a)
            if fd is None or d < fd:
                first_date[a] = d
            if n % 5_000_000 == 0:
                print(f"  pass 1: {n:,} rows", file=sys.stderr)
    return ref_price, first_date, max_date


def season_natural_end(code):
    """When a season would naturally finish (SS ~end Jul, AW ~end Jan next year)."""
    yy = int(code[2:])
    return f"20{yy:02d}-07-31" if code.startswith("SS") else f"20{yy + 1:02d}-01-31"


CHANNEL_MAP = {"1": "In-store", "2": "Online"}
CURVE_WEEKS = 16


def load_or_create_forecast():
    """Forecast strength per (season,color), editable in data/hm_forecast.csv.
    Seeded from hm_config (Pantone-anchored) on first run; edit it to plug in
    Google Trends or your own trend scores, then re-run."""
    path = os.path.join(HERE, "data", "hm_forecast.csv")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["season", "color", "forecast_strength"])
            for sc in C.SEASON_META:
                for color in C.COLOR_HEX:
                    if color in C.EXCLUDE_COLORS:
                        continue
                    w.writerow([sc, color, C.forecast_strength(sc, color)])
        print(f"  wrote editable forecast table {path}", file=sys.stderr)
    ov = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                ov[(row["season"], row["color"])] = int(float(row["forecast_strength"]))
            except (ValueError, KeyError):
                pass
    return ov


def second_pass(tx_path, amap, ref_price, first_date, md_threshold, sample_frac, max_rows, forecast_ov):
    agg = {}            # (season,color,cat,channel) -> metrics
    curves = {}         # season -> bucket -> [fp_units_by_week]
    n = 0

    def bucket(is_core, forecast):
        if is_core:
            return "Core neutral"
        return "Forecasted trend" if forecast >= 60 else "Other fashion"

    with open(tx_path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        i_a, i_p, i_d = header.index("article_id"), header.index("price"), header.index("t_dat")
        i_ch = header.index("sales_channel_id")
        for row in r:
            n += 1
            if max_rows and n > max_rows:
                break
            a = row[i_a]
            if sample_frac < 1.0 and (hash(a) % 1000) / 1000.0 >= sample_frac:
                continue
            meta = amap.get(a)
            if not meta:
                continue
            color, cat, core = meta
            try:
                price = float(row[i_p])
            except ValueError:
                continue
            t_dat = row[i_d]
            season = C.season_for_date(t_dat)
            channel = CHANNEL_MAP.get(row[i_ch].strip(), "Online")
            forecast = forecast_ov.get((season, color), C.forecast_strength(season, color))
            ref = ref_price.get(a, price)
            is_md = ref > 0 and price < ref * (1 - md_threshold)

            k = (season, color, cat, channel)
            o = agg.get(k)
            if o is None:
                o = {"season": season, "color": color, "hex": C.color_hex(color),
                     "is_core": core, "forecast": forecast, "category": cat,
                     "region": "All markets", "channel": channel,
                     "received": 0, "sold": 0, "sold_fp": 0, "sold_md": 0,
                     "revenue": 0.0, "fp_revenue": 0.0, "returns": 0}
                agg[k] = o
            o["sold"] += 1
            o["revenue"] += price
            if is_md:
                o["sold_md"] += 1
            else:
                o["sold_fp"] += 1
                o["fp_revenue"] += price

            # decay curve: full-price units by week since the style's launch
            if not is_md:
                fd = first_date.get(a)
                if fd:
                    wk = (dt.date.fromisoformat(t_dat) - dt.date.fromisoformat(fd)).days // 7
                    if 0 <= wk < CURVE_WEEKS:
                        b = bucket(core, forecast)
                        cv = curves.setdefault(season, {}).setdefault(b, [0] * CURVE_WEEKS)
                        cv[wk] += 1
            if n % 5_000_000 == 0:
                print(f"  pass 2: {n:,} rows", file=sys.stderr)
    return agg, curves


def build(data_dir, md_threshold, sample_frac, max_rows):
    art_path = os.path.join(data_dir, "articles.csv")
    tx_path = os.path.join(data_dir, "transactions_train.csv")
    for p in (art_path, tx_path):
        if not os.path.exists(p):
            sys.exit(f"Missing {p}. Download the H&M dataset or run make_hm_sample.py first.")

    print("Loading articles...", file=sys.stderr)
    amap, cat_counts = load_articles(art_path)
    print(f"  {len(amap):,} articles, {len(cat_counts)} product groups", file=sys.stderr)

    forecast_ov = load_or_create_forecast()
    print("Scanning transactions (pass 1/2: reference prices)...", file=sys.stderr)
    ref_price, first_date, max_date = first_pass(tx_path, amap, sample_frac, max_rows)
    print("Aggregating transactions (pass 2/2)...", file=sys.stderr)
    agg, curves = second_pass(tx_path, amap, ref_price, first_date,
                              md_threshold, sample_frac, max_rows, forecast_ov)

    # round revenue, set received = sold so the dashboard's fp/received = FP share
    records = []
    for o in agg.values():
        o["received"] = o["sold"]
        o["revenue"] = round(o["revenue"], 2)
        o["fp_revenue"] = round(o["fp_revenue"], 2)
        records.append(o)

    # keep the busiest categories for a readable dashboard
    MAX_CATEGORIES = 8
    top_cats = [c for c, _ in sorted(cat_counts.items(), key=lambda kv: -kv[1])][:MAX_CATEGORIES]
    top_cats_set = set(top_cats)
    records = [r for r in records if r["category"] in top_cats_set]

    # drop negligible-volume colors (the long tail, e.g. Bluish/Yellowish Green
    # from a handful of articles) - their full-price share is pure noise
    MIN_COLOR_UNITS = 5000
    color_units = {}
    for r in records:
        color_units[r["color"]] = color_units.get(r["color"], 0) + r["sold"]
    keep_colors = {c for c, u in color_units.items() if u >= MIN_COLOR_UNITS}
    dropped = sorted(c for c in color_units if c not in keep_colors)
    if dropped:
        print(f"  dropped low-volume colors (<{MIN_COLOR_UNITS} units): "
              f"{', '.join(dropped)}", file=sys.stderr)
    records = [r for r in records if r["color"] in keep_colors]

    seasons_present = sorted({r["season"] for r in records}, key=C.season_sort_key)
    colors_present = {r["color"] for r in records}
    channels_present = sorted({r["channel"] for r in records})

    # A season is "In-season" only if it is the newest AND the data still reaches
    # near today. If the newest season's data was cut off before it would naturally
    # end (as with a historical export), it is "Partial", not live.
    recent = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    season_objs = []
    for i, sc in enumerate(seasons_present):
        is_last = i == len(seasons_present) - 1
        if is_last and max_date and max_date < season_natural_end(sc):
            status = "Partial"
        elif is_last and max_date >= recent:
            status = "In-season"
        else:
            status = "Closed"
        season_objs.append({
            "code": sc, "label": C.SEASON_META.get(sc, {}).get("label", sc),
            "weeks": CURVE_WEEKS, "status": status,
        })

    # cumulative full-price curves -> % of bucket's full-price units realized by week
    curve_out = {}
    for sc in seasons_present:
        curve_out[sc] = {}
        for b, arr in curves.get(sc, {}).items():
            total = sum(arr) or 1
            run, out = 0, []
            for v in arr:
                run += v
                out.append(round(100 * run / total, 1))
            curve_out[sc][b] = out

    palette = [{"name": n, "hex": C.color_hex(n), "is_core": C.is_core(n)}
               for n in sorted(colors_present, key=lambda c: (not C.is_core(c), c))]

    # forecast detail (search term + raw signal + method) for the explainer section
    fdetail, fmethod = {}, None
    fpath = os.path.join(HERE, "data", "hm_forecast.csv")
    if os.path.exists(fpath):
        with open(fpath, newline="") as f:
            for row in csv.DictReader(f):
                fdetail.setdefault(row.get("season"), {})[row.get("color")] = {
                    "term": row.get("search_term", ""), "signal": row.get("raw_signal", "")}
                if fmethod is None and row.get("method"):
                    fmethod = row["method"]

    # per-garment detail (momentum + volume per color) so the dashboard can recompute
    # search interest for any Category subset — the category-aware forecast
    fgarments = None
    gpath = os.path.join(HERE, "data", "hm_forecast_detail.json")
    if os.path.exists(gpath):
        with open(gpath) as f:
            fgarments = json.load(f)

    payload = {
        "meta": {
            "dataset": "H&M (Kaggle) · Sep 2018 – Sep 2020",
            "metricLabel": "Full-price share of sales",
            "metricShort": "FP share",
            "forecastLabel": "Search interest",
            "forecastShort": "Interest",
            "forecastSource": "Google Trends",
            "salesSource": "H&M sales",
            "revenueLabel": "Revenue (idx)",
            "moneyPrefix": "",
            "hasReturns": False,
            "hasRegion": False,
            "note": "Public transaction data has no buy/inventory, so this shows full-price "
                    "SHARE of sales — not true sell-through. Search interest = Google Trends "
                    "(via fetch_trends.py), a rough proxy for how trendy each color was.",
        },
        "seasons": season_objs,
        "categories": top_cats,
        "regions": ["All markets"],
        "channels": channels_present,
        "palette": palette,
        "records": records,
        "curves": curve_out,
        "forecastMethod": fmethod,
        "forecastDetail": fdetail,
        "forecastGarments": fgarments,
    }

    out_path = os.path.join(HERE, "dashboard", "data.js")
    with open(out_path, "w") as f:
        f.write("// Auto-generated by build_hm_data.py from the H&M dataset.\n")
        f.write("window.COLOR_DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")

    print(f"\nWrote {out_path}")
    print(f"  records {len(records):,} | seasons {', '.join(seasons_present)} "
          f"| colors {len(colors_present)} | categories {len(top_cats)}")
    # quick sanity read
    chk = {}
    for r in records:
        if r["season"] != seasons_present[0]:
            continue
        x = chk.setdefault(r["color"], {"fp": 0, "tot": 0, "fc": r["forecast"]})
        x["fp"] += r["sold_fp"]
        x["tot"] += r["sold"]
    print(f"\nFull-price share by color, {seasons_present[0]}:")
    for color, x in sorted(chk.items(), key=lambda kv: -kv[1]["fp"] / max(1, kv[1]["tot"])):
        print(f"  {color:14s} forecast {x['fc']:3d}  FP share {100*x['fp']/max(1,x['tot']):5.1f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build dashboard data.js from the H&M dataset.")
    ap.add_argument("--data-dir", default="data/hm_sample",
                    help="Folder with articles.csv and transactions_train.csv")
    ap.add_argument("--md-threshold", type=float, default=0.12,
                    help="Price drop below peak that counts as a markdown (default 0.12)")
    ap.add_argument("--sample-frac", type=float, default=1.0,
                    help="Fraction of articles to sample for a quick run (0-1)")
    ap.add_argument("--max-rows", type=int, default=0,
                    help="Stop after N transaction rows (0 = all)")
    a = ap.parse_args()
    build(a.data_dir, a.md_threshold, a.sample_frac, a.max_rows or 0)
