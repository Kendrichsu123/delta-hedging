# Day 8 — Real price paths

Reproduce with `python day8_real_paths.py` (~30s).

Data: `data/aapl_daily.csv`, 506 adjusted daily closes, Feb 2015 – Feb 2017.

---

## Read this before the results

**The sample is small.** 506 days, 21-day windows, **about 24 independent
months.** Every number below has an effective sample size in the tens. This day
is a *check* on the conclusions of Days 1–7, not a source of new ones.

**And it cannot attribute anything.** Real paths carry fat tails, volatility
clustering, and gaps for free, without any of them being modelled — that is the
appeal. It is also why Day 6 came first: Day 6 changed *one* thing and could
therefore say *this feature causes that effect*. Day 8 changes everything at once
and can only say *reality differs, by this much*.

That ordering is deliberate. Real data is the last step, not the first.

---

## 1. What real returns have that GBM does not

```
annualized vol                      0.2426
daily return skew                   -0.192
daily return kurtosis                6.117   (normal = 3.000)
days with |move| > 4 sd                  4   (normal expects ~0.03)
vol clustering corr(|r_t|,|r_t-1|) +0.1388
  same for iid normal              -0.0503
```

**Kurtosis 6.1 against 3.0.** Four days moved more than 4 standard deviations in
two years; a normal distribution expects 0.03 such days. And volatility clusters —
big moves follow big moves, which GBM forbids by construction.

---

## 2. The loop back to Day 2

Day 2 swept a realized-vol forecast error `s` from 0 to 5 vol points **as an
assumption**, finding P(loss) went 2.0% → 16.1%. Real data prices that sweep.

Distribution of 21-day annualized realized vol:

| | mean | std | p5 | p95 |
|---|---:|---:|---:|---:|
| real | 0.2239 | **0.0804** | 0.1050 | 0.3956 |
| GBM, same average | 0.2329 | **0.0366** | 0.1752 | 0.2980 |

![vol dispersion](../figures/day8_vol_dispersion.png)

**Real 21-day realized vol has a standard deviation of 8.0 vol points. GBM with
the same average gives 3.7. A ratio of 2.2×.**

So **Day 2's harshest assumed scenario — s = 5 points — was still optimistic.**
The month-to-month spread of realized vol *by itself* is 8 points here, before any
forecasting error is layered on top. Day 2 guessed at a parameter; this measures
it, and the guess was too kind.

*(Caveats: the windows overlap heavily, which inflates the apparent sample. And
AAPL is a single name — more volatile and more dispersed than an index would be.)*

---

## 3. Hedging real paths

Sell at 29.26% (5 vol points above the full-sample realized 24.26%), hedge once
per trading day (N=21). **GBM is matched to the same volatility**, so the only
difference is the *shape* of the return distribution.

| | n | mean | std | P(loss) | skew | p5 |
|---|---:|---:|---:|---:|---:|---:|
| real, overlapping windows | 485 | 0.6870 | 0.9427 | **22.27%** | **−0.564** | −1.0128 |
| real, block bootstrap | 20,000 | 0.5980 | 0.9034 | **23.71%** | **−0.529** | −0.9198 |
| GBM (control) | 20,000 | 0.5764 | 0.5526 | 13.16% | **+0.233** | −0.2577 |

![real vs GBM](../figures/day8_real_vs_gbm.png)

**The skew flips sign on real data.** +0.23 under GBM, **−0.53** on real returns —
matched on volatility, matched on edge, matched on rebalancing frequency.

Days 5 and 6 predicted this by *adding features to the model*. Day 8 confirms it
by *removing the model*. Two routes, same conclusion.

The rest of the comparison:

- **P(loss) nearly doubles**, 13.2% → 23.7%
- **Spread is 63% wider**, 0.55 → 0.90, at identical volatility
- **The 5th percentile is 3.6× worse**, −0.26 → −0.92

That last one is the practical statement. At the same volatility and the same
edge, your bad month is nearly four times worse than the model says.

### Why the block bootstrap, and not an ordinary one

Resampling *individual days* would destroy volatility clustering — it would
rebuild something close to GBM out of real returns, which is the opposite of the
point. Blocks of 5 consecutive days preserve the local structure.

It still does not add information: 20,000 paths resampled from the same two years
inherit that period's regime. It widens the sample without deepening it, which is
why the overlapping-window row is reported alongside it and lands in the same
place.

---

## What this establishes, and what it does not

**Establishes:** the sign flip in skew is real, not an artifact of the jump model.
Reached independently of Days 5 and 6, on data with no fitted parameters.

**Does not establish:** any magnitude. 24 independent months, one ticker, one
two-year regime. The −0.53 should be read as "negative, order of a half," never
as a measurement.

**Cannot establish:** *why*. Fat tails, clustering, and earnings gaps all arrived
together. Day 6's controlled experiment is what identifies the mechanism; this
only confirms the direction.

---

## Running it on your own data

The engine is separated from the path generator (`hedge_paths` in `hedge.py`
takes any `(n_paths, N+1)` array), so pointing this at a better series is a
two-line change:

```python
CSV_PATH, CLOSE_COL = "data/spy_daily.csv", "Close"
```

**SPY over a decade would be strictly better** — 2,500 days gives ~120 independent
months instead of 24, an index rather than a single name, and it would connect
directly to the vol-surface work. The market-data hosts were unreachable from the
environment this was built in; the AAPL file came from a public GitHub dataset.
If you fetch SPY locally, everything here reruns unchanged.

---

## Caveats

**One ticker, one regime.** Feb 2015 – Feb 2017 contains the Aug 2015 selloff and
the 2016 recovery. A different two years would give different numbers.

**AAPL has earnings gaps**, which is realistic and also means roughly 8 scheduled
jumps sit inside this sample. That is arguably a feature — it is Day 6's setup
occurring naturally — but it is not controlled.

**Overlapping windows are not independent observations.** The n=485 row is 485
*windows* over 24 months of information. Its agreement with the block bootstrap is
reassuring but not independent confirmation.

**The GBM control uses the full-sample vol**, so it cannot reproduce the
month-to-month vol dispersion in §2 even in principle. That is the point of the
comparison, but it means the two columns differ in more than one way.
