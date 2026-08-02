"""Black-Scholes pricing and Greeks.

Vendored from the vol-surface project and extended with gamma/theta, so this
repo clones and runs standalone.

Everything is vectorized over S: the hedging engine prices 10,000 paths in a
single call rather than looping in Python. Convention throughout is cp=+1 for
a call, cp=-1 for a put.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr

_INV_SQRT_2PI = 1.0 / np.sqrt(2.0 * np.pi)

# Time-to-expiry is floored (not branched on) so that T can be an ARRAY: a
# scalar `if T <= 0` raises on arrays, which blocks pricing a whole path's worth
# of maturities in one call. Values at or below zero are masked out by np.where
# afterwards, so the floor never affects a returned number -- it only keeps the
# intermediate arithmetic finite.
_T_FLOOR = 1e-12


def _npdf(x):
    """Standard normal PDF. Inlined rather than scipy.stats.norm.pdf."""
    return _INV_SQRT_2PI * np.exp(-0.5 * x * x)


# ndtr IS the normal CDF; scipy.stats.norm.cdf calls it after a layer of
# argument validation and distribution-object dispatch. Skipping that wrapper
# is bit-identical (verified in test_day1) and makes the hedging loop ~1.6x
# faster, since the loop calls these once per rebalance per path batch.


def _d1_d2(S, K, T, r, sigma, q):
    """The two Black-Scholes arguments. Assumes T > 0 and sigma > 0."""
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    return d1, d1 - sigma * sqrt_T


def payoff(S, K, cp=1):
    """Terminal value of the option. max(S-K, 0) for a call."""
    return np.maximum(cp * (np.asarray(S, dtype=float) - K), 0.0)


def bs_price(S, K, T, r, sigma, q=0.0, cp=1):
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Tp = np.maximum(T, _T_FLOOR)
        d1, d2 = _d1_d2(S, K, Tp, r, sigma, q)
        v = cp * (
            S * np.exp(-q * Tp) * ndtr(cp * d1)
            - K * np.exp(-r * Tp) * ndtr(cp * d2)
        )
    return np.where(T <= 0, payoff(S, K, cp), v)


def bs_delta(S, K, T, r, sigma, q=0.0, cp=1):
    """dV/dS -- the hedge ratio. Shares of stock per option."""
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Tp = np.maximum(T, _T_FLOOR)
        d1, _ = _d1_d2(S, K, Tp, r, sigma, q)
        d = cp * np.exp(-q * Tp) * ndtr(cp * d1)
    # At expiry delta is the indicator of being in the money.
    return np.where(T <= 0, cp * (cp * (S - K) > 0).astype(float), d)


def bs_gamma(S, K, T, r, sigma, q=0.0):
    """d2V/dS2 -- how fast delta goes stale. Same for calls and puts."""
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Tp = np.maximum(T, _T_FLOOR)
        d1, _ = _d1_d2(S, K, Tp, r, sigma, q)
        g = np.exp(-q * Tp) * _npdf(d1) / (S * sigma * np.sqrt(Tp))
    return np.where(T <= 0, 0.0, g)


def bs_vega(S, K, T, r, sigma, q=0.0):
    """dV/dsigma, per 1.00 of vol (not per vol point). Same for calls and puts."""
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Tp = np.maximum(T, _T_FLOOR)
        d1, _ = _d1_d2(S, K, Tp, r, sigma, q)
        v = S * np.exp(-q * Tp) * _npdf(d1) * np.sqrt(Tp)
    return np.where(T <= 0, 0.0, v)


def bs_theta(S, K, T, r, sigma, q=0.0, cp=1):
    """dV/dt, per year. Negative for a long option: it decays."""
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Tp = np.maximum(T, _T_FLOOR)
        d1, d2 = _d1_d2(S, K, Tp, r, sigma, q)
        th = (
            -S * np.exp(-q * Tp) * _npdf(d1) * sigma / (2 * np.sqrt(Tp))
            - cp * r * K * np.exp(-r * Tp) * ndtr(cp * d2)
            + cp * q * S * np.exp(-q * Tp) * ndtr(cp * d1)
        )
    return np.where(T <= 0, 0.0, th)


def implied_vol(price, S, K, T, r, q=0.0, cp=1, lo=1e-6, hi=5.0):
    """Invert bs_price for sigma. Scalar only -- Brent needs a scalar objective.

    Returns nan for any quote we cannot invert meaningfully, rather than
    raising, so one bad row in a chain doesn't kill a whole run.

    Two separate rejections, and the second one matters more than it looks:

    1. Prices outside the no-arbitrage bounds. Brent has no sign change to
       bracket and raises; we return nan.

    2. Prices that DO bracket but land against an endpoint. A price exactly at
       intrinsic returns sigma = lo = 1e-6 -- a real number, not nan, which
       then silently poisons anything downstream that averages or fits it.

    Case 2 is worse than just "the endpoint gets returned", because the
    inversion is catastrophically ill-conditioned there. For S=100, K=90,
    T=30/365, a price of exactly 10.0 gives sigma = 1e-6, while 10.0 + 1e-9
    gives sigma = 0.0635. A one-nanodollar move in the quote swings implied
    vol by 6.3 points. So we reject a BAND around each endpoint, not just the
    endpoint itself: nothing in that region carries information.
    """
    def objective(sigma):
        return bs_price(S, K, T, r, sigma, q, cp) - price

    try:
        sigma = brentq(objective, lo, hi, xtol=1e-12, rtol=1e-10)
    except ValueError:
        return np.nan

    if sigma < lo * 1e3 or sigma > hi * (1 - 1e-6):
        return np.nan
    return sigma


def dollar_gamma(S, K, T, r, sigma, q=0.0):
    """S^2 * Gamma -- gamma expressed in money.

    This is the weight in the P&L integral. Raw gamma is in shares-per-dollar
    and is not comparable across price levels; this is.

    The exact identity carries a discount factor INSIDE the integral, because
    P&L accrues at time t and is worth more at T than at 0:

        PV of P&L = (1/2)(sigma_i^2 - sigma_r^2) * int_0^T e^{-rt} S^2 Gamma dt

    This function returns S^2 * Gamma only. The caller applies e^{-rt} --
    simulate_hedge does, in its accumulation step. Dropping it is not free:
    measured along real paths at r=4%, the gamma-weighted discount overstates
    P&L by 0.16% over one month but 2.0% over one year. Negligible at the
    horizons used here, not negligible if you are attributing variance risk
    premium capture over longer ones.
    """
    S = np.asarray(S, dtype=float)
    return S**2 * bs_gamma(S, K, T, r, sigma, q)
