"""Day 8: run the engine on real price paths instead of simulated ones.

Days 1-7 never touched market data. Every conclusion about how this model
disagrees with reality was reached by comparing against folklore, not against a
measurement. This day closes that gap -- partially, and with a sample small
enough that the limitation has to lead rather than follow.

WHY THIS IS BOTH THE MOST AND LEAST INFORMATIVE DAY

Real paths carry fat tails, volatility clustering, and gaps for free, without any
of them being modelled. That is the appeal. It is also the difficulty: they
arrive TOGETHER, so a difference in the P&L cannot be attributed to any one of
them. Day 6 could say "the no-gaps assumption causes the vanishing loss rate"
precisely because it changed one thing. Day 8 changes everything at once and can
only say "reality differs, by this much."

That is why it comes last rather than first. It is a check on the conclusions,
not a route to them.

THE DATA

data/aapl_daily.csv -- 506 adjusted daily closes, Feb 2015 to Feb 2017. Real, and
small: 21-day windows give only about 24 non-overlapping months. Any statistic
here has an effective sample size in the tens, not the thousands, and the file
says so everywhere rather than quoting confident numbers.

To point this at your own data, supply any CSV with a date column and a close
column and pass the column name. SPY over a decade would be strictly better and
is a one-line change.

Run:  python day8_real_paths.py
"""

import csv

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hedge import hedge_paths
from paths import gbm_paths

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e5e2"

CSV_PATH, CLOSE_COL = "data/aapl_daily.csv", "AAPL.Adjusted"
W = 21                 # trading days in the option's life (~30 calendar days)
T = 30 / 365
EDGE = 0.05            # vol points sold above the full-sample realized vol
TRADING_DAYS = 252


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


def load_closes(path=CSV_PATH, col=CLOSE_COL):
    rows = list(csv.DictReader(open(path)))
    return np.array([float(r[col]) for r in rows]), rows[0]["Date"], rows[-1]["Date"]


# ---------------------------------------------------------------------------
# 1. How real returns differ from the model's
# ---------------------------------------------------------------------------


def characterise(lr):
    print("=" * 76)
    print("1. WHAT REAL RETURNS HAVE THAT GBM DOES NOT")
    print("=" * 76)
    sig = lr.std() * np.sqrt(TRADING_DAYS)
    kurt = ((lr - lr.mean()) ** 4).mean() / lr.std() ** 4
    clus = np.corrcoef(np.abs(lr[:-1]), np.abs(lr[1:]))[0, 1]
    z = np.random.default_rng(0).standard_normal(len(lr))
    print(f"  annualized vol                   {sig:.4f}")
    print(f"  daily return skew                {skew(lr):+.3f}")
    print(f"  daily return kurtosis            {kurt:8.3f}   (normal = 3.000)")
    print(f"  days with |move| > 4 sd          {(np.abs(lr - lr.mean()) > 4*lr.std()).sum():8d}   (normal expects ~0.03)")
    print(f"  vol clustering corr(|r_t|,|r_t-1|) {clus:+.4f}")
    print(f"    same for iid normal              {np.corrcoef(np.abs(z[:-1]), np.abs(z[1:]))[0,1]:+.4f}")
    print("\n  Fat tails and clustering, neither of them modelled. This is the")
    print("  appeal of real paths and also why attribution is impossible here:")
    print("  both arrive at once, along with gaps.")
    return sig


# ---------------------------------------------------------------------------
# 2. The loop back to Day 2
# ---------------------------------------------------------------------------


def vol_dispersion(lr, sig, seed=0):
    print("\n" + "=" * 76)
    print("2. HOW MUCH DOES REALIZED VOL ACTUALLY MOVE MONTH TO MONTH?")
    print("=" * 76)
    print("  Day 2 swept a forecast error s from 0 to 5 vol points AS AN ASSUMPTION")
    print("  and found P(loss) went 2.0% -> 16.1%. Real data can price that sweep.\n")
    wins = np.array([lr[i:i + W] for i in range(len(lr) - W + 1)])
    rv_real = wins.std(axis=1) * np.sqrt(TRADING_DAYS)
    rng = np.random.default_rng(seed)
    rv_gbm = (rng.standard_normal((len(wins), W)) * sig / np.sqrt(TRADING_DAYS)
              ).std(axis=1) * np.sqrt(TRADING_DAYS)
    print(f"{'':>12} {'mean':>8} {'std':>8} {'p5':>8} {'p95':>8}")
    for lbl, v in [("real", rv_real), ("GBM", rv_gbm)]:
        print(f"{lbl:>12} {v.mean():8.4f} {v.std():8.4f} "
              f"{np.percentile(v, 5):8.4f} {np.percentile(v, 95):8.4f}")
    print(f"\n  Real 21-day realized vol has std {rv_real.std()*100:.2f} vol points.")
    print(f"  GBM with the same average has    {rv_gbm.std()*100:.2f}.  Ratio {rv_real.std()/rv_gbm.std():.2f}x.")
    print(f"\n  So Day 2's HARSHEST assumed scenario (s = 5 points) was still")
    print(f"  optimistic. The month-to-month spread of realized vol alone is")
    print(f"  {rv_real.std()*100:.1f} points here, before any forecast error is added on top.")
    print("  Caveat: these windows overlap heavily, which inflates the apparent")
    print("  sample; and AAPL is a single name, more volatile than an index.")
    return rv_real, rv_gbm


# ---------------------------------------------------------------------------
# 3. Hedging real paths
# ---------------------------------------------------------------------------


