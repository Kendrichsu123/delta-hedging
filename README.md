# Delta-Hedging P&L Simulation

What it actually looks like to sell volatility and hedge it.

A previous project ([vol-surface](https://github.com/Kendrichsu123/vol-surface))
measured what the options market *charges* for risk. This one measures what
*earning* that premium looks like: sell an option at implied vol, delta-hedge it
at discrete intervals, and study the distribution of what you end up with.

---

## The headline

> The standard delta-hedging model, implemented correctly and validated against
> every closed form the literature offers, implies that selling volatility is
> **riskless in the continuous limit** and **positively skewed** at realistic
> hedging frequencies. Both conclusions are false about the real world.
>
> This project localizes the discrepancy to two assumptions and quantifies the
> first: relaxing perfect volatility knowledge to a realistic 3-point forecast
> error **flips the skew from +0.40 to −0.01** while barely moving the mean.

Worst outcome out of 40,000 simulated trades, as rebalancing gets finer:

```
     N   worst of 40k   P(loss)     skew
     4        -5.0076    0.2084   -0.274
    30        -0.9659    0.0200   +0.418
   128        -0.0969    0.0000   +0.375
   512        +0.0740    0.0000   +0.121
  2048        +0.0922    0.0000   -0.009
```

**Zero losses in 40,000 trades** at fine rebalancing. That is what the model
says, and it is not a bug — `P&L = ½(σᵢ²−σᵣ²)·∫S²Γdt`, and when σᵢ > σᵣ every
factor is positive, so no path can lose. The interesting question is what the
world has that this model doesn't.

---

## The trade

You sell an option and collect a premium set by **implied volatility**. The
stock then moves by some amount — its **realized volatility**. Delta hedging
strips out the directional bet and leaves a pure wager on implied vs. realized.

The mechanism is a tug-of-war:

- Selling an option makes you **short gamma**. Every rebalance forces you to buy
  after the stock rises and sell after it falls. The loss on a move of size `h`
  is `½Γh²` — quadratic in the move, identical up or down.
- Selling an option also makes you **collect theta**, a fixed amount per day
  regardless of what the stock does.

Fixed income against quadratic cost. Solve for the move size where they cancel,
and the answer is the implied vol you sold at:

```
theta over 2 days      = 0.07753
Gamma at 100           = 0.06955
solve  Γ·(ΔS)² = θ     →  ΔS = 1.056%  daily
annualized (365d)      =  20.17%   ≈  the 20% we sold at
```

That is the whole thesis, in arithmetic. See [`docs/intuition.md`](docs/intuition.md).

---

## The arc

Each day answers one decision. Full writeups in [`results/`](results/).

### [Day 1](test_day1.py) — Can any number this produces be trusted?

56 checks against closed forms and arbitrage identities before any analysis.
The headline test: sell at exactly the vol the stock realizes, and P&L must
collapse to zero.

Three deliberately introduced bugs — a sign flip, a look-ahead, a missing
settlement — all returned ≈ +2.28 (the option premium) against a required 0.000,
and **all three produced smooth, plausible histograms.** That is the argument for
validating against closed forms rather than eyeballing distributions.

### [Day 2](results/day2.md) — How much edge do you need?

At a 5-point edge with daily hedging: mean +0.5703, **P(loss) 1.97%** [1.88%,
2.05%]. Confidence intervals are percentile bootstrap, since the distribution is
skewed and the textbook formulas assume normality.

- **P(loss) is violently nonlinear in edge:** halving it from 5.0 to 2.5 vol
  points takes the loss rate from 2.0% to 17.5%
- **Mean is linear in edge, spread is flat** → reward/risk ≈ **0.35 per vol point**
- **Rebalancing creates no edge.** At zero edge, P(loss) stays ~50% from N=8 to
  N=512. It is a risk lever, never a return lever.

Crossing edge with forecast error gives the actual decision table:

```
 edge you think |      s=0pt     s=2pt     s=3pt     s=4pt
          2.5pt |     17.4%     20.0%     25.8%     30.2%
          5.0pt |      2.0%      6.9%     10.7%     13.5%
          7.0pt |      0.1%      1.3%      4.0%      7.7%
```

**With a realistic 3-point vol forecast error you need ~7 vol points of edge to
get the loss rate under 5%.** Not 2, not 3.

### [Day 3](results/day3.md) — How much risk can rebalancing remove?

Fits `var(N) = a + b/N` to separate removable discretization noise from an
irreducible floor.

```
hedge at realized vol:  a = +0.00004283   (theory: exactly 0)
hedge at implied vol:   a = +0.03373052   floor std 0.18366
```

The control returning zero is what licenses believing the other number. And the
floor is **identified, not just measured**: extrapolating the fit gives 0.033731;
measuring `var(½(σᵢ²−σᵣ²)∫S²Γdt)` directly at N=2048 gives 0.033828 — **two
routes sharing no arithmetic, agreeing to 0.3%.**

Documents a **regression-leverage trap** rather than hiding it: plotting against
1/N puts one point at x=1 and the rest below 0.5, giving N=1 a leverage of
**0.7777**. Fitting all points reads 0.22638; restricting to the asymptotic
region reads 0.18304 — a 24% swing from one observation, which is also where the
model is least valid.

Practically: at N=64 the position is already half irreducible risk; at N=256 it
is 80%. Since costs grow like √N while this noise falls like 1/√N, trading past
that is value-destroying.

### [Day 4](results/day4.md) — Where does the money physically come from?

`P&L = ½(σᵢ²−σᵣ²)·∫S²Γdt` holds **path by path**, not just on average —
correlation 0.9889 at N=2048, explaining 98% of cross-path variation.

The negative result is sharper:

```
corr(P&L, terminal price)             -0.0238
corr(P&L, path's OWN realized vol)    -0.2092
corr(P&L, dollar-gamma integral)      +0.9774
```

Neither where the stock ended nor how much it moved predicts your P&L. Two paths
that finished at the same price: one stayed near the strike 99.9% of the time and
made **+1.1219**; the other was near it 58% of the time, **realized more
volatility**, and made **+0.4859**.

**Being right about volatility is necessary but not sufficient.**

### [Day 5](results/day5.md) — Is the distribution lopsided?

Skew against rebalancing frequency, with bootstrap CIs. It is **non-monotonic**:
−0.98 at N=1, crossing zero near **N=8**, peaking at **+0.44 at N=64**, decaying
to +0.04 by N=1024. Both features are many CI-widths wide.

**A single measurement at one N would have supported almost any story.**

The mechanism is a cross term, and an earlier version of this analysis got it
wrong. Both components are *negatively* skewed at every N, yet the sum is
positive, because skewness is not additive:

```
E[(a+b)³] = E[a³] + 3E[a²b] + 3E[ab²] + E[b³]
```

`3E[ab²]` dominates by an order of magnitude. It is the covariance between where
the stock went and how big the hedging noise was — structurally linked, since the
per-step noise is proportional to the same `S²Γ` being accumulated.
`corr(gamma term, squared noise) = +0.331`.

### [Day 6](results/day6.md) — What a scheduled jump does

Adds a gap at a known time of unknown size, **priced correctly** so the edge is
held constant and only the jump's presence differs.

```
   N |  no jump: P(loss)  skew  |  with jump: P(loss)  skew
   8 |            13.32%  +0.02 |              20.25%  -0.80
  30 |             1.97%  +0.42 |              13.94%  -1.14
 128 |             0.01%  +0.37 |              12.39%  -1.48
2048 |             0.00%  -0.02 |              12.17%  -1.60
```

**P(loss) stops going to zero.** It plateaus at 12.2% and rebalancing 2,048 times
instead of 128 buys nothing — you cannot rebalance through a gap. The means are
identical: fair compensation buys the right *mean*, never a shape you can't hedge.

The same event is worth **13.7 vol points on a 1-day option and 0.03 on a
2-year**, because a jump adds `σ_J²` regardless of tenor while diffusion adds
`σ²T`. That predicts vol-surface's measured 5–7 point front-expiry collapse at a
2–4 day expiry, and says the 0.3 seen at 2 years was *not* the event — the same
inference, reached from the opposite direction.

**The FOMC trade.** Selling the July 2026 announcement at the measured ±0.95%
premium, against SPY's actual −0.67%:

| | 0.95% as std | 0.95% as E\|move\| |
|---|---:|---:|
| break-even move | ±0.856% | ±1.046% |
| P&L | +16.3% of premium | +29.2% of premium |
| ex-ante P(profit) | 0.631 | 0.620 |

It paid under both readings — and it was a **62/38 proposition, n=1**. The
defensible claim is "the priced premium exceeded the realized move on this
occasion," not "selling FOMC events is profitable."

### [Day 7](results/day7.md) — Transaction costs and optimal N

Costs grow like √N while hedging noise falls like 1/√N, so there is a genuine
interior optimum — the cost-free case had none.

```
   N |  0bp mean   1bp mean   5bp mean
   8 |    0.5716     0.5544     0.4857
 128 |    0.5711     0.5301     0.3661
2048 |    0.5724     0.4385    -0.0972   <- a real edge, traded away entirely
```

**Optimal N under `U = mean − (λ/2)·var`:**

| cost | λ=0.5 | λ=2 | λ=10 |
|---:|---:|---:|---:|
| 0.0bp | 512 | 2048 | 2048 |
| 1.0bp | 64 | 128 | 512 |
| 5.0bp | 16 | 64 | 256 |

The zero-cost row is the control: with no costs the optimum is always the largest
N, so **costs are what create an optimum at all**.

**Impact on earlier results:** Day 2 survives almost intact — at daily hedging
P(loss) goes 1.99% → 2.53% at 1bp and the ~5 vol point threshold is unchanged.
**Day 6 gets sharper**: with costs, the jump case bottoms at 13.39% (N=128) and
*rises* to 14.42% (N=2048). Hedging harder against a gap goes from useless to
actively value-destroying.

### [Day 8](results/day8.md) — Real price paths

The first day that touches market data. **SPY, 2,513 daily closes, Aug 2016 –
Aug 2026** (~119 independent months).

Selling 5 vol points above the mean 21-day realized vol, hedged daily, with GBM
matched to that same reference so only the return *shape* differs:

```
                 mean   P(loss)     skew        p5
real returns   0.3144    21.81%   -4.165   -1.3228
GBM (control)  0.5751     3.69%   +0.321   +0.0385
```

**GBM's 5th percentile is positive** — the model says 95% of months make money.
Reality says 22% lose, and the 5th percentile is −1.32, more than twice the
average profit. At identical edge the real mean is **45% lower**: fat tails cost
more in gamma on the violent days than the calm days save in theta.

**The result strengthens on an index.** AAPL gave skew −0.67; SPY gives **−4.17**.
That matters because three of AAPL's four 4-sigma days were earnings — scheduled
jumps, Day 6's setup occurring naturally. SPY has no earnings, twenty 4-sigma
days, kurtosis 18.3, and a six times stronger effect. **So the skew flip is fat
tails and volatility clustering, not scheduled events** — a claim AAPL alone
could not support.

It also prices a Day 2 assumption. Day 2 swept a forecast error of 0–5 vol points;
real 21-day realized vol has a standard deviation of **10.0 points** against GBM's
2.7, spanning 5.9% to 28.6% between the 5th and 95th percentile. **Day 2's
harshest assumed scenario was optimistic by half.**

What it still cannot do is attribute — fat tails, clustering and gaps arrive
together, which is why Day 6's controlled experiment came first and this comes
last.

---

## What is validated, and what is assumed

**Reproduces every closed form available** (Boyle–Emanuel 1980, Ahmad–Wilmott
2005):

| result | measured | theory |
|---|---|---|
| mean P&L = BS(σᵢ) − BS(σᵣ) | 0.571613 | 0.571685 |
| hedging error ∝ 1/√N | slope −0.4923 | −0.5 |
| hedging at realized vol is deterministic | floor 0.000043 | 0 |
| P&L = ½(σᵢ²−σᵣ²)∫S²Γdt, per path | corr 0.9889 | 1 |
| break-even daily move = implied vol | 20.17% | 20.00% |

**Assumes, and these are load-bearing:**

1. **Realized vol is a known constant.** Tested in isolation — relaxing it to a
   3-point forecast error flips the skew sign and takes P(loss) 2.0% → 8.9%.
2. **The stock moves continuously, with no gaps.** Tested in Day 6 — a scheduled
   jump puts a floor of 12.2% under P(loss) that no amount of rebalancing lifts,
   and drives the skew to −1.60.

**Days 1–7 never touched real market data** — every path there is simulated GBM.
Day 8 uses SPY over a decade and confirms the skew sign flip independently:
**−4.17 on real returns against +0.32 on volatility-matched GBM**, with P(loss)
5.9× higher at identical edge. Its sample is ~119 independent months spanning one
particular decade, so it establishes direction and rough magnitude, not a
stationary constant.

---

## Layout

```
bs.py                     Black-Scholes pricing, Greeks, implied vol, dollar gamma
paths.py                  GBM path simulation (exact log-Euler), realized vol
hedge.py                  the hedging engine + closed-form predictions
test_day1.py              56 validation checks
explore.py                interactive VS Code cells, walk through it yourself
day2_distribution.py      P&L distribution, edge sweep, vol-uncertainty
day3_convergence.py       N-sweep, var = a + b/N, leverage analysis
day4_path_dependence.py   dollar gamma, what predicts P&L and what doesn't
day5_skew.py              skew vs N with bootstrap, third-moment decomposition
day6_jump.py              scheduled jump at a known time, priced to hold edge fixed
day7_costs.py             proportional costs, the √N/1/√N tension, optimal N
day8_real_paths.py        the engine on real SPY returns, against a matched GBM control
data/fetch_prices.py      fetches a daily close series for Day 8
docs/intuition.md         the whole trade in arithmetic, no calculus
docs/exercises.md         predict-then-run exercises with an answer key
docs/corrections.md       every claim that was revised, and what triggered it
docs/story.md             the narrative: how each answer created the next question
results/                  per-day writeups with figures
figures/                  generated charts
```

## Running it

```bash
pip install -r requirements.txt
python test_day1.py          # 56 checks, ~1 min
python day2_distribution.py  # ~75s
python day3_convergence.py   # ~75s
python day4_path_dependence.py
python day5_skew.py          # ~3 min
python day6_jump.py          # ~2 min
python day7_costs.py         # ~6 min
python data/fetch_prices.py  # builds data/spy_daily.csv (needs network)
python day8_real_paths.py    # ~30s
```

New here? Read [`docs/intuition.md`](docs/intuition.md), then work
[`explore.py`](explore.py) cell by cell, then
[`docs/exercises.md`](docs/exercises.md).

[`docs/corrections.md`](docs/corrections.md) logs every claim this project made
and then revised — a profiler that misattributed the bottleneck by 15x, a test
threshold that contradicted the theory it was testing, and a skew mechanism that
was stated confidently and was wrong.

---

## Design notes

**Paths are stepped in logs.** `S[k+1] = S[k]·exp((μ−q−σ²/2)dt + σ√dt·Z)` is the
exact solution and is correct at any step size. The arithmetic form carries its
own N-dependent discretization error — fatal here, because the headline result
*is* an N-dependence. We would be measuring the simulator instead of the hedging.

**Three volatilities, never conflated.** `sigma_real` drives the paths,
`sigma_implied` sets the premium, `sigma_hedge` computes the delta.

**The engine is an account, not a formula.** Cash, shares, interest and dividends
tracked explicitly; P&L falls out at the end. The simulation is free to disagree
with the theory, which is the point.

**Assertions are stated as rates or in standard errors, never as hand-picked
levels.** Two early tests used absolute thresholds and both failed against a
correct engine; one demanded a 10× variance reduction from a 16× increase in N,
which 1/√N forbids.

**Percentiles, never sample min/max.** Across 1k to 400k paths from the same
distribution the sample minimum drifts −0.16 → −1.40 while p1 moves only −0.049 →
−0.067. The minimum is a property of sample size, not of the distribution.

---

## Status

Days 1–8 complete. 56/56 checks passing.

Day 6 was written as a prediction — that a scheduled jump would flip the skew
negative and stop P(loss) from going to zero as you hedge more, because you
cannot rebalance through a gap. It held: P(loss) plateaus at 12.2% and skew
reaches −1.60. Day 7 turned Day 3's "past N≈256 you are paying for nothing" into
a measured optimum, and Day 8 put the engine on ten years of real SPY returns,
where the skew flip reproduces without any jump being modelled at all.

**Reproducing Day 8.** The SPY series is not committed — run
`python data/fetch_prices.py` to build `data/spy_daily.csv`. Without it Day 8
falls back to the committed `data/aapl_daily.csv`, which is a shorter single-name
series and gives the weaker result (skew −0.67 against SPY's −4.17); the
substitution is deliberate and `results/day8.md` explains what changes.

**What is still open**, ranked by what it would settle:

- **Attribution within real returns.** Day 8 changes fat tails, clustering and
  gaps all at once, so it can say reality differs and by how much, but not which
  feature did it. Bootstrapping returns to break clustering while holding the
  marginal distribution fixed would separate the two.
- **More than one event.** The FOMC trade in Day 6 is n=1, and a 62/38 ex-ante
  proposition resolving favourably once is not evidence that it pays.
- **A stochastic-volatility path generator.** The remaining load-bearing
  assumption is that σᵣ is a constant the hedger merely mis-estimates. Day 2
  relaxes the *estimate*; nothing here relaxes the *constant*.
