"""Delta-hedging simulation: sell an option, hedge it discretely, measure P&L.

WHAT THIS SIMULATES

At t=0 we sell one option and receive a premium computed at the IMPLIED vol.
We immediately buy `delta` shares to neutralize direction, funding the purchase
from the premium and borrowing/lending the rest at rate r. At each of N
rebalancing dates we recompute delta and trade to it. At expiry we liquidate
the stock and pay the option's settlement value. Whatever is left in the bank
account is the P&L.

This is deliberately written as an ACCOUNT, not as a formula. We track cash,
shares, interest, and dividends explicitly and let the P&L fall out. That means
the simulation can disagree with the theory -- which is the whole point, since
the theory is what we are trying to test.

THREE DIFFERENT VOLATILITIES

The single most important thing about this module is that there are three
distinct volatility inputs and conflating any two of them destroys the
experiment:

  sigma_real     what the stock actually does. Drives the simulated paths.
  sigma_implied  what we SOLD at. Sets the premium we receive. Never changes.
  sigma_hedge    what we compute our delta with. Free parameter.

Setting sigma_hedge = sigma_implied is the realistic case: you mark your book
at the market's vol because that is the only one you can observe. Setting
sigma_hedge = sigma_real is the counterfactual: it requires knowing the future,
but it produces a strikingly different P&L distribution, and the comparison is
one of the main results of this project.
"""

from dataclasses import dataclass, field

import numpy as np

import bs
from paths import gbm_paths, realized_vol


@dataclass
class HedgeResult:
    """Outcome of one batch of hedged paths."""

    pnl: np.ndarray                  # (n_paths,) terminal P&L, in dollars
    premium: float                   # option premium received at t=0
    dollar_gamma_integral: np.ndarray  # (n_paths,) discounted int S^2 Gamma dt
    realized_vol: np.ndarray         # (n_paths,) per-path annualized realized vol
    n_rebalances: int
    traded_notional: np.ndarray | None = None  # (n_paths,) cumulative $ traded
    params: dict = field(default_factory=dict)
    S: np.ndarray | None = None      # paths, only if keep_paths=True

    def summary(self):
        p = self.pnl
        n = len(p)
        return {
            "mean": p.mean(),
            "stderr": p.std(ddof=1) / np.sqrt(n),
            "std": p.std(ddof=1),
            "skew": ((p - p.mean()) ** 3).mean() / p.std() ** 3,
            "p_loss": (p < 0).mean(),
            "min": p.min(),
            "max": p.max(),
        }


