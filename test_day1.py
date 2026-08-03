"""Day 1 validation.

The point of this file is to make the engine trustworthy BEFORE we use it to
claim anything. Every test here compares the simulation against something known
independently -- a closed form, an arbitrage identity, or a convergence rate.

The headline test is test_zero_edge. If you sell an option at 20% vol, the stock
realizes exactly 20%, and you hedge at 20%, then you have no edge and your P&L
must go to zero as you hedge more often. That single test catches almost every
way this engine could be wrong: a sign error on the stock unwind, using
tomorrow's price for today's hedge, forgetting to settle the option, dropping
interest. None of those survive it, and none of them are visible by eyeballing
a histogram.

Tolerances are stated in standard errors rather than as absolute numbers,
because the quantity being tested is a Monte Carlo estimate and its uncertainty
depends on the sample size.

Run:  python test_day1.py
"""

import numpy as np

import bs
from hedge import (
    simulate_hedge,
    theory_pnl_hedged_at_realized,
    theory_mean_pnl,
    theory_pnl_from_gamma,
)
from paths import gbm_paths, realized_vol

PASSED = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}{'  ' + detail if detail else ''}")
    PASSED.append(condition)
    if not condition:
        raise AssertionError(f"{name}: {detail}")


# ---------------------------------------------------------------------------
# 1. Black-Scholes layer
# ---------------------------------------------------------------------------


def test_black_scholes():
    print("\n1. Black-Scholes pricing and Greeks")
    S0, K, T, r, sigma, q = 100.0, 100.0, 30 / 365, 0.03, 0.20, 0.01

    # Put-call parity is model-free: any pricer that violates it is broken.
    call = bs.bs_price(S0, K, T, r, sigma, q, cp=1)
    put = bs.bs_price(S0, K, T, r, sigma, q, cp=-1)
    parity_lhs = call - put
    parity_rhs = S0 * np.exp(-q * T) - K * np.exp(-r * T)
    check(
        "put-call parity",
        abs(parity_lhs - parity_rhs) < 1e-10,
        f"C-P={parity_lhs:.10f} vs S e^-qT - K e^-rT={parity_rhs:.10f}",
    )

    # Delta bounds.
    d_call = bs.bs_delta(S0, K, T, r, sigma, q, cp=1)
    d_put = bs.bs_delta(S0, K, T, r, sigma, q, cp=-1)
    check("call delta in (0, 1)", 0 < d_call < 1, f"{d_call:.4f}")
    check("put delta in (-1, 0)", -1 < d_put < 0, f"{d_put:.4f}")
    check(
        "delta parity: dC - dP = e^-qT",
        abs((d_call - d_put) - np.exp(-q * T)) < 1e-12,
    )

    # Gamma is positive and identical for calls and puts.
    g = bs.bs_gamma(S0, K, T, r, sigma, q)
    check("gamma > 0", g > 0, f"{g:.6f}")

    # Delta should be the numerical derivative of price.
    h = 1e-5
    fd = (
        bs.bs_price(S0 + h, K, T, r, sigma, q) - bs.bs_price(S0 - h, K, T, r, sigma, q)
    ) / (2 * h)
    check("delta == d(price)/dS", abs(fd - d_call) < 1e-6, f"fd={fd:.8f} analytic={d_call:.8f}")

    # Gamma should be the numerical derivative of delta.
    h = 1e-4
    fd_g = (
        bs.bs_delta(S0 + h, K, T, r, sigma, q) - bs.bs_delta(S0 - h, K, T, r, sigma, q)
    ) / (2 * h)
    check("gamma == d(delta)/dS", abs(fd_g - g) < 1e-6, f"fd={fd_g:.8f} analytic={g:.8f}")

    # Vega = S^2 * sigma * T * Gamma  (dollar gamma and vega are the same thing).
    v = bs.bs_vega(S0, K, T, r, sigma, q)
    check(
        "vega == S^2 sigma T gamma",
        abs(v - S0**2 * sigma * T * g) < 1e-9,
        f"{v:.6f}",
    )

    # Implied vol must invert the pricer.
    iv = bs.implied_vol(call, S0, K, T, r, q, cp=1)
    check("implied_vol round-trip", abs(iv - sigma) < 1e-8, f"recovered {iv:.10f}")

    # T must accept arrays, not just scalars. A scalar `if T <= 0` raises on an
    # array, which blocks pricing a whole path's worth of maturities at once.
    # This was flagged in review, deferred as YAGNI, and then blocked a Day 4
    # figure three days later.
    Ts = np.array([0.25, T, 1e-9, 0.0, -0.01])
    for name, fn, at_expiry in [
        ("price", lambda t: bs.bs_price(S0, K, t, r, sigma, q), max(S0 - K, 0.0)),
        ("delta", lambda t: bs.bs_delta(S0, K, t, r, sigma, q), 1.0 * (S0 > K)),
        ("gamma", lambda t: bs.bs_gamma(S0, K, t, r, sigma, q), 0.0),
        ("vega", lambda t: bs.bs_vega(S0, K, t, r, sigma, q), 0.0),
        ("theta", lambda t: bs.bs_theta(S0, K, t, r, sigma, q), 0.0),
    ]:
        vec = fn(Ts)
        check(f"bs_{name} accepts array T", vec.shape == Ts.shape, str(vec.shape))
        check(f"bs_{name} array matches scalar", abs(vec[1] - fn(T)) < 1e-12)
        check(f"bs_{name} finite everywhere", np.all(np.isfinite(vec)), str(vec))
        check(f"bs_{name} correct at T<=0", abs(vec[3] - at_expiry) < 1e-12
              and abs(vec[4] - at_expiry) < 1e-12, f"{vec[3]}, {vec[4]}")

    # S and T may vary together, which is the case a path actually needs.
    g2 = bs.bs_gamma(np.array([95.0, 100.0, 105.0]), K, np.array([0.2, 0.1, 0.0]), r, sigma, q)
    check("gamma with S and T both arrays", g2.shape == (3,) and g2[2] == 0.0, str(g2))

    # The BS PDE must hold. This is the identity the whole P&L derivation
    # rests on, so it is worth asserting directly rather than trusting.
    theta = bs.bs_theta(S0, K, T, r, sigma, q, cp=1)
    pde = theta + 0.5 * sigma**2 * S0**2 * g + (r - q) * S0 * d_call - r * call
    check("Black-Scholes PDE residual == 0", abs(pde) < 1e-8, f"residual={pde:.2e}")