def block_bootstrap(lr, n_paths, block=5, seed=1):
    """Resample blocks of CONSECUTIVE returns, so volatility clustering survives.

    An iid bootstrap of single days would destroy exactly the structure we are
    trying to keep -- it would rebuild something close to GBM out of real
    returns, which is the opposite of the point.
    """
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(W / block))
    starts = rng.integers(0, len(lr) - block, size=(n_paths, n_blocks))
    out = np.concatenate([lr[s:s + block] for s in starts.ravel()]).reshape(
        n_paths, n_blocks * block)[:, :W]
    return out


def paths_from_returns(lr_windows, S0=100.0):
    log_S = np.log(S0) + np.concatenate(
        [np.zeros((len(lr_windows), 1)), np.cumsum(lr_windows, axis=1)], axis=1)
    return np.exp(log_S)


def hedge_comparison(lr, sig, seed=1):
    print("\n" + "=" * 76)
    print("3. HEDGING REAL PATHS vs GBM MATCHED ON VOLATILITY")
    print("=" * 76)

    overlap = np.array([lr[i:i + W] for i in range(len(lr) - W + 1)])

    # Match on the MEAN WINDOW vol, not the full-sample vol. Those are not the
    # same number: full-sample vol is sqrt(average variance) while mean window
    # vol is average of sqrt(variance), and sqrt is concave, so Jensen makes the
    # second strictly smaller. The gap grows with how dispersed the window vols
    # are -- 1.9 points for AAPL, 3.4 for SPY.
    #
    # Using the full-sample vol as the reference silently hands the REAL paths
    # more edge than the GBM control, because the typical real window realizes
    # less than the full-sample figure while GBM realizes its sigma by
    # construction. Measured on SPY that inflated the real mean by 53%, which
    # exactly matched the variance-edge ratio -- i.e. the entire mean difference
    # was the mismatch, not a property of real returns.
    ref = (overlap.std(axis=1) * np.sqrt(TRADING_DAYS)).mean()
    si = ref + EDGE
    print(f"  full-sample vol      {sig:.4f}")
    print(f"  mean 21-day window   {ref:.4f}   <- the reference, see comment in source")
    print(f"  sell at              {si:.4f}   ({EDGE*100:.0f} vol points above it)")
    print(f"  hedge once per trading day (N={W}); GBM sigma set to {ref:.4f} so BOTH")
    print("  face the same edge against their own typical realized vol. The only")
    print("  remaining difference is the shape of the return distribution.\n")

    boot = block_bootstrap(lr, 20_000, seed=seed)
    rng = np.random.default_rng(seed)
    gbm = gbm_paths(100.0, 0.0, ref, T, W, 20_000, seed=seed)

    sets = [
        ("real, overlapping windows", paths_from_returns(overlap)),
        ("real, block bootstrap", paths_from_returns(boot)),
        ("GBM (control)", gbm),
    ]
    print(f"{'':>28} {'n':>7} {'mean':>9} {'std':>8} {'P(loss)':>9} {'skew':>9} {'p5':>9}")
    out = {}
    for lbl, S in sets:
        pnl, prem, _, _ = hedge_paths(S, 100.0, T, sigma_implied=si)
        out[lbl] = pnl
        print(f"{lbl:>28} {len(pnl):7d} {pnl.mean():9.4f} {pnl.std():8.4f} "
              f"{(pnl < 0).mean():9.4f} {skew(pnl):+9.3f} {np.percentile(pnl, 5):9.4f}")

    print(f"\n  The overlapping-window row has n={len(overlap)} but only about")
    print(f"  {len(lr)//W} INDEPENDENT months in it. Treat it as an illustration.")
    print("  The block bootstrap has many paths but they are all resampled from")
    print("  the same two years, so it inherits that period's regime -- it widens")
    print("  the sample without adding information.")
    return out


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_vol(rv_real, rv_gbm, path="figures/day8_vol_dispersion.png"):
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bins = np.linspace(0.05, 0.50, 46)
    ax.hist(rv_real, bins=bins, color=ORANGE, alpha=0.8, edgecolor="none",
            density=True, label=f"real (std {rv_real.std()*100:.1f} vol pts)")
    ax.hist(rv_gbm, bins=bins, color=BLUE, alpha=0.7, edgecolor="none",
            density=True, label=f"GBM, same average (std {rv_gbm.std()*100:.1f})")
    style(ax, "Realized vol moves far more in reality than the model allows",
          "21-day annualized realized vol", "density")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


def fig_pnl(out, path="figures/day8_real_vs_gbm.png"):
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bins = np.linspace(-4.0, 2.5, 120)
    ax.hist(out["GBM (control)"], bins=bins, color=BLUE, alpha=0.8, edgecolor="none",
            density=True, label=f"GBM (skew {skew(out['GBM (control)']):+.2f})")
    ax.hist(out["real, block bootstrap"], bins=bins, color=ORANGE, alpha=0.7,
            edgecolor="none", density=True,
            label=f"real returns (skew {skew(out['real, block bootstrap']):+.2f})")
    ax.axvline(0, color=INK, linewidth=1.2)
    style(ax, "Same volatility, same edge, different return shape",
          "terminal P&L ($ per share)", "density")
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    print(f"  wrote {path}")


if __name__ == "__main__":
    import os

    os.makedirs("figures", exist_ok=True)
    px, d0, d1 = load_closes()
    lr = np.diff(np.log(px))
    print(f"data: {CSV_PATH}, {len(px)} closes, {d0} -> {d1}\n")
    sig = characterise(lr)
    rv_real, rv_gbm = vol_dispersion(lr, sig)
    out = hedge_comparison(lr, sig)
    print("\n" + "=" * 76)
    print("FIGURES")
    print("=" * 76)
    fig_vol(rv_real, rv_gbm)
    fig_pnl(out)
