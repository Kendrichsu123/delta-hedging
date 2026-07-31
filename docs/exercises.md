# Day 1 exercises — answer key

Work the exercises in `explore.py` cell 8 first. Predicting *before* running is
the entire value; reading the answers first gets you nothing.

All numbers below use `S0=K=100`, `T=30/365`, `r=q=0`, 20,000 paths.

---

## E1 — Selling 20% vol when the stock realizes 25%

```python
simulate_hedge(sigma_real=0.25, sigma_implied=0.20, N=128, n_paths=20_000, seed=1)
```

```
mean         -0.5705
closed form  -0.5716      = BS(0.20) - BS(0.25)
P(loss)       0.997
```

**Why.** Exactly the mirror of the profitable case. The formula is symmetric in
the vol spread, so selling 5 points *below* realized loses the same amount that
selling 5 points *above* gains.

The number worth staring at is **P(loss) = 99.7%**. Not 100% — a handful of
paths still made money, the ones where the stock trended hard away from the
strike early, killing the gamma before the vol difference could be paid out.
Your loss is proportional to `∫S²Γdt`, and if that integral is small enough,
even a bad vol call costs you almost nothing.

That's the same path dependence as the winning case, running in reverse.

---

## E2 — Hedging once vs. 128 times

```
N =   1   mean +0.0050   std 1.7275
N =   4   mean +0.0079   std 0.9225
N = 128   mean -0.0004   std 0.1748
```

Mean stays at zero throughout — **no amount of rebalancing creates or destroys
edge.** Hedging frequency is purely a risk decision, not a return decision. That
is worth internalizing.

The std ratio from N=1 to N=128 is `1.7275 / 0.1748 = 9.88`. Naive 1/√N predicts
`√128 = 11.3`. The gap is real and not an error: **1/√N is an asymptotic result**
and N=1 is nowhere near the asymptote. Check the well-behaved region instead —
from the tests, N=32→128→512 gave ratios of 1.960 and 1.970 against a predicted
2.000.

Useful habit: a scaling law that fits at large N will usually miss at small N.
Fit it where it applies and say so, rather than quoting one ratio spanning the
whole range.

---

## E3 — Break-even for a 110 strike

```
gamma           0.01832     (vs 0.06955 at K=100)
theta (2 days)  0.01947     (vs 0.07753)
break-even      1.0308  ->  19.69% annualized
```

Gamma drops by ~3.8× and theta drops by ~4.0×, and the *ratio* is nearly
unchanged — so the break-even move barely moves. It comes out at **19.69%**,
close to the 20% we sold at but not exact.

The residual gap is the `½Γh²` approximation degrading, not an error. For an OTM
option, gamma changes faster in relative terms as the stock moves toward the
strike, so treating gamma as constant over a 1% move is a worse assumption than
it was at the money.

**The lesson is the robustness, not the 0.31% miss.** Break-even ≈ implied vol
holds across strikes, which is what makes "sell vol above realized" a strategy
rather than a coincidence at one strike.

---

## E4 — Deliberate bugs and their signatures

Zero edge (`σᵢ = σᵣ = σ_hedge = 20%`), N=128, so a correct engine gives mean 0.
The premium is **2.2872** — remember that number.

```
                mean        std
correct       -0.0001     0.1770
lookahead     +2.2732     0.8583
sign flip   +102.0360    95.9347
no settle     +2.2829     3.4577
```

**Sign flip** (`cash += (target - shares) * S_k`). Mean +102 on a $2.29 premium —
about 45× the entire option. Absurd by inspection. You're no longer hedging, you
are doubling the position, so you hold a huge leveraged stock bet. Any test
touching the mean catches this instantly.

**Look-ahead** (`bs_delta(S[:, k+1], ...)`). Mean **+2.2732 ≈ the premium**. This
is the dangerous one, because it isn't absurd — it's a plausible-looking profit,
and the histogram would look perfectly reasonable. With one step of foresight you
always rebalance in the correct direction, so you *collect* gamma instead of
paying it and keep the whole premium. This is the single easiest bug to write and
the hardest to spot by eye.

**No settle** (delete `cash -= bs.payoff(...)`). Mean **+2.2829**, also ≈ the
premium — you keep it and never pay the option out.

The subtlety worth noticing: **look-ahead and no-settle have nearly identical
means** (2.2732 vs 2.2829) but very different spreads (0.858 vs 3.458). Two
different bugs, same headline number. The mean alone flags that something is
wrong but cannot tell you which — you need the distribution.

### Which test catches what

All three are caught by `test_zero_edge`, on the assertion
`|mean| < 4 × stderr`. With a standard error near 0.0012, the threshold is about
0.005, and every bug above misses it by two to five orders of magnitude.

That is why the zero-edge test is first and why it uses standard errors rather
than a hand-picked tolerance. It doesn't ask whether the output looks sensible.
It asks whether a number that must be zero is zero, to within the precision the
sample can actually resolve.

Note what would NOT have caught these: looking at a histogram. All three broken
engines produce smooth, plausible, unimodal distributions.
