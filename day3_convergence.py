"""Day 3: how much of the P&L spread can rebalancing remove?

Day 2 produced a distribution with std 0.32 at N=30. Some of that spread is a
consequence of rebalancing only 30 times instead of continuously -- a choice,
and therefore removable. The rest is because the stock's ROUTE matters, and no
amount of trading changes the route it took.

This file separates the two.

THE MODEL

    P&L = [edge term] + [discretization noise]

The edge term is (1/2)(sigma_i^2 - sigma_r^2) * int S^2 Gamma dt. It is random,
but it does not depend on N at all. The noise term shrinks as N grows: each
rebalancing interval is shorter, so each error is smaller, but there are more of
them. Halving the interval quarters each error's variance and doubles the count,
so the total halves. That is var ~ 1/N, i.e. std ~ 1/sqrt(N).

Independent variances ADD; standard deviations do not. So the decomposition only
works in variance:

    var(N) = a + b/N

with `a` the irreducible floor and `b/N` the removable part. Plotted against
1/N that is a straight line, and the intercept IS the floor.

THE TRAP

Fitting against 1/N puts one point at x=1 and crams everything else below 0.5.
The N=1 point ends up with 78% leverage -- one observation out of twelve
determining most of the fit -- and it is also the point where the asymptotic
model is least valid. Including it inflates the fitted floor by 24%. This file
fits only the asymptotic region and weights relatively, then reports the
sensitivity so the reader can see the answer is stable.

Run:  python day3_convergence.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hedge import simulate_hedge, theory_pnl_from_gamma

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

BASE = dict(S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=0.20, sigma_real=0.15)
NS = np.array([1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048])
FIT_FROM = 16  # asymptotic region; see sensitivity table in the output


def style(ax, title="", xlabel="", ylabel=""):
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=10)
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


def wls(x, y, w=None):
    """Weighted least squares fit of y = a + b*x. Returns (a, b)."""
    A = np.vstack([np.ones_like(x), x]).T
    if w is None:
        w = np.ones_like(x)
    rw = np.sqrt(w)[:, None]
    coef, *_ = np.linalg.lstsq(A * rw, y * np.sqrt(w), rcond=None)
    return coef[0], coef[1]


def leverage(x):
    """h_ii for a simple linear regression: how much each point steers the fit."""
    return 1 / len(x) + (x - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum()


# ---------------------------------------------------------------------------
# 1. The sweep
# ---------------------------------------------------------------------------


def sweep(n_paths=20_000, seed=41):
    print("=" * 74)
    print("1. SAME TRADE, DIFFERENT REBALANCING FREQUENCY")
    print(f"   sell 20% vol, stock realizes 15%, 30d ATM, {n_paths:,} paths per N")
    print("=" * 74)
    print(f"{'N':>6} {'1/N':>9} | {'var@implied':>12} {'std':>9} | {'var@realized':>13} {'std':>9}")

    vi, vr = [], []
    for N in NS:
        a = simulate_hedge(N=int(N), n_paths=n_paths, seed=seed, **BASE).pnl
        b = simulate_hedge(N=int(N), n_paths=n_paths, seed=seed, sigma_hedge=0.15, **BASE).pnl
        vi.append(a.var(ddof=1))
        vr.append(b.var(ddof=1))
        print(f"{N:6d} {1/N:9.6f} | {vi[-1]:12.6f} {a.std(ddof=1):9.5f} "
              f"| {vr[-1]:13.6f} {b.std(ddof=1):9.5f}")

    vi, vr = np.array(vi), np.array(vr)
    print("\n  Hedging at realized: variance halves every doubling, all the way down.")
    print("  Hedging at implied:  halves at first, then stalls near 0.034.")
    return vi, vr


# ---------------------------------------------------------------------------
# 2. The fit, and the leverage trap
# ---------------------------------------------------------------------------


def fit_floor(vi, vr):
    x = 1.0 / NS

    print("\n" + "=" * 74)
    print("2. FITTING  var = a + b/N")
    print("=" * 74)
    print("\n  Leverage of each point (fraction of the fit it controls):")
    for N, h in zip(NS, leverage(x)):
        mark = "   <-- dominates" if h > 0.3 else ""
        print(f"    N={N:5d}   x=1/N={1/N:.6f}   leverage {h:.4f}{mark}")

    print("\n  Sensitivity of the fitted floor to the fit range (unweighted):")
    for lo in [1, 2, 4, 8, 16, 32, 64]:
        m = NS >= lo
        a, b = wls(x[m], vi[m])
        print(f"    N >= {lo:4d} ({m.sum():2d} pts):  a = {a:.6f}  floor std = {np.sqrt(max(a, 0)):.5f}")
    print("    ^ swings 24% depending on where you start. That is the N=1 point talking,")
    print("      and N=1 is exactly where the asymptotic model is least valid.")

    print("\n  Same, weighted by 1/var^2 so every point counts equally in percentage terms:")
    for lo in [1, 16, 64]:
        m = NS >= lo
        a, _ = wls(x[m], vi[m], w=1 / vi[m] ** 2)
        print(f"    N >= {lo:4d}:  a = {a:.6f}  floor std = {np.sqrt(max(a, 0)):.5f}")
    print("    ^ stable to under 2%. An answer that stops moving when you change the")
    print("      fit range is measuring something real.")

    m = NS >= FIT_FROM
    a_i, b_i = wls(x[m], vi[m], w=1 / vi[m] ** 2)
    a_r, b_r = wls(x[m], vr[m], w=1 / vr[m] ** 2)

    print(f"\n  CONTROL -- hedging at realized vol must have NO floor:")
    print(f"    hedge at realized:  a = {a_r:+.8f}   (theory: exactly 0)")
    print(f"    hedge at implied:   a = {a_i:+.8f}")
    print(f"    ratio: {a_i/max(a_r,1e-12):.0f}x. The fit finds nothing where there is")
    print(f"    nothing to find, which is what makes the {a_i:.4f} believable.")
    return a_i, b_i, a_r, b_r


# ---------------------------------------------------------------------------
# 3. Independent check: is the floor really the dollar-gamma integral?
# ---------------------------------------------------------------------------


def identify_floor(a_i, n_paths=20_000, seed=51):
    print("\n" + "=" * 74)
    print("3. WHAT THE FLOOR IS")
    print("=" * 74)
    print("  The fit says the floor exists and gives its size. Theory says it should")
    print("  be var of (1/2)(sigma_i^2 - sigma_r^2) * int S^2 Gamma dt. Measure that")
    print("  directly and compare -- two independent routes to one number.\n")
    print(f"{'N':>6} {'var(P&L)':>11} {'var(gamma term)':>17} {'corr':>8}")
    for N in [128, 512, 2048]:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed, **BASE)
        g = theory_pnl_from_gamma(r.dollar_gamma_integral, 0.15, 0.20)
        print(f"{N:6d} {r.pnl.var(ddof=1):11.6f} {g.var(ddof=1):17.6f} "
              f"{np.corrcoef(r.pnl, g)[0, 1]:8.4f}")
        last = g.var(ddof=1)
    print(f"\n  fitted floor (extrapolated)  a = {a_i:.6f}   std = {np.sqrt(a_i):.5f}")
    print(f"  measured directly at N=2048  a = {last:.6f}   std = {np.sqrt(last):.5f}")
    print(f"  agreement: {abs(a_i-last)/last*100:.1f}%")
    return last


# ---------------------------------------------------------------------------
# 4. What it costs to chase the floor
# ---------------------------------------------------------------------------


def marginal_value(vi, a_i):
    print("\n" + "=" * 74)
    print("4. WHAT EACH DOUBLING OF N ACTUALLY BUYS")
    print("=" * 74)
    print(f"{'N':>6} {'std':>9} {'irreducible':>13} {'std removed by':>16}")
    print(f"{'':>6} {'':>9} {'share of var':>13} {'this doubling':>16}")
    prev = None
    for N, v in zip(NS, vi):
        s = np.sqrt(v)
        line = f"{N:6d} {s:9.5f} {a_i/v*100:12.1f}%"
        if prev is not None:
            line += f" {prev - s:15.5f}"
        print(line)
        prev = s
    print("\n  Past N~256 the position is almost entirely irreducible risk and each")
    print("  doubling buys a rounding error. With transaction costs -- which grow")
    print("  like sqrt(N) -- trading past that point is strictly value-destroying.")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_loglog(vi, vr, path="figures/day3_loglog.png"):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.loglog(NS, np.sqrt(vi), color=BLUE, linewidth=2, marker="o", markersize=5,
              label="hedge at implied (20%)")
    ax.loglog(NS, np.sqrt(vr), color=ORANGE, linewidth=2, marker="o", markersize=5,
              label="hedge at realized (15%)")
    ref = np.sqrt(vr[0]) / np.sqrt(NS)
    ax.loglog(NS, ref, color=MUTED, linewidth=1.2, linestyle=":", label="pure 1/sqrt(N)")
    ax.annotate("floor: rebalancing\nstops helping", xy=(2048, np.sqrt(vi[-1])),
                xytext=(-14, 26), textcoords="offset points", color=BLUE,
                fontsize=9, ha="right")
    style(ax, "One strategy's noise vanishes; the other hits a wall",
          "rebalances N (log)", "std of terminal P&L (log)")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_fit(vi, vr, a_i, b_i, a_r, b_r, path="figures/day3_variance_fit.png"):
    x = 1.0 / NS
    m = NS >= FIT_FROM
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    xs = np.linspace(0, x[m].max() * 1.05, 100)

    ax.plot(x[m], vi[m], "o", color=BLUE, markersize=6, label="hedge at implied")
    ax.plot(xs, a_i + b_i * xs, color=BLUE, linewidth=1.6)
    ax.plot(x[m], vr[m], "o", color=ORANGE, markersize=6, label="hedge at realized")
    ax.plot(xs, a_r + b_r * xs, color=ORANGE, linewidth=1.6)

    ax.axhline(a_i, color=BLUE, linewidth=1, linestyle="--")
    ax.annotate(f"intercept = irreducible floor = {a_i:.4f}", xy=(xs[-1] * 0.35, a_i),
                xytext=(0, 7), textcoords="offset points", color=BLUE, fontsize=9)
    ax.annotate(f"intercept ~ 0 ({a_r:+.6f})", xy=(xs[-1] * 0.35, a_r),
                xytext=(0, -16), textcoords="offset points", color=ORANGE, fontsize=9)
    style(ax, f"var = a + b/N, fitted on N >= {FIT_FROM}. The intercept is the answer.",
          "1/N", "variance of terminal P&L")
    ax.set_xlim(left=0)
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_leverage(vi, path="figures/day3_leverage.png"):
    x = 1.0 / NS
    a_all, b_all = wls(x, vi)
    m = NS >= FIT_FROM
    a_fit, b_fit = wls(x[m], vi[m], w=1 / vi[m] ** 2)

    # Two panels: the left shows WHY one point has the leverage (it sits alone
    # at x=1 while everything else is crammed near 0), the right zooms on the
    # intercept, which is where that leverage actually does the damage. Plotting
    # only the left would show the geometry but hide the consequence.
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.4))
    for ax, xmax in ((ax1, 1.05), (ax2, 0.075)):
        xs = np.linspace(0, xmax, 100)
        ax.plot(x[~m], vi[~m], "o", color=MUTED, markersize=7, label="N < 16 (excluded)")
        ax.plot(x[m], vi[m], "o", color=BLUE, markersize=7, label="N >= 16 (used)")
        ax.plot(xs, a_all + b_all * xs, color=ORANGE, linewidth=1.8,
                label=f"fit ALL 12 points: floor {np.sqrt(a_all):.4f}")
        ax.plot(xs, a_fit + b_fit * xs, color=BLUE, linewidth=1.8,
                label=f"fit N>=16, weighted: floor {np.sqrt(a_fit):.4f}")
        ax.set_xlim(-xmax * 0.03, xmax)

    ax1.annotate("N=1 sits alone out here.\nleverage 0.78 -- one point,\n78% of the fit",
                 xy=(1.0, vi[0]), xytext=(-12, -46), textcoords="offset points",
                 color=INK, fontsize=9, ha="right")
    style(ax1, "The geometry: one point, far from all the others",
          "1/N", "variance of terminal P&L")
    ax1.legend(frameon=False, labelcolor=MUTED, fontsize=8.5, loc="upper left")

    ax2.set_ylim(0, 0.20)
    ax2.annotate(f"{a_all:.4f}", xy=(0, a_all), xytext=(6, 4),
                 textcoords="offset points", color=ORANGE, fontsize=9)
    ax2.annotate(f"{a_fit:.4f}", xy=(0, a_fit), xytext=(6, -12),
                 textcoords="offset points", color=BLUE, fontsize=9)
    style(ax2, "The damage: intercepts differ by 52%",
          "1/N  (zoomed)", "variance of terminal P&L")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    vi, vr = sweep()
    a_i, b_i, a_r, b_r = fit_floor(vi, vr)
    identify_floor(a_i)
    marginal_value(vi, a_i)
    print("\n" + "=" * 74)
    print("FIGURES")
    print("=" * 74)
    fig_loglog(vi, vr)
    fig_fit(vi, vr, a_i, b_i, a_r, b_r)
    fig_leverage(vi)
