"""
Synthetic retail dataset generator for seasonal color trend-validation analysis.

Produces:
  data/sales_skuweek.csv  - granular SKU x week sales/inventory rows (for BI / Excel)
  data/color_palette.csv  - reference: color families, hex, per-season forecast strength
  dashboard/data.js       - aggregated metrics + palette, embedded as a JS global
                            so the dashboard opens straight from disk (no server needed)

The model is deliberately built so that forecast strength (how hard Pantone / WGSN /
runway pushed a color in a given season) predicts actual demand ONLY imperfectly.
A handful of colors are engineered as "hype traps" (loud forecast, weak sell-through)
and "sleeper hits" (quiet forecast, strong sell-through) so the trend-validation
quadrant has something real to say.

Pure standard library - no external dependencies. Run:  python3 generate_data.py
"""

import csv
import json
import math
import os
import random

random.seed(20260626)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DASH_DIR = os.path.join(HERE, "dashboard")

# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------

# Seasons: SS = Spring/Summer, AW = Autumn/Winter. The most recent is in-season
# (fewer weeks of data) so the dashboard shows a "live" season too.
SEASONS = [
    {"code": "SS24", "label": "Spring/Summer 2024", "weeks": 14, "status": "Closed"},
    {"code": "AW24", "label": "Autumn/Winter 2024", "weeks": 14, "status": "Closed"},
    {"code": "SS25", "label": "Spring/Summer 2025", "weeks": 14, "status": "Closed"},
    {"code": "AW25", "label": "Autumn/Winter 2025", "weeks": 14, "status": "Closed"},
    {"code": "SS26", "label": "Spring/Summer 2026", "weeks": 7,  "status": "In-season"},
]

CATEGORIES = [
    {"name": "Dresses",   "buy": 1.00, "price": 89},
    {"name": "Knitwear",  "buy": 0.90, "price": 75},
    {"name": "Tops",      "buy": 1.15, "price": 39},
    {"name": "Denim",     "buy": 0.80, "price": 69},
    {"name": "Outerwear", "buy": 0.70, "price": 159},
    {"name": "Footwear",  "buy": 0.85, "price": 99},
]

REGIONS = [
    {"name": "North America", "w": 1.00},
    {"name": "Europe",        "w": 0.92},
    {"name": "APAC",          "w": 0.70},
]

CHANNELS = [
    {"name": "Retail", "w": 1.00, "return_base": 0.07},
    {"name": "Online", "w": 0.85, "return_base": 0.19},
]

# --------------------------------------------------------------------------
# Color palette. is_core = perennial neutral carried every season (the baseline
# that fashion colors are judged against). Fashion colors get a per-season
# forecast strength 0-100.
# --------------------------------------------------------------------------

CORE_COLORS = [
    {"name": "Black",        "hex": "#1A1A1A"},
    {"name": "White",        "hex": "#F2EFE6"},
    {"name": "Navy",         "hex": "#1F2D4D"},
    {"name": "Charcoal",     "hex": "#4A4A4A"},
    {"name": "Camel",        "hex": "#C19A6B"},
    {"name": "Beige",        "hex": "#D9C7A8"},
]

FASHION_COLORS = [
    {"name": "Peach Fuzz",      "hex": "#FFBE98"},
    {"name": "Burgundy",        "hex": "#6E1423"},
    {"name": "Chocolate Brown", "hex": "#4B3621"},
    {"name": "Butter Yellow",   "hex": "#F3E5AB"},
    {"name": "Sage Green",      "hex": "#9CAF88"},
    {"name": "Cobalt Blue",     "hex": "#2A4FC4"},
    {"name": "Lilac",           "hex": "#C8A2C8"},
    {"name": "Coral",           "hex": "#FF6F61"},
    {"name": "Mocha Mousse",    "hex": "#A47864"},
    {"name": "Aqua",            "hex": "#7FD7D2"},
    {"name": "Terracotta",      "hex": "#C66B3D"},
    {"name": "Hot Pink",        "hex": "#E55D9C"},
]

