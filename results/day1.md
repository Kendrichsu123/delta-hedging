# Day 1 — Validation

Reproduce with `python test_day1.py` (~1 min). 56 checks, all passing.

---

## Why this comes first

Every number in Days 2–8 is produced by the same engine. If the engine is wrong,
every one of those numbers is wrong in a way that looks completely normal — the
histograms stay smooth, the distributions stay plausible, and nothing announces
itself. So the engine is checked against things known independently *before* it
is used to claim anything: closed forms, arbitrage identities, and convergence
rates.

**Tolerances are stated in standard errors, not absolute levels.** Every quantity
here is a Monte Carlo estimate whose uncertainty depends on sample size, so
"within 4 standard errors" is a statement about the engine and "within 0.01" is a
statement about how many paths happened to be run. Two early tests used absolute
thresholds and both failed against a correct engine — one demanded a 10× variance
reduction from a 16× increase in N, which the 1/√N law forbids.

---

## What is checked

| # | group | what it establishes |
|---|---|---|
| 1 | Black-Scholes layer | prices, Greeks, and the inverse all agree with theory |
| 2 | GBM path simulator | the paths are the process they claim to be |
| 3 | **Zero edge** | the engine has no edge when there is none to have |
| 4 | Hedging at realized vol | P&L is deterministic, as the theory requires |
| 5 | Hedging at implied vol | same mean, but the spread does not vanish |
| 6 | Dollar-gamma identity | the P&L formula holds path by path, not just on average |
| 7 | Puts, rates, dividends | the account is right when carry is switched on |
| 8 | Scheduled jump | a jump priced into implied vol restores a fair trade |
| 9 | Transaction costs | costs can only reduce P&L, and scale as √N |

Group 1 goes further than pricing: delta is checked against a finite difference
of the price, gamma against a finite difference of delta, `implied_vol` against a
round trip, and the whole thing against the **Black-Scholes PDE residual**, which
must vanish to 1e-8. A pricer can be wrong in ways parity alone won't catch; the
PDE is a much narrower target to hit by accident.

---

## The headline test

Sell at 20% vol, let the stock realize exactly 20%, hedge at 20%. There is no
edge, so the P&L must go to zero as hedging gets finer.

That one test catches nearly every way this engine could be wrong — a sign error
on the stock unwind, using tomorrow's price for today's hedge, forgetting to
settle the option at expiry, dropping interest on the cash balance. None of them
survive it. **None of them are visible in a histogram.**

---

## Three deliberate bugs

Zero edge, N=128, correct engine gives mean 0. The option premium is **2.2872** —
the number to watch.

```
                mean        std
correct       -0.0001     0.1770
lookahead     +2.2732     0.8583
sign flip   +102.0360    95.9347
no settle     +2.2829     3.4577
```

**Sign flip** (`cash += (target - shares) * S_k`) — mean +102 against a $2.29
premium, roughly 45× the entire option. You are no longer hedging, you are
doubling the position, so you hold a large leveraged stock bet. Absurd by
inspection, and any test touching the mean catches it instantly.

**Look-ahead** (`bs_delta(S[:, k+1], ...)`) — mean **+2.2732 ≈ the premium**.
This is the dangerous one. It is not absurd; it is a plausible-looking profit
attached to a perfectly reasonable histogram. With one step of foresight you
always rebalance in the correct direction, so you collect gamma instead of paying
it and keep the whole premium. Easiest bug here to write, hardest to see.

**No settle** (delete `cash -= bs.payoff(...)`) — mean **+2.2829**, also ≈ the
premium. You keep it and never pay the option out.

The detail worth sitting with: **look-ahead and no-settle produce nearly
identical means** (2.2732 vs 2.2829) from completely different causes, and are
told apart only by their spreads (0.858 vs 3.458). The mean flags that something
is wrong. It cannot tell you what.

All three are caught by the zero-edge assertion. None would have been caught by
looking at the output.

---

## What this licenses

Days 2–8 lean on Day 1 in a specific way. Day 3's irreducible variance floor is
believable because the *control* — hedging at realized vol — returns 0.000043
against a theoretical exactly-zero. Day 4's path-wise identity is trusted because
group 6 asserted it above correlation 0.98 before any analysis leaned on it.
Every later result has a Day 1 check standing behind the machinery it depends on.

The pattern that kept working, here and throughout the project, is **checking one
quantity two ways that share no arithmetic.** See
[`docs/corrections.md`](../docs/corrections.md) for the times it caught something.
