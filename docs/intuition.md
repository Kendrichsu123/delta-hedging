# The whole trade, in arithmetic

No calculus. Everything here can be checked on a calculator, and everything the
project does later is this, in the limit of small moves.

## Short gamma bleeds

Sell one 30-day $100 call at 20% vol. Let the stock round-trip `100 → X → 100`.
No time passes, so this isolates the hedging effect from time decay.

```
   X   delta@100  delta@X  shares bought   round-trip P&L
 101     0.5114   0.5801      +0.0687          -0.0687
 102     0.5114   0.6458      +0.1344          -0.2687
 105     0.5114   0.8105      +0.2990          -1.4951
 110     0.5114   0.9546      +0.4431          -4.4314
```

Read the `X = 105` row. Delta rises to 0.81, so you buy 0.299 shares **at 105**.
The stock comes back to 100, delta returns to 0.51, so you sell those same 0.299
shares **at 100**. You bought at 105 and sold at 100: `0.299 × 5 = $1.495` gone.

The stock ended exactly where it started and you lost money. That is short
gamma. Not bad luck — the rebalancing rule *forces* it.

Double the move (1 → 2) and the loss goes 0.0687 → 0.2687, about **4×**. The
loss scales with the **square** of the move. That squared dependence is why this
is a volatility trade: volatility is about the size of moves, and your cost is
quadratic in size.

## Where the ½ in ½Γh² comes from

Gamma is how fast delta changes: `Γ = 0.06955` means delta changes by 0.06955
per $1 of spot.

Stock rises by `h`. Delta rises by `Γh`, so you buy `Γh` shares. But you don't
buy them all at the top — you accumulate as the stock climbs, so on average you
pay about `h/2` above where you started.

```
shares bought   =  Γh
average overpay =  h/2
────────────────────────────
loss            =  Γh × h/2  =  ½Γh²
```

A round trip is **two** moves, so it costs `2 × ½Γh² = Γh²` — the 2 eats the ½.
Check: `½ × 0.06955 × 1 × 2 = 0.0695` vs measured `0.0687`. ✓

Note the loss is the same up or down: `h²` is positive either way. **Direction
never matters, only size.**

## What pays for it

Theta. Spot pinned at $100, two days passing:

```
V(30d) = 2.2872
V(28d) = 2.2096
collected = +0.0775
```

You collect $0.0775 whatever the stock does. **Fixed income, quadratic cost.**

## Break-even

Set the hedging cost equal to the theta and solve:

```
theta over 2 days    = 0.07753
Gamma at 100         = 0.06955
solve Γ·(ΔS)² = θ    →  ΔS = 1.0558   (a 1.056% daily move)

annualize:  1.056% × √365  =  20.17%
implied vol sold at        =  20.00%
```

**The break-even daily move, annualized, is the implied volatility you sold at.**

Move less than 1.056% a day and theta beats your hedging costs. Move more and it
doesn't. "You profit when realized vol comes in below implied" is that
arithmetic — no stochastic calculus required.

## What the calculus is for

The quadratic formula `½Γh²` is not exact. Compare it against the true
round-trip losses:

```
move    actual loss   ½Γh² × 2    error
  1       -0.0687      -0.0695      1%
  2       -0.2687      -0.2782      3%
  5       -1.4951      -1.7387     16%
 10       -4.4314      -6.9548     57%
```

Nearly exact for small moves, badly wrong for large ones — because gamma itself
changes as the stock moves away from the strike.

That is the entire job of `dt → 0`. All the `dS`, `dW`, `(dS)²` notation exists
to say: *take the move small enough that `½Γ(dS)²` becomes exact, then add up
all the pieces*. Itô's lemma is this table in the limit where the approximation
stops having error. The `(dS)²` term that survives in Itô's lemma **is** the
buy-high-sell-low bleed above.

## 1/√N

Not an options result — the ordinary law of averaging. Average N independent
random things and the noise shrinks by √N. It's why a poll of 1,000 has ±3%
error and you need 4,000 to get ±1.5%.

Each rebalancing interval contributes its own independent error. Hedge more
often and you get more errors, each smaller, partly cancelling:

```
noise ∝ 1/√N
```

Measured in `test_day1.py`:

```
N =  32  →  std = 0.34454
N = 128  →  std = 0.17578     (4× the hedges)
N = 512  →  std = 0.08922     (4× again)

log-log slope = -0.4873   (theory: -0.5)
```

**Quadruple the rebalancing, halve the noise.** Which is bad news: cutting noise
to a tenth needs **100×** the trades. The returns diminish brutally, and that is
before transaction costs.
