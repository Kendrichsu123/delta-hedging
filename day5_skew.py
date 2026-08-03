"""Day 5: is the P&L distribution lopsided, and why?

Short volatility is famously negatively skewed -- small steady gains, occasional
large loss. This model produces the OPPOSITE over most of its range, and the
sign depends on how often you rebalance. Getting that right requires care,
because a skewness estimate is a third moment and third moments are noisy.

WHAT THIS FILE FIXES

An earlier reading of this project claimed the crossover worked like this: the
dollar-gamma term is right-skewed, the discretization noise is left-skewed, and
the sign flips as the noise shrinks. Measured directly, that is wrong on the
first count. BOTH components are negatively skewed at every N:

    skew(gamma term)   negative everywhere, approaching about -0.07
    skew(noise)        negative everywhere, shrinking toward 0

Yet the sum is positively skewed over most of the range. Skewness is not
additive, and the reason is a cross term. Expanding the third central moment of
P&L = A + B (A the gamma term, B the noise, a and b their deviations):

    E[(a+b)^3]  =  E[a^3]  +  3E[a^2 b]  +  3E[a b^2]  +  E[b^3]

The term that drives the sign is 3E[a b^2] -- the covariance between where the
stock went and how big the hedging noise was. Those are not independent: the
noise contributed by each step is proportional to S^2*Gamma, the very same
quantity being accumulated in A. High-dollar-gamma paths therefore carry wider
noise, their outcomes spread further, and because A is bounded below by zero the
extra spread lengthens the right tail.

That also explains why the skew is non-monotonic -- it peaks and then falls back
toward zero rather than converging to a positive number. The cross term is
proportional to var(B), which vanishes as N grows, so at very large N the skew
converges to skew(A) alone, which is slightly negative.

Run:  python day5_skew.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hedge import simulate_hedge, theory_pnl_from_gamma

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

BASE = dict(S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=0.20, sigma_real=0.15)
SIGMA_R, SIGMA_I = 0.15, 0.20
NS = [1, 2, 4, 8, 12, 16, 24, 32, 64, 128, 256, 512, 1024]


def style(ax, title="", xlabel="", ylabel=""):
    ax.set_title(title, color=INK, fontsize=10.5, loc="left", pad=9)
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c9c9c4")
    ax.tick_params(colors=MUTED, labelsize=9)
    return ax


def skew(x):
    return ((x - x.mean()) ** 3).mean() / x.std() ** 3


def boot_ci(x, stat, n_boot=1500, seed=0):
    """Percentile bootstrap. The textbook standard error for skewness is
    sqrt(6/n), which assumes the data is normal -- exactly the assumption under
    test here. Bootstrap makes no such assumption."""
    rng = np.random.default_rng(seed)
    m = len(x)
    v = np.array([stat(x[rng.integers(0, m, m)]) for _ in range(n_boot)])
    return np.percentile(v, [2.5, 97.5])


# ---------------------------------------------------------------------------
# 1. Skew vs N, with error bars
# ---------------------------------------------------------------------------


def skew_sweep(n_paths=40_000, seed=71):
    print("=" * 76)
    print("1. SKEW OF P&L vs REBALANCING FREQUENCY")
    print(f"   sell 20% vol, stock realizes 15%, {n_paths:,} paths, bootstrap 95% CI")
    print("=" * 76)
    print(f"{'N':>6} {'skew':>9} {'95% CI':>24} {'verdict':>11}")
    rows = []
    for N in NS:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed, **BASE)
        s = skew(r.pnl)
        lo, hi = boot_ci(r.pnl, skew)
        verdict = "negative" if hi < 0 else ("positive" if lo > 0 else "AMBIGUOUS")
        rows.append((N, s, lo, hi))
        print(f"{N:6d} {s:+9.4f}   [{lo:+.4f}, {hi:+.4f}] {verdict:>11}")

    print("\n  Two features, both real and both outside the CIs:")
    print("   - the sign FLIPS between N=4 and N=12, crossing zero around N=8")
    print("   - the skew PEAKS near N=64 and then falls back toward zero")
    print("  Neither is estimator noise. A single measurement at one N would have")
    print("  supported almost any story you wanted to tell.")
    return rows


# ---------------------------------------------------------------------------
# 2. Where the sign actually comes from
# ---------------------------------------------------------------------------


def decompose(n_paths=40_000, seed=73):
    print("\n" + "=" * 76)
    print("2. WHY -- AND IT IS NOT WHAT IT LOOKS LIKE")
    print("=" * 76)
    print("  Split P&L into A (the dollar-gamma term: where the stock went) and")
    print("  B (the discretization noise). Measure each one's skew separately:\n")
    print(f"{'N':>6} {'skew(P&L)':>11} {'skew(A)':>10} {'skew(B)':>10} {'std(A)':>9} {'std(B)':>9}")
    sub = [4, 8, 16, 32, 64, 128, 256, 512, 1024]
    for N in sub:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed + 1, **BASE)
        A = theory_pnl_from_gamma(r.dollar_gamma_integral, SIGMA_R, SIGMA_I)
        B = r.pnl - A
        print(f"{N:6d} {skew(r.pnl):+11.4f} {skew(A):+10.4f} {skew(B):+10.4f} "
              f"{A.std():9.5f} {B.std():9.5f}")

    print("\n  BOTH components are negatively skewed at every N. Yet the sum is")
    print("  positive over most of the range. Skewness is not additive.")
    print("\n  Expanding the third central moment of A+B:")
    print("      E[(a+b)^3] = E[a^3] + 3E[a^2 b] + 3E[a b^2] + E[b^3]\n")
    print(f"{'N':>6} {'E[a^3]':>10} {'3E[a^2b]':>11} {'3E[ab^2]':>11} {'E[b^3]':>10} | {'skew':>8}")
    terms = []
    for N in [8, 32, 64, 128, 512]:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed, **BASE)
        A = theory_pnl_from_gamma(r.dollar_gamma_integral, SIGMA_R, SIGMA_I)
        B = r.pnl - A
        a, b = A - A.mean(), B - B.mean()
        t = [(a**3).mean(), 3 * (a**2 * b).mean(), 3 * (a * b**2).mean(), (b**3).mean()]
        terms.append((N, t, r.pnl.std()))
        print(f"{N:6d} {t[0]:10.5f} {t[1]:11.5f} {t[2]:11.5f} {t[3]:10.5f} "
              f"| {sum(t)/r.pnl.std()**3:+8.4f}")

    r = simulate_hedge(N=64, n_paths=n_paths, seed=seed + 2, **BASE)
    A = theory_pnl_from_gamma(r.dollar_gamma_integral, SIGMA_R, SIGMA_I)
    B = r.pnl - A
    c = np.corrcoef(A, (B - B.mean()) ** 2)[0, 1]
    print(f"\n  3E[a b^2] is the term carrying the sign. It is the covariance between")
    print(f"  where the stock went and how BIG the hedging noise was:")
    print(f"      corr(gamma term, squared noise) at N=64 = {c:+.4f}")
    print("\n  Those are not independent. The noise contributed by each step is")
    print("  proportional to S^2*Gamma -- the same quantity being accumulated in A.")
    print("  So high-dollar-gamma paths carry wider noise, their outcomes spread")
    print("  further, and since A is bounded below by zero the extra spread has")
    print("  more room on the right. That is the positive skew.")
    print("\n  It also explains the peak: 3E[a b^2] scales with var(B), which dies")
    print("  like 1/N. At very large N only E[a^3] survives, and that is negative.")
    return terms


# ---------------------------------------------------------------------------
# 3. What this does NOT show
# ---------------------------------------------------------------------------


def min_is_not_a_statistic(n_paths=400_000, seed=91):
    """The sample minimum is a property of your sample size, not of the
    distribution. Worth demonstrating because 'worst case in the backtest' is
    quoted as a risk measure constantly, and it is not one."""
    print("\n" + "=" * 76)
    print("3. AN ASIDE: THE SAMPLE MINIMUM IS NOT A RISK MEASURE")
    print("=" * 76)
    p = simulate_hedge(N=30, n_paths=n_paths, seed=seed, **BASE).pnl
    print(f"{'paths drawn':>13} {'worst':>10} {'p0.1':>10} {'p1':>10}")
    for n in [1_000, 10_000, 40_000, 100_000, 400_000]:
        sub = p[:n]
        print(f"{n:13,} {sub.min():10.4f} {np.percentile(sub, 0.1):10.4f} "
              f"{np.percentile(sub, 1):10.4f}")
    print("\n  The minimum keeps drifting down as paths are added; the percentiles")
    print("  barely move. Draw more paths, find a worse path -- always. This is the")
    print("  same reason 'worst drawdown in backtest' gets worse the longer you")
    print("  backtest. Quote percentiles, which converge.")


def folklore(n_paths=60_000, seed=75):
    print("\n" + "=" * 76)
    print("4. THIS IS NOT THE SKEW THE FOLKLORE IS ABOUT")
    print("=" * 76)
    r = simulate_hedge(N=30, n_paths=n_paths, seed=seed, **BASE)
    p = r.pnl
    print(f"  At daily hedging (N=30): skew = {skew(p):+.4f}, CI {np.round(boot_ci(p, skew), 4)}")
    print(f"  P(loss) {(p < 0).mean():.4f}, mean {p.mean():+.4f}")
    print("\n  Real short-vol books are NEGATIVELY skewed: many small gains, rare")
    print("  large losses. This model says positive. The model is not wrong -- it is")
    print("  answering a question with two assumptions baked in that remove exactly")
    print("  the thing the folklore is about:")
    print("\n    1. sigma_real is a KNOWN CONSTANT. Real realized vol is random.")
    print("    2. The stock moves CONTINUOUSLY. No gaps. A delta hedge is helpless")
    print("       against a jump, by construction -- you cannot rebalance through it.")
    print("\n  Test assumption 1 in isolation. Keep continuous paths, but draw the")
    print("  realized vol per trade from N(15%, s) instead of fixing it at 15%:\n")
    rng = np.random.default_rng(93)
    print(f"{'forecast error s':>17} {'mean':>9} {'std':>8} {'skew':>9} {'P(loss)':>9}")
    for s in [0.0, 0.01, 0.02, 0.03, 0.05]:
        if s == 0:
            q = simulate_hedge(sigma_real=SIGMA_R, N=30, n_paths=n_paths, seed=1,
                               S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=SIGMA_I)
            q = q.pnl
        else:
            srs = np.clip(rng.normal(SIGMA_R, s, 300), 0.02, None)
            q = np.concatenate([
                simulate_hedge(sigma_real=float(v), N=30, n_paths=n_paths // 300, seed=700 + i,
                               S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=SIGMA_I).pnl
                for i, v in enumerate(srs)
            ])
        print(f"{s:17.3f} {q.mean():+9.4f} {q.std():8.4f} {skew(q):+9.4f} {(q < 0).mean():9.4f}")

    print("\n  Assumption 1 ALONE flips the sign. The skew crosses zero at about a")
    print("  3-point forecast error and reaches -0.12 at 5 points, while the mean")
    print("  barely moves. Reason: P&L = 1/2*(si^2 - sr^2)*int S^2 Gamma dt, and when")
    print("  sigma_r is random it occasionally lands ABOVE sigma_i. That bracket goes")
    print("  negative and the trade genuinely loses -- a left tail the fixed-vol")
    print("  model cannot produce at all.")
    print("\n  So one of the two doors is now quantified. Day 6 opens the other.")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_skew(rows, path="figures/day5_skew_vs_n.png"):
    N = np.array([r[0] for r in rows], dtype=float)
    s = np.array([r[1] for r in rows])
    lo = np.array([r[2] for r in rows])
    hi = np.array([r[3] for r in rows])
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.fill_between(N, lo, hi, color=BLUE, alpha=0.22, linewidth=0)
    ax.plot(N, s, color=BLUE, linewidth=2, marker="o", markersize=4.5)
    ax.axhline(0, color=INK, linewidth=1.1)
    ax.set_xscale("log")
    ax.annotate("sign flips here\n(N~8)", xy=(8, 0), xytext=(-4, -44),
                textcoords="offset points", color=INK, fontsize=9, ha="center")
    ax.annotate("peaks near N=64, then falls\nback toward zero", xy=(64, s[NS.index(64)]),
                xytext=(26, -36), textcoords="offset points", color=BLUE, fontsize=9)
    style(ax, "The sign of the skew is a knob, not a fact  (shaded = bootstrap 95% CI)",
          "rebalances N (log)", "skewness of terminal P&L")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_terms(terms, path="figures/day5_decomposition.png"):
    N = np.array([t[0] for t in terms], dtype=float)
    sd = np.array([t[2] for t in terms])
    arr = np.array([t[1] for t in terms])
    labels = [r"$E[a^3]$  (gamma term alone)", r"$3E[a^2b]$",
              r"$3E[ab^2]$  (the cross term)", r"$E[b^3]$  (noise alone)"]
    cols = [MUTED, AQUA, BLUE, ORANGE]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    for j in range(4):
        ax.plot(N, arr[:, j] / sd**3, color=cols[j], linewidth=2,
                marker="o", markersize=4.5, label=labels[j])
    ax.plot(N, arr.sum(axis=1) / sd**3, color=INK, linewidth=1.6,
            linestyle="--", label="total = skew(P&L)")
    ax.axhline(0, color=INK, linewidth=1)
    ax.set_xscale("log")
    style(ax, "Each term's contribution to the skew. The cross term carries the sign.",
          "rebalances N (log)", "contribution to skewness")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_shapes(n_paths=40_000, seed=76, path="figures/day5_shapes.png"):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    for ax, N, col in [(axes[0], 4, ORANGE), (axes[1], 64, BLUE)]:
        p = simulate_hedge(N=N, n_paths=n_paths, seed=seed, **BASE).pnl
        ax.hist(p, bins=110, color=col, edgecolor="none")
        ax.axvline(p.mean(), color=INK, linewidth=1.4, linestyle="--")
        style(ax, f"N = {N}:  skew {skew(p):+.3f}", "terminal P&L ($)", "paths")
    fig.suptitle("Same trade, same edge -- opposite lopsidedness",
                 color=INK, fontsize=12, x=0.006, ha="left", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    rows = skew_sweep()
    terms = decompose()
    min_is_not_a_statistic()
    folklore()
    print("\n" + "=" * 76)
    print("FIGURES")
    print("=" * 76)
    fig_skew(rows)
    fig_terms(terms)
    fig_shapes()
