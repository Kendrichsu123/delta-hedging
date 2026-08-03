# Corrections log

Every claim in this project that was made and then revised, with what triggered
the revision. Kept because the corrections are more informative than the results
that survived unchanged — each one is a way this analysis could have shipped a
confident wrong number.

---

## 1. Two Day 1 tests asserted hand-picked thresholds and failed against a correct engine

**Claimed:** zero-edge P&L std should be `< 0.05` at N=512; hedge-at-realized std
should fall `10×` from N=32 to N=512.

**Reality:** both thresholds were invented. The second was arithmetically
impossible under the theory being tested — N rises 16×, and 1/√N gives exactly
√16 = **4×**, not 10×. Measured: 0.25847/4 = 0.0646 predicted vs 0.0660 actual.
The engine was tracking theory to 2% and the test called it broken.

**Fix:** assert the decay *rate* (log-log slope in [−0.55, −0.45]), which is the
actual claim, instead of a level.

**Lesson:** a threshold picked by feel will confidently tell you something false.
Tie assertions to a predicted quantity.

---

## 2. cProfile misattributed the engine's bottleneck by a factor of ~15

**Claimed** (from cProfile): `gbm_paths` was 93% of runtime; all Black-Scholes
pricing was 6%; `scipy.stats.norm` was 3.7%. Conclusion: a reviewer's claim that
scipy was the bottleneck was "flatly wrong."

**Reality** (wall clock): path generation is **20%**, the hedge loop is **80%**.
The profiler's per-call overhead wrecked the attribution.

**Fix:** measured with `time.perf_counter` on the real call instead. The reviewer
was directionally right — scipy *was* worth replacing.

**Lesson:** the instrument lied. Same failure mode as any measurement artifact —
verify a profiler's story against wall clock before acting on it.

---

## 3. The scipy speedup was overstated by the reviewer and understated by me

**Reviewer claimed:** 5–20× from replacing `scipy.stats.norm` with
`scipy.special.ndtr`.

**I projected:** 1.28× overall, from a scratch benchmark.

**Measured after the swap:** hedge loop 1.63×, **engine 2.1× end to end**
(622.7 → 294.4 ms), bit-identical output.

Both estimates were wrong in opposite directions. The reviewer's ceiling was too
high because `norm.cdf` *calls* `ndtr` internally — you only strip a dispatch
wrapper, you don't reach better math. Mine was too low because my scratch
benchmark made fewer scipy calls than the real engine does.

---

## 4. "YAGNI" on array-valued `T`, which blocked a figure three days later

**Claimed:** the scalar `if T <= 0` branch is a real limitation but low priority —
nothing in the project's scope needs to price a vector of maturities.

**Reality:** Day 4's cumulative-gamma figure needed exactly that and crashed with
`ValueError: The truth value of an array with more than one element is ambiguous`.

**Fix:** floor `T` and mask with `np.where` across all five Greek functions, plus
21 tests covering array `T`, scalar agreement, finiteness, and behavior at `T ≤ 0`.

**Lesson:** the reviewer was right about the substance; I was wrong about the
priority. "We won't need it" is a prediction, and it was checkable against the
remaining plan.

---

## 5. The skew mechanism was wrong, and stated confidently several times

**Claimed:** the dollar-gamma term `∫S²Γdt` is right-skewed; the discretization
noise is left-skewed; the P&L skew flips sign as the noise shrinks, converging to
a positive value.

**Reality:** measured directly, **both components are negatively skewed at every
N.** The gamma term is not right-skewed and never was — it converges to about
−0.07. And the skew does not converge to a positive value; it **peaks near N=64
and decays back toward zero**, which the old story could not explain at all.

**What is actually happening:** skewness is not additive. Expanding
`E[(a+b)³] = E[a³] + 3E[a²b] + 3E[ab²] + E[b³]`, the term `3E[ab²]` dominates by
an order of magnitude at every N. It is the covariance between where the stock
went and how big the hedging noise was — structurally linked, because the
per-step noise is proportional to the same `S²Γ` being accumulated in the gamma
term. `corr(gamma term, squared noise) = +0.331`.

**Fix:** measured each component's skew separately, then decomposed the third
moment into its four pieces.

**Lesson:** the original story was plausible, matched the observed sign flip, and
was wrong. It survived because the *sign flip* it predicted did occur — the
prediction it got wrong (convergence to a positive limit) was outside the range
first examined. A mechanism that explains one feature is not confirmed.

---

## 6. Sample min/max quoted as if they were risk measures

**Claimed:** "worst path −1.0231, best +1.8536" as a description of tail risk.

**Reality:** the sample minimum is a property of *how many paths you drew*, not
of the distribution. From the same distribution:

```
  1,000 paths -> worst -0.1592   p1 -0.0490
 10,000 paths -> worst -1.1629   p1 -0.0636
400,000 paths -> worst -1.3955   p1 -0.0669
```

The minimum drifts down without limit; `p1` barely moves.

**Fix:** quote percentiles, which converge. Same reason "worst drawdown in
backtest" always worsens the longer you backtest.

---

## 7. A correlation that would have misled if quoted alone

**Nearly claimed:** `corr(P&L, terminal price) = −0.024`, i.e. "where the stock
finishes is irrelevant."

**Reality:** the relationship is a **tent**, peaked at the strike and falling both
ways. Pearson correlation measures only *linear* association, and a symmetric
tent has none by construction. Against `|terminal − strike|` the correlation is
**−0.78** — the destination matters a great deal, just not *directionally*.

**Fix:** report both, and say why they differ.

**Lesson:** a correlation near zero means "no linear relationship," never "no
relationship." Plot before quoting.

---

## Pattern

Five of the seven are the same failure: **a number was produced by a tool or a
convention that quietly assumed something false** — a threshold assuming a rate,
a profiler assuming its overhead is negligible, a correlation assuming linearity,
a sample minimum assuming convergence, a mechanism assuming independence.

The defense that actually worked, every time, was checking one quantity two ways
that share no arithmetic. That is why Day 3's floor is trusted (extrapolation
0.033731 vs direct measurement 0.033828) and why Day 1's tests compare against
closed forms rather than against expectations.
