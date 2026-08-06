# The story

The README lists what each day found. This is why each day happened.

The property worth noticing: **every day's answer created the next day's
question.** Nothing past Day 4 was planned. Days 5, 6 and 7 exist because the
earlier results demanded them.

---

## The question

> You sell an option and collect a premium set by implied vol. The stock moves by
> some amount — realized vol. Delta hedging strips out the direction and leaves a
> pure bet on implied vs. realized. **What does that actually feel like to hold?**

Before any code, the thesis in arithmetic. You collect **theta**, fixed per day.
You pay **gamma costs**, `½Γh²`, quadratic in the move. Set them equal:

```
Γ·(ΔS)² = θ  →  ΔS = 1.056% daily  →  annualized 20.17%
```

**The break-even daily move, annualized, is the implied vol you sold at.**

---

## Day 1 — "Can I trust anything this produces?"

Every later result would be a claim about a *distribution*, and distributions look
plausible when they are wrong. Three deliberately broken engines:

```
correct       -0.0001
lookahead     +2.2732      <- the option premium
sign flip   +102.0360
no settle     +2.2829      <- the option premium
```

**All three produced smooth, believable histograms.** Two returned exactly the
premium as profit. None would have been caught by eye.

So: 66 assertions against closed forms and arbitrage identities, before any
analysis. The headline one — sell at exactly the vol the stock realizes, and P&L
must collapse to zero.

**→ The engine works. So what does it say?**

---

## Day 2 — "How much edge do you actually need?"

Run it 100,000 times. A mean is not an answer; the distribution is.

```
mean +0.5703, P(loss) 1.97% [1.88%, 2.05%]
```

You sold a genuinely mispriced option, hedged it correctly, and lost money 2% of
the time.

- **P(loss) is violently nonlinear in edge.** 5.0 → 2.5 vol points takes the loss
  rate 2.0% → **17.5%**.
- **Mean scales with edge, spread does not** → reward/risk ≈ **0.35 per vol point**.
- **Rebalancing creates no edge.** The zero-edge control sits at ~50% from N=8 to
  N=512. A risk lever, never a return lever.

Then the caveat that dominated: **σᵣ was an input.** Nobody knows realized vol in
advance. A 3-point forecast error takes P(loss) 2.0% → **11.4%**. Crossing edge
with forecast error: **~7 vol points needed** to keep the loss rate under 5%.

**→ The spread runs −1.02 to +1.83. How much of that is my own fault?**

---

## Day 3 — "How much risk can I trade away?"

```
P&L = [where the stock went] + [how sloppily I hedged]
```

The second shrinks with N; the first does not. **Variances add, standard
deviations do not**, so the split only works in variance: `var(N) = a + b/N`.

```
hedge at realized vol:  a = +0.00004283   (theory: exactly 0)
hedge at implied vol:   a = +0.03373052   (788x larger)
```

**The control returning zero is what licenses believing the other number.**

The floor was then identified **two independent ways** — extrapolating the fit
gave 0.033731, measuring the dollar-gamma term directly gave 0.033828.
**Agreement to 0.3%, sharing no arithmetic.**

**This day nearly produced a fake result.** Plotting against `1/N` gives the N=1
point a **leverage of 0.7777** — one observation of twelve steering 78% of the
fit, and it is exactly where the asymptotic model is least valid. Include it:
floor std 0.226. Restrict to the asymptotic region: **0.183.** A 24% swing.

**→ There is a floor and I know its size. What *is* it?**

---

## Day 4 — "Where does the money physically come from?"

Day 3's floor was inferred by extrapolation, never observed. Day 4 made it
physical: `P&L = ½(σᵢ²−σᵣ²)·∫S²Γdt` holds **path by path** — correlation
**0.9889**, explaining 98% of cross-path variation.

The negative result was sharper:

```
corr(P&L, terminal price)               -0.0238
corr(P&L, the path's OWN realized vol)  -0.2092
corr(P&L, dollar-gamma integral)        +0.9774
```

Two paths ending at the same price: one stayed near the strike 99.9% of the time
and made **+1.1219**; the other was near it 58% of the time, **realized more
volatility**, and made **+0.4859**.

**Being right about volatility is necessary but not sufficient.**

**→ I know the level and the mechanism. What *shape* is this distribution?**

---

## Day 5 — The day the project turned

```
   N=1    -0.9845        N=64   +0.4385   <- peak
   N=8    +0.0139        N=1024 +0.0357   <- non-monotonic
```

Firmly **positive** at realistic hedging frequencies. Real short vol is famously
*negatively* skewed. And worse:

```
     N   worst of 40,000 trades
   512        +0.0740
  2048        +0.0922
```

**Zero losses in 40,000 trades.** Not a bug — `½(σᵢ²−σᵣ²)∫S²Γdt` has every factor
positive when σᵢ > σᵣ, so no path *can* lose.

**A model that says a blow-up-prone strategy is riskless would get you killed.**
That is the finding. Two suspects named: σᵣ known, and no gaps. The first was
convicted in isolation — a 3-point forecast error flips the skew **+0.40 → −0.01**
while the mean barely moves.

