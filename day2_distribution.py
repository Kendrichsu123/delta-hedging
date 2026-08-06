"""Day 2: how reliably does selling volatility actually pay?

Day 1 established that the mean P&L is BS(sigma_i) - BS(sigma_r). A mean is not
an answer to "how reliably" -- it says nothing about how often you lose, how bad
the bad cases are, or how sensitive any of it is to the things you cannot know
in advance. This file works out the full distribution.

Three questions, in order of how much they change the answer:

  1. What does the P&L distribution look like at a realistic edge?
  2. How does the loss rate depend on the edge you sold at, and on how often
     you rebalance?
  3. What happens when you DON'T know realized vol in advance -- which is the
     actual situation of anyone selling options?

Question 3 turns out to dominate the other two, and Days 1-2 are silent on it
by construction, because sigma_real is an input. Worth being loud about.

Run:  python day2_distribution.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")  # write files; no native windows, no macOS backend errors
import matplotlib.pyplot as plt

from hedge import simulate_hedge

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

SIGMA_I = 0.20
BASE = dict(S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=SIGMA_I)


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


def bootstrap_ci(x, stat, n_boot=2000, seed=0):
    """Percentile bootstrap CI. Used instead of textbook standard-error formulas
    because those assume normality, and the whole point here is that the P&L
    distribution is skewed."""
    rng = np.random.default_rng(seed)
    n = len(x)
    vals = np.array([stat(x[rng.integers(0, n, n)]) for _ in range(n_boot)])
    return np.percentile(vals, [2.5, 97.5])


def skew(x):
    return ((x - x.mean()) ** 3).mean() / x.std() ** 3


# ---------------------------------------------------------------------------
# 1. The base case, characterized properly
# ---------------------------------------------------------------------------


def base_case(n_paths=100_000, N=30, sigma_real=0.15, seed=21):
    res = simulate_hedge(sigma_real=sigma_real, N=N, n_paths=n_paths, seed=seed, **BASE)
    p = res.pnl

    print(f"\n{'=' * 72}")
    print(f"1. BASE CASE  --  sell {SIGMA_I:.0%} vol, stock realizes {sigma_real:.0%},")
    print(f"   30-day ATM call, rebalanced {N}x (daily), {n_paths:,} paths")
    print("=" * 72)
    print(f"  premium received      {res.premium:8.4f}")
    print(f"  mean P&L              {p.mean():+8.4f}   95% CI {bootstrap_ci(p, np.mean).round(4)}")
    print(f"  std                   {p.std():8.4f}")
    print(f"  P(loss)               {(p < 0).mean():8.4f}   95% CI "
          f"{bootstrap_ci(p, lambda v: (v < 0).mean()).round(4)}")
    print(f"  skew                  {skew(p):+8.4f}   95% CI {bootstrap_ci(p, skew).round(4)}")
    print(f"  mean / std            {p.mean() / p.std():8.3f}")
    print()
    qs = [1, 5, 25, 50, 75, 95, 99]
    print("  quantiles:  " + "  ".join(f"p{q}={v:+.3f}" for q, v in zip(qs, np.percentile(p, qs))))
    print(f"  worst path            {p.min():+8.4f}  ({p.min() / res.premium * 100:+.1f}% of premium)")
    print(f"  best path             {p.max():+8.4f}")
    return res


# ---------------------------------------------------------------------------
# 2. Edge and rebalancing frequency
# ---------------------------------------------------------------------------


def edge_sweep(n_paths=30_000, seed=22):
    sigmas = np.array([0.10, 0.125, 0.15, 0.165, 0.175, 0.185, 0.19, 0.195, 0.20])
    Ns = [8, 30, 128, 512]

    print(f"\n{'=' * 72}")
    print("2. P(loss) vs edge and rebalancing frequency")
    print("=" * 72)
    print(f"{'edge (vol pts)':>15}" + "".join(f"{'N=' + str(n):>10}" for n in Ns))

    grid = np.zeros((len(sigmas), len(Ns)))
    means = np.zeros(len(sigmas))
    for i, sr in enumerate(sigmas):
        for j, N in enumerate(Ns):
            p = simulate_hedge(sigma_real=float(sr), N=N, n_paths=n_paths,
                               seed=seed + j, **BASE).pnl
            grid[i, j] = (p < 0).mean()
            if N == 30:
                means[i] = p.mean()
        print(f"{(SIGMA_I - sr) * 100:15.1f}" + "".join(f"{grid[i, j]:10.4f}" for j in range(len(Ns))))

    edge_pts = (SIGMA_I - sigmas) * 100
    print("\n  Mean P&L is linear in the edge; the spread is nearly flat. So the")
    print("  reward-to-risk ratio scales linearly with how many vol points you sold above realized:")
    for i in [0, 2, 4, 6]:
        print(f"    edge {edge_pts[i]:4.1f} pts -> mean {means[i]:+.4f}")
    return sigmas, edge_pts, Ns, grid


# ---------------------------------------------------------------------------
# 3. The caveat that dominates everything above
# ---------------------------------------------------------------------------


def vol_uncertainty(n_total=40_000, N=30, seed=77):
    """Everything above assumes sigma_real is KNOWN. It never is.

    Here the trade is the same -- sell at 20%, expecting 15% -- but realized vol
    is drawn per trade from N(15%, s). s is the accuracy of your forecast.
    """
    print(f"\n{'=' * 72}")
    print("3. What if you DON'T know realized vol in advance?")
    print("   Sell at 20% expecting 15%; realized drawn per trade from N(15%, s).")
    print("=" * 72)
    print(f"{'s (forecast error)':>20} {'mean':>9} {'std':>8} {'P(loss)':>9} {'mean/std':>9}")

    rng = np.random.default_rng(seed)
    out = {}
    for s in [0.0, 0.01, 0.02, 0.03, 0.05]:
        if s == 0.0:
            pool = simulate_hedge(sigma_real=0.15, N=N, n_paths=n_total, seed=1000, **BASE).pnl
        else:
            n_batch = 200
            srs = np.clip(rng.normal(0.15, s, n_batch), 0.02, None)
            pool = np.concatenate([
                simulate_hedge(sigma_real=float(sr), N=N, n_paths=n_total // n_batch,
                               seed=1000 + i, **BASE).pnl
                for i, sr in enumerate(srs)
            ])
        out[s] = pool
        print(f"{s:20.3f} {pool.mean():+9.4f} {pool.std():8.4f} "
              f"{(pool < 0).mean():9.4f} {pool.mean() / pool.std():9.3f}")

    print("\n  The mean barely moves. The spread and the loss rate do not.")
    return out


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def decision_table(edges=(0.025, 0.050, 0.070), errors=(0.0, 0.02, 0.03, 0.04),
                   n_total=40_000, N=30, seed=91):
    """Cross the edge you THINK you have with how wrong your forecast can be.

    `vol_uncertainty` above sweeps the forecast error at a single 5-point edge.
    That answers "how much does uncertainty cost me?" but not the question an
    actual decision needs: "given that my forecast is only good to s, how much
    edge do I need before this is worth doing?" Those are different questions
    and only the crossed grid answers the second.

    Each cell: sell at SIGMA_I, believe realized will come in `edge` below that,
    and let the realized vol actually drawn per trade be N(belief, s). Reports
    P(loss). The s=0 column is the control -- a perfect forecast -- and every
    row must be monotone across it, because more forecast error cannot make a
    trade safer.
    """
    print(f"\n{'=' * 72}")
    print("4. The decision table: edge needed vs. forecast accuracy")
    print(f"   Sell at {SIGMA_I:.0%}; realized drawn per trade from N(belief, s).")
    print("=" * 72)

    rng = np.random.default_rng(seed)
    header = "".join(f"{s * 100:>9.0f}pt" for s in errors)
    print(f"{'edge you think':>16} |{header}")

    grid = np.zeros((len(edges), len(errors)))
    for i, edge in enumerate(edges):
        belief = SIGMA_I - edge
        cells = []
        for j, s in enumerate(errors):
            if s == 0.0:
                pool = simulate_hedge(sigma_real=belief, N=N, n_paths=n_total,
                                      seed=1000, **BASE).pnl
            else:
                # Same construction as vol_uncertainty: many small batches, each
                # at its own draw of realized vol, pooled. One batch per draw is
                # what makes sigma_real vary ACROSS trades rather than within.
                n_batch = 200
                srs = np.clip(rng.normal(belief, s, n_batch), 0.02, None)
                pool = np.concatenate([
                    simulate_hedge(sigma_real=float(sr), N=N,
                                   n_paths=n_total // n_batch,
                                   seed=1000 + k, **BASE).pnl
                    for k, sr in enumerate(srs)
                ])
            grid[i, j] = (pool < 0).mean()
            cells.append(f"{grid[i, j] * 100:8.1f}%")
        print(f"{edge * 100:15.1f}pt |{''.join(cells)}")

    # Monotonicity is the check that this table means anything: within a row,
    # a worse forecast can only raise the loss rate, and down a column, more
    # edge can only lower it. Asserted rather than eyeballed.
    assert np.all(np.diff(grid, axis=1) >= -0.01), "loss rate fell as forecast worsened"
    assert np.all(np.diff(grid, axis=0) <= 0.01), "loss rate rose as edge increased"

    print("\n  Read down a column, not across a row: the column is the world you")
    print("  are actually in, and the row is what it costs to be wrong about it.")
    return edges, errors, grid


def fig_distribution(res, path="figures/day2_distribution.png"):
    p = res.pnl
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    counts, bins, patches = ax.hist(p, bins=110, color=BLUE, edgecolor="none")
    for patch, left in zip(patches, bins[:-1]):
        if left < 0:
            patch.set_facecolor(ORANGE)
    ax.axvline(0, color=INK, linewidth=1.2)
    ax.axvline(p.mean(), color=INK, linewidth=1.6, linestyle="--")
    ax.annotate(f"mean {p.mean():+.3f}", xy=(p.mean(), counts.max() * 0.95),
                xytext=(8, 0), textcoords="offset points", color=INK, fontsize=9)
    ax.annotate(f"{(p < 0).mean():.1%} of paths lose money", xy=(-0.35, counts.max() * 0.42),
                color=ORANGE, fontsize=9, ha="center")
    style(ax, "Sell 20% vol, stock realizes 15%, hedge daily for 30 days",
          "terminal P&L ($ per share)", "paths")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_edge(edge_pts, Ns, grid, path="figures/day2_edge_vs_ploss.png"):
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    colors = [BLUE, ORANGE, AQUA, YELLOW]
    # Anchor the direct labels where the four curves are furthest apart, not at
    # an endpoint -- they all converge on 0% at high edge and on 50% at zero
    # edge, so labels at either end pile up on top of each other.
    label_at = int(np.argmin(np.abs(edge_pts - 1.0)))
    for j, N in enumerate(Ns):
        ax.plot(edge_pts, grid[:, j] * 100, color=colors[j], linewidth=2,
                marker="o", markersize=4, label=f"N = {N}")
        # Direct labels as well as the legend: some of these hues sit below 3:1
        # contrast on a light surface, so identity must not rest on color alone.
        # The results table in results/day2.md is the other half of that relief.
        ax.annotate(f"N={N}", xy=(edge_pts[label_at], grid[label_at, j] * 100),
                    xytext=(-9, 0), textcoords="offset points", color=colors[j],
                    fontsize=9, va="center", ha="right", fontweight="bold")
    ax.axhline(50, color=MUTED, linewidth=1, linestyle=":")
    ax.annotate("coin flip", xy=(9.4, 51), color=MUTED, fontsize=8, ha="right")
    style(ax, "Loss rate collapses with edge -- and rebalancing only helps if you have edge",
          "vol points sold above realized", "P(loss)  %")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9, loc="center right")
    ax.set_xlim(-0.4, 10.4)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_uncertainty(out, path="figures/day2_vol_uncertainty.png"):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    bins = np.linspace(-1.6, 2.2, 130)
    ax.hist(out[0.0], bins=bins, color=BLUE, alpha=0.8, edgecolor="none",
            density=True, label="realized vol known exactly (15%)")
    ax.hist(out[0.03], bins=bins, color=ORANGE, alpha=0.7, edgecolor="none",
            density=True, label="realized vol uncertain: N(15%, 3%)")
    ax.axvline(0, color=INK, linewidth=1.2)
    style(ax, "Not knowing realized vol is a bigger risk than hedging discretely",
          "terminal P&L ($ per share)", "density")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)

    res = base_case()
    sigmas, edge_pts, Ns, grid = edge_sweep()
    out = vol_uncertainty()
    decision_table()

    print(f"\n{'=' * 72}")
    print("FIGURES")
    print("=" * 72)
    fig_distribution(res)
    fig_edge(edge_pts, Ns, grid)
    fig_uncertainty(out)