# ---------------------------------------------------------------------------
# 2. Path simulator
# ---------------------------------------------------------------------------


def test_paths():
    print("\n2. GBM path simulator")
    S0, mu, sigma, T, N, n = 100.0, 0.07, 0.25, 1.0, 252, 200_000

    S = gbm_paths(S0, mu, sigma, T, N, n, seed=42)
    check("shape is (n_paths, N+1)", S.shape == (n, N + 1), str(S.shape))
    check("column 0 is S0", np.all(S[:, 0] == S0))
    check("all prices positive", np.all(S > 0))

    # E[S_T] = S0 * exp(mu*T). Compare against the sample standard error.
    ST = S[:, -1]
    expected = S0 * np.exp(mu * T)
    se = ST.std(ddof=1) / np.sqrt(n)
    check(
        "E[S_T] == S0 exp(mu T)",
        abs(ST.mean() - expected) < 4 * se,
        f"{ST.mean():.4f} vs {expected:.4f} (4*se={4*se:.4f})",
    )

    # E[ln S_T] carries the Ito correction -mu*sigma^2/2. This is the term
    # ordinary calculus would miss, so it is worth testing on its own.
    log_expected = np.log(S0) + (mu - 0.5 * sigma**2) * T
    log_se = np.log(ST).std(ddof=1) / np.sqrt(n)
    check(
        "E[ln S_T] carries the -sigma^2/2 drag",
        abs(np.log(ST).mean() - log_expected) < 4 * log_se,
        f"{np.log(ST).mean():.5f} vs {log_expected:.5f}",
    )

    # The paths must actually realize the volatility we asked for.
    rv = realized_vol(S, T)
    check(
        "realized vol recovers sigma",
        abs(rv.mean() - sigma) < 0.002,
        f"mean realized {rv.mean():.5f} vs requested {sigma:.5f}",
    )

    # Same seed must give the same paths, or nothing is reproducible.
    S2 = gbm_paths(S0, mu, sigma, T, N, n, seed=42)
    check("seeding is reproducible", np.array_equal(S, S2))


# ---------------------------------------------------------------------------
# 3. THE HEADLINE TEST: no edge means no P&L
# ---------------------------------------------------------------------------


