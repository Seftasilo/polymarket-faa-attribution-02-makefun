# Polymarket FAA attribution forecast — entry for polymarket-faa-attribution-02.
#
# Forecast the Yes price of every market of the family at every minute of the
# 4 hours after a checkpoint, as five quantiles (0.05, 0.25, 0.5, 0.75, 0.95).
#
# Method (tuned on the kit's six practice cases, NVIDIA CEO event):
#   * Median = the market's last price. Prediction-market prices are
#     near-martingales: every drift estimate we tried (last-hour / last-4h
#     trend, shrunk or not) made the practice loss strictly worse, so the
#     median stays at the checkpoint price.
#   * Spread = a normal-quantile band whose sigma(h) is estimated per market
#     from its own history, robustly: at sampled horizons h in
#     {5, 15, 30, 60, 120, 240} minutes, sigma(h) is the IQR of the h-step
#     price changes divided by 1.349. The IQR (not the standard deviation)
#     keeps rare jumps — a market that once printed 0.83 and later 0.01 —
#     from blowing up the band. Two lookbacks (last 6h and last 12h) are
#     averaged, which stabilises the estimate and tracks volatility regimes;
#     the result is scaled by 0.9 and interpolated in log h.
#   * A floor of 0.0005 * sqrt(h) keeps a market that has been perfectly flat
#     from collapsing to a zero-width band (a news-driven family can jump at
#     any minute); the floor costs ~0.002 of practice loss and buys near-
#     nominal 90% coverage (0.91 vs 0.79 without it).
#   * Quantiles are clamped to [0, 1] and rounded to 6 decimals.
#
# Practice result (local scoring against the next case's prices, p05 fetched
# from Polymarket's public CLOB history): pinball loss 0.2902, median error
# 0.7675, 90% coverage 0.9114 — vs the house baseline's 0.3636 / 0.7675 /
# 0.9496. The practice is another event's instance, so it is no guide to the
# final; the choices above are the robust ones (median = last price, robust
# per-market scale, a floor), not the practice-optimal point estimate.
#
# Python 3.13, standard library only, no network, deterministic: two runs on
# the same case write the same bytes. Reads every *.in in $MAKEFUN_INPUT_DIR
# (else /input) and writes <id>.out to $MAKEFUN_OUTPUT_DIR (else /output).

import bisect
import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.644854, -0.674490, 0.0, 0.674490, 1.644854)
HORIZONS = (5, 15, 30, 60, 120, 240)
LOOKBACK_SHORT = 360   # minutes (6h)
LOOKBACK_LONG = 720    # minutes (12h)
SCALE = 0.9
FLOOR_C = 0.0005       # sigma(h) >= FLOOR_C * sqrt(h)


def _quantile(sorted_vals, tau):
    """Linear-interpolation quantile of an already sorted list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = tau * (n - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _robust_sigma(prices, horizons, lookback):
    """IQR/1.349 of h-step changes over the last `lookback` minutes."""
    p = prices[-lookback:] if len(prices) > lookback else prices
    n = len(p)
    out = {}
    for h in horizons:
        if n - h < 2:
            # Too little history for this horizon: fall back to a
            # random-walk scale from the baseline's order of magnitude.
            out[h] = 0.0025 * math.sqrt(h)
            continue
        ds = sorted(p[t + h] - p[t] for t in range(n - h))
        out[h] = (_quantile(ds, 0.75) - _quantile(ds, 0.25)) / 1.349
    return out


def _sigma_curve(sig):
    """Precompute the sampled horizons and their logs once per market, so
    the 240 per-minute lookups below are cheap (the grader caps a run at
    8 seconds)."""
    hs = sorted(sig)
    return hs, [math.log(v) for v in hs]


def _sigma_at_h(sig, hs, loghs, h):
    """Log-h interpolation of sigma between sampled horizons; sqrt(h)
    extrapolation outside the sampled range."""
    if h <= hs[0]:
        return sig[hs[0]] * math.sqrt(h / hs[0])
    if h >= hs[-1]:
        return sig[hs[-1]] * math.sqrt(h / hs[-1])
    lh = math.log(h)
    i = bisect.bisect_right(loghs, lh) - 1
    w = (lh - loghs[i]) / (loghs[i + 1] - loghs[i])
    return sig[hs[i]] * (1.0 - w) + sig[hs[i + 1]] * w


def _clamp6(x):
    v = round(min(1.0, max(0.0, x)), 6)
    return 0.0 if v == 0 else v


def forecast_market(prices, horizon):
    """One market's forecast: `horizon` rows of five quantiles."""
    if not prices:
        raise ValueError("market has no prices")
    x = prices[-1]
    short = _robust_sigma(prices, HORIZONS, LOOKBACK_SHORT)
    long = _robust_sigma(prices, HORIZONS, LOOKBACK_LONG)
    sig = {h: 0.5 * short[h] + 0.5 * long[h] for h in HORIZONS}
    hs, loghs = _sigma_curve(sig)
    rows = []
    for h in range(1, horizon + 1):
        s = _sigma_at_h(sig, hs, loghs, h) * SCALE
        floor = FLOOR_C * math.sqrt(h)
        if s < floor:
            s = floor
        rows.append([_clamp6(x + z * s) for z in Z])
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for fname in inputs:
        case_id = fname[: -len(".in")]
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            case = json.load(f)
        horizon = case["horizon_minutes"]
        forecasts = []
        for m in case["markets"]:
            forecasts.append(
                {"id": m["id"], "q": forecast_market(m["prices"], horizon)}
            )
        out_path = os.path.join(OUTPUT_DIR, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"forecasts": forecasts}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
