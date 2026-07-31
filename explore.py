"""Interactive exploration of the Day 1 engine.

HOW TO USE THIS IN VS CODE

Each block below starts with `# %%`, which VS Code's Python extension turns into
a runnable cell with a "Run Cell" link above it (needs the Python + Jupyter
extensions). Click a cell, hit Shift+Enter, and the output appears in an
interactive window. Variables persist between cells, so you can poke at things
afterwards in the REPL box at the bottom.

If you'd rather not use cells, `python explore.py` runs the whole file top to
bottom and shows every plot.

Work through it in order. The last section has exercises with no answers filled
in -- do those before reading docs/exercises.md.
"""

# %%
import matplotlib.pyplot as plt
import numpy as np

import bs
from hedge import (
    simulate_hedge,
    theory_pnl_from_gamma,
    theory_pnl_hedged_at_realized,
)
from paths import gbm_paths, realized_vol

# Categorical colors, assigned in fixed order and never cycled.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED = "#0b0b0b", "#52514e"


def style(ax, title="", xlabel="", ylabel=""):
    """Recessive axes and grid, so the data is the loudest thing on the chart."""
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=10)
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.grid(True, color="#e5e5e2", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c9c9c4")
    ax.tick_params(colors=MUTED, labelsize=9)
    return ax


print("imports OK")

# %%
# ---------------------------------------------------------------------------
# 1. One option. Get a feel for the numbers before anything moves.
# ---------------------------------------------------------------------------
S0, K, T, r, sigma = 100.0, 100.0, 30 / 365, 0.0, 0.20

print(f"price  {bs.bs_price(S0, K, T, r, sigma):.4f}")
print(f"delta  {bs.bs_delta(S0, K, T, r, sigma):.4f}")
print(f"gamma  {bs.bs_gamma(S0, K, T, r, sigma):.5f}")
print(f"theta  {bs.bs_theta(S0, K, T, r, sigma):.4f}  per year")
print(f"vega   {bs.bs_vega(S0, K, T, r, sigma):.4f}")

# The ATM rule of thumb: price ~= 0.4 * S * sigma * sqrt(T).
print(f"\nrule of thumb 0.4*S*sigma*sqrt(T) = {0.4 * S0 * sigma * np.sqrt(T):.4f}")

# The identity everything rests on (at r=0):  Theta = -1/2 * sigma^2 * S^2 * Gamma
lhs = bs.bs_theta(S0, K, T, r, sigma)
rhs = -0.5 * sigma**2 * S0**2 * bs.bs_gamma(S0, K, T, r, sigma)
print(f"\nTheta          = {lhs:.6f}")
print(f"-1/2 s^2 S^2 G = {rhs:.6f}   <- these must be equal")

# %%
# ---------------------------------------------------------------------------
# 2. Short gamma bleeds. Reproduce the round-trip table by hand.
# ---------------------------------------------------------------------------
# Stock goes 100 -> X -> 100 with NO time passing, so this isolates the hedging
# effect. You buy shares on the way up and sell them back lower.
print(f"{'X':>6} {'delta@X':>9} {'shares':>9} {'round-trip $':>13}")
d0 = bs.bs_delta(100.0, K, T, r, sigma)
for X in [101.0, 102.0, 105.0, 110.0]:
    dX = bs.bs_delta(X, K, T, r, sigma)
    shares = dX - d0
    pnl = -shares * (X - 100.0)  # bought `shares` at X, sold back at 100
    print(f"{X:6.0f} {dX:9.4f} {shares:+9.4f} {pnl:13.4f}")

# Double the move -> roughly 4x the loss. The cost is QUADRATIC in the move.

# %%
# ---------------------------------------------------------------------------
# 3. Break-even. What daily move exactly cancels the theta you collect?
# ---------------------------------------------------------------------------
G = bs.bs_gamma(100.0, K, T, r, sigma)
theta_2d = bs.bs_price(100.0, K, T, r, sigma) - bs.bs_price(100.0, K, T - 2 / 365, r, sigma)
dS = np.sqrt(theta_2d / G)  # a round trip is 2 moves: 2*(1/2)*G*dS^2 = G*dS^2

print(f"theta over 2 days   {theta_2d:.5f}")
print(f"gamma               {G:.5f}")
print(f"break-even move     {dS:.4f}  ({dS:.3f}% daily)")
print(f"annualized          {dS / 100 * np.sqrt(365) * 100:.2f}%")
print(f"implied vol sold at 20.00%   <- the break-even IS the implied vol")

# %%
# ---------------------------------------------------------------------------
# 4. Look at some paths.
# ---------------------------------------------------------------------------
S = gbm_paths(100.0, 0.0, 0.20, T, 30, 200, seed=1)
t_grid = np.linspace(0, T * 365, 31)

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(t_grid, S[:60].T, color=BLUE, linewidth=0.8, alpha=0.35)
ax.axhline(K, color=ORANGE, linewidth=2, label="strike")
style(ax, "60 simulated paths, 30 days at 20% vol", "days", "spot")
ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
plt.tight_layout()
plt.show()

print(f"realized vol of this sample: {realized_vol(S, T).mean():.4f}  (asked for 0.2000)")

# %%
# ---------------------------------------------------------------------------
# 5. The P&L distribution. Sell 20% vol, stock realizes 15%.
# ---------------------------------------------------------------------------
res = simulate_hedge(
    sigma_real=0.15, sigma_implied=0.20, N=30, n_paths=20_000, seed=7
)
s = res.summary()
for key, value in s.items():
    print(f"{key:>8}  {value:+.4f}")
print(f"\npremium received: {res.premium:.4f}")
print(f"closed form mean: {theory_pnl_hedged_at_realized(100, 100, T, 0.0, 0.15, 0.20):.4f}")

fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(res.pnl, bins=80, color=BLUE, edgecolor="none")
ax.axvline(0, color=MUTED, linewidth=1.5, linestyle="--")
ax.axvline(res.pnl.mean(), color=ORANGE, linewidth=2)
style(ax, "P&L: sold 20% vol, stock realized 15%, hedged 30x", "P&L ($)", "paths")
ax.text(res.pnl.mean(), ax.get_ylim()[1] * 0.92, f"  mean {res.pnl.mean():.3f}",
        color=ORANGE, fontsize=9)
plt.tight_layout()
plt.show()

# %%
# ---------------------------------------------------------------------------
# 6. The two hedging strategies, side by side. This is the money comparison.
# ---------------------------------------------------------------------------
at_implied = simulate_hedge(sigma_real=0.15, sigma_implied=0.20, N=256,
                           n_paths=20_000, seed=8)
at_realized = simulate_hedge(sigma_real=0.15, sigma_implied=0.20, sigma_hedge=0.15,
                             N=256, n_paths=20_000, seed=8)

fig, ax = plt.subplots(figsize=(7, 4))
bins = np.linspace(-0.4, 1.6, 90)
ax.hist(at_implied.pnl, bins=bins, color=BLUE, alpha=0.75,
        edgecolor="none", label="hedge at implied (20%)")
ax.hist(at_realized.pnl, bins=bins, color=ORANGE, alpha=0.75,
        edgecolor="none", label="hedge at realized (15%)")
style(ax, "Same mean, very different risk (N=256)", "P&L ($)", "paths")
ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
plt.tight_layout()
plt.show()

print(f"hedge at implied:  mean {at_implied.pnl.mean():.4f}  std {at_implied.pnl.std():.4f}")
print(f"hedge at realized: mean {at_realized.pnl.mean():.4f}  std {at_realized.pnl.std():.4f}")

# %%
# ---------------------------------------------------------------------------
# 7. Where the money comes from: P&L vs the dollar-gamma integral.
# ---------------------------------------------------------------------------
res = simulate_hedge(sigma_real=0.15, sigma_implied=0.20, N=1024,
                     n_paths=4_000, seed=9)
predicted = theory_pnl_from_gamma(res.dollar_gamma_integral, 0.15, 0.20)

fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.scatter(predicted, res.pnl, s=6, color=BLUE, alpha=0.3, edgecolor="none")
lims = [min(predicted.min(), res.pnl.min()), max(predicted.max(), res.pnl.max())]
ax.plot(lims, lims, color=ORANGE, linewidth=2)
style(ax, "Simulated P&L vs the dollar-gamma formula (N=1024)",
      r"$\frac{1}{2}(\sigma_i^2-\sigma_r^2)\int S^2\Gamma\,dt$", "simulated P&L ($)")
plt.tight_layout()
plt.show()

print(f"correlation: {np.corrcoef(res.pnl, predicted)[0, 1]:.4f}")

# %%
# ---------------------------------------------------------------------------
# 8. YOUR TURN. Predict each answer BEFORE running. Answers in docs/exercises.md.
# ---------------------------------------------------------------------------
# E1. You sell at 20% and the stock realizes 25%. What is the mean P&L, and
#     what fraction of paths lose money? Predict both, then run:
#
#     simulate_hedge(sigma_real=0.25, sigma_implied=0.20, N=128, n_paths=20_000)
#
# E2. Zero edge, but hedge only ONCE at inception (N=1). The mean should still
#     be ~0. What about the std -- bigger or smaller than N=128, and by roughly
#     what factor?
#
# E3. Redo the break-even calculation from cell 3 for a strike of 110 instead
#     of 100. Both gamma and theta will be much smaller. Does the break-even
#     annualized vol still come out near 20%?
#
# E4. Break the engine on purpose. Copy the hedging loop out of hedge.py, then
#     introduce ONE bug at a time and predict its signature before running:
#       (a) flip the sign on the rebalance:  cash += (target - shares) * S_k
#       (b) hedge using next step's spot:    bs_delta(S[:, k+1], ...)
#       (c) never settle the option: delete the `cash -= bs.payoff(...)` line
#     For each, predict whether the mean P&L goes up or down and roughly how far.
#     Then work out WHICH test in test_day1.py would have caught it.

print("Work through the exercises above before opening docs/exercises.md.")
