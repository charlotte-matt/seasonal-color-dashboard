"""
Shared configuration for the H&M trend-validation pipeline.

Used by both build_hm_data.py (the real adapter) and make_hm_sample.py (the mock
generator), so the forecast story stays in sync across them.

The H&M dataset (Kaggle: h-and-m-personalized-fashion-recommendations) gives us:
  - articles.csv      : per-product metadata incl. perceived_colour_master_name
  - transactions_*.csv: t_dat, customer_id, article_id, price, sales_channel_id

It does NOT give us the buy quantity (units received) or geography, so we measure
full-price SHARE of sales and velocity rather than true sell-through, and run a
single global market. See README for the full mapping.
"""

# --------------------------------------------------------------------------
# Colors. We aggregate on H&M's perceived_colour_master_name (a clean ~20-value
# field), map each to a representative hex for the swatches, and flag the
# perennial neutrals as "core" (the baseline fashion colors are judged against).
# --------------------------------------------------------------------------

COLOR_HEX = {
    "Black": "#1A1A1A", "White": "#F2EFE6", "Grey": "#8C8C8C", "Beige": "#D9C7A8",
    "Blue": "#3B5BA5", "Brown": "#6B4A2B",
    "Pink": "#E8709F", "Red": "#C0392B", "Green": "#4E9A5A", "Yellow": "#F2C53D",
    "Orange": "#E8843C", "Purple": "#7E5BA6", "Turquoise": "#3FB8AF",
    "Bluish Green": "#2E9E8F", "Khaki green": "#7C7B4F", "Yellowish Green": "#A6BE4B",
    "Metal": "#B8B8B8", "Mole": "#9B8B7A",
}

CORE_COLORS = {"Black", "White", "Grey", "Beige", "Blue", "Brown"}

# Master-colour values to drop from the analysis (not real colors).
EXCLUDE_COLORS = {"undefined", "unknown", "other", "transparent", ""}

# Real H&M master-colour names that should fold into our canonical families.
NAME_NORMALIZE = {
    "Lilac Purple": "Purple",
}


def normalize_color(name):
    name = (name or "").strip()
    return NAME_NORMALIZE.get(name, name)


def is_excluded(name):
    return (name or "").strip().lower() in EXCLUDE_COLORS


def color_hex(name):
    return COLOR_HEX.get(name, "#9AA0A6")


def is_core(name):
    return name in CORE_COLORS


# --------------------------------------------------------------------------
# Seasons. H&M data runs Sep 2018 - Sep 2020. We bucket transaction dates into
# fashion seasons: SS = Feb-Jul, AW = Aug-Jan (Jan rolls into the prior AW).
# --------------------------------------------------------------------------

def season_for_date(date_str):
    """'YYYY-MM-DD' -> season code like 'SS19' / 'AW19'."""
    y = int(date_str[0:4])
    m = int(date_str[5:7])
    if 2 <= m <= 7:
        return f"SS{y % 100:02d}"
    if m >= 8:
        return f"AW{y % 100:02d}"
    return f"AW{(y - 1) % 100:02d}"  # January belongs to the previous AW


def season_sort_key(code):
    """SS before AW within a year; chronological overall."""
    yy = int(code[2:])
    return yy * 10 + (0 if code.startswith("SS") else 1)


SEASON_META = {
    "AW18": {"label": "Autumn/Winter 2018"},
    "SS19": {"label": "Spring/Summer 2019"},
    "AW19": {"label": "Autumn/Winter 2019"},
    "SS20": {"label": "Spring/Summer 2020"},
    "AW20": {"label": "Autumn/Winter 2020"},
}

# Date windows used ONLY by the mock generator to place sales in a season.
SEASON_WINDOWS = {
    "AW18": ("2018-09-20", "2019-01-31"),
    "SS19": ("2019-02-01", "2019-07-31"),
    "AW19": ("2019-08-01", "2020-01-31"),
    "SS20": ("2020-02-01", "2020-07-31"),
    "AW20": ("2020-08-01", "2020-09-22"),
}

# --------------------------------------------------------------------------
# Product groups (H&M product_group_name). The mock uses this subset; the real
# adapter reads whatever groups exist and keeps the busiest MAX_CATEGORIES.
# --------------------------------------------------------------------------

PRODUCT_GROUPS = [
    "Garment Upper body", "Garment Lower body", "Garment Full body",
    "Accessories", "Shoes", "Nightwear",
]

GROUP_PRICE = {  # normalized price scale, matching H&M's tiny float prices
    "Garment Upper body": 0.025, "Garment Lower body": 0.034,
    "Garment Full body": 0.051, "Accessories": 0.014,
    "Shoes": 0.044, "Nightwear": 0.020,
}

# --------------------------------------------------------------------------
# Forecast strength 0-100: how hard each color was pushed that season (Pantone /
# WGSN / runway). Anchored on Pantone Color of the Year:
#   2018 Ultra Violet (Purple), 2019 Living Coral (Orange), 2020 Classic Blue.
# Replace/extend with Google Trends in data/hm_forecast.csv to make it live.
# --------------------------------------------------------------------------

FORECAST = {
    "AW18": {"Purple": 88, "Red": 58, "Pink": 50, "Green": 45, "Orange": 40,
             "Yellow": 35, "Turquoise": 30},
    "SS19": {"Orange": 85, "Pink": 72, "Purple": 60, "Green": 55, "Red": 55,
             "Yellow": 50, "Turquoise": 35},
    "AW19": {"Orange": 78, "Red": 62, "Green": 60, "Pink": 55, "Purple": 45,
             "Yellow": 40, "Turquoise": 30},
    "SS20": {"Blue": 86, "Green": 64, "Yellow": 58, "Red": 50, "Pink": 50,
             "Orange": 45, "Turquoise": 40, "Purple": 35},
    "AW20": {"Blue": 80, "Green": 66, "Red": 58, "Brown": 50, "Yellow": 45,
             "Orange": 42, "Pink": 40, "Purple": 30},
}

DEFAULT_FORECAST_CORE = 18      # neutrals are never a "trend bet"
DEFAULT_FORECAST_FASHION = 25   # un-hyped fashion color


def forecast_strength(season, color):
    s = FORECAST.get(season, {})
    if color in s:
        return s[color]
    return DEFAULT_FORECAST_CORE if is_core(color) else DEFAULT_FORECAST_FASHION


# --------------------------------------------------------------------------
# Realization multipliers - used ONLY by the mock generator to make forecast
# translate to sales imperfectly (hype traps < 1, sleepers/validated > 1), so
# the demo quadrant tells a real story. The adapter never sees these; the
# pattern emerges from the generated transactions.
# --------------------------------------------------------------------------

REALIZATION = {
    ("AW18", "Purple"): 0.66,   # Ultra Violet - the textbook hype trap
    ("SS19", "Purple"): 0.80,
    ("SS19", "Orange"): 1.24,   # Living Coral - validated
    ("AW19", "Orange"): 1.12,
    ("SS19", "Pink"): 1.10,
    ("AW18", "Red"): 1.14,
    ("AW19", "Green"): 1.20,    # sleeper building
    ("SS20", "Green"): 1.30,    # sleeper hit
    ("AW20", "Green"): 1.22,
    ("SS20", "Blue"): 1.12,     # Classic Blue - validated
    ("SS20", "Yellow"): 0.76,   # hype trap
    ("SS20", "Turquoise"): 0.80,
}
