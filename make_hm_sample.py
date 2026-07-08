"""
Generate a small, schema-accurate mock of the H&M Kaggle dataset so the adapter
(build_hm_data.py) and dashboard can be tested without the real 3.5GB download.

Writes, under data/hm_sample/ :
  articles.csv          - same columns as the real articles.csv (subset of rows)
  transactions_train.csv- t_dat, customer_id, article_id, price, sales_channel_id

Demand is driven by forecast strength x a realization multiplier (see hm_config),
so the resulting quadrant shows real Validated / Hype-trap / Sleeper structure
anchored on Pantone's Colors of the Year (Ultra Violet '18, Living Coral '19,
Classic Blue '20). This is TEST DATA - swap in the real Kaggle files for analysis.

Run:  python3 make_hm_sample.py
"""

import csv
import datetime as dt
import os
import random

import hm_config as C

random.seed(424242)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "hm_sample")
os.makedirs(OUT, exist_ok=True)

COLORS = ["Black", "White", "Grey", "Beige", "Blue", "Brown",
          "Pink", "Red", "Green", "Yellow", "Orange", "Purple", "Turquoise"]

# H&M articles.csv column order (the real file has 25 columns; we populate the
# ones the adapter reads and fill the rest plausibly so the schema matches).
ARTICLE_COLS = [
    "article_id", "product_code", "prod_name", "product_type_no",
    "product_type_name", "product_group_name", "graphical_appearance_no",
    "graphical_appearance_name", "colour_group_code", "colour_group_name",
    "perceived_colour_value_id", "perceived_colour_value_name",
    "perceived_colour_master_id", "perceived_colour_master_name",
    "department_no", "department_name", "index_code", "index_name",
    "index_group_name", "section_no", "section_name", "garment_group_no",
    "garment_group_name", "detail_desc",
]

GROUP_TYPE = {
    "Garment Upper body": ("Sweater", 252), "Garment Lower body": ("Trousers", 272),
    "Garment Full body": ("Dress", 265), "Accessories": ("Bag", 60),
    "Shoes": ("Sneakers", 87), "Nightwear": ("Pyjama set", 73),
}


def d(s):
    return dt.date.fromisoformat(s)


def target_fp_share(color, season, group):
    """Intended full-price share of sales for a style-color before simulation."""
    fc = C.forecast_strength(season, color)
    base = 0.55 + (0.12 if C.is_core(color) else 0.0)
    base += (fc / 100.0) * 0.22
    base *= C.REALIZATION.get((season, color), 1.0)
    base += random.uniform(-0.05, 0.05)
    return max(0.20, min(0.95, base))


def article_volume(color, season, group):
    """Roughly how many units this style-color will sell (drives buy depth)."""
    fc = C.forecast_strength(season, color)
    base = 36 * (2.0 if C.is_core(color) else 1.0)
    base *= (0.6 + fc / 100.0)            # buyers chase forecasted colors
    base *= {"Garment Upper body": 1.2, "Garment Lower body": 1.0,
             "Garment Full body": 0.9, "Accessories": 0.7,
             "Shoes": 0.8, "Nightwear": 0.6}[group]
    return max(6, int(base * random.uniform(0.7, 1.3)))


articles = []
tx_rows = []
aid = 108000000          # H&M article_ids are 9-digit-ish
cust_pool = [f"c{n:07d}" for n in range(4000)]

for season, (start, end) in C.SEASON_WINDOWS.items():
    s_start, s_end = d(start), d(end)
    span_days = (s_end - s_start).days
    for color in COLORS:
        for group in C.PRODUCT_GROUPS:
            n_articles = 2 if C.is_core(color) else 1
            for _ in range(n_articles):
                aid += random.randint(1, 9)
                ptype, ptype_no = GROUP_TYPE[group]
                articles.append({
                    "article_id": aid, "product_code": aid // 100,
                    "prod_name": f"{color} {ptype}", "product_type_no": ptype_no,
                    "product_type_name": ptype, "product_group_name": group,
                    "graphical_appearance_no": 1010016, "graphical_appearance_name": "Solid",
                    "colour_group_code": 9, "colour_group_name": color,
                    "perceived_colour_value_id": 4, "perceived_colour_value_name": "Dark",
                    "perceived_colour_master_id": 5, "perceived_colour_master_name": color,
                    "department_no": 1676, "department_name": f"{ptype} S",
                    "index_code": "A", "index_name": "Ladieswear",
                    "index_group_name": "Ladieswear", "section_no": 16,
                    "section_name": "Womens Everyday", "garment_group_no": 1002,
                    "garment_group_name": ptype, "detail_desc": f"{color} {ptype.lower()}.",
                })

                fps = target_fp_share(color, season, group)
                vol = article_volume(color, season, group)
                ref_price = C.GROUP_PRICE[group] * random.uniform(0.9, 1.15)

                # launch within the first ~40% of the season, then 14-week life
                launch = s_start + dt.timedelta(days=random.randint(0, max(1, int(span_days * 0.4))))
                n_weeks = 14
                fp_units = int(round(vol * fps))
                md_units = vol - fp_units
                # front-loaded full-price demand, markdown clears late
                fp_w = [pow(2.718, -0.18 * w) for w in range(n_weeks)]
                tot = sum(fp_w)
                fp_w = [x / tot for x in fp_w]

                for w in range(n_weeks):
                    week_day0 = launch + dt.timedelta(weeks=w)
                    if week_day0 > s_end + dt.timedelta(weeks=4):
                        break
                    # full-price units this week
                    fpu = int(round(fp_units * fp_w[w]))
                    # markdown units land mostly in the back half
                    mdu = 0
                    if w >= int(n_weeks * 0.55):
                        mdu = int(round(md_units / max(1, n_weeks - int(n_weeks * 0.55))))
                    for _ in range(fpu):
                        day = week_day0 + dt.timedelta(days=random.randint(0, 6))
                        tx_rows.append((day.isoformat(), random.choice(cust_pool), aid,
                                        round(ref_price * random.uniform(0.99, 1.0), 6),
                                        random.choice([1, 1, 2])))
                    for _ in range(mdu):
                        day = week_day0 + dt.timedelta(days=random.randint(0, 6))
                        tx_rows.append((day.isoformat(), random.choice(cust_pool), aid,
                                        round(ref_price * random.uniform(0.55, 0.72), 6),
                                        random.choice([1, 2, 2])))  # markdowns skew online

random.shuffle(tx_rows)

with open(os.path.join(OUT, "articles.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ARTICLE_COLS)
    w.writeheader()
    w.writerows(articles)

with open(os.path.join(OUT, "transactions_train.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_dat", "customer_id", "article_id", "price", "sales_channel_id"])
    w.writerows(tx_rows)

print(f"Wrote {len(articles):,} articles and {len(tx_rows):,} transactions to {OUT}")
print("Seasons:", ", ".join(C.SEASON_WINDOWS.keys()))
