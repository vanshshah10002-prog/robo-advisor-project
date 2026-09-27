"""
Return model: arithmetic annualisation, reference-portfolio equilibrium
prior, single fee deduction and history-length weighting.
"""

import numpy as np
import pandas as pd
import pytest
from pypfopt import EfficientFrontier

from backend.config import BL_RISK_AVERSION, EXPECTED_RETURN_TRAILING_WEIGHT
from backend.engine.quant_models import (
    annual_arithmetic_mean,
    equilibrium_returns,
    ewma_lw_cov,
    log_monthly_to_annual_geometric,
    production_expected_returns,
    reference_weights,
)

AC = {"US": "us_equity", "UK": "uk_equity", "EM": "emerging_market_equity",
      "GILT": "uk_gilts", "AGG": "global_bonds", "GOLD": "commodities_gold"}


def _returns(n=120, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-31", periods=n, freq="ME")
    common = rng.standard_normal(n)
    spec = {"US": (0.07, 0.16, 0.8), "UK": (0.06, 0.14, 0.7), "EM": (0.07, 0.20, 0.7),
            "GILT": (0.03, 0.07, 0.1), "AGG": (0.03, 0.05, 0.1), "GOLD": (0.04, 0.15, 0.1)}
    data = {}
    for t, (m, v, b) in spec.items():
        z = b * common + np.sqrt(1 - b * b) * rng.standard_normal(n)
        data[t] = m / 12 + v / np.sqrt(12) * z
    return pd.DataFrame(data, index=idx)


class TestAnnualisation:
    def test_arithmetic_exceeds_geometric_by_half_variance(self):
        R = _returns()
        arith = annual_arithmetic_mean(R)
        geom = log_monthly_to_annual_geometric(R.mean())
        half_var = 6.0 * R.var()  # 12σ²_monthly / 2
        gap = np.log1p(arith) - np.log1p(geom)
        assert np.allclose(gap, half_var)
        assert (arith > geom).all()


class TestReferencePrior:
    def test_weights_follow_market_not_fund_size(self):
        w = reference_weights(list(AC), AC)
        assert w["US"] > w["UK"] > w["EM"]
        assert w["GOLD"] < 0.05
        assert w.sum() == pytest.approx(1.0)

    def test_unconstrained_utility_optimum_is_the_reference_portfolio(self):
        R = _returns()
        cov = ewma_lw_cov(R)
        w_ref = reference_weights(list(cov.columns), AC)
        mu = equilibrium_returns(cov, w_ref, risk_free_annual=0.04)
        ef = EfficientFrontier(mu, cov, weight_bounds=(-1, 1))
        w = pd.Series(ef.max_quadratic_utility(risk_aversion=BL_RISK_AVERSION))
        assert np.allclose(w.reindex(w_ref.index).values, w_ref.values, atol=1e-4)

    def test_prior_ranks_equity_above_bonds(self):
        R = _returns()
        cov = ewma_lw_cov(R)
        mu = equilibrium_returns(cov, reference_weights(list(cov.columns), AC), 0.04)
        assert mu["US"] > mu["GILT"] > 0.04


class TestBlend:
    def test_fee_deducted_once(self):
        R = _returns()
        cov = ewma_lw_cov(R)
        fees = {"US": 0.005}
        mu_fee, d = production_expected_returns(R, cov, AC, fees, 0.04)
        mu_none, _ = production_expected_returns(R, cov, AC, {}, 0.04)
        w = d["trailing_weight"]
        assert mu_none["US"] - mu_fee["US"] == pytest.approx((1 - w) * 0.005)

    def test_trailing_weight_scales_with_history(self):
        cov = ewma_lw_cov(_returns())
        _, full = production_expected_returns(_returns(120), cov, AC, {}, 0.04)
        _, short = production_expected_returns(_returns(60), cov, AC, {}, 0.04)
        assert full["trailing_weight"] == pytest.approx(EXPECTED_RETURN_TRAILING_WEIGHT)
        assert short["trailing_weight"] == pytest.approx(EXPECTED_RETURN_TRAILING_WEIGHT / 2)

    def test_trailing_uses_common_window(self):
        R = _returns()
        R.loc[R.index[:60], "EM"] = np.nan  # EM only has the last 60 months
        cov = ewma_lw_cov(R)
        _, d = production_expected_returns(R, cov, AC, {}, 0.04)
        assert d["common_months"] == 60
