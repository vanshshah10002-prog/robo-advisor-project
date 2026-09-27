"""
Allocation policy and optimiser on a synthetic 13-block universe:
every risk level satisfies the policy, risk rises monotonically, bonds
(not cash) do the de-risking, and failures are reported, not hidden.
"""

import numpy as np
import pandas as pd
import pytest

from backend.config import CORE_UNIVERSE, POLICY_MIN_POSITION
from backend.engine.optimizer import (
    OptimisationError,
    build_policy_portfolio,
    compute_efficient_frontier,
    compute_tangent_portfolio,
)
from backend.engine.policy import check_policy, growth_range, sleeve_of, weight_bounds
from backend.engine.quant_models import ewma_lw_cov, production_expected_returns

RF = 0.04
# (annual mean, annual vol, loading on the common equity factor)
SPEC = {
    "us_equity": (0.075, 0.16, 0.85), "uk_equity": (0.065, 0.14, 0.75),
    "europe_ex_uk_equity": (0.07, 0.17, 0.8), "emerging_market_equity": (0.075, 0.20, 0.7),
    "japan_equity": (0.06, 0.15, 0.6), "asia_pacific_equity": (0.065, 0.18, 0.7),
    "global_reits": (0.06, 0.18, 0.6), "commodities_gold": (0.04, 0.15, 0.0),
    "uk_gilts": (0.04, 0.08, -0.1), "uk_inflation_linked": (0.04, 0.10, 0.0),
    "global_bonds": (0.038, 0.05, 0.0), "corporate_bonds": (0.045, 0.07, 0.2),
    "cash_equivalent": (0.04, 0.005, 0.0),
}
AC = {ac: ac for ac in SPEC}  # ticker == asset class in these tests


@pytest.fixture(scope="module")
def inputs():
    rng = np.random.default_rng(11)
    n = 120
    idx = pd.date_range("2016-01-31", periods=n, freq="ME")
    f = rng.standard_normal(n)
    data = {}
    for ac, (m, v, b) in SPEC.items():
        z = b * f + np.sqrt(max(1e-9, 1 - b * b)) * rng.standard_normal(n)
        data[ac] = m / 12 + v / np.sqrt(12) * z
    R = pd.DataFrame(data, index=idx)
    cov = ewma_lw_cov(R)
    mu, _ = production_expected_returns(R, cov, AC, {}, RF)
    mu["cash_equivalent"] = RF
    return mu, cov


def _vol(w, cov):
    s = pd.Series(w).reindex(cov.columns).fillna(0.0)
    return float(np.sqrt(s.values @ cov.values @ s.values))


def _sleeves(w):
    g = sum(v for t, v in w.items() if sleeve_of(AC[t]) == "growth")
    cash = w.get("cash_equivalent", 0.0)
    return g, 1 - g - cash, cash


class TestPolicyAtEveryRisk:
    def test_all_constraints_hold(self, inputs):
        mu, cov = inputs
        for r in range(1, 11):
            res = build_policy_portfolio(r, mu, cov, AC)
            assert check_policy(res["weights"], AC, growth_range(r)) == [], r
            assert sum(res["weights"].values()) == pytest.approx(1.0)

    def test_growth_share_tracks_risk_score(self, inputs):
        mu, cov = inputs
        for r in range(1, 11):
            g, _, _ = _sleeves(build_policy_portfolio(r, mu, cov, AC)["weights"])
            assert g == pytest.approx(0.1 * r, abs=1e-4), (r, g)

    def test_volatility_rises_with_risk(self, inputs):
        mu, cov = inputs
        vols = [_vol(build_policy_portfolio(r, mu, cov, AC)["weights"], cov) for r in range(1, 11)]
        assert all(b > a for a, b in zip(vols, vols[1:])), vols

    def test_bonds_not_cash_do_the_de_risking(self, inputs):
        mu, cov = inputs
        for r in range(1, 10):
            _, bonds, cash = _sleeves(build_policy_portfolio(r, mu, cov, AC)["weights"])
            assert bonds >= cash - 1e-6, (r, bonds, cash)

    def test_no_dust_positions_mid_and_high_risk(self, inputs):
        mu, cov = inputs
        for r in range(3, 11):
            w = build_policy_portfolio(r, mu, cov, AC)["weights"]
            assert min(w.values()) >= POLICY_MIN_POSITION - 1e-9, (r, w)

    def test_uk_home_bias_within_range(self, inputs):
        mu, cov = inputs
        from backend.config import EQUITY_REGION_REFERENCE
        w = build_policy_portfolio(6, mu, cov, AC)["weights"]
        eq = sum(v for t, v in w.items() if t in EQUITY_REGION_REFERENCE)
        assert 0.10 - 1e-3 <= w["uk_equity"] / eq <= 0.25 + 1e-3

    def test_crisis_overlay_lowers_growth_within_policy(self, inputs):
        mu, cov = inputs
        normal = build_policy_portfolio(6, mu, cov, AC)
        crisis = build_policy_portfolio(6, mu, cov, AC, crisis=True)
        assert crisis["growth_weight"] < normal["growth_weight"]
        assert check_policy(crisis["weights"], AC, growth_range(6, crisis=True)) == []


class TestFailuresAreReported:
    def test_infeasible_policy_raises(self, inputs):
        mu, cov = inputs
        sub = ["cash_equivalent", "commodities_gold"]
        with pytest.raises(OptimisationError):
            build_policy_portfolio(5, mu[sub], cov.loc[sub, sub], AC)

    def test_frontier_raises_instead_of_returning_empty(self, inputs):
        mu, cov = inputs
        sub = ["cash_equivalent", "commodities_gold"]
        with pytest.raises(OptimisationError):
            compute_efficient_frontier(mu[sub], cov.loc[sub, sub], None, asset_class_of=AC)

    def test_frontier_spans_policy(self, inputs):
        mu, cov = inputs
        pts = compute_efficient_frontier(mu, cov, None, n_points=10, risk_free_rate=RF, asset_class_of=AC)
        assert len(pts) >= 8
        assert pts[0]["volatility"] < pts[-1]["volatility"]

    def test_no_tangency_when_nothing_allowed_beats_cash(self, inputs):
        # Cash is the only asset above rf but is capped by the policy → no tangency.
        mu, cov = inputs
        low = mu.copy() * 0 + 0.02
        low["cash_equivalent"] = 0.05
        tickers = list(low.index)
        assert compute_tangent_portfolio(low, cov, weight_bounds(tickers, AC), 0.045, AC) is None

    def test_tangency_found_when_it_exists(self, inputs):
        mu, cov = inputs
        tickers = list(mu.index)
        w = compute_tangent_portfolio(mu, cov, weight_bounds(tickers, AC), RF, AC)
        assert w is not None and sum(w.values()) == pytest.approx(1.0, abs=1e-3)


def test_core_universe_matches_policy_sleeves():
    for ac in CORE_UNIVERSE:
        assert sleeve_of(ac) in ("growth", "defensive")