def test_zero_edge():
    print("\n3. Zero-edge test  (sigma_implied == sigma_real == sigma_hedge)")
    print("   No edge, so P&L must collapse to zero as N grows.")

    common = dict(
        S0=100.0, K=100.0, T=30 / 365, r=0.0,
        sigma_real=0.20, sigma_implied=0.20, sigma_hedge=0.20,
        n_paths=20_000, seed=11,
    )

    stds = {}
    for N in [32, 128, 512]:
        res = simulate_hedge(N=N, **common)
        s = res.summary()
        stds[N] = s["std"]
        print(
            f"     N={N:4d}   mean={s['mean']:+.5f}  (se {s['stderr']:.5f})"
            f"   std={s['std']:.5f}"
        )
        check(
            f"mean P&L is zero at N={N}",
            abs(s["mean"]) < 4 * s["stderr"],
            f"mean={s['mean']:+.5f}, 4*se={4*s['stderr']:.5f}",
        )

    # Quadrupling the rebalances should halve the spread.
    for a, b in [(32, 128), (128, 512)]:
        ratio = stds[a] / stds[b]
        check(
            f"std shrinks ~2x from N={a} to N={b}",
            1.8 < ratio < 2.2,
            f"ratio={ratio:.3f} (expect ~2.0)",
        )

    # Assert the RATE, not an absolute level. "std < 0.05 at N=512" would be an
    # arbitrary threshold; the actual claim is that the spread decays like
    # N^(-1/2), which extrapolates to zero. It decays slowly -- at N=512 the
    # spread is still ~4% of the premium -- and that slowness is a real finding
    # about hedging, not a defect in the engine.
    slope = np.polyfit(np.log(list(stds)), np.log(list(stds.values())), 1)[0]
    print(f"     log-log slope = {slope:+.4f}   (theory: -0.5)")
    check(
        "spread decays like 1/sqrt(N)",
        -0.55 < slope < -0.45,
        f"slope={slope:+.4f}",
    )


# ---------------------------------------------------------------------------
# 4. Hedging at realized vol -> deterministic P&L
# ---------------------------------------------------------------------------


def test_hedge_at_realized():
    print("\n4. Hedging at realized vol  ->  P&L is deterministic")
    common = dict(
        S0=100.0, K=100.0, T=30 / 365, r=0.0,
        sigma_real=0.15, sigma_implied=0.20,
        n_paths=20_000, seed=12,
    )
    predicted = theory_pnl_hedged_at_realized(100.0, 100.0, 30 / 365, 0.0, 0.15, 0.20)
    print(f"     closed form: (V(0.20) - V(0.15)) = {predicted:.6f}")

    stds = {}
    for N in [32, 128, 512]:
        res = simulate_hedge(N=N, sigma_hedge=0.15, **common)
        s = res.summary()
        stds[N] = s["std"]
        print(
            f"     N={N:4d}   mean={s['mean']:.6f}  (se {s['stderr']:.6f})"
            f"   std={s['std']:.5f}"
        )
        check(
            f"mean matches closed form at N={N}",
            abs(s["mean"] - predicted) < 4 * s["stderr"],
            f"{s['mean']:.6f} vs {predicted:.6f}",
        )

    # The spread must decay at the full 1/sqrt(N) rate with NO floor: hedging at
    # realized vol has no path-dependent term left over, so all the remaining
    # randomness is discretization and it extrapolates to exactly zero.
    # Contrast with test 5, where the same fit finds a slope well short of -0.5
    # because a floor is in the way.
    slope = np.polyfit(np.log(list(stds)), np.log(list(stds.values())), 1)[0]
    print(f"     log-log slope = {slope:+.4f}   (theory: -0.5, no floor)")
    check(
        "spread decays at the full 1/sqrt(N) rate",
        -0.55 < slope < -0.45,
        f"slope={slope:+.4f}",
    )


# ---------------------------------------------------------------------------
# 5. Hedging at implied vol -> same mean, irreducible spread
# ---------------------------------------------------------------------------


def test_hedge_at_implied():
    print("\n5. Hedging at implied vol  ->  same mean, but spread does NOT vanish")
    common = dict(
        S0=100.0, K=100.0, T=30 / 365, r=0.0,
        sigma_real=0.15, sigma_implied=0.20,
        n_paths=20_000, seed=13,
    )
    predicted = theory_mean_pnl(100.0, 100.0, 30 / 365, 0.0, 0.15, 0.20)

    stds = {}
    for N in [32, 128, 512]:
        res = simulate_hedge(N=N, **common)  # sigma_hedge defaults to implied
        s = res.summary()
        stds[N] = s["std"]
        print(
            f"     N={N:4d}   mean={s['mean']:.6f}  (se {s['stderr']:.6f})"
            f"   std={s['std']:.5f}"
        )
        check(
            f"mean matches closed form at N={N}",
            abs(s["mean"] - predicted) < 4 * s["stderr"],
            f"{s['mean']:.6f} vs {predicted:.6f}",
        )

    # This is the contrast with test 4: the spread flattens instead of vanishing.
    check(
        "spread does NOT collapse (path dependence is irreducible)",
        stds[512] > 0.5 * stds[128],
        f"std {stds[128]:.5f} -> {stds[512]:.5f}, still {stds[512]:.4f}",
    )


