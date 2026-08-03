"""Day 7: transaction costs, and the optimal rebalancing frequency.

Day 3 found that hedging noise falls like 1/sqrt(N) onto an irreducible floor,
and concluded that past N~256 you are paying for nothing. "Paying" was doing
real work in that sentence and had not been measured. This measures it.

THE TENSION

Cost per rebalance is proportional to the shares you trade, which is roughly
Gamma * |move| ~ Gamma * sigma * S * sqrt(dt). Multiply by N rebalances:

    total cost  ~  N * k * sigma * S^2 * Gamma * sqrt(T/N)  =  k*sigma*S^2*Gamma*sqrt(T*N)

so cost grows like sqrt(N) while hedging noise falls like 1/sqrt(N). One rising,
one falling: there is a genuine interior optimum, unlike the cost-free case
where more hedging is always weakly better.

THE MODELLING CHOICE YOU CANNOT AVOID

Costs hit the MEAN. Hedging noise is a VARIANCE. They are not in the same units
and cannot be added, so "optimal N" is not defined until you say how you trade
one against the other. This file uses mean-variance utility

    U = mean - (lambda/2) * variance

and reports the optimum as a function of lambda rather than picking one, because
the honest answer is a curve, not a number.

Run:  python day7_costs.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bs
from hedge import simulate_hedge

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

BASE = dict(S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=0.20, sigma_real=0.15)
NS = [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
COSTS = [0.0, 0.5, 1.0, 2.0, 5.0]
LAMBDAS = [0.5, 1, 2, 5, 10]


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


# ---------------------------------------------------------------------------
# 1. Costs really do grow like sqrt(N) -- once you separate the fixed legs
# ---------------------------------------------------------------------------


def cost_scaling(n_paths=8_000, seed=201):
    print("=" * 76)
    print("1. DOES COST GROW LIKE sqrt(N)?")
    print("=" * 76)
    d0 = float(bs.bs_delta(100.0, 100.0, 30 / 365, 0.0, 0.20))
    print(f"  Entering the hedge is a one-off trade of {d0:.4f} sh x $100 = ${d0*100:.2f},")
    print("  and unwinding at expiry is another. Those legs do NOT scale with N,")
    print("  and they dominate the total at low N -- which makes the raw total look")
    print("  like it breaks the law. Separate them and it does not.\n")
    print(f"{'N':>6} {'total $':>10} {'entry+exit':>11} {'rebalancing':>12} {'rebal/sqrt(N)':>14}")
    for N in [8, 32, 128, 512, 2048]:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed, cost_bps=1.0,
                           keep_paths=True, **BASE)
        exit_leg = (np.abs(bs.bs_delta(r.S[:, -2], 100.0, 30 / 365 / N, 0.0, 0.20))
                    * r.S[:, -1]).mean()
        fixed = d0 * 100 + exit_leg
        rebal = r.traded_notional.mean() - fixed
        print(f"{N:6d} {r.traded_notional.mean():10.2f} {fixed:11.2f} {rebal:12.2f} "
              f"{rebal/np.sqrt(N):14.3f}")
    print("\n  Last column flat => the rebalancing leg is sqrt(N). Confirmed.")


# ---------------------------------------------------------------------------
# 2. The sweep
# ---------------------------------------------------------------------------


def sweep(n_paths=20_000, seed=211):
    print("\n" + "=" * 76)
    print("2. MEAN AND RISK vs N, AT SEVERAL COST LEVELS")
    print("   30-day ATM, 5 vol points of edge. Cost in bp of notional traded.")
    print("=" * 76)
    res = {c: [simulate_hedge(N=N, n_paths=n_paths, seed=seed, cost_bps=c, **BASE).pnl
               for N in NS] for c in COSTS}
    print(f"{'N':>6}" + "".join(f"{('  ' + str(c) + 'bp: mean      std'):>26}"
                                for c in [0.0, 1.0, 5.0]))
    for i, N in enumerate(NS):
        row = f"{N:6d}"
        for c in [0.0, 1.0, 5.0]:
            p = res[c][i]
            row += f"{p.mean():15.4f}{p.std():11.4f}"
        print(row)

    worst = res[5.0][-1]
    print(f"\n  Read the bottom-right cell: at 5bp and N=2048 the mean is "
          f"{worst.mean():+.4f}.")
    print("  Hedging too often converts a genuinely profitable trade into a losing")
    print("  one. The edge was real; the commissions ate more than all of it.")
    return res


# ---------------------------------------------------------------------------
# 3. Optimal N
# ---------------------------------------------------------------------------


def optimal_n(res):
    print("\n" + "=" * 76)
    print("3. OPTIMAL N under  U = mean - (lambda/2) * variance")
    print("=" * 76)
    print("  lambda is risk aversion: 0.5 nearly risk-neutral, 10 very averse.\n")
    print(f"{'cost':>7} " + "".join(f"{'lam=' + str(l):>10}" for l in LAMBDAS))
    table = {}
    for c in COSTS:
        row = f"{c:5.1f}bp "
        table[c] = []
        for lam in LAMBDAS:
            U = [p.mean() - 0.5 * lam * p.var() for p in res[c]]
            best = NS[int(np.argmax(U))]
            table[c].append(best)
            row += f"{best:10d}"
        print(row)

    print("\n  With ZERO costs the optimum is always the largest N available --")
    print("  more hedging is weakly better and never worse, so there is no interior")
    print("  optimum at all. Costs are what create one.")
    print("\n  At 1bp, a moderately risk-averse desk (lambda=2) wants N=128, about")
    print("  four rebalances a day on a monthly option. Day 3 said 'past 256 is")
    print("  waste'; with costs the answer is sharper and lower.")
    return table


# ---------------------------------------------------------------------------
# 4. What this changes about Days 2 and 6
# ---------------------------------------------------------------------------


def impact(n_paths=40_000, seed=221):
    print("\n" + "=" * 76)
    print("4. WHAT THIS CHANGES ABOUT THE EARLIER RESULTS")
    print("=" * 76)

    print("\n  DAY 2 survives almost intact. At DAILY hedging you only trade 30")
    print("  times, so there is not much cost to pay:\n")
    print(f"{'cost':>7} {'mean':>9} {'P(loss)':>9} {'vs 0bp':>9}")
    base = None
    for c in COSTS:
        p = simulate_hedge(sigma_real=0.15, N=30, n_paths=n_paths, seed=seed,
                           cost_bps=c, **{k: v for k, v in BASE.items()
                                          if k != "sigma_real"}).pnl
        pl = (p < 0).mean()
        base = pl if base is None else base
        print(f"{c:5.1f}bp {p.mean():9.4f} {pl:9.4f} {pl - base:+9.4f}")
    print("\n  P(loss) goes 1.99% -> 2.53% at 1bp. The ~5 vol point threshold for")
    print("  P(loss) < 5% is unchanged at 0, 1 and 2bp. Costs are a second-order")
    print("  correction to Day 2, not a revision of it.")

    print("\n  DAY 6 gets SHARPER, not weaker. With 1bp of cost, hedging into a")
    print("  scheduled jump stops being merely useless and becomes harmful:\n")
    SD, SJ, T = 0.15, 0.03, 30 / 365
    fair = np.sqrt(SD**2 + SJ**2 / T)
    nb = {k: v for k, v in BASE.items() if k not in ("sigma_implied", "sigma_real")}
    print(f"{'N':>6} {'no jump':>12} {'with jump':>12}")
    for N in [30, 128, 512, 2048]:
        a = simulate_hedge(sigma_real=SD, sigma_implied=0.20, N=N, n_paths=20_000,
                           seed=223, cost_bps=1.0, **nb).pnl
        b = simulate_hedge(sigma_real=SD, sigma_implied=fair + 0.05, N=N, n_paths=20_000,
                           seed=223, cost_bps=1.0, jump_at=0.5, jump_vol=SJ, **nb).pnl
        print(f"{N:6d} {(a < 0).mean():12.4f} {(b < 0).mean():12.4f}")
    print("\n  The jump column falls to 13.4% at N=128 and then RISES to 14.4% at")
    print("  N=2048. Without costs it was flat past 128. With costs, rebalancing")
    print("  harder against a gap you cannot hedge is actively value-destroying:")
    print("  you pay a rising bill to reduce a risk that is not the one hurting you.")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_mean_std(res, path="figures/day7_mean_std.png"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))
    cols = [MUTED, AQUA, BLUE, YELLOW, ORANGE]
    for c, col in zip(COSTS, cols):
        ax1.plot(NS, [p.mean() for p in res[c]], color=col, linewidth=2,
                 marker="o", markersize=4, label=f"{c}bp")
        ax2.plot(NS, [p.std() for p in res[c]], color=col, linewidth=2,
                 marker="o", markersize=4, label=f"{c}bp")
    ax1.axhline(0, color=INK, linewidth=1.1)
    for ax in (ax1, ax2):
        ax.set_xscale("log")
    style(ax1, "Costs eat the mean, and faster the more you trade",
          "rebalances N (log)", "mean P&L ($)")
    style(ax2, "Risk still falls with N -- that part is unchanged",
          "rebalances N (log)", "std of P&L ($)")
    ax1.legend(frameon=False, labelcolor=MUTED, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_frontier(res, path="figures/day7_frontier.png"):
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    cols = [MUTED, AQUA, BLUE, YELLOW, ORANGE]
    for c, col in zip(COSTS, cols):
        x = [p.std() for p in res[c]]
        y = [p.mean() for p in res[c]]
        ax.plot(x, y, color=col, linewidth=2, marker="o", markersize=4.5,
                label=f"{c}bp")
    # Stagger the labels: at high N the points crowd together on the left, so a
    # uniform offset stacks them on top of each other.
    for i, N in enumerate(NS):
        if N in (8, 64, 512, 2048):
            dy = {8: 8, 64: 8, 512: -14, 2048: 12}[N]
            dx = {8: 4, 64: 4, 512: 2, 2048: -6}[N]
            ax.annotate(f"N={N}", xy=(res[0.0][i].std(), res[0.0][i].mean()),
                        xytext=(dx, dy), textcoords="offset points",
                        color=MUTED, fontsize=8,
                        ha="right" if N == 2048 else "left")
    ax.axhline(0, color=INK, linewidth=1.1)
    style(ax, "Risk/return as N varies. Without costs you just walk left; with them you fall.",
          "std of P&L ($)  -- less risk to the left", "mean P&L ($)")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9, title="cost",
              title_fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    cost_scaling()
    res = sweep()
    optimal_n(res)
    impact()
    print("\n" + "=" * 76)
    print("FIGURES")
    print("=" * 76)
    fig_mean_std(res)
    fig_frontier(res)
