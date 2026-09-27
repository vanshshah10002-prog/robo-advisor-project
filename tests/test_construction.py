"""
Preview, construction snapshot and the valued portfolio list.

The optimiser and prices are stubbed (tests/conftest.py); these tests check
what the API does with a construction, not the construction itself.
"""

import copy

import pytest

from backend.config import VOL_CALIBRATION_MULTIPLIER
from backend.engine.construction import ConstructionCache, scaled_allocations, snapshot_from_result
from tests.conftest import FAKE_RESULT

RICH_RESULT = {
    **copy.deepcopy(FAKE_RESULT),
    "policy": {"growth_target": 0.6, "growth_range": [0.6, 0.6], "growth_weight": 0.6,
               "defensive_weight": 0.4, "cash_weight": 0.0},
    "frontier": [{"expected_return": 0.07, "volatility": 0.12, "sharpe_ratio": 0.25, "weights": {}},
                 {"expected_return": 0.03, "volatility": 0.04, "sharpe_ratio": 0.1, "weights": {}}],
    "inputs": {
        "expected_returns": {"VUAG.L": 0.075, "IGLT.L": 0.04},
        "volatilities": {"VUAG.L": 0.17, "IGLT.L": 0.07},
        "correlation": {"tickers": ["VUAG.L", "IGLT.L"], "matrix": [[1.0, -0.1], [-0.1, 1.0]]},
        "vol_calibration": VOL_CALIBRATION_MULTIPLIER,
    },
    "etf_fallbacks": {"uk_equity": ["ISF.L"]},
}


class TestConstructionCache:
    def test_reuses_a_build_within_its_lifetime(self):
        now = [0.0]
        cache = ConstructionCache(ttl=100, clock=lambda: now[0])
        calls = []

        def build():
            calls.append(1)
            return {"n": len(calls)}

        first, reused_first = cache.get_or_build(5.0, build)
        now[0] = 99
        second, reused_second = cache.get_or_build(5.004, build)   # same key after rounding

        assert first is second
        assert (reused_first, reused_second) == (False, True)
        assert len(calls) == 1

    def test_rebuilds_after_expiry_and_per_risk_score(self):
        now = [0.0]
        cache = ConstructionCache(ttl=100, clock=lambda: now[0])
        cache.get_or_build(5.0, lambda: {"v": 1})
        cache.get_or_build(6.0, lambda: {"v": 2})
        now[0] = 101

        result, reused = cache.get_or_build(5.0, lambda: {"v": 3})
        assert (result, reused) == ({"v": 3}, False)

    def test_a_failed_build_is_not_cached(self):
        cache = ConstructionCache(ttl=100)

        def boom():
            raise ValueError("no data")

        with pytest.raises(ValueError):
            cache.get_or_build(5.0, boom)
        assert cache.get(5.0) is None


class TestSnapshot:
    def test_records_estimates_policy_and_calibrated_frontier(self):
        snap = snapshot_from_result(RICH_RESULT, 5.0)

        assert [h["ticker"] for h in snap["holdings"]] == ["VUAG.L", "IGLT.L"]
        vuag = snap["holdings"][0]
        assert (vuag["sleeve"], vuag["expected_return"], vuag["volatility"]) == ("growth", 0.075, 0.17)
        assert snap["holdings"][1]["sleeve"] == "defensive"
        assert snap["policy"]["growth_target"] == 0.6
        # Frontier volatility is put on the portfolio's (calibrated) scale, sorted by risk.
        assert [p["volatility"] for p in snap["frontier"]] == pytest.approx(
            [0.04 * VOL_CALIBRATION_MULTIPLIER, 0.12 * VOL_CALIBRATION_MULTIPLIER])
        assert snap["correlation"]["tickers"] == ["VUAG.L", "IGLT.L"]
        assert snap["etf_fallbacks"] == {"uk_equity": ["ISF.L"]}

    def test_tolerates_results_without_inputs(self):
        snap = snapshot_from_result(FAKE_RESULT, 5.0)
        assert snap["holdings"][0]["expected_return"] is None
        assert snap["frontier"] == [] and snap["correlation"] == {"tickers": [], "matrix": []}

    def test_scales_allocations_to_the_amount(self):
        allocs = scaled_allocations(FAKE_RESULT, 25_000)
        assert [a["amount_gbp"] for a in allocs] == [15_000.0, 10_000.0]


@pytest.fixture
def counted_builder(api, monkeypatch):
    """Count optimiser calls and serve the rich result."""
    import backend.api.routes.portfolio as portfolio_routes
    calls = []

    def build(**kw):
        calls.append(kw)
        return RICH_RESULT

    monkeypatch.setattr(portfolio_routes, "build_optimised_portfolio", build)
    return calls