# Per-season forecast strength (0-100) for fashion colors. Loosely mirrors real
# trend narratives: Peach Fuzz = Pantone 2024, burgundy/brown owned AW24,
# butter yellow broke SS25, Mocha Mousse = Pantone 2025.
FORECAST = {
    "SS24": {"Peach Fuzz": 92, "Lilac": 70, "Aqua": 58, "Coral": 55, "Sage Green": 50,
             "Cobalt Blue": 45, "Butter Yellow": 38, "Hot Pink": 35, "Terracotta": 30,
             "Mocha Mousse": 28, "Burgundy": 25, "Chocolate Brown": 22},
    "AW24": {"Burgundy": 90, "Chocolate Brown": 82, "Mocha Mousse": 60, "Terracotta": 55,
             "Cobalt Blue": 50, "Sage Green": 40, "Lilac": 30, "Peach Fuzz": 28,
             "Aqua": 22, "Coral": 22, "Butter Yellow": 20, "Hot Pink": 20},
    "SS25": {"Butter Yellow": 88, "Aqua": 74, "Sage Green": 64, "Lilac": 56, "Coral": 50,
             "Cobalt Blue": 42, "Hot Pink": 40, "Peach Fuzz": 32, "Terracotta": 30,
             "Mocha Mousse": 28, "Burgundy": 24, "Chocolate Brown": 28},
    "AW25": {"Mocha Mousse": 90, "Burgundy": 78, "Chocolate Brown": 70, "Terracotta": 60,
             "Cobalt Blue": 44, "Sage Green": 40, "Lilac": 26, "Aqua": 22,
             "Peach Fuzz": 20, "Coral": 22, "Butter Yellow": 24, "Hot Pink": 24},
    "SS26": {"Cobalt Blue": 80, "Coral": 70, "Hot Pink": 64, "Aqua": 60, "Butter Yellow": 46,
             "Sage Green": 44, "Lilac": 42, "Peach Fuzz": 30, "Terracotta": 32,
             "Mocha Mousse": 30, "Burgundy": 30, "Chocolate Brown": 26},
}

# Engineered story: realization multiplier on demand vs. what forecast implies.
# >1 = forecast translated to sales (validated). <1 = hype trap. Sleepers are
# low-forecast colors given a >1 boost so they over-perform their hype.
REALIZATION = {
    ("SS24", "Peach Fuzz"): 0.68,    # the textbook hype trap - everywhere on the runway, soft at the till
    ("SS24", "Sage Green"): 1.32,    # quiet forecast, sleeper hit
    ("SS24", "Cobalt Blue"): 1.20,
    ("AW24", "Burgundy"): 1.28,      # validated - the AW24 color that actually sold
    ("AW24", "Chocolate Brown"): 1.18,
    ("AW24", "Mocha Mousse"): 1.15,
    ("SS25", "Butter Yellow"): 1.24, # validated
    ("SS25", "Aqua"): 0.74,          # hype trap
    ("SS25", "Chocolate Brown"): 1.30, # sleeper - off-trend for SS but quietly strong
    ("AW25", "Mocha Mousse"): 1.16,  # validated (Pantone 2025)
    ("AW25", "Terracotta"): 0.78,    # hype trap
    ("AW25", "Navy"): 1.10,
    ("SS26", "Cobalt Blue"): 1.18,
    ("SS26", "Coral"): 0.80,         # early read: hyped, underperforming
    ("SS26", "Sage Green"): 1.22,    # sleeper building
}

# Deterministic color x category fit. Some colors just work better in some
# product types. Built once, reused for every region/channel/season.
def build_fit_map():
    notable = {
        ("Butter Yellow", "Dresses"): 0.12, ("Butter Yellow", "Denim"): -0.12,
        ("Burgundy", "Knitwear"): 0.12, ("Burgundy", "Outerwear"): 0.10,
        ("Cobalt Blue", "Footwear"): 0.12, ("Cobalt Blue", "Knitwear"): -0.08,
        ("Hot Pink", "Outerwear"): -0.12, ("Hot Pink", "Tops"): 0.10,
        ("Chocolate Brown", "Outerwear"): 0.12, ("Chocolate Brown", "Dresses"): -0.06,
        ("Sage Green", "Knitwear"): 0.10, ("Aqua", "Denim"): -0.10,
        ("White", "Tops"): 0.10, ("Black", "Outerwear"): 0.08,
    }
    fit = {}
    for c in CORE_COLORS + FASHION_COLORS:
        for cat in CATEGORIES:
            key = (c["name"], cat["name"])
            fit[key] = notable.get(key, round(random.uniform(-0.06, 0.06), 3))
    return fit

FIT = build_fit_map()

# --------------------------------------------------------------------------
# Demand model
# --------------------------------------------------------------------------

BASE_BUY = 1100  # baseline units received for a fashion color in a 1.0 category/region/retail


