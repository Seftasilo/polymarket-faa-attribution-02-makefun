# FAA Outage Attribution Forecaster — make.fun entry

Forecasts the Yes price of every market of Polymarket's FAA outage
attribution family at every minute of the 4 hours after a checkpoint, as five
quantiles (0.05, 0.25, 0.5, 0.75, 0.95), for the lowest mean pinball loss.

Competition: `polymarket-faa-attribution-02` ($250, 100 places).

## Run

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network. Reads every `*.in` in the
input directory and writes `<id>.out` per case. Deterministic: two runs on the
same case write identical bytes. One case runs in well under a second.

## Method

See the header comment in `main.py`. In short:

- **Median = last price.** Prediction-market prices are near-martingales;
  every drift estimate tried (last-hour / last-4h trend, shrunk or not) made
  the practice loss worse.
- **Spread from the market's own history, robustly.** At sampled horizons
  (5, 15, 30, 60, 120, 240 minutes) sigma is the IQR of h-step price changes
  / 1.349 — the IQR, not the standard deviation, so rare jumps don't blow up
  the band. The last 6h and last 12h estimates are averaged, scaled by 0.9,
  interpolated in log h, with a floor of 0.0005·√h so a flat market never gets
  a zero-width band.
- Quantiles are normal quantiles around the last price, clamped to [0, 1],
  rounded to 6 decimals.

## Local practice score

Scored locally on the kit's six practice cases (NVIDIA CEO event; the next
case's prices as ground truth, p05 fetched from Polymarket's public CLOB
history):

| entry | pinball loss | median error | 90% coverage |
|---|---|---|---|
| house baseline | 0.363589 | 0.7675 | 0.9496 |
| **this entry** | **0.2902** | 0.7675 | 0.9114 |

The practice is another event's instance, so it is no guide to the final;
the choices above are the robust ones, not the practice-optimal point.

## Files

- `main.py` — the entry (the only file the grader runs)
- `README.md` — this file
- `LICENSE` — MIT (SPDX-License-Identifier: MIT)
- `.makefun/owner.json` — payout wallet claim file