def simulate_hedge(
    S0=100.0,
    K=100.0,
    T=30 / 365,
    r=0.0,
    q=0.0,
    sigma_real=0.15,
    sigma_implied=0.20,
    sigma_hedge=None,
    N=30,
    n_paths=10_000,
    mu=None,
    cp=1,
    seed=0,
    keep_paths=False,
    jump_at=None,
    jump_vol=0.0,
    cost_bps=0.0,
):
    """Sell one option, delta-hedge it N times, return the P&L distribution.

    sigma_hedge defaults to sigma_implied (the realistic case).
    mu defaults to r (the risk-neutral measure).

    jump_at / jump_vol insert a scheduled gap (see paths.gbm_paths). Note that
    sigma_real then describes only the DIFFUSIVE part; total realized variance
    is sigma_real^2 * T + jump_vol^2.

    Sign convention: we are SHORT the option and LONG the hedge. A positive
    P&L means the trade made money.
    """
    if sigma_hedge is None:
        sigma_hedge = sigma_implied
    if mu is None:
        mu = r

    dt = T / N
    S = gbm_paths(S0, mu, sigma_real, T, N, n_paths, q=q, seed=seed,
                  jump_at=jump_at, jump_vol=jump_vol)

    # Premium received for the option we sold, priced at the implied vol.
    premium = float(bs.bs_price(S0, K, T, r, sigma_implied, q, cp))

    cash = np.full(n_paths, premium)
    shares = np.zeros(n_paths)
    dgamma = np.zeros(n_paths)
    traded = np.zeros(n_paths)   # cumulative notional traded, for cost accounting
    cost_rate = cost_bps * 1e-4

    for k in range(N):
        t = k * dt
        tau = T - t  # time remaining; strictly positive for k = 0 .. N-1

        S_k = S[:, k]

        # Rebalance: trade into the new delta at the current spot.
        target = bs.bs_delta(S_k, K, tau, r, sigma_hedge, q, cp)
        trade = target - shares
        cash -= trade * S_k
        # Proportional cost: you cross a spread on every share, in either
        # direction. Charged on |notional|, so it is always a drain and never
        # a windfall -- unlike the trade itself, which is a transfer.
        if cost_rate:
            notional = np.abs(trade) * S_k
            traded += notional
            cash -= cost_rate * notional
        shares = target

        # Carry the position across [t, t+dt]: interest on cash, dividends on
        # stock. Dividends use the spot at the start of the step, an O(dt)
        # approximation that is exactly zero when q = 0 (the default for all
        # core experiments).
        cash *= np.exp(r * dt)
        cash += shares * S_k * q * dt

        # Accumulate the dollar-gamma integral that the theory predicts the
        # P&L is proportional to. Gamma is taken at the IMPLIED vol, which is
        # what the P&L formula calls for, and discounted to present value.
        dgamma += np.exp(-r * t) * bs.dollar_gamma(S_k, K, tau, r, sigma_implied, q) * dt

    # Expiry: liquidate the stock, settle the option we are short.
    S_T = S[:, N]
    cash += shares * S_T
    if cost_rate:
        # Liquidating the stock at expiry crosses the spread one final time.
        final = np.abs(shares) * S_T
        traded += final
        cash -= cost_rate * final
    cash -= bs.payoff(S_T, K, cp)

    return HedgeResult(
        pnl=cash,
        premium=premium,
        dollar_gamma_integral=dgamma,
        realized_vol=realized_vol(S, T),
        n_rebalances=N,
        traded_notional=traded,
        params=dict(
            S0=S0, K=K, T=T, r=r, q=q,
            sigma_real=sigma_real, sigma_implied=sigma_implied,
            sigma_hedge=sigma_hedge, N=N, n_paths=n_paths, mu=mu, cp=cp, seed=seed,
            jump_at=jump_at, jump_vol=jump_vol, cost_bps=cost_bps,
        ),
        S=S if keep_paths else None,
    )


# ---------------------------------------------------------------------------
# Closed-form predictions to test the simulation against.
# ---------------------------------------------------------------------------


def theory_pnl_hedged_at_realized(S0, K, T, r, sigma_real, sigma_implied, q=0.0, cp=1):
    """Exact terminal P&L when hedging at the realized vol.

    In the continuous limit this strategy's P&L is DETERMINISTIC and known at
    trade time -- it does not depend on the path at all:

        P&L = (V(sigma_implied) - V(sigma_real)) * exp(r*T)

    Reason: the gamma cost you pay and the theta you collect are both computed
    at the same vol, so they cancel exactly, leaving the portfolio to grow at
    the riskless rate from a starting value of (V_implied - V_realized).

    With discrete hedging the mean still lands here and the spread around it
    shrinks like 1/sqrt(N).
    """
    v_implied = float(bs.bs_price(S0, K, T, r, sigma_implied, q, cp))
    v_realized = float(bs.bs_price(S0, K, T, r, sigma_real, q, cp))
    return (v_implied - v_realized) * np.exp(r * T)


def theory_mean_pnl(S0, K, T, r, sigma_real, sigma_implied, q=0.0, cp=1):
    """Expected P&L when hedging at the implied vol.

    Same number as hedging at realized, but only in EXPECTATION and only under
    the risk-neutral measure (mu = r). Individual paths scatter around it,
    and that scatter does not vanish as N grows -- it is path dependence, not
    discretization noise.
    """
    return theory_pnl_hedged_at_realized(S0, K, T, r, sigma_real, sigma_implied, q, cp)


def theory_pnl_from_gamma(dollar_gamma_integral, sigma_real, sigma_implied):
    """P&L predicted by the dollar-gamma formula, path by path.

        P&L = (1/2) * (sigma_implied^2 - sigma_real^2) * integral of S^2*Gamma dt

    In the continuous limit this is EXACT for each individual path, not just on
    average. Comparing it against the simulated P&L path-by-path is the sharpest
    test of the whole framework, and it is what Day 4 is built on.
    """
    return 0.5 * (sigma_implied**2 - sigma_real**2) * dollar_gamma_integral
