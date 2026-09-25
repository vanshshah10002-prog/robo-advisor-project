"""
Holdings ledger: units, cost basis, mark-to-market, and the API flow that
opens and refreshes a portfolio. No network: prices and the optimiser are stubbed.
"""

import datetime

import pytest
from fastapi.testclient import TestClient

from backend.engine.ledger import Book, buy, open_portfolio, sell, valuation

TODAY = datetime.date(2026, 9, 24)


class TestLedgerMaths:
    def test_open_portfolio_invests_at_target_weights(self):
        book, fills = open_portfolio(
            10_000, {"A": 0.6, "B": 0.4}, {"A": 50.0, "B": 20.0}, cost_bps=0.0
        )
        assert book.units["A"] == pytest.approx(120.0)
        assert book.units["B"] == pytest.approx(200.0)
        assert book.cash == pytest.approx(0.0)
        val = valuation(book, {"A": 50.0, "B": 20.0})
        assert val["total"] == pytest.approx(10_000)
        assert val["weights"] == pytest.approx({"A": 0.6, "B": 0.4})
        assert len(fills) == 2

    def test_costs_reduce_units_and_enter_cost_basis(self):
        book, fills = open_portfolio(10_000, {"A": 1.0}, {"A": 100.0}, cost_bps=10.0)
        assert fills[0].cost == pytest.approx(10.0)
        assert book.units["A"] == pytest.approx(99.9)
        # Cost basis includes the dealing cost: £10,000 / 99.9 units
        assert book.avg_cost["A"] == pytest.approx(10_000 / 99.9)

    def test_value_moves_exactly_with_price(self):
        book, _ = open_portfolio(10_000, {"A": 0.5, "B": 0.5}, {"A": 10.0, "B": 10.0}, cost_bps=0.0)
        val = valuation(book, {"A": 12.0, "B": 9.0})
        assert val["values"]["A"] == pytest.approx(6_000)
        assert val["values"]["B"] == pytest.approx(4_500)
        assert val["weights"]["A"] == pytest.approx(6_000 / 10_500)

    def test_missing_price_is_an_error_not_a_guess(self):
        book = Book(units={"A": 1.0}, avg_cost={"A": 1.0})
        with pytest.raises(ValueError):
            valuation(book, {})

    def test_sell_realises_gain_at_average_cost(self):
        book = Book(cash=1_000.0)
        buy(book, "A", 1_000, 10.0, cost_bps=0.0)   # 100 units @ £10
        f = sell(book, "A", 600, 12.0, cost_bps=0.0)  # 50 units @ £12
        assert f.units == pytest.approx(50.0)
        assert f.realised_gain == pytest.approx(100.0)
        assert book.units["A"] == pytest.approx(50.0)
        assert book.cash == pytest.approx(600.0)

    def test_buy_cannot_overspend_cash(self):
        with pytest.raises(ValueError):
            buy(Book(cash=100.0), "A", 200.0, 1.0)


# =============================================================================
# API flow with stubbed optimiser and prices
# =============================================================================

FAKE_RESULT = {
    "weights": {"us_equity": 0.6, "uk_gilts": 0.4},
    "ticker_weights": {"VUAG.L": 0.6, "IGLT.L": 0.4},
    "allocations": [
        {"asset_class": "us_equity", "ticker": "VUAG.L", "weight": 0.6,
         "amount_gbp": 6000.0, "expense_ratio": 0.0007},
        {"asset_class": "uk_gilts", "ticker": "IGLT.L", "weight": 0.4,
         "amount_gbp": 4000.0, "expense_ratio": 0.0007},
    ],
    "performance": {"expected_return": 0.06, "volatility": 0.10, "sharpe_ratio": 0.2},
    "total_expense_ratio": 0.0007,
    "risk_free_rate": 0.04,
    "asset_classes_used": ["us_equity", "uk_gilts"],
}


@pytest.fixture
def api(monkeypatch):
    import backend.api.routes.portfolio as portfolio_routes
    import backend.data.prices as prices_mod
    from backend.main import app

    state = {"prices": {"VUAG.L": 100.0, "IGLT.L": 10.0}}

    def fake_quotes(tickers):
        return {t: (state["prices"][t], TODAY) for t in tickers if t in state["prices"]}

    monkeypatch.setattr(portfolio_routes, "build_optimised_portfolio", lambda **kw: FAKE_RESULT)
    monkeypatch.setattr(portfolio_routes, "get_latest_gbp_prices", fake_quotes)
    monkeypatch.setattr(prices_mod, "get_latest_gbp_prices", fake_quotes)
    return TestClient(app), state


def _create(client):
    r = client.post("/api/portfolio", json={
        "user_id": 1, "risk_score": 5, "investment_amount": 10_000, "uses_isa": True,
    })
    assert r.status_code == 200, r.text
    return r.json()["portfolio_id"]


class TestLedgerApi:
    def test_create_stores_units_and_transactions(self, api):
        client, _ = api
        pid = _create(client)
        p = client.get(f"/api/portfolio/{pid}").json()
        units = {h["ticker"]: h["units"] for h in p["holdings"]}
        # £6,000 less 10bp cost at £100 → 59.94 units
        assert units["VUAG.L"] == pytest.approx(5_994 / 100.0)
        assert units["IGLT.L"] == pytest.approx(3_996 / 10.0)
        assert p["net_contributions"] == pytest.approx(10_000)
        tx = client.get(f"/api/transactions/{pid}").json()
        assert sorted(t["action"] for t in tx) == ["buy", "buy", "deposit"]

    def test_alpha_uses_live_risk_free_rate(self, api):
        client, _ = api
        r = client.post("/api/portfolio", json={
            "user_id": 1, "risk_score": 5, "investment_amount": 10_000,
        })
        assert r.json()["alpha"] == pytest.approx(0.06 - 0.04)

    def test_refresh_marks_to_market(self, api):
        client, state = api
        pid = _create(client)
        state["prices"] = {"VUAG.L": 110.0, "IGLT.L": 10.0}  # US equity +10%
        r = client.post(f"/api/portfolio/{pid}/refresh").json()
        expected_total = 59.94 * 110.0 + 399.6 * 10.0
        assert r["total_value"] == pytest.approx(expected_total, abs=0.01)
        assert r["total_return_pct"] == pytest.approx(expected_total / 10_000 - 1)
        assert r["stale_tickers"] == []

    def test_refresh_flags_missing_price_and_keeps_last(self, api):
        client, state = api
        pid = _create(client)
        state["prices"] = {"VUAG.L": 100.0}  # gilt price unavailable
        r = client.post(f"/api/portfolio/{pid}/refresh").json()
        assert r["stale_tickers"] == ["IGLT.L"]
        assert r["total_value"] == pytest.approx(9_990.0, abs=0.01)

    def test_create_refuses_without_prices(self, api):
        client, state = api
        state["prices"] = {"VUAG.L": 100.0}
        r = client.post("/api/portfolio", json={
            "user_id": 1, "risk_score": 5, "investment_amount": 10_000,
        })
        assert r.status_code == 503
        assert "IGLT.L" in r.json()["detail"]
