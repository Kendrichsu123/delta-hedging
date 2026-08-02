"""Day 4: where the money physically comes from.

Day 3 established that a floor exists and measured its size (var 0.0337) by
extrapolating a fit to infinite rebalancing. That is a statistical argument --
the floor is inferred, never observed directly.

This file makes it physical. The claim is:

    P&L  =  (1/2)(sigma_i^2 - sigma_r^2) * int_0^T S^2 Gamma dt

not on average, but PATH BY PATH. If that is right, then knowing where a single
stock path went is enough to predict that path's P&L, and the scatter of
simulated P&L against the formula should collapse onto the 45-degree line as N
grows.

The interesting part is what this implies about what does NOT matter. The
formula contains no reference to where the stock ended up, and only an indirect
reference to how far it travelled. So:

  - the terminal price should be nearly uninformative
  - the path's own realized volatility should be only weakly informative
  - only the gamma-weighted time integral should predict the outcome

All three are testable, and the second one is the surprising one.

Run:  python day4_path_dependence.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bs
from hedge import simulate_hedge, theory_pnl_from_gamma

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

BASE = dict(S0=100.0, K=100.0, T=30 / 365, r=0.0, sigma_implied=0.20, sigma_real=0.15)
SIGMA_I, SIGMA_R, K_STRIKE, T = 0.20, 0.15, 100.0, 30 / 365


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
# 1. Where is gamma actually worth money?
# ---------------------------------------------------------------------------


def gamma_profile():
    print("=" * 74)
    print("1. DOLLAR GAMMA (S^2 * Gamma) -- the weight in the P&L integral")
    print("=" * 74)
    print("   How much P&L one unit of time generates, by spot and time remaining.\n")
    days = [30, 15, 5, 1]
    print(f"{'spot':>7} " + "".join(f"{str(d) + 'd left':>11}" for d in days))
    for S in [85, 90, 95, 100, 105, 110, 115]:
        row = [bs.dollar_gamma(float(S), K_STRIKE, d / 365, 0.0, SIGMA_I) for d in days]
        print(f"{S:7.0f} " + "".join(f"{v:11.1f}" for v in row))

    print("\n  Two things to read off this table:")
    print("   - Gamma is worth money ONLY near the strike. At 30 days out, moving")
    print("     from 100 to 110 costs you 74% of your dollar gamma; 115 costs 95%.")
    print("   - It CONCENTRATES as expiry approaches. With 1 day left, spot 100 is")
    print("     worth 3810 but spot 105 is worth 0.1 -- a factor of 38,000.")
    print("   So a path that drifts away from the strike late stops earning almost")
    print("   entirely, no matter how well the trade was going before.")


# ---------------------------------------------------------------------------
# 2. Does the formula predict individual paths?
# ---------------------------------------------------------------------------


def formula_vs_simulation(n_paths=8000, seed=61):
    print("\n" + "=" * 74)
    print("2. DOES THE FORMULA PREDICT EACH PATH, NOT JUST THE AVERAGE?")
    print("=" * 74)
    print(f"{'N':>7} {'corr':>9} {'R^2':>9}   interpretation")
    out = {}
    for N in [30, 128, 512, 2048]:
        r = simulate_hedge(N=N, n_paths=n_paths, seed=seed, **BASE)
        g = theory_pnl_from_gamma(r.dollar_gamma_integral, SIGMA_R, SIGMA_I)
        c = np.corrcoef(r.pnl, g)[0, 1]
        out[N] = (r, g, c)
        note = f"formula explains {c**2:.0%} of the variation across paths"
        print(f"{N:7d} {c:9.4f} {c**2:9.4f}   {note}")
    print("\n  The residual IS the discretization noise from Day 3. As N grows the")
    print("  noise shrinks and the formula takes over, which is why R^2 climbs.")
    return out


# ---------------------------------------------------------------------------
# 3. What does NOT predict your P&L
# ---------------------------------------------------------------------------


def what_does_not_matter(n_paths=8000, seed=62):
    print("\n" + "=" * 74)
    print("3. WHAT DOES NOT PREDICT YOUR P&L")
    print("=" * 74)
    r = simulate_hedge(N=1024, n_paths=n_paths, seed=seed, keep_paths=True, **BASE)
    ST = r.S[:, -1]
    g = theory_pnl_from_gamma(r.dollar_gamma_integral, SIGMA_R, SIGMA_I)

    print(f"  corr(P&L, terminal price)             {np.corrcoef(r.pnl, ST)[0, 1]:+.4f}   <- nothing")
    print(f"  corr(P&L, |terminal - strike|)        {np.corrcoef(r.pnl, np.abs(ST - K_STRIKE))[0, 1]:+.4f}")
    print(f"  corr(P&L, path's OWN realized vol)    {np.corrcoef(r.pnl, r.realized_vol)[0, 1]:+.4f}   <- weak!")
    print(f"  corr(P&L, dollar-gamma integral)      {np.corrcoef(r.pnl, g)[0, 1]:+.4f}   <- almost everything")

    print("\n  The second-to-last line is the surprise. You would expect the amount a")
    print("  stock actually moved to drive the P&L of a volatility trade. It barely")
    print("  does. Two paths can realize the same volatility and pay very differently,")
    print("  because what you are short is not 'movement' -- it is movement WEIGHTED")
    print("  by how much dollar gamma you were carrying when it happened.")

    m = np.abs(ST - K_STRIKE) < 0.5
    print(f"\n  Sharpest version. Among the {m.sum()} paths that finished within $0.50 of")
    print(f"  the strike -- effectively the same ending:")
    print(f"    P&L ranges {r.pnl[m].min():+.4f} to {r.pnl[m].max():+.4f}  (a spread of {r.pnl[m].max() - r.pnl[m].min():.4f})")
    print(f"    std among them {r.pnl[m].std():.4f} vs {r.pnl.std():.4f} across all paths")
    print("  Fixing the destination removes only about half the uncertainty.")
    return r, g, ST


# ---------------------------------------------------------------------------
# 4. Two paths, same destination, very different outcome
# ---------------------------------------------------------------------------


def two_paths(r):
    ST = r.S[:, -1]
    m = np.where(np.abs(ST - K_STRIKE) < 0.4)[0]
    best, worst = m[np.argmax(r.pnl[m])], m[np.argmin(r.pnl[m])]

    print("\n" + "=" * 74)
    print("4. TWO PATHS THAT ENDED IN THE SAME PLACE")
    print("=" * 74)
    N = r.S.shape[1] - 1
    for lbl, i in [("PINNED", best), ("WANDERED", worst)]:
        S = r.S[i]
        print(f"\n  {lbl}:  P&L = {r.pnl[i]:+.4f}   ended at {S[-1]:.3f}")
        print(f"    spot every 5 days: " + " ".join(f"{S[int(k * N / 6)]:7.2f}" for k in range(7)))
        print(f"    stayed within $3 of the strike {np.mean(np.abs(S - K_STRIKE) < 3):.1%} of the time")
        print(f"    dollar-gamma integral  {r.dollar_gamma_integral[i]:7.2f}")
        print(f"    its OWN realized vol   {r.realized_vol[i]:7.4f}")

    print(f"\n  Same destination. The WANDERED path realized MORE volatility")
    print(f"  ({r.realized_vol[worst]:.4f} vs {r.realized_vol[best]:.4f}) and still made less than half as much,")
    print(f"  because it spent its time where gamma was worth nothing.")

    near = np.mean(np.abs(r.S - K_STRIKE) < 3, axis=1)
    print(f"\n  Plain-language proxy: corr(time spent within $3 of strike, gamma")
    print(f"  integral) = {np.corrcoef(near, r.dollar_gamma_integral)[0, 1]:.4f}. 'Time near the strike' is most of it.")
    return best, worst


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_profile(path="figures/day4_gamma_profile.png"):
    spots = np.linspace(80, 125, 400)
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    for c, d in zip([BLUE, ORANGE, AQUA], [30, 15, 5]):
        ax.plot(spots, bs.dollar_gamma(spots, K_STRIKE, d / 365, 0.0, SIGMA_I),
                color=c, linewidth=2, label=f"{d} days to expiry")
    ax.axvline(K_STRIKE, color=MUTED, linewidth=1, linestyle=":")
    ax.annotate("strike", xy=(K_STRIKE, ax.get_ylim()[1] * 0.96), xytext=(5, 0),
                textcoords="offset points", color=MUTED, fontsize=9)
    style(ax, "Gamma is only worth money near the strike -- and increasingly so",
          "spot price", r"dollar gamma  $S^2\Gamma$")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_predictors(r, g, ST, path="figures/day4_what_predicts.png"):
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))
    panels = [
        (ST, "terminal price", f"corr {np.corrcoef(r.pnl, ST)[0,1]:+.3f}", MUTED),
        (r.realized_vol, "the path's own realized vol",
         f"corr {np.corrcoef(r.pnl, r.realized_vol)[0,1]:+.3f}", ORANGE),
        (g, r"$\frac{1}{2}(\sigma_i^2-\sigma_r^2)\int S^2\Gamma dt$",
         f"corr {np.corrcoef(r.pnl, g)[0,1]:+.3f}", BLUE),
    ]
    for ax, (x, name, note, col) in zip(axes, panels):
        ax.scatter(x, r.pnl, s=4, color=col, alpha=0.25, edgecolor="none")
        style(ax, f"vs {name}\n{note}", name, "simulated P&L ($)")
    lims = [min(g.min(), r.pnl.min()), max(g.max(), r.pnl.max())]
    axes[2].plot(lims, lims, color=INK, linewidth=1.4)
    fig.suptitle("Neither where it ended nor how much it moved predicts your P&L",
                 color=INK, fontsize=12, x=0.006, ha="left", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_two_paths(r, best, worst, path="figures/day4_two_paths.png"):
    N = r.S.shape[1] - 1
    t = np.linspace(0, 30, N + 1)
    dt = T / N
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))

    for i, c, lbl in [(best, BLUE, "pinned"), (worst, ORANGE, "wandered")]:
        ax1.plot(t, r.S[i], color=c, linewidth=1.6,
                 label=f"{lbl}:  P&L {r.pnl[i]:+.3f}")
        dg = np.cumsum(bs.dollar_gamma(r.S[i, :-1], K_STRIKE,
                                       np.maximum(T - np.arange(N) * dt, 1e-12),
                                       0.0, SIGMA_I) * dt)
        ax2.plot(t[:-1], 0.5 * (SIGMA_I**2 - SIGMA_R**2) * dg, color=c, linewidth=1.8,
                 label=f"{lbl}")
    ax1.axhline(K_STRIKE, color=MUTED, linewidth=1, linestyle=":")
    style(ax1, "Same destination, different route", "days", "spot")
    ax1.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    style(ax2, "Running P&L earned, from the gamma integral", "days", "cumulative P&L ($)")
    ax2.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    gamma_profile()
    formula_vs_simulation()
    r, g, ST = what_does_not_matter()
    best, worst = two_paths(r)
    print("\n" + "=" * 74)
    print("FIGURES")
    print("=" * 74)
    fig_profile()
    fig_predictors(r, g, ST)
    fig_two_paths(r, best, worst)
