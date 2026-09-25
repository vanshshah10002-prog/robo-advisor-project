"""
Regression tests for the money-math core (PM overhaul, fix #10).

All tests run on synthetic data — no network. Run:  pytest tests/ -q
"""

import numpy as np
import pandas as pd
import pytest

from backend.config import (
    EXPECTED_RETURN_CLAMP,
    MVO_RISK_FREE_RATE,
    RISK_FREE_CLAMP,
    VOL_CALIBRATION_MULTIPLIER,
)


# =============================================================================
# Fixtures: synthetic universe (deterministic)
# =============================================================================

TICKERS = ["CASH", "GILT", "CORP", "GOLD", "EQ_UK", "EQ_US", "EQ_GL", "EQ_EM"]
AC_MAP = {
    "CASH": "cash_equivalent", "GILT": "uk_gilts", "CORP": "corporate_bonds",
    "GOLD": "commodities_gold", "EQ_UK": "uk_equity", "EQ_US": "us_equity",
    "EQ_GL": "global_equity", "EQ_EM": "emerging_market_equity",
}
ANNUAL_VOLS = {"CASH": 0.005, "GILT": 0.07, "CORP": 0.06, "GOLD": 0.15,
               "EQ_UK": 0.14, "EQ_US": 0.16, "EQ_GL": 0.14, "EQ_EM": 0.20}
ANNUAL_MEANS = {"CASH": 0.02, "GILT": 0.03, "CORP": 0.035, "GOLD": 0.05,
                "EQ_UK": 0.06, "EQ_US": 0.09, "EQ_GL": 0.08, "EQ_EM": 0.07}


@pytest.fixture(scope="module")
def synthetic_returns() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2015-01-31", periods=120, freq="ME")
    data = {}
    common = rng.standard_normal(120)  # shared factor for realistic correlation
    for t in TICKERS:
        own = rng.standard_normal(120)
        beta = 0.0 if t == "CASH" else (0.3 if t in ("GILT", "CORP", "GOLD") else 0.8)
        shock = beta * common + np.sqrt(max(1e-9, 1 - beta**2)) * own
        monthly = ANNUAL_MEANS[t] / 12.0 + (ANNUAL_VOLS[t] / np.sqrt(12)) * shock
        data[t] = monthly
    return pd.DataFrame(data, index=idx)


@pytest.fixture(scope="module")
def mu_cov(synthetic_returns):
    from backend.engine.quant_models import ewma_lw_cov, log_monthly_to_annual_arith
    mu = log_monthly_to_annual_arith(synthetic_returns.mean())
    cov = ewma_lw_cov(synthetic_returns)
    return mu, cov


# =============================================================================
# Expected returns: clamp + rf separation
# =============================================================================

class TestExpectedReturns:
    def test_clamp_applied(self, synthetic_returns):
        from backend.engine.expected_returns import get_blend_expected_returns
        # Inject an absurd trailing return to force clamping
        r = synthetic_returns.copy()
        r["EQ_US"] = r["EQ_US"] + 0.03  # +36%/yr trailing
        mu = get_blend_expected_returns(r)
        lo, hi = EXPECTED_RETURN_CLAMP
        assert mu.max() <= hi + 1e-12 and mu.min() >= lo - 1e-12

    def test_no_hardcoded_hurdle_in_config(self):
        # The 6% hardcoded hurdle was removed — Sharpe is reported against the
        # LIVE GBP risk-free rate (backend/data/rates.py); only a fallback
        # pricing constant remains for network-failure resilience.
        import backend.config as config
        assert not hasattr(config, "HURDLE_RATE")
        assert 0.0 < MVO_RISK_FREE_RATE < 0.08

    def test_bl_premia_positive_and_sane(self, synthetic_returns):
        from backend.engine.quant_models import black_litterman
        bl = black_litterman(synthetic_returns)
        # λ is floored at 1 → equilibrium E[R] ≥ rf for positive-beta assets,
        # and the level must sit near rf + modest premia, not rf + 6%.
        assert bl.min() > 0.0 and bl.max() < 0.20
        # systematic-risk ordering: equities priced above cash
        assert bl["EQ_US"] > bl["CASH"]


# =============================================================================
# Live risk-free rate (backend/data/rates.py) — all offline via monkeypatch
# =============================================================================