*(This day also corrected a mechanism stated confidently for days: both components
are negatively skewed, and the positive sign comes entirely from the cross term
`3E[ab²]`, the covariance between where the stock went and how big the noise was
— structurally linked, since both are driven by the same `S²Γ`.)*

**→ Which assumption causes the vanishing losses?**

---

## Day 6 — Convicting the second suspect

```
diffusive loss per step  =  ½ΓS²σ²·dt      <- proportional to dt
jump loss                =  ½ΓS²J²         <- no dt anywhere
```

Sum the diffusive one over N steps and the N cancels — that is why it is
hedgeable. The jump has nothing to cancel.

Holding edge constant:

```
   N |  no jump   with jump
  30 |     1.97%     13.94%
2048 |     0.00%     12.17%   <- plateau
```

**P(loss) stops falling**, and the plateau is predictable without reference to
hedging at all: break-even jump ±4.72%, and `P(|J| > 4.72%) = 11.56%` against a
measured 12.17%.

**The payoff.** A jump adds `σ_J²` regardless of tenor, so fair vol is
`sqrt(σ² + σ_J²/T)` — the same event is worth **13.72 vol points at 1 day and
0.03 at 2 years.** That predicts vol-surface's measured 5–7 point front-expiry
collapse at a 2–4 day expiry, and says the 0.3 observed at 2 years was *not* the
event. **The same inference, reached from the opposite direction** — that project
inferred the jump from the surface; this one predicts the surface from the jump.

Applied to the real FOMC: break-even ±0.856% or ±1.046% against SPY's actual
−0.67%. **+16.3% or +29.2% of premium** — on a **62/38 bet, n=1**.

**→ Day 3 said "past N=256 you're *paying* for nothing." What does paying mean?**

---

## Day 7 — Pricing the friction

```
cost ∝ √N          hedging noise ∝ 1/√N
```

One rising, one falling — a genuine optimum, which the cost-free case never had.

```
   N |  0bp mean   1bp mean   5bp mean
2048 |    0.5724     0.4385    -0.0972
```

**You can turn a genuinely profitable trade into a losing one purely by trading it
too carefully.**

Optimal N is a *table*, not a number: costs hit the mean, noise is a variance, and
combining them requires stating a risk preference. The zero-cost row is the
control — with no costs the optimum is always the largest N, so **costs are what
create an optimum at all**.

**And it retroactively sharpened Day 6.** With costs, the jump case bottoms at
13.39% (N=128) and **rises** to 14.42% (N=2048). Hedging harder against a gap went
from *useless* to *actively value-destroying*.

---

## The thread underneath

One habit did the work in every single day:

> **Measure the same quantity two ways that share no arithmetic.**

| day | route A | route B | agreement |
|---|---|---|---|
| 1 | simulation | closed form | 0.15 std errors |
| 3 | extrapolated floor | directly measured floor | 0.3% |
| 4 | simulated P&L | gamma formula, per path | corr 0.989 |
| 6 | measured P(loss) plateau | `P(\|J\| > break-even)` | 12.17% vs 11.56% |
| 6 | this project's prediction | vol-surface's measurement | consistent |
| 7 | measured √N coefficient | theory | 27.24 vs 27.42 |

And the counter-habit: [`corrections.md`](corrections.md), seven claims made and
then revised. **Five were the same failure** — a number produced by a tool or
convention that quietly assumed something false. A threshold assuming a rate. A
profiler assuming negligible overhead. A correlation assuming linearity. A sample
minimum assuming convergence. A mechanism assuming independence.

---

## The 60-second version

> I built a delta-hedging simulator and validated it against every closed form in
> the literature — 56 checks. It says selling volatility needs about 7 vol points
> of edge to be reliably profitable once you account for realistic forecast error,
> and that where the stock spends its time matters more than how much it moves.
>
> Then the model told me selling volatility was riskless — zero losses in 40,000
> trades, positively skewed. That is the opposite of reality, so I traced it to two
> assumptions. Uncertain realized vol flips the skew. A scheduled jump puts a
> **12.2% floor under the loss rate that no amount of rebalancing lifts**, because
> you cannot rebalance through a gap.
>
> Applied to an FOMC announcement I had independently measured in a previous
> project: the priced move predicts the exact term-structure collapse I had
> observed, and selling it would have returned 16–29% of premium on a 62/38 bet.

---

## What it does not claim

- **The GBM results never touched real market data.** Every path in Days 1–7 is
  simulated. The "real short vol is negatively skewed" comparison is imported from
  outside, not measured here. Day 8 is the first day that uses a real price series,
  and its sample is small.
- **The FOMC result is n=1**, and depends on an interpretation worth 2×.
- **No vol forecaster was built.** Forecast error is a swept sensitivity parameter,
  not a solved problem.
- **The Day 1–4 numbers are optimistic bounds**, and Days 5–7 say by roughly how
  much.
