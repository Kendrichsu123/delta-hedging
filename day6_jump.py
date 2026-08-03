"""Day 6: what a scheduled jump does, and the FOMC trade.

Day 5 established that this model produces a POSITIVELY skewed P&L and, at fine
rebalancing, no losses at all in 40,000 trades. Both are false about the world.
It named two suspect assumptions and tested the first (known constant vol),
which alone flips the skew sign. This file tests the second.

WHAT A SCHEDULED JUMP IS

A gap at a KNOWN time of UNKNOWN size. Earnings, an FOMC announcement, a
scheduled court ruling. The distinguishing feature is not that it is large --
it is that you cannot rebalance during it. Every other risk in this project
shrinks when you hedge more often, because more rebalancing means smaller moves
between trades. A jump does not shrink. You hold whatever delta you had, the
stock gaps, and you eat the gamma cost of the entire move at once.

That is a structural difference, not a quantitative one, and it makes the
central prediction of this file easy to state: P(loss) should stop going to
zero as N grows.

WHY IT IS PRICED IN SHORT EXPIRIES

A jump contributes jump_vol^2 of variance regardless of the option's tenor,
while diffusion contributes sigma^2 * T. So fair implied vol is

    sqrt(sigma^2 + jump_vol^2 / T)

which blows up as T shrinks. The same event is worth 13.7 vol points on a
one-day option and 0.03 on a two-year one. That term-structure collapse is
exactly what the vol-surface project measured around the July 2026 FOMC.

Run:  python day6_jump.py
"""

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import brentq

import bs
from hedge import simulate_hedge
from paths import gbm_paths

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

T30 = 30 / 365
SD, SJ = 0.15, 0.03          # diffusive vol, jump size for the main comparison
EDGE = 0.05                  # vol points sold above fair, held constant


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


def fair_vol(sigma_diff, jump_vol, T):
    """Implied vol that correctly prices diffusion plus a scheduled jump."""
    return np.sqrt(sigma_diff**2 + jump_vol**2 / T)


# ---------------------------------------------------------------------------
# 1. The structural result
# ---------------------------------------------------------------------------


def jump_vs_nojump(n_paths=40_000, seed=101):
    fn, fj = fair_vol(SD, 0.0, T30), fair_vol(SD, SJ, T30)

    print("=" * 78)
    print("1. A SCHEDULED JUMP, PRICED CORRECTLY, STILL RUINS THE DISTRIBUTION")
    print("=" * 78)
    print(f"  fair vol without jump : {fn:.4f}")
    print(f"  fair vol with 3% jump : {fj:.4f}   (the jump is worth {(fj-SD)*100:.2f} vol pts at 30 days)")
    print(f"\n  Both columns sell {EDGE*100:.0f} vol points ABOVE their own fair value, so the")
    print("  EDGE is identical and only the jump's presence differs. If the jump")
    print("  merely made you underpaid, holding edge constant would remove the effect.\n")
    print(f"{'N':>6} | {'NO JUMP':^36} | {'WITH JUMP (paid fairly for it)':^36}")
    print(f"{'':>6} | {'mean':>9}{'std':>8}{'P(loss)':>9}{'skew':>10} | {'mean':>9}{'std':>8}{'P(loss)':>9}{'skew':>10}")

    rows = []
    for N in [8, 30, 64, 128, 512, 2048]:
        a = simulate_hedge(sigma_real=SD, sigma_implied=fn + EDGE, N=N,
                           n_paths=n_paths, seed=seed, T=T30).pnl
        b = simulate_hedge(sigma_real=SD, sigma_implied=fj + EDGE, N=N,
                           n_paths=n_paths, seed=seed, T=T30,
                           jump_at=0.5, jump_vol=SJ).pnl
        rows.append((N, a, b))
        print(f"{N:6d} | {a.mean():9.4f}{a.std():8.4f}{(a < 0).mean():9.4f}{skew(a):+10.3f} "
              f"| {b.mean():9.4f}{b.std():8.4f}{(b < 0).mean():9.4f}{skew(b):+10.3f}")

    print("\n  Three things, and the first is the point of the whole day:")
    print("   - P(loss) STOPS FALLING. Without the jump it goes 13.3% -> 0.0%. With")
    print("     it, 20.3% -> 12.2% and then flat. Rebalancing 2048 times instead of")
    print("     128 buys nothing, because you cannot rebalance through a gap.")
    print("   - The skew flips hard negative and gets MORE negative with N:")
    print("     +0.42 -> -0.02 without, versus -1.14 -> -1.60 with.")
    print("   - The means are identical. You were paid fairly. It did not help.")
    return rows