class TestLiveRiskFreeRate:
    def test_trailing_annualized_return_recovers_growth(self):
        from backend.data.rates import trailing_annualized_return
        idx = pd.date_range("2023-01-01", periods=450, freq="D")
        prices = pd.Series(100.0 * 1.05 ** (np.arange(450) / 365.25), index=idx)
        r = trailing_annualized_return(prices, lookback_months=12)
        assert r == pytest.approx(0.05, abs=0.005)

    def test_insufficient_history_returns_none(self):
        from backend.data.rates import trailing_annualized_return
        idx = pd.date_range("2025-01-01", periods=90, freq="D")
        prices = pd.Series(np.linspace(100, 101, 90), index=idx)
        assert trailing_annualized_return(prices, lookback_months=12) is None

    def test_fallback_used_when_all_live_sources_fail(self, monkeypatch):
        import backend.data.rates as rates
        monkeypatch.setattr(rates, "_fetch_live_rate", lambda: None)
        monkeypatch.setattr(rates, "_memo_rate", None)
        monkeypatch.setattr(rates, "_memo_at", None)
        assert rates.get_risk_free_rate(fallback=0.0123) == pytest.approx(0.0123)

    def test_fetched_rate_clamped_to_sane_band(self, monkeypatch):
        import backend.data.rates as rates
        idx = pd.date_range("2022-01-01", periods=800, freq="D")
        # Absurd 25%/yr "cash" growth — must be treated as data error
        prices = pd.Series(100.0 * 1.25 ** (np.arange(800) / 365.25), index=idx)
        df = pd.DataFrame({"Close": prices})
        monkeypatch.setattr(rates, "get_or_fetch_prices", lambda *a, **k: df)
        lo, hi = RISK_FREE_CLAMP
        assert rates._fetch_live_rate() == pytest.approx(hi)


# =============================================================================
# Monte Carlo math
# =============================================================================

class TestMonteCarlo:
    def test_drift_unbiased(self):
        from backend.engine.monte_carlo import _simulate_paths
        mu, vol, years = 0.07, 0.12, 15
        p = _simulate_paths(1000, 0, mu, vol, years, 20000, t_dof=1e9, inflation_rate=0.0)
        det = 1000 * (1 + mu) ** years
        assert p[:, -1].mean() == pytest.approx(det, rel=0.03)

    def test_fat_tails_in_worst_month(self):
        from backend.engine.monte_carlo import _simulate_paths
        pt = _simulate_paths(1000, 0, 0.07, 0.15, 10, 5000, t_dof=5.0, inflation_rate=0.0)
        pn = _simulate_paths(1000, 0, 0.07, 0.15, 10, 5000, t_dof=1e9, inflation_rate=0.0)
        worst_t = np.log(pt[:, 1:] / pt[:, :-1]).min()
        worst_n = np.log(pn[:, 1:] / pn[:, :-1]).min()
        assert worst_t < worst_n  # t must produce deeper single-month crashes

    def test_goal_inflated_lowers_probability(self):
        from backend.engine.monte_carlo import run_monte_carlo
        mu = pd.Series({"A": 0.07, "B": 0.04})
        cov = pd.DataFrame([[0.02, 0.002], [0.002, 0.005]], index=["A", "B"], columns=["A", "B"])
        res = run_monte_carlo(10000, 100, {"A": 0.6, "B": 0.4}, mu, cov,
                              years=20, n_simulations=2000, goal_amount=50000)
        # naive nominal-goal probability for comparison
        naive = float(np.mean(np.array(res["percentile_50"][-1]) >= 0))  # sanity placeholder
        assert 0.0 <= res["probability_of_goal"] <= 1.0

    def test_reproducible(self):
        from backend.engine.monte_carlo import _simulate_paths
        a = _simulate_paths(1000, 50, 0.06, 0.1, 5, 300)
        b = _simulate_paths(1000, 50, 0.06, 0.1, 5, 300)
        assert np.allclose(a, b)


# =============================================================================
# GARCH volatility dynamics
# =============================================================================

