"""
Universe view, track record artefact and API, Monte Carlo summaries.
"""

import json

import numpy as np
import pandas as pd
import pytest

from backend.config import CORE_UNIVERSE, POLICY_BLOCK_MAX
from backend.engine.monte_carlo import paid_in_by_year, quick_projection, summarise_paths
from backend.engine.universe_view import build_universe
from backend.eval.track_record import build_artefact, calendar_years, track_record_entry, weekly_series
from backend.eval.walkforward_backtest import BacktestResult, Decision


class TestUniverse:
    def test_every_core_block_growth_first(self):
        blocks = build_universe()
        assert {b["asset_class"] for b in blocks} == set(CORE_UNIVERSE)
        sleeves = [b["sleeve"] for b in blocks]
        assert sleeves == sorted(sleeves, key=lambda s: s != "growth")

    def test_candidates_follow_preference_and_state_the_rule(self):
        by_class = {b["asset_class"]: b for b in build_universe()}
        gilts = by_class["uk_gilts"]
        assert [c["preferred"] for c in gilts["candidates"]][0] is True
        assert sum(c["preferred"] for c in gilts["candidates"]) == 1
        assert gilts["max_weight"] == POLICY_BLOCK_MAX["uk_gilts"]
        assert "35%" in gilts["rule"]
        us = by_class["us_equity"]
        assert us["equity_share_range"] is not None and "of the shares" in us["rule"]
        assert "defensive" in by_class["cash_equivalent"]["rule"]

    def test_marks_what_a_portfolio_holds(self):
        blocks = build_universe({"VUAG.L": {"asset_class": "us_equity", "weight": 0.61}}, {"us_equity": 0.6})
        us = next(b for b in blocks if b["asset_class"] == "us_equity")
        assert (us["held_ticker"], us["held_weight"], us["target_weight"]) == ("VUAG.L", 0.61, 0.6)
        assert next(b for b in blocks if b["asset_class"] == "uk_gilts")["held_ticker"] is None

    def test_api_marks_holdings_and_404s_unknown_portfolio(self, api, create_portfolio):
        client, _ = api
        pid = create_portfolio(client)
        body = client.get(f"/api/universe?portfolio_id={pid}").json()
        held = {b["asset_class"]: b["held_ticker"] for b in body["blocks"] if b["held_ticker"]}
        assert held == {"us_equity": "VUAG.L", "uk_gilts": "IGLT.L"}
        assert client.get("/api/universe?portfolio_id=999999").status_code == 404
        assert len(client.get("/api/universe").json()["blocks"]) == len(CORE_UNIVERSE)


def _result(values: list[float], start="2024-12-20", expected=0.05) -> BacktestResult:
    idx = pd.bdate_range(start, periods=len(values))
    equity = pd.DataFrame({"value": values, "cash": 0.0, "rf": 0.04}, index=idx)
    events = pd.DataFrame([{"reason": "initial", "cost_gbp": 10.0, "turnover": 1.0},
                           {"reason": "drift", "cost_gbp": 2.0, "turnover": 0.1}])
    decision = Decision(date=idx[0], weights={"A": 1.0}, asset_class_of={"A": "us_equity"},
                        growth_target=1.0, risk_free=0.04, expected_return=expected,
                        volatility_model=0.1, volatility=0.115)
    return BacktestResult(equity=equity, decisions=[decision], orders=[], checks=pd.DataFrame(),
                          events=events, fills=pd.DataFrame([{}] * 3))