# ---------------------------------------------------------------------------
# 6. The dollar-gamma formula, path by path
# ---------------------------------------------------------------------------


def test_dollar_gamma_formula():
    print("\n6. P&L == (1/2)(sigma_i^2 - sigma_r^2) * int S^2 Gamma dt,  path by path")
    res = simulate_hedge(
        S0=100.0, K=100.0, T=30 / 365, r=0.0,
        sigma_real=0.15, sigma_implied=0.20,
        N=2048, n_paths=8_000, seed=14,
    )
    predicted = theory_pnl_from_gamma(res.dollar_gamma_integral, 0.15, 0.20)
    corr = np.corrcoef(res.pnl, predicted)[0, 1]
    print(f"     corr(simulated, formula) = {corr:.5f}")
    print(f"     mean: simulated {res.pnl.mean():.6f}  formula {predicted.mean():.6f}")
    check("correlation > 0.98 at N=2048", corr > 0.98, f"corr={corr:.5f}")
    check(
        "means agree",
        abs(res.pnl.mean() - predicted.mean()) < 0.01,
        f"{res.pnl.mean():.6f} vs {predicted.mean():.6f}",
    )


# ---------------------------------------------------------------------------
# 7. Puts, and nonzero rates/dividends
# ---------------------------------------------------------------------------


def test_puts_and_carry():
    print("\n7. Puts, interest rates, and dividends")

    # Same test as #4 but for a put, and with r and q switched on.
    S0, K, T, r, q = 100.0, 95.0, 60 / 365, 0.04, 0.02
    predicted = theory_pnl_hedged_at_realized(S0, K, T, r, 0.18, 0.24, q=q, cp=-1)
    res = simulate_hedge(
        S0=S0, K=K, T=T, r=r, q=q,
        sigma_real=0.18, sigma_implied=0.24, sigma_hedge=0.18,
        N=512, n_paths=20_000, cp=-1, seed=15,
    )
    s = res.summary()
    print(f"     put, r=4%, q=2%: mean={s['mean']:.6f} (se {s['stderr']:.6f})")
    print(f"     closed form (V(0.24)-V(0.18))e^rT = {predicted:.6f}")
    check(
        "put with carry matches closed form",
        abs(s["mean"] - predicted) < 4 * s["stderr"] + 0.01,
        f"{s['mean']:.6f} vs {predicted:.6f}",
    )

    # An OTM call we sold with NO edge should still produce zero P&L.
    res2 = simulate_hedge(
        S0=100.0, K=110.0, T=45 / 365, r=0.03,
        sigma_real=0.22, sigma_implied=0.22,
        N=512, n_paths=20_000, seed=16,
    )
    s2 = res2.summary()
    print(f"     OTM call, no edge: mean={s2['mean']:+.6f} (se {s2['stderr']:.6f})")
    check(
        "OTM call with no edge gives zero P&L",
        abs(s2["mean"]) < 4 * s2["stderr"],
        f"mean={s2['mean']:+.6f}",
    )


def test_transaction_costs():
    print("\n9. Transaction costs")
    S0, K, T = 100.0, 100.0, 30 / 365

    # Cost must be exactly cost_rate * traded notional, and must only ever
    # reduce P&L. A signed cost would be a windfall on one side of the trade.
    a = simulate_hedge(S0=S0, K=K, T=T, N=128, n_paths=8_000, seed=201, cost_bps=0.0)
    b = simulate_hedge(S0=S0, K=K, T=T, N=128, n_paths=8_000, seed=201, cost_bps=1.0)
    drop = a.pnl - b.pnl
    check(
        "cost equals rate x traded notional, path by path",
        np.allclose(drop, b.traded_notional * 1e-4, atol=1e-10),
        f"max discrepancy {np.abs(drop - b.traded_notional * 1e-4).max():.2e}",
    )
    check("cost never increases P&L", np.all(drop >= -1e-12), f"min drop {drop.min():.2e}")
    check(
        "cost_bps=0 is identical to no costs",
        np.array_equal(a.pnl, simulate_hedge(S0=S0, K=K, T=T, N=128, n_paths=8_000,
                                             seed=201).pnl),
    )

    # Cost must be linear in the rate: 2bp costs exactly twice 1bp.
    c = simulate_hedge(S0=S0, K=K, T=T, N=128, n_paths=8_000, seed=201, cost_bps=2.0)
    check(
        "cost is linear in cost_bps",
        np.allclose(a.pnl - c.pnl, 2 * (a.pnl - b.pnl), atol=1e-10),
    )

    # The REBALANCING leg must scale like sqrt(N). Entry and exit are fixed
    # and dominate at low N, so they are removed before testing the rate.
    d0 = float(bs.bs_delta(S0, K, T, 0.0, 0.20))
    rates = []
    for N in [128, 512, 2048]:
        r = simulate_hedge(S0=S0, K=K, T=T, N=N, n_paths=8_000, seed=201,
                           cost_bps=1.0, keep_paths=True)
        exit_leg = (np.abs(bs.bs_delta(r.S[:, -2], K, T / N, 0.0, 0.20)) * r.S[:, -1]).mean()
        rates.append((r.traded_notional.mean() - d0 * S0 - exit_leg) / np.sqrt(N))
    spread = (max(rates) - min(rates)) / np.mean(rates)
    check(
        "rebalancing notional scales like sqrt(N)",
        spread < 0.05,
        f"rebal/sqrt(N) = {[round(x, 2) for x in rates]}, spread {spread:.1%}",
    )


