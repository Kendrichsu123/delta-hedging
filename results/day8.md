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

### Matching the edge, not just the volatility

The reference vol here is the **mean 21-day window vol (22.39%)**, not the
full-sample vol (24.26%). Those are different numbers and using the wrong one
silently biases the comparison.

Full-sample vol is `sqrt(average variance)`. Mean window vol is
`average of sqrt(variance)`. Square root is concave, so **Jensen's inequality
makes the second strictly smaller**, and the gap grows with how dispersed the
window vols are — 1.9 points for AAPL, 3.4 points for SPY.

Selling 5 points above the *full-sample* figure therefore hands the real paths
more edge than the GBM control gets, because GBM realizes its sigma by
construction while the typical real window realizes less. On SPY that inflated
the real mean by 53%, which matched the variance-edge ratio of 1.539 almost
exactly — **the entire mean difference was the mismatch, not a property of real
returns.**

Both sides now sell 5 points above the same reference, so the only remaining
difference is the shape of the return distribution.

| | n | mean | std | P(loss) | skew | p5 |
|---|---:|---:|---:|---:|---:|---:|
| real, overlapping windows | 485 | 0.4766 | 0.9376 | **29.28%** | **−0.678** | −1.2037 |
| real, block bootstrap | 20,000 | 0.3802 | 0.9012 | **29.71%** | **−0.670** | −1.1664 |
| GBM (control) | 20,000 | 0.5761 | 0.5146 | 11.43% | **+0.253** | −0.1966 |

![real vs GBM](../figures/day8_real_vs_gbm.png)

**The skew flips sign on real data.** +0.25 under GBM, **−0.67** on real returns —
matched on volatility, matched on edge, matched on rebalancing frequency.

Days 5 and 6 predicted this by *adding features to the model*. Day 8 confirms it
by *removing the model*. Two routes, same conclusion.

The rest of the comparison:

- **P(loss) is 2.6× higher**, 11.4% → 29.7%
- **The mean is 34% LOWER**, 0.576 → 0.380, at the same edge. Fat tails cost real
  money: the big days cost more in gamma than the calm days save in theta.
- **Spread is 75% wider**, 0.51 → 0.90
- **The 5th percentile is 5.9× worse**, −0.20 → −1.17

The mean is the one to notice. Before the edge was matched properly, real returns
appeared to *outperform* the model. They do not — that was the bias. Corrected,
they underperform on every axis.

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

## Why AAPL, and why SPY would be better

**SPY is the right series for this project and AAPL is a substitute.** Three
reasons SPY wins:

1. **It is an index.** AAPL's return distribution is dominated by one company's
   news — eight earnings gaps sit inside this two-year sample. SPY's tails come
   from macro events, which is the risk a vol seller on an index actually faces.
2. **History.** A decade of SPY is ~2,500 days, about **120 independent months**
   against AAPL's 24. That is the difference between "the direction is negative"
   and "the magnitude is X."
3. **It matches vol-surface.** That project measured the SPY surface. Using SPY
   here would make the two repos describe the same instrument, and Day 6's FOMC
   analysis is already SPY-based.

**Why the AAPL file is what shipped:** the environment this was built in blocks
market-data hosts at the proxy — stooq returns 403, Yahoo is unreachable, and
five public dataset repositories carry only monthly index data. AAPL from a
public GitHub dataset was the only real *daily* equity series obtainable.

**Fixing it takes one command**, because the engine was separated from the path
generator (`hedge_paths` in `hedge.py` accepts any `(n_paths, N+1)` array):

```bash
python data/fetch_prices.py            # SPY, 10 years -> data/spy_daily.csv
```

then in `day8_real_paths.py`:

```python
CSV_PATH, CLOSE_COL = "data/spy_daily.csv", "Close"
```

Nothing else changes. **Expect the numbers to move**: SPY realizes roughly 15–18%
against AAPL's 24%, has fewer idiosyncratic gaps, and with 120 independent months
the vol-dispersion figure in §2 becomes a measurement rather than an
illustration. The *direction* of the skew result should survive — that is the
prediction to check.

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