class TestTrackRecord:
    def test_weekly_series_keeps_the_last_day(self):
        s = pd.Series(np.arange(12.0), index=pd.bdate_range("2025-01-01", periods=12))
        points = weekly_series(s, s * 2, step=5)
        assert [p["strategy"] for p in points] == [0.0, 5.0, 10.0, 11.0]
        assert points[-1]["benchmark"] == 22.0

    def test_calendar_years_chain_and_flag_partial_years(self):
        idx = pd.DatetimeIndex(["2024-12-20", "2024-12-31", "2025-06-30", "2025-12-31", "2026-03-31"])
        s = pd.Series([100.0, 110.0, 99.0, 121.0, 133.1], index=idx)
        years = calendar_years(s, s)
        assert [y["year"] for y in years] == [2024, 2025, 2026]
        assert [round(y["strategy"], 4) for y in years] == [0.1, 0.1, 0.1]
        assert [y["partial"] for y in years] == [True, False, True]

    def test_entry_summarises_both_runs(self):
        strategy = _result([100_000.0 * 1.001 ** i for i in range(300)])
        benchmark = _result([100_000.0 * 1.0005 ** i for i in range(300)])
        entry = track_record_entry(strategy, benchmark, "Two-fund 50%/50%")

        assert entry["strategy"]["total_return"] > entry["benchmark"]["total_return"] > 0
        assert entry["costs_gbp"] == 12.0 and entry["rebalances"] == 1
        assert entry["forecast_return"] == pytest.approx(0.05)
        assert entry["forecast_volatility"] == pytest.approx(0.115)
        assert entry["series"][0]["date"] == "2024-12-20"

    def test_artefact_is_json_safe(self):
        art = build_artefact({3: {"x": float("nan")}}, "2021-09-27", "2026-09-25", 100_000.0, "now", "then")
        assert json.loads(json.dumps(art))["risks"]["3"]["x"] is None

    def test_api_serves_the_artefact(self, api, tmp_path, monkeypatch):
        import backend.api.routes.insight as insight
        client, _ = api
        strategy = _result([100_000.0 * 1.001 ** i for i in range(300)])
        art = build_artefact({5: track_record_entry(strategy, strategy, "Two-fund 50%/50%")},
                             "2024-12-20", "2026-02-10", 100_000.0, "2026-09-26T00:00:00+00:00", "x")
        path = tmp_path / "track_record.json"
        path.write_text(json.dumps(art), encoding="utf-8")
        monkeypatch.setattr(insight, "TRACK_RECORD_PATH", str(path))
        insight._load_track_record.cache_clear()

        body = client.get("/api/strategy/track-record?risk=5").json()
        assert body["risk"] == 5 and body["benchmark_label"] == "Two-fund 50%/50%"
        assert body["notes"] and body["series"]
        assert client.get("/api/strategy/track-record?risk=4").status_code == 404
        assert client.get("/api/strategy/track-record?risk=11").status_code == 422

    def test_committed_artefact_covers_every_risk_level(self):
        import backend.api.routes.insight as insight
        insight._load_track_record.cache_clear()
        data = insight.load_track_record()
        assert data is not None, "run scripts/build_track_record.py"
        assert sorted(int(r) for r in data["risks"]) == list(range(1, 11))


class TestMonteCarloSummaries:
    def test_paid_in_grows_contributions_with_inflation(self):
        paid = paid_in_by_year(1_000.0, 100.0, 2, inflation_rate=0.0)
        assert list(paid) == [1_000.0, 2_200.0, 3_400.0]
        assert paid_in_by_year(0.0, 100.0, 1, inflation_rate=0.12)[1] > 1_200.0

    def test_probabilities_count_paths_below_what_was_paid_in(self):
        paths = np.array([[100.0] * 13, [100.0] * 12 + [80.0], [100.0] * 12 + [150.0]])
        out = summarise_paths(paths, 100.0, 0.0, 1, goal_amount=120.0, inflation_rate=0.0)
        assert out["loss_probability_by_year"] == [0.0, pytest.approx(1 / 3, abs=1e-4)]
        assert out["probability_of_loss"] == pytest.approx(1 / 3, abs=1e-4)
        assert out["probability_of_goal"] == pytest.approx(1 / 3)
        assert out["contributions"] == [100.0, 100.0]

    def test_real_terms_deflate_values_but_not_probabilities(self):
        nominal = quick_projection(10_000, 100, 0.05, 0.1, years=5, n_simulations=400, goal_amount=12_000)
        real = quick_projection(10_000, 100, 0.05, 0.1, years=5, n_simulations=400, goal_amount=12_000,
                                real_terms=True)
        assert real["percentile_50"][-1] == pytest.approx(nominal["percentile_50"][-1] / 1.025 ** 5, rel=1e-6)
        assert real["probability_of_goal"] == nominal["probability_of_goal"]
        assert real["probability_of_loss"] == nominal["probability_of_loss"]
        assert real["real_terms"] is True and nominal["real_terms"] is False

    def test_api_projects_an_unsaved_preview(self, api):
        client, _ = api
        r = client.post("/api/monte-carlo", json={
            "initial_investment": 10_000, "monthly_contribution": 200, "years": 10,
            "n_simulations": 500, "annual_return": 0.05, "annual_volatility": 0.1,
            "goal_amount": 30_000, "real_terms": True,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["percentile_50"]) == 11 and len(body["loss_probability_by_year"]) == 11
        assert 0 <= body["probability_of_goal"] <= 1 and body["real_terms"] is True

    def test_api_needs_some_inputs(self, api):
        client, _ = api
        r = client.post("/api/monte-carlo", json={"initial_investment": 10_000})
        assert r.status_code == 400