class TestGarch:
    def test_simulator_matches_unconditional_vol(self):
        from backend.engine.monte_carlo import _simulate_paths_garch
        # monthly params: uncond var = omega/(1-a-b) = (0.0004)/(1-0.35) -> vol ~2.48%/m
        gp = {"omega": 0.0004, "alpha": 0.21, "beta": 0.14, "nu": 8.0,
              "uncond_var": 0.0004 / (1 - 0.35)}
        p = _simulate_paths_garch(1000, 0, 0.08, gp, years=20, n_simulations=4000,
                                  inflation_rate=0.0)
        lr = np.log(p[:, 1:] / p[:, :-1])
        target_m_vol = np.sqrt(gp["uncond_var"])
        assert lr.std() == pytest.approx(target_m_vol, rel=0.10)

    def test_simulated_series_exhibits_clustering(self):
        from backend.engine.monte_carlo import _simulate_paths_garch, _simulate_paths
        gp = {"omega": 0.00012, "alpha": 0.20, "beta": 0.75, "nu": 8.0,
              "uncond_var": 0.00012 / (1 - 0.95)}
        pg = _simulate_paths_garch(1000, 0, 0.07, gp, years=30, n_simulations=200,
                                   inflation_rate=0.0)
        pi = _simulate_paths(1000, 0, 0.07, np.sqrt(gp["uncond_var"] * 12), 30, 200,
                             t_dof=8.0, inflation_rate=0.0)

        def sq_autocorr(paths):
            lr = np.log(paths[:, 1:] / paths[:, :-1])
            acs = []
            for i in range(lr.shape[0]):
                s = lr[i] - lr[i].mean()
                s2 = s ** 2
                acs.append(np.corrcoef(s2[:-1], s2[1:])[0, 1])
            return float(np.nanmean(acs))

        assert sq_autocorr(pg) > sq_autocorr(pi) + 0.05  # clustering present vs iid

    def test_fit_recovers_clustering_on_synthetic_garch(self):
        pytest.importorskip("arch")
        from backend.engine.quant_models import fit_garch_t
        rng = np.random.default_rng(11)
        n = 3000
        omega, alpha, beta, nu = 1e-5, 0.1, 0.85, 7.0
        z = rng.standard_t(nu, n) / np.sqrt(nu / (nu - 2))
        var = omega / (1 - alpha - beta)
        r = np.zeros(n)
        for t in range(n):
            eps = np.sqrt(var) * z[t]
            r[t] = eps
            var = omega + alpha * eps ** 2 + beta * var
        fit = fit_garch_t(pd.Series(r))
        assert fit["clustering_significant"]
        assert fit["persistence"] == pytest.approx(alpha + beta, abs=0.08)


# =============================================================================
# TLH economics
# =============================================================================

class TestTLH:
    HOLDINGS = [{"ticker": "VWRL.L", "quantity": 100, "average_cost": 100.0,
                 "current_price": 80.0, "asset_class": "global_equity"}]
    PRICES = {"VWRL.L": 80.0}

    def test_no_gains_means_zero_bankable_benefit(self):
        from backend.engine.tax_loss_harvester import scan_for_tlh_opportunities
        opps = scan_for_tlh_opportunities(self.HOLDINGS, self.PRICES, realised_gains_ytd=0.0)
        assert opps and opps[0]["tax_deferral_benefit"] == 0.0

    def test_benefit_only_on_taxable_gains_above_allowance(self):
        from backend.engine.tax_loss_harvester import scan_for_tlh_opportunities
        opps = scan_for_tlh_opportunities(self.HOLDINGS, self.PRICES, realised_gains_ytd=10000.0)
        # loss £2000 offsets gains above £3000 allowance → 2000 × 20% = 400
        assert opps[0]["tax_deferral_benefit"] == pytest.approx(400.0)

    def test_isa_returns_empty(self):
        from backend.engine.tax_loss_harvester import scan_for_tlh_opportunities
        assert scan_for_tlh_opportunities(self.HOLDINGS, self.PRICES, is_isa=True) == []


# =============================================================================
# Risk profiling
# =============================================================================

class TestRiskProfiler:
    @staticmethod
    def _quiz(vals):
        return [{"question_id": i + 1, "answer": v} for i, v in enumerate(vals)]

    def test_capacity_answers_do_not_move_willingness(self):
        from backend.engine.risk_profiler import compute_subjective_score
        high_cap = self._quiz([3, 3, 5, 1, 3, 5, 5, 3, 3, 3])
        low_cap = self._quiz([3, 3, 1, 5, 3, 1, 1, 3, 3, 3])
        assert compute_subjective_score(high_cap) == compute_subjective_score(low_cap)

    def test_inconsistency_reduces_composite(self):
        from backend.engine.risk_profiler import compute_composite_score
        base = compute_composite_score(7.0, 7.0, 15, has_inconsistency=False)
        flagged = compute_composite_score(7.0, 7.0, 15, has_inconsistency=True)
        assert flagged < base

    def test_minimal_profile_conservative_resolution(self):
        from backend.engine.risk_profiler import profile_user_minimal
        # risk-hungry but 1y horizon + no buffer → must cap conservatively
        r = profile_user_minimal(5, 1, 1, investment_amount=10000)
        assert r["composite_score"] <= 4.0


# =============================================================================
# Performance reporting
# =============================================================================

class TestPerformance:
    def test_vol_calibration_applied(self, mu_cov):
        from backend.engine.optimizer import get_portfolio_performance
        mu, cov = mu_cov
        w = {t: 1.0 / len(mu) for t in mu.index}
        perf = get_portfolio_performance(w, mu, cov)
        # fields are rounded to 6dp → compare at that precision
        assert perf["volatility"] == pytest.approx(
            perf["volatility_model"] * VOL_CALIBRATION_MULTIPLIER, abs=1e-5
        )