# ---------------------------------------------------------------------------
# 2. Why event premium lives in the front
# ---------------------------------------------------------------------------


def term_structure(jump_vol=0.0095 / np.sqrt(2 / np.pi), sigma_diff=0.12):
    print("\n" + "=" * 78)
    print("2. TERM STRUCTURE: THE SAME EVENT IS WORTH WILDLY DIFFERENT VOL")
    print("=" * 78)
    print(f"  fair vol = sqrt(sigma_diff^2 + jump_vol^2 / T), sigma_diff={sigma_diff:.0%},")
    print(f"  jump_vol={jump_vol*100:.2f}% (the July 2026 FOMC as priced, see section 3)\n")
    print(f"{'expiry':>10} {'T (yrs)':>9} {'fair vol':>10} {'event adds':>12}")
    out = []
    for d, lbl in [(1, "1 day"), (2, "2 days"), (3, "3 days"), (5, "5 days"),
                   (7, "1 week"), (30, "1 month"), (90, "3 months"),
                   (365, "1 year"), (730, "2 years")]:
        T = d / 365
        f = fair_vol(sigma_diff, jump_vol, T)
        out.append((d, T, f))
        print(f"{lbl:>10} {T:9.4f} {f:10.4f} {(f - sigma_diff) * 100:11.2f}pt")

    print("\n  CROSS-CHECK against vol-surface, which measured front expiries falling")
    print("  5-7 vol points when this event resolved, and the 2-year moving 0.3.")
    print("   - 5-7 pts here corresponds to a 2-4 day expiry. Consistent.")
    print("   - 2 years gets 0.03pt, so the 0.3 observed there was NOT the event.")
    print("     Same inference vol-surface drew, reached from the opposite direction:")
    print("     that project inferred the jump from the surface, this one predicts")
    print("     the surface from the jump.")
    return out


# ---------------------------------------------------------------------------
# 3. The FOMC trade
# ---------------------------------------------------------------------------


SDIFF_FOMC, T_FOMC, N_FOMC = 0.12, 1 / 365, 48
ACTUAL_MOVE = -0.0067   # SPY closed -0.67% on 29 July 2026


