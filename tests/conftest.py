"""
Test setup: point the app at a throwaway SQLite database BEFORE any backend
module reads DATABASE_URL, so API tests never touch backend/data/portfolios.db.
"""

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="robo-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"


# =============================================================================
# API fixtures: stubbed optimiser and prices, no network
# =============================================================================
# Imported after DATABASE_URL is set above.
import datetime  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TODAY = datetime.date(2026, 9, 24)

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
    from backend.db.database import init_db
    from backend.engine.construction import construction_cache
    from backend.main import app

    init_db()   # TestClient without a `with` block does not run the app's startup
    construction_cache.clear()

    state = {"prices": {"VUAG.L": 100.0, "IGLT.L": 10.0}}

    def fake_quotes(tickers):
        return {t: (state["prices"][t], TODAY) for t in tickers if t in state["prices"]}

    monkeypatch.setattr(portfolio_routes, "build_optimised_portfolio", lambda **kw: FAKE_RESULT)
    monkeypatch.setattr(portfolio_routes, "get_latest_gbp_prices", fake_quotes)
    monkeypatch.setattr(prices_mod, "get_latest_gbp_prices", fake_quotes)
    return TestClient(app), state


def _create(client):
    """Open the standard 60/40 test portfolio and return its id."""
    r = client.post("/api/portfolio", json={
        "user_id": 1, "risk_score": 5, "investment_amount": 10_000, "uses_isa": True,
    })
    assert r.status_code == 200, r.text
    return r.json()["portfolio_id"]


@pytest.fixture
def create_portfolio():
    return _create
