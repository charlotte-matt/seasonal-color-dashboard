"""
Populate data/hm_forecast.csv with a REAL Google Trends forecast axis, replacing
the hand-typed Pantone placeholders. Two methods:

  --method momentum   (default)  rising-interest: a color's search interest in the
                                 season vs. its OWN long-run average. Isolates trend
                                 *novelty* from baseline popularity. Scale-invariant
                                 (each color compared only to itself), so no anchor
                                 needed and the anchor-seasonality confound disappears.

  --method level                 absolute search interest, anchor-batched and rescaled
                                 so all colors share one scale. This is "popularity",
                                 which is dominated by neutrals - kept for A/B contrast.

Why the extra machinery (see README "forecast axis"):
  * fashion-qualified terms ("burgundy dress", not "burgundy")
  * a LEAD-UP window per season (hype measured before the sales it should predict)
  * Google normalizes each query to its own peak and caps at 5 terms - level mode
    anchor-batches to fix that; momentum mode dodges it via self-ratios.

Google has no official API, so this uses the unofficial `pytrends`, which rate-limits
(HTTP 429). Every response is cached, so re-runs resume from disk.

    pip install pytrends
    python3 fetch_trends.py                       # momentum, US, "<color> dress"
    python3 fetch_trends.py --method level         # popularity, for comparison
    python3 build_hm_data.py --data-dir data/hm    # rebuild dashboard with the result
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import time

import hm_config as C

HERE = os.path.dirname(os.path.abspath(__file__))

# Fashion-qualified term per color; overrides fix colors whose plain name is non-fashion.
TERM_OVERRIDE = {
    "Metal": "metallic", "Mole": "taupe", "Khaki green": "khaki",
    "Bluish Green": "teal", "Yellowish Green": "lime green", "Grey": "grey",
}

# Momentum mode averages each color's search interest across a BASKET of garments so the
# signal represents color demand across the assortment, not just one silhouette. US terms.
DEFAULT_GARMENTS = ["dress", "top", "shirt", "sweater", "jeans", "pants",
                    "skirt", "coat", "jacket", "heels", "sneakers", "bag"]


def term_for(color, qualifier):
    base = TERM_OVERRIDE.get(color, color.lower())
    return f"{base} {qualifier}".strip()


def season_start(code):
    yy = 2000 + int(code[2:])
    return dt.date(yy, 2, 1) if code.startswith("SS") else dt.date(yy, 8, 1)


def lead_window(code, lead_months):
    """The hype window: lead_months ending the day before the season starts."""
    start = season_start(code)
    m, y = start.month - lead_months, start.year
    while m <= 0:
        m += 12
        y -= 1
    return f"{dt.date(y, m, 1).isoformat()} {(start - dt.timedelta(days=1)).isoformat()}"


def color_list():
    return [c for c in C.COLOR_HEX if not C.is_excluded(c)]


def batches(terms, anchor, size=5):
    step = size - 1
    return [[anchor] + terms[i:i + step] for i in range(0, len(terms), step)]


def _cache_path(cache_dir, *parts):
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.md5("|".join(parts).encode()).hexdigest()  # stable across runs
    return os.path.join(cache_dir, f"{key}.json")


def _retry(fn, sleep, retries, what):
    last = None
    for attempt in range(retries):
        try:
            out = fn()
            time.sleep(sleep)
            return out
        except Exception as e:                       # 429s, parse errors, network
            last = e
            wait = sleep * (2 ** attempt)
            print(f"    retry {attempt+1}/{retries} ({type(e).__name__}); waiting {wait:.0f}s",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Google Trends failed for {what}: {last}")


# --------------------------------------------------------------------------
# Fetchers (cached)
# --------------------------------------------------------------------------

def fetch_means(pytrends, terms, timeframe, geo, cache_dir, sleep, retries):
    """Mean interest over a window for each term (level mode)."""
    cp = _cache_path(cache_dir, geo, timeframe, *terms)
    if os.path.exists(cp):
        return json.load(open(cp))

    def go():
        pytrends.build_payload(terms, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            return {t: 0.0 for t in terms}
        df = df.drop(columns=["isPartial"], errors="ignore")
        return {t: float(df[t].mean()) if t in df.columns else 0.0 for t in terms}

    means = _retry(go, sleep, retries, f"{terms}@{timeframe}")
    json.dump(means, open(cp, "w"))
    return means


def fetch_series(pytrends, term, timeframe, geo, cache_dir, sleep, retries):
    """Full date->value series for one term (momentum mode)."""
    cp = _cache_path(cache_dir, geo, timeframe, "series", term)
    if os.path.exists(cp):
        return json.load(open(cp))

    def go():
        pytrends.build_payload([term], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            return {}
        df = df.drop(columns=["isPartial"], errors="ignore")
        return {ix.strftime("%Y-%m-%d"): float(df[term].iloc[i]) for i, ix in enumerate(df.index)}

    series = _retry(go, sleep, retries, f"{term}@{timeframe}")
    json.dump(series, open(cp, "w"))
    return series


# --------------------------------------------------------------------------
# Methods -> rows
# --------------------------------------------------------------------------

def normalize_rows(per_season_signal, color_terms, method):
    """Per season, rescale so the top FASHION color = 100 (neutrals clamp)."""
    rows = []
    for sc, sig in per_season_signal.items():
        fashion = [v for c, v in sig.items() if not C.is_core(c)]
        top = (max(fashion) if any(fashion) else max(sig.values() or [1.0])) or 1.0
        for c, v in sig.items():
            rows.append({"season": sc, "color": c, "method": method,
                         "forecast_strength": min(100, int(round(100 * v / top))),
                         "search_term": color_terms[c], "raw_signal": round(v, 3)})
    return rows


def compute_level(pytrends, colors, color_terms, seasons, geo, anchor, lead_months,
                  sleep, retries, cache_dir):
    per_season = {}
    for sc in seasons:
        tf = lead_window(sc, lead_months)
        print(f"{sc} (level): window {tf}", file=sys.stderr)
        rel = {}
        for batch in batches([color_terms[c] for c in colors], anchor):
            means = fetch_means(pytrends, batch, tf, geo, cache_dir, sleep, retries)
            a = means.get(anchor, 0.0)
            if a <= 0:
                print(f"    WARN anchor '{anchor}' had no volume; batch skipped", file=sys.stderr)
                continue
            for c in colors:
                if color_terms[c] in batch:
                    rel[c] = means.get(color_terms[c], 0.0) / a
        if not rel:
            sys.exit(f"No usable Trends data for {sc} - aborting.")
        per_season[sc] = rel
    return normalize_rows(per_season, color_terms, "level")


def compute_top_garment(pytrends, colors, bases, garments, span, geo, sleep, retries, cache_dir):
    """Per color, the ONE garment it was searched for most (by volume) over the span.

    Trends self-normalizes each series to its own max, so per-garment momentum series are
    NOT comparable across garments. To rank garments for a color we put them on one scale:
    anchor-batch them against that color's own 'dress' term and compare each garment's mean
    interest to dress. Returns ({color: "<base> <top garment>"}, {color: {garment: rel-volume}})
    — the terms drive the 'Searched as' column, the volumes let the dashboard re-pick the top
    garment for any category subset.
    """
    top, vols = {}, {}
    for c in colors:
        base = bases[c]
        anchor = f"{base} dress"
        others = [g for g in garments if g != "dress"]
        rel = {"dress": 1.0}                       # everything measured relative to dress
        for i in range(0, len(others), 4):         # anchor + 4 = 5 terms per Trends batch
            batch_g = others[i:i + 4]
            terms = [anchor] + [f"{base} {g}" for g in batch_g]
            try:
                means = fetch_means(pytrends, terms, span, geo, cache_dir, sleep, retries)
            except Exception as e:
                print(f"    skip garment batch for {c}: {type(e).__name__}", file=sys.stderr)
                continue
            a = means.get(anchor, 0.0)
            if a <= 0:
                continue
            for g in batch_g:
                rel[g] = means.get(f"{base} {g}", 0.0) / a
        vols[c] = {g: round(v, 4) for g, v in rel.items()}
        best = max(rel, key=rel.get)
        top[c] = f"{base} {best}"
        print(f"  {c}: most searched as '{top[c]}'", file=sys.stderr)
    return top, vols


def compute_momentum(pytrends, colors, bases, garments, color_terms, seasons, geo,
                     lead_months, sleep, retries, cache_dir):
    """Momentum averaged across a BASKET of garments.

    For each color x garment we fetch the color's own search series ("<color> <garment>"),
    measure how far the season's lead-up window sits above that series' own long-run average
    (a unitless momentum ratio, scale-invariant per garment), then average those ratios
    across garments. Garments with no real volume for a color are skipped so they don't add
    noise; a single failing term is skipped rather than aborting the whole run.
    """
    windows = {sc: lead_window(sc, lead_months).split() for sc in seasons}
    span_lo = min(w[0] for w in windows.values())
    span_hi = max(w[1] for w in windows.values())
    span = f"{span_lo} {span_hi}"
    print(f"momentum: {len(colors)} colors x {len(garments)} garments over {span}",
          file=sys.stderr)
    MIN_OVERALL = 2.0  # normalized-scale floor below which a color+garment has no real signal

    per_season = {sc: {} for sc in seasons}
    detail = {sc: {} for sc in seasons}   # detail[season][color][garment] = momentum ratio
    for c in colors:
        ratios = {sc: [] for sc in seasons}
        pg = {sc: {} for sc in seasons}   # per-garment ratio for this color, this season
        used = []
        for g in garments:
            term = f"{bases[c]} {g}".strip()
            try:
                s = fetch_series(pytrends, term, span, geo, cache_dir, sleep, retries)
            except Exception as e:
                print(f"    skip '{term}': {type(e).__name__}", file=sys.stderr)
                continue
            vals = list(s.values())
            overall = (sum(vals) / len(vals)) if vals else 0.0
            if overall < MIN_OVERALL:
                continue                       # too little search volume for this pairing
            used.append(g)
            for sc in seasons:
                w0, w1 = windows[sc]
                wv = [v for d, v in s.items() if w0 <= d <= w1]
                wmean = (sum(wv) / len(wv)) if wv else 0.0
                r = wmean / overall
                ratios[sc].append(r)
                pg[sc][g] = round(r, 4)
        for sc in seasons:
            rs = ratios[sc]
            per_season[sc][c] = (sum(rs) / len(rs)) if rs else 0.0
            detail[sc][c] = pg[sc]
        print(f"  {c}: {len(used)}/{len(garments)} garments [{', '.join(used)}]",
              file=sys.stderr)
    return normalize_rows(per_season, color_terms, "momentum"), detail


# --------------------------------------------------------------------------

def build(method, geo, qualifier, garments, anchor, lead_months, sleep, retries,
          cache_dir, out_path):
    try:
        from pytrends.request import TrendReq
    except ImportError:
        sys.exit("pytrends not installed. Run:  pip install pytrends")

    pytrends = TrendReq(hl="en-US", tz=0)
    colors = color_list()
    seasons = sorted(C.SEASON_META.keys(), key=C.season_sort_key)
    bases = {c: TERM_OVERRIDE.get(c, c.lower()) for c in colors}

    detail_out = None
    if method == "level":
        color_terms = {c: term_for(c, qualifier) for c in colors}
        rows = compute_level(pytrends, colors, color_terms, seasons, geo, anchor,
                             lead_months, sleep, retries, cache_dir)
    else:
        # "Searched as" column = each color's single most-searched garment (interest score
        # itself is still the basket average). Ranked on one scale by compute_top_garment.
        windows = {sc: lead_window(sc, lead_months).split() for sc in seasons}
        span = f"{min(w[0] for w in windows.values())} {max(w[1] for w in windows.values())}"
        print("ranking garments per color for the 'Searched as' label...", file=sys.stderr)
        color_terms, volumes = compute_top_garment(pytrends, colors, bases, garments, span,
                                                    geo, sleep, retries, cache_dir)
        rows, momentum_detail = compute_momentum(pytrends, colors, bases, garments,
                                                 color_terms, seasons, geo, lead_months,
                                                 sleep, retries, cache_dir)
        # per-garment detail lets the dashboard recompute interest for any category subset
        # (core = neutral colors, needed so the dashboard normalizes against the top FASHION
        # color even for colors later dropped from the sales side)
        detail_out = {"garments": garments, "bases": bases,
                      "core": [c for c in colors if C.is_core(c)],
                      "momentum": momentum_detail, "volume": volumes}

    if os.path.exists(out_path):
        bak = out_path.replace(".csv", ".backup.csv")
        os.replace(out_path, bak)
        print(f"Backed up previous forecast -> {bak}", file=sys.stderr)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["season", "color", "forecast_strength",
                                          "search_term", "method", "raw_signal"])
        w.writeheader()
        w.writerows(rows)

    if detail_out is not None:
        detail_path = out_path.replace(".csv", "_detail.json")
        with open(detail_path, "w") as f:
            json.dump(detail_out, f)
        print(f"Wrote per-garment detail -> {detail_path}", file=sys.stderr)

    print(f"\nWrote {len(rows)} rows to {out_path}  (method: {method})")
    print("Top forecasted FASHION colors per season:")
    for sc in seasons:
        sr = sorted([r for r in rows if r["season"] == sc and not C.is_core(r["color"])],
                    key=lambda r: -r["forecast_strength"])
        print(f"  {sc}: " + ", ".join(f"{r['color']} {r['forecast_strength']}" for r in sr[:4]))
    print("\nNext:  python3 build_hm_data.py --data-dir data/hm")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch a Google Trends color forecast -> hm_forecast.csv")
    ap.add_argument("--method", choices=["momentum", "level"], default="momentum",
                    help="momentum = rising interest vs own norm (default); level = raw popularity")
    ap.add_argument("--geo", default="US", help="Region (US, GB, '' = worldwide). "
                    "US default: worldwide dilutes non-English markets to ~0")
    ap.add_argument("--qualifier", default="dress", help="Single garment term (level mode only)")
    ap.add_argument("--garments", default=",".join(DEFAULT_GARMENTS),
                    help="Comma-separated garment basket averaged over (momentum mode)")
    ap.add_argument("--anchor", default="maxi dress", help="Bridge term (level mode only)")
    ap.add_argument("--lead-months", type=int, default=6, help="Hype window length before season")
    ap.add_argument("--sleep", type=float, default=5.0, help="Seconds between requests")
    ap.add_argument("--retries", type=int, default=4, help="Retries with backoff per request")
    ap.add_argument("--cache", default=os.path.join(HERE, "data", "trends_cache"))
    ap.add_argument("--out", default=os.path.join(HERE, "data", "hm_forecast.csv"))
    a = ap.parse_args()
    garments = [g.strip() for g in a.garments.split(",") if g.strip()]
    build(a.method, a.geo, a.qualifier, garments, a.anchor, a.lead_months, a.sleep,
          a.retries, a.cache, a.out)
