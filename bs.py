"""Black-Scholes pricing and Greeks.

Vendored from the vol-surface project and extended with gamma/theta, so this
repo clones and runs standalone.

Everything is vectorized over S: the hedging engine prices 10,000 paths in a
single call rather than looping in Python. Convention throughout is cp=+1 for
a call, cp=-1 for a put.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def _d1_d2(S, K, T, r, sigma, q):
    """The two Black-Scholes arguments. Assumes T > 0 and sigma > 0."""
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    return d1, d1 - sigma * sqrt_T


def payoff(S, K, cp=1):
    """Terminal value of the option. max(S-K, 0) for a call."""
    return np.maximum(cp * (np.asarray(S, dtype=float) - K), 0.0)


def bs_price(S, K, T, r, sigma, q=0.0, cp=1):
    S = np.asarray(S, dtype=float)
    if T <= 0:
        return payoff(S, K, cp)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    return cp * (
        S * np.exp(-q * T) * norm.cdf(cp * d1)
        - K * np.exp(-r * T) * norm.cdf(cp * d2)
    )


def bs_delta(S, K, T, r, sigma, q=0.0, cp=1):
    """dV/dS -- the hedge ratio. Shares of stock per option."""
    S = np.asarray(S, dtype=float)
    if T <= 0:
        # At expiry delta is the indicator of being in the money.
        return cp * (cp * (S - K) > 0).astype(float)
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    return cp * np.exp(-q * T) * norm.cdf(cp * d1)


def bs_gamma(S, K, T, r, sigma, q=0.0):
    """d2V/dS2 -- how fast delta goes stale. Same for calls and puts."""
    S = np.asarray(S, dtype=float)
    if T <= 0:
        return np.zeros_like(S)
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    return np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))


def bs_vega(S, K, T, r, sigma, q=0.0):
    """dV/dsigma, per 1.00 of vol (not per vol point). Same for calls and puts."""
    S = np.asarray(S, dtype=float)
    if T <= 0:
        return np.zeros_like(S)
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)


def bs_theta(S, K, T, r, sigma, q=0.0, cp=1):
    """dV/dt, per year. Negative for a long option: it decays."""
    S = np.asarray(S, dtype=float)
    if T <= 0:
        return np.zeros_like(S)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    return (
        -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
        - cp * r * K * np.exp(-r * T) * norm.cdf(cp * d2)
        + cp * q * S * np.exp(-q * T) * norm.cdf(cp * d1)
    )


def implied_vol(price, S, K, T, r, q=0.0, cp=1, lo=1e-6, hi=5.0):
    """Invert bs_price for sigma. Scalar only -- Brent needs a scalar objective.

    Returns nan if the price is outside the no-arbitrage bounds reachable by
    the bracket, rather than raising, so a bad quote in a chain doesn't kill
    a whole run.
    """
    def objective(sigma):
        return bs_price(S, K, T, r, sigma, q, cp) - price

    try:
        return brentq(objective, lo, hi, xtol=1e-12, rtol=1e-10)
    except ValueError:
        return np.nan


def dollar_gamma(S, K, T, r, sigma, q=0.0):
    """S^2 * Gamma -- gamma expressed in money.

    This is the weight in the P&L integral: the payoff of a delta-hedged short
    option is (1/2)(sigma_i^2 - sigma_r^2) * integral of dollar gamma over the
    path. Raw gamma is in shares-per-dollar and is not comparable across price
    levels; this is.
    """
    S = np.asarray(S, dtype=float)
    return S**2 * bs_gamma(S, K, T, r, sigma, q)