def target_sell_through(color, season_code, category):
    """Intended full-price sell-through fraction for a style-color, before the
    weekly simulation. Blends a base rate, a core-neutral bonus, the forecast
    lift, the realization story, category fit, and noise."""
    is_core = color in [c["name"] for c in CORE_COLORS]
    forecast = 20 if is_core else FORECAST[season_code].get(color, 25)

    stp = 0.46
    if is_core:
        stp += 0.17                       # neutrals are the dependable floor
    stp += (forecast / 100.0) * 0.30      # forecast genuinely lifts demand...
    stp *= REALIZATION.get((season_code, color), 1.0)  # ...but only partly translates
    stp += FIT[(color, category)]
    stp += random.uniform(-0.06, 0.06)
    return max(0.14, min(0.97, stp)), forecast, is_core


def weekly_weights(n):
    """Front-loaded launch curve - newness sells hardest early, then decays."""
    raw = [math.exp(-0.16 * w) for w in range(n)]
    s = sum(raw)
    return [r / s for r in raw]


def simulate(units_received, stp_target, n_weeks):
    """Walk the season week by week. Sell full price against the demand pool;
    trigger an early markdown if underperforming by the back third, and always
    run an end-of-season clearance on whatever inventory remains."""
    weights = weekly_weights(n_weeks)
    fp_pool = stp_target * units_received
    inv = units_received
    sold_fp = [0.0] * n_weeks
    sold_md = [0.0] * n_weeks
    md_active = False
    early_md_week = int(round(n_weeks * 0.6))

    for w in range(n_weeks):
        if not md_active:
            cum_st = (units_received - inv) / units_received if units_received else 0
            if (w >= early_md_week and cum_st < 0.55) or (w >= n_weeks - 2):
                md_active = True
        if not md_active:
            demand = fp_pool * weights[w]
            s = min(inv, demand)
            sold_fp[w] = s
            inv -= s
        else:
            s = min(inv, inv * 0.45)   # clearance velocity on remaining stock
            sold_md[w] = s
            inv -= s
    return sold_fp, sold_md, inv


# --------------------------------------------------------------------------
# Generate
# --------------------------------------------------------------------------

ALL_COLORS = [(c["name"], c["hex"], True) for c in CORE_COLORS] + \
             [(c["name"], c["hex"], False) for c in FASHION_COLORS]

skuweek_rows = []   # granular output
agg = {}            # (season,color,category,region,channel) -> metrics
# cumulative full-price sell-through curves: season -> bucket -> {received, sold_by_week[]}
curves = {}

BUCKETS = ["Forecasted trend", "Other fashion", "Core neutral"]


def bucket_for(is_core, forecast):
    if is_core:
        return "Core neutral"
    return "Forecasted trend" if forecast >= 60 else "Other fashion"


for season in SEASONS:
    sc, n_weeks = season["code"], season["weeks"]
    curves[sc] = {b: {"received": 0.0, "sold": [0.0] * n_weeks} for b in BUCKETS}

    for color_name, color_hex, is_core in ALL_COLORS:
        for cat in CATEGORIES:
            for reg in REGIONS:
                for ch in CHANNELS:
                    stp_target, forecast, _ = target_sell_through(color_name, sc, cat["name"])

                    core_mult = 2.1 if is_core else 1.0
                    color_buy = 0.6 + (forecast / 100.0) * 0.9   # buyers chase forecasted colors
                    units = BASE_BUY * core_mult * cat["buy"] * reg["w"] * ch["w"] * color_buy
                    units = max(40, int(round(units * random.uniform(0.85, 1.15))))

                    sold_fp, sold_md, leftover = simulate(units, stp_target, n_weeks)

                    tot_fp = sum(sold_fp)
                    tot_md = sum(sold_md)
                    tot = tot_fp + tot_md
                    price = cat["price"]
                    md_discount = 0.38
                    revenue = tot_fp * price + tot_md * price * (1 - md_discount)
                    fullprice_revenue = tot_fp * price

                    ret_rate = ch["return_base"]
                    if color_name in ("White", "Hot Pink", "Cobalt Blue", "Coral"):
                        ret_rate += 0.04   # whites + saturated brights disappoint more online
                    if is_core and color_name != "White":
                        ret_rate -= 0.02
                    returns = tot * ret_rate

                    # granular SKU x week rows
                    for w in range(n_weeks):
                        skuweek_rows.append({
                            "season": sc,
                            "category": cat["name"],
                            "region": reg["name"],
                            "channel": ch["name"],
                            "color_family": color_name,
                            "color_hex": color_hex,
                            "is_core": int(is_core),
                            "forecast_strength": forecast,
                            "week": w + 1,
                            "units_received": units if w == 0 else 0,
                            "units_sold_fullprice": round(sold_fp[w], 1),
                            "units_sold_markdown": round(sold_md[w], 1),
                            "on_markdown": int(sold_md[w] > 0),
                            "unit_price": price,
                        })

                    key = (sc, color_name, cat["name"], reg["name"], ch["name"])
                    agg[key] = {
                        "season": sc, "color": color_name, "hex": color_hex,
                        "is_core": is_core, "forecast": forecast,
                        "category": cat["name"], "region": reg["name"], "channel": ch["name"],
                        "received": units,
                        "sold": round(tot), "sold_fp": round(tot_fp), "sold_md": round(tot_md),
                        "revenue": round(revenue), "fp_revenue": round(fullprice_revenue),
                        "returns": round(returns),
                    }

                    b = bucket_for(is_core, forecast)
                    curves[sc][b]["received"] += units
                    run = 0.0
                    for w in range(n_weeks):
                        run += sold_fp[w]
                        curves[sc][b]["sold"][w] += run


