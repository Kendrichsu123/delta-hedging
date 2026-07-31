"""Geometric Brownian motion path simulation.

One design decision matters here and it is not cosmetic.

We step the LOG of the price:

    S[k+1] = S[k] * exp( (mu - q - sigma^2/2) * dt  +  sigma * sqrt(dt) * Z )

rather than the arithmetic form S[k+1] = S[k] * (1 + mu*dt + sigma*sqrt(dt)*Z).

The log form is the exact solution of the GBM equation, so it is correct at
ANY step size. The arithmetic form carries its own discretization error that
shrinks as the number of steps grows -- and it can produce negative prices.

That would be fatal here specifically. The headline result of this project is
that hedging error shrinks like 1/sqrt(N) in the number of rebalances. If the
path generator ALSO had an N-dependent error, we could not tell the two apart:
we would be measuring our own simulator. The log form has zero discretization
error, so any N-dependence we measure comes from the hedging, which is what we
are actually studying.
"""

import numpy as np


def gbm_paths(S0, mu, sigma, T, N, n_paths, q=0.0, seed=None, rng=None):
    """Simulate GBM paths on a uniform grid of N steps over [0, T].

    Parameters
    ----------
    S0 : float
        Spot at t=0.
    mu : float
        Total expected return of the stock (real-world drift). Set mu = r for
        the risk-neutral measure. See the note below on why this matters.
    sigma : float
        The volatility the stock actually realizes.
    T : float
        Horizon in years.
    N : int
        Number of time steps. The hedging engine rebalances once per step.
    n_paths : int
        Number of independent paths.
    q : float
        Continuous dividend yield. The price process drifts at (mu - q); the
        yield itself is paid to the holder as cash and is credited separately
        by the hedging engine.

    Returns
    -------
    ndarray, shape (n_paths, N+1)
        Column 0 is S0 for every path; column N is the terminal price.

    Note on mu
    ----------
    The mean P&L of hedging at implied vol depends on mu, because drift changes
    where the stock spends its time and therefore how much dollar gamma the
    position accumulates. Hedging at realized vol does not depend on mu at all.
    That difference is a real, testable prediction -- see the docstring on
    simulate_hedge.
    """
    if rng is None:
        rng = np.random.default_rng(seed)

    dt = T / N
    Z = rng.standard_normal((n_paths, N))

    drift = (mu - q - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * Z

    log_increments = drift + diffusion
    log_S = np.log(S0) + np.cumsum(log_increments, axis=1)

    S = np.empty((n_paths, N + 1))
    S[:, 0] = S0
    S[:, 1:] = np.exp(log_S)
    return S


def realized_vol(S, T):
    """Annualized realized volatility of each path, from its log returns.

    Uses the uncentered estimator (no mean subtraction), which is the one that
    matches the quadratic variation appearing in the hedging P&L. Subtracting
    the sample mean would remove drift but also bias the estimate relative to
    what the hedge actually pays for.

    Returns one number per path, shape (n_paths,).
    """
    log_returns = np.diff(np.log(S), axis=1)
    N = log_returns.shape[1]
    dt = T / N
    return np.sqrt((log_returns**2).sum(axis=1) / (N * dt))