def fomc_pnl(J, iv, n=20_000, seed=11):
    """P&L of selling and hedging a 1-day ATM option through a KNOWN jump J."""
    S0 = K = 100.0
    S = gbm_paths(S0, 0.0, SDIFF_FOMC, T_FOMC, N_FOMC, n, seed=seed)
    S[:, N_FOMC // 2 + 1:] *= np.exp(J)
    dt = T_FOMC / N_FOMC
    cash = np.full(n, float(bs.bs_price(S0, K, T_FOMC, 0.0, iv)))
    sh = np.zeros(n)
    for i in range(N_FOMC):
        d = bs.bs_delta(S[:, i], K, T_FOMC - i * dt, 0.0, iv)
        cash -= (d - sh) * S[:, i]
        sh = d
    return (cash + sh * S[:, -1] - bs.payoff(S[:, -1], K)).mean()


def fomc():
    print("\n" + "=" * 78)
    print("3. WOULD SELLING THE JULY 2026 FOMC HAVE PAID?")
    print("=" * 78)
    print("  vol-surface measured the market pricing the announcement at +/-0.95%")
    print("  of SPY. That phrase is ambiguous and the ambiguity is worth 2x in the")
    print("  answer, so both readings are carried through.\n")

    results = {}
    for lbl, sJ in [("0.95% read as a standard deviation", 0.0095),
                    ("0.95% read as E|move|", 0.0095 / np.sqrt(2 / np.pi))]:
        iv = fair_vol(SDIFF_FOMC, sJ, T_FOMC)
        prem = float(bs.bs_price(100.0, 100.0, T_FOMC, 0.0, iv))
        be = brentq(lambda J: fomc_pnl(J, iv), 0.001, 0.03, xtol=1e-6)
        act = fomc_pnl(ACTUAL_MOVE, iv)
        rng = np.random.default_rng(3)
        draws = rng.standard_normal(200_000) * sJ
        results[lbl] = (sJ, iv, prem, be, act)

        print(f"  {lbl}")
        print(f"    sigma_J {sJ*100:.2f}%  ->  1-day implied vol {iv:.4f}, premium {prem:.4f}")
        print(f"    break-even move          +/-{be*100:.3f}%")
        print(f"    SPY actually moved       {ACTUAL_MOVE*100:.2f}%")
        print(f"    P&L                      {act:+.4f}  = {act/prem*100:+.1f}% of premium")
        print(f"    ex-ante P(profit)        {(np.abs(draws) < be).mean():.3f}\n")

    print("  It paid, under both readings. But read the last line before")
    print("  celebrating: ex ante this was about a 62/38 proposition, not a")
    print("  free lunch. And n=1. One event, one outcome, no error bar. The")
    print("  honest claim is 'the priced premium exceeded the realized move on")
    print("  this occasion', not 'selling FOMC events is profitable'.")
    return results


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_ploss(rows, path="figures/day6_ploss_vs_n.png"):
    N = np.array([r[0] for r in rows], dtype=float)
    a = np.array([(r[1] < 0).mean() for r in rows]) * 100
    b = np.array([(r[2] < 0).mean() for r in rows]) * 100
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.plot(N, b, color=ORANGE, linewidth=2.2, marker="o", markersize=5,
            label="with a scheduled jump")
    ax.plot(N, a, color=BLUE, linewidth=2.2, marker="o", markersize=5,
            label="no jump")
    ax.set_xscale("log")
    ax.annotate("hedging more\nstops helping", xy=(512, b[-2]), xytext=(-6, 26),
                textcoords="offset points", color=ORANGE, fontsize=9, ha="center")
    ax.annotate("goes to zero", xy=(512, a[-2]), xytext=(0, 18),
                textcoords="offset points", color=BLUE, fontsize=9, ha="center")
    style(ax, "You cannot rebalance through a gap  (same edge in both cases)",
          "rebalances N (log)", "P(loss)  %")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_shapes(rows, path="figures/day6_distributions.png"):
    _, a, b = [r for r in rows if r[0] == 512][0]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bins = np.linspace(-3.0, 1.6, 150)
    ax.hist(a, bins=bins, color=BLUE, alpha=0.8, edgecolor="none",
            density=True, label=f"no jump   (skew {skew(a):+.2f})")
    ax.hist(b, bins=bins, color=ORANGE, alpha=0.75, edgecolor="none",
            density=True, label=f"with jump (skew {skew(b):+.2f})")
    ax.axvline(0, color=INK, linewidth=1.2)
    style(ax, "N=512, identical edge and identical mean. Only the tail differs.",
          "terminal P&L ($ per share)", "density")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_term(out, path="figures/day6_term_structure.png"):
    d = np.array([o[0] for o in out], dtype=float)
    f = np.array([o[2] for o in out])
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.plot(d, f * 100, color=BLUE, linewidth=2.2, marker="o", markersize=5)
    ax.axhline(SDIFF_FOMC * 100, color=MUTED, linewidth=1.2, linestyle=":")
    ax.annotate("no-event baseline (12%)", xy=(400, SDIFF_FOMC * 100), xytext=(0, 7),
                textcoords="offset points", color=MUTED, fontsize=9, ha="right")
    ax.axhspan(17, 19, color=ORANGE, alpha=0.15)
    ax.annotate("vol-surface measured a 5-7pt\ndrop here (2-4 day expiries)",
                xy=(3, 18), xytext=(16, 6), textcoords="offset points",
                color=ORANGE, fontsize=9)
    ax.set_xscale("log")
    style(ax, "One event, priced across the curve: 13.7 vol pts at 1 day, 0.03 at 2 years",
          "days to expiry (log)", "fair implied vol  %")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_fomc(results, path="figures/day6_fomc.png"):
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    Js = np.linspace(-0.025, 0.025, 41)
    for (lbl, (sJ, iv, prem, be, act)), col in zip(results.items(), [BLUE, ORANGE]):
        y = [fomc_pnl(J, iv) for J in Js]
        ax.plot(Js * 100, y, color=col, linewidth=2.2,
                label=f"{lbl}  (break-even ±{be*100:.2f}%)")
    ax.axhline(0, color=INK, linewidth=1.1)
    ax.axvline(ACTUAL_MOVE * 100, color=AQUA, linewidth=2, linestyle="--")
    ax.annotate("SPY actually\nmoved -0.67%", xy=(ACTUAL_MOVE * 100, -0.42),
                xytext=(-8, 0), textcoords="offset points", color=AQUA,
                fontsize=9, ha="right")
    style(ax, "Selling the FOMC event: P&L against the move that actually happened",
          "realized jump  %", "P&L ($ per share)")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=8.5, loc="lower center")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    rows = jump_vs_nojump()
    out = term_structure()
    results = fomc()
    print("\n" + "=" * 78)
    print("FIGURES")
    print("=" * 78)
    fig_ploss(rows)
    fig_shapes(rows)
    fig_term(out)
    fig_fomc(results)