# --------------------------------------------------------------------------
# Write granular CSV
# --------------------------------------------------------------------------

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DASH_DIR, exist_ok=True)

with open(os.path.join(DATA_DIR, "sales_skuweek.csv"), "w", newline="") as f:
    fields = ["season", "category", "region", "channel", "color_family", "color_hex",
              "is_core", "forecast_strength", "week", "units_received",
              "units_sold_fullprice", "units_sold_markdown", "on_markdown", "unit_price"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(skuweek_rows)

# --------------------------------------------------------------------------
# Write palette reference CSV
# --------------------------------------------------------------------------

with open(os.path.join(DATA_DIR, "color_palette.csv"), "w", newline="") as f:
    fields = ["color_family", "color_hex", "is_core"] + [s["code"] for s in SEASONS]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for color_name, color_hex, is_core in ALL_COLORS:
        row = {"color_family": color_name, "color_hex": color_hex, "is_core": int(is_core)}
        for s in SEASONS:
            row[s["code"]] = (20 if is_core else FORECAST[s["code"]].get(color_name, 25))
        writer.writerow(row)

# --------------------------------------------------------------------------
# Write dashboard data.js (aggregated records + curves + meta)
# --------------------------------------------------------------------------

curve_out = {}
for sc, buckets in curves.items():
    curve_out[sc] = {}
    for b, d in buckets.items():
        rec = d["received"] or 1
        curve_out[sc][b] = [round(100 * v / rec, 1) for v in d["sold"]]

payload = {
    "generated_for": "Seasonal color trend-validation",
    "meta": {
        "metricLabel": "Full-price sell-through",
        "metricShort": "FP sell-thru",
        "forecastLabel": "Trend hype",
        "forecastShort": "Hype",
        "forecastSource": "Pantone / WGSN",
        "salesSource": "Simulated sales",
    },
    "seasons": SEASONS,
    "categories": [c["name"] for c in CATEGORIES],
    "regions": [r["name"] for r in REGIONS],
    "channels": [c["name"] for c in CHANNELS],
    "palette": [{"name": n, "hex": h, "is_core": c} for (n, h, c) in ALL_COLORS],
    "records": list(agg.values()),
    "curves": curve_out,
}

with open(os.path.join(DASH_DIR, "data.js"), "w") as f:
    f.write("// Auto-generated by generate_data.py - do not edit by hand.\n")
    f.write("window.COLOR_DATA = ")
    json.dump(payload, f, separators=(",", ":"))
    f.write(";\n")

# --------------------------------------------------------------------------
# Console summary
# --------------------------------------------------------------------------

print(f"SKU-week rows : {len(skuweek_rows):,}")
print(f"Agg records   : {len(agg):,}")
print(f"Colors        : {len(ALL_COLORS)} ({len(CORE_COLORS)} core, {len(FASHION_COLORS)} fashion)")
print(f"Seasons       : {', '.join(s['code'] for s in SEASONS)}")
print()
print("Sanity check - full-price sell-through by color, AW24 (all cats/regions/channels):")
chk = {}
for r in agg.values():
    if r["season"] != "AW24":
        continue
    d = chk.setdefault(r["color"], {"fp": 0, "rec": 0, "fc": r["forecast"]})
    d["fp"] += r["sold_fp"]
    d["rec"] += r["received"]
for color, d in sorted(chk.items(), key=lambda kv: -kv[1]["fp"] / kv[1]["rec"]):
    print(f"  {color:18s} forecast {d['fc']:3d}  FP sell-through {100*d['fp']/d['rec']:5.1f}%")