class TestPreview:
    def test_previews_without_storing_anything(self, api, counted_builder):
        client, _ = api
        before = len(client.get("/api/portfolios/user/1").json())

        r = client.post("/api/portfolio/preview", json={"risk_score": 6, "investment_amount": 20_000})

        assert r.status_code == 200, r.text
        body = r.json()
        assert [a["amount_gbp"] for a in body["allocations"]] == [12_000.0, 8_000.0]
        assert [a["sleeve"] for a in body["allocations"]] == ["growth", "defensive"]
        assert body["annual_fund_cost_gbp"] == pytest.approx(0.0007 * 20_000)
        assert body["policy"]["growth_target"] == 0.6
        assert body["capped"] is False
        assert len(client.get("/api/portfolios/user/1").json()) == before

    def test_opening_after_a_preview_reuses_its_construction(self, api, counted_builder):
        client, _ = api
        client.post("/api/portfolio/preview", json={"risk_score": 5, "investment_amount": 5_000})
        r = client.post("/api/portfolio", json={"user_id": 1, "risk_score": 5, "investment_amount": 10_000})

        assert r.status_code == 200, r.text
        assert len(counted_builder) == 1
        assert counted_builder[0]["investment_amount"] == 1.0

    def test_preview_is_capped_by_the_stored_profile(self, api, counted_builder):
        from backend.db.database import SessionLocal
        from backend.db.models import RiskProfile, User
        client, _ = api
        db = SessionLocal()
        if not db.query(User).filter(User.id == 77).first():
            db.add(User(id=77, name="Capped"))
            db.add(RiskProfile(user_id=77, subjective_score=4, objective_score=4, composite_score=4,
                               risk_band="Moderately Conservative", quiz_answers=[], objective_inputs={},
                               time_horizon_years=5))
            db.commit()
        db.close()

        body = client.post("/api/portfolio/preview", json={
            "user_id": 77, "risk_score": 9, "investment_amount": 10_000}).json()

        assert (body["requested_risk_score"], body["risk_score"], body["capped"]) == (9, 4, True)
        assert body["risk_band"] == "Moderately Conservative"


class TestConstructionEndpoint:
    def test_a_new_portfolio_records_how_it_was_built(self, api, counted_builder, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)

        body = client.get(f"/api/portfolio/{pid}/construction").json()

        assert body["recorded"] is True
        assert body["snapshot"]["holdings"][0]["expected_return"] == 0.075
        assert body["snapshot"]["policy"]["growth_weight"] == 0.6

    def test_older_portfolios_say_nothing_was_recorded(self, api, create_portfolio):
        from backend.db.database import SessionLocal
        from backend.db.models import Portfolio
        client, _ = api
        pid = create_portfolio(client)
        db = SessionLocal()
        db.query(Portfolio).filter(Portfolio.id == pid).update({"construction": None})
        db.commit()
        db.close()

        assert client.get(f"/api/portfolio/{pid}/construction").json() == {
            "portfolio_id": pid, "recorded": False, "snapshot": None}

    def test_unknown_portfolio_is_404(self, api):
        client, _ = api
        assert client.get("/api/portfolio/999999/construction").status_code == 404


class TestPortfolioList:
    def test_lists_newest_first_with_values(self, api, create_portfolio):
        client, state = api
        first = create_portfolio(client)
        second = create_portfolio(client)
        state["prices"]["VUAG.L"] = 110.0
        client.post(f"/api/portfolio/{second}/refresh")

        items = client.get("/api/portfolios/user/1").json()
        ids = [i["portfolio_id"] for i in items]
        assert ids.index(second) < ids.index(first)

        item = next(i for i in items if i["portfolio_id"] == second)
        # 60% in VUAG rose 10%: value about £10,600 less the opening cost.
        assert item["total_value"] == pytest.approx(10_590, abs=15)
        assert item["total_return_pct"] == pytest.approx(item["total_value"] / 10_000 - 1)
        assert item["holdings_count"] == 2
        assert item["uses_isa"] is True

    def test_a_never_valued_legacy_portfolio_has_no_value(self, api, create_portfolio):
        from backend.db.database import SessionLocal
        from backend.db.models import Holding
        client, _ = api
        pid = create_portfolio(client)
        db = SessionLocal()
        # Legacy rows stored a GBP amount in `quantity` and no cost basis.
        db.query(Holding).filter(Holding.portfolio_id == pid).update({"average_cost": 0.0})
        db.commit()
        db.close()

        item = next(i for i in client.get("/api/portfolios/user/1").json() if i["portfolio_id"] == pid)
        assert item["total_value"] is None and item["total_return_pct"] is None
