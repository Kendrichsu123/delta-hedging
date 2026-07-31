# Delta-Hedging P&L Simulation

What it actually looks like to sell volatility and hedge it.

A previous project ([vol-surface](https://github.com/Kendrichsu123/vol-surface))
measured what the options market *charges* for risk. This one measures what
*earning* that premium looks like: sell an option at implied vol, delta-hedge it
at discrete intervals, and study the distribution of what you end up with.

## The trade

You sell an option and collect a premium set by **implied volatility**. The
stock then moves by some amount — its **realized volatility**. Delta hedging
strips out the directional bet and leaves a pure wager on implied vs. realized.

The mechanism is a tug-of-war:

- Selling an option makes you **short gamma**. Every rebalance forces you to buy
  after the stock rises and sell after it falls — buy high, sell low, every
  time. The loss on a move of size `h` is `½Γh²`: quadratic in the move, and
  identical whether the stock goes up or down.
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

That is the whole thesis, in arithmetic. See `docs/intuition.md`.

## Questions this project answers

1. You profit when realized comes in under implied — but how reliably?
2. How much of the P&L is noise from hedging discretely rather than continuously?
3. Is the P&L distribution skewed, and why?
4. Does it matter *where* the stock goes, not just how far?
5. What changes if you hedge at realized vol instead of implied?

## Two results already visible in the tests

**Hedging at realized vol makes the P&L deterministic.** The gamma you pay and
the theta you collect are computed at the same vol, so they cancel exactly and
the P&L is known at trade time:

```
P&L = (V(σ_implied) − V(σ_realized)) · e^{rT}
```

Simulated mean at N=512: `0.571613` against a closed form of `0.571685`. The
spread around it decays at the full 1/√N rate (measured slope **−0.4923**) with
no floor.

**Hedging at implied vol earns the same on average, but keeps permanent path
risk.** Same mean, but the spread flattens out instead of vanishing — measured
std goes 0.319 → 0.226 → 0.196 for N = 32 → 128 → 512 and stalls. The
irreducible part is the dollar-gamma integral:

```
P&L = ½(σ_i² − σ_r²) · ∫₀ᵀ S²Γ dt
```

At N=2048 the simulated P&L correlates **0.988** with that formula path by path.
Where the stock spends its time sets the payout: pin near the strike and you
collect the full edge; trend away and gamma dies and you collect a fraction of
it, even though you were right about volatility.

## Layout

```
bs.py           Black-Scholes pricing, Greeks, implied vol, dollar gamma
paths.py        GBM path simulation (exact log-Euler) and realized vol
hedge.py        the hedging engine + closed-form predictions to test against
test_day1.py    35 validation checks
docs/           intuition notes
```

## Running it

```bash
pip install -r requirements.txt
python test_day1.py
```

## Design notes

**Paths are stepped in logs.** `S[k+1] = S[k]·exp((μ−q−σ²/2)dt + σ√dt·Z)` is the
exact solution of the GBM equation and is correct at any step size. The
arithmetic form carries its own N-dependent discretization error — which would
be fatal here, because the headline result *is* an N-dependence. We would end up
measuring the simulator instead of the hedging.

**Three volatilities, never conflated.** `sigma_real` drives the paths,
`sigma_implied` sets the premium, `sigma_hedge` computes the delta. Collapsing
any two of them destroys the experiment.

**The engine is an account, not a formula.** Cash, shares, interest and
dividends are tracked explicitly and the P&L falls out at the end. The
simulation is therefore free to disagree with the theory, which is the point —
the theory is what we are testing.

**Tolerances are stated in standard errors.** Every quantity here is a Monte
Carlo estimate. Two tests originally used hard-coded thresholds and both failed
against a correct engine; one of them demanded a 10× variance reduction from a
16× increase in N, which 1/√N forbids. Asserting the *rate* rather than a level
is the honest test.

## Status

Day 1 complete: engine built and validated, 35/35 checks passing.

Next: the N-sweep and the `var = a + b/N` decomposition, separating irreducible
path risk from reducible discretization noise.