def test_scheduled_jump():
    print("\n8. Scheduled jump")
    S0, sd, sj, T, N, n = 100.0, 0.15, 0.03, 30 / 365, 256, 200_000

    S = gbm_paths(S0, 0.0, sd, T, N, n, seed=5, jump_at=0.5, jump_vol=sj)
    ST = S[:, -1]

    # The jump is drift-compensated, so adding it must not move E[S_T]. Without
    # the -jump_vol^2/2 term a zero-mean shock to the LOG raises the level, and
    # every jump-vs-no-jump comparison would be confounded by a drift change.
    se = ST.std(ddof=1) / np.sqrt(n)
    check(
        "jump does not change E[S_T]",
        abs(ST.mean() - S0) < 4 * se,
        f"{ST.mean():.4f} vs {S0} (4*se={4*se:.4f})",
    )

    # Total realized variance must be diffusion + jump, exactly.
    log_var = (np.diff(np.log(S), axis=1) ** 2).sum(axis=1).mean()
    expected = sd**2 * T + sj**2
    check(
        "total variance == sigma^2*T + jump_vol^2",
        abs(log_var - expected) / expected < 0.01,
        f"{log_var:.6f} vs {expected:.6f}",
    )

    # jump_vol=0 must reproduce the no-jump path exactly, or the jump branch is
    # silently perturbing the baseline every comparison is measured against.
    a = gbm_paths(S0, 0.0, sd, T, 64, 1000, seed=9)
    b = gbm_paths(S0, 0.0, sd, T, 64, 1000, seed=9, jump_at=0.5, jump_vol=0.0)
    check("jump_vol=0 is identical to no jump", np.array_equal(a, b))

    # The jump must land in exactly one step, and that step only.
    S2 = gbm_paths(S0, 0.0, 1e-9, T, 10, 20_000, seed=3, jump_at=0.5, jump_vol=0.05)
    step_std = np.diff(np.log(S2), axis=1).std(axis=0)
    jumpy = np.where(step_std > 0.01)[0]
    check(
        "jump occupies exactly one step",
        len(jumpy) == 1 and jumpy[0] == 5,
        f"steps with large moves: {jumpy}",
    )

    # A jump priced into implied vol should restore a fair trade: sell at the
    # jump-inclusive fair vol and the mean P&L must be ~0.
    fair = np.sqrt(sd**2 + sj**2 / T)
    res = simulate_hedge(S0=S0, K=S0, T=T, r=0.0, sigma_real=sd,
                         sigma_implied=fair, N=512, n_paths=40_000, seed=7,
                         jump_at=0.5, jump_vol=sj)
    s = res.summary()
    check(
        "selling at jump-inclusive fair vol is zero-edge",
        abs(s["mean"]) < 4 * s["stderr"],
        f"mean={s['mean']:+.5f}, 4*se={4*s['stderr']:.5f}",
    )
    print(f"     fair vol with jump = {fair:.4f}; mean P&L {s['mean']:+.5f} "
          f"(se {s['stderr']:.5f}), skew {s['skew']:+.3f}")


if __name__ == "__main__":
    print("=" * 70)
    print("DAY 1 VALIDATION")
    print("=" * 70)
    test_black_scholes()
    test_paths()
    test_zero_edge()
    test_hedge_at_realized()
    test_hedge_at_implied()
    test_dollar_gamma_formula()
    test_puts_and_carry()
    test_scheduled_jump()
    test_transaction_costs()
    print("\n" + "=" * 70)
    print(f"ALL {len(PASSED)} CHECKS PASSED")
    print("=" * 70)
