"""
Value history replayed from the ledger (engine and API).
"""

import datetime

import pandas as pd
import pytest

from backend.engine.history import Trade, price_panel, replay

D = datetime.date


def closes(rows: dict[str, list[float]], start="2026-09-21") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(next(iter(rows.values()))))
    return pd.DataFrame(rows, index=idx)


def opening(day=D(2026, 9, 21), amount=1_000.0, price=10.0, cost=1.0) -> list[Trade]:
    units = (amount - cost) / price
    return [
        Trade(day, "CASH", "deposit", 0.0, 1.0, amount, 0.0),
        Trade(day, "AAA", "buy", units, price, units * price, cost),
    ]


class TestReplay:
    def test_values_units_at_each_close_and_starts_below_the_deposit_by_the_cost(self):
        series = replay(opening(), closes({"AAA": [10.0, 11.0, 9.9]}), D(2026, 9, 23))

        assert list(series.index.date) == [D(2026, 9, 21), D(2026, 9, 22), D(2026, 9, 23)]
        assert series["value"].iloc[0] == pytest.approx(999.0)
        assert series["cumulative_return"].iloc[0] == pytest.approx(-0.001)
        assert series["value"].iloc[1] == pytest.approx(99.9 * 11.0)
        assert series["net_contributions"].iloc[-1] == 1_000.0

    def test_a_deposit_is_not_counted_as_growth(self):
        trades = opening() + [
            Trade(D(2026, 9, 22), "CASH", "deposit", 0.0, 1.0, 500.0, 0.0),
        ]
        series = replay(trades, closes({"AAA": [10.0, 10.0, 10.0]}), D(2026, 9, 23))

        assert series["value"].iloc[-1] == pytest.approx(1_499.0)
        assert series["net_contributions"].iloc[-1] == 1_500.0
        # Only the opening cost ever moved the time-weighted return.
        assert series["cumulative_return"].iloc[-1] == pytest.approx(-0.001)

    def test_time_weighted_return_chains_daily_returns(self):
        trades = opening(cost=0.0) + [
            Trade(D(2026, 9, 22), "CASH", "deposit", 0.0, 1.0, 1_100.0, 0.0),
        ]
        # The fund rises 10% twice; the £1,100 deposit lands on day 2 and sits in cash.
        # Day 2: (2,200 − 1,000 − 1,100) / (1,000 + 1,100) = +4.76%; day 3: 2,310 / 2,200 = +5%.
        series = replay(trades, closes({"AAA": [10.0, 11.0, 12.1]}), D(2026, 9, 23))
        assert list(series["value"]) == pytest.approx([1_000.0, 2_200.0, 2_310.0])
        assert series["cumulative_return"].iloc[-1] == pytest.approx((2_200 / 2_100) * 1.05 - 1)

    def test_a_weekend_opening_uses_the_trade_price_until_the_next_close(self):
        trades = opening(day=D(2026, 9, 20))   # Sunday
        series = replay(trades, closes({"AAA": [12.0]}, start="2026-09-21"), D(2026, 9, 21))

        assert series.index[0].date() == D(2026, 9, 20)
        assert series["value"].iloc[0] == pytest.approx(999.0)
        assert series["value"].iloc[1] == pytest.approx(99.9 * 12.0)

    def test_sells_return_cash_net_of_cost(self):
        trades = opening(cost=0.0) + [Trade(D(2026, 9, 22), "AAA", "sell", 50.0, 10.0, 500.0, 0.5)]
        series = replay(trades, closes({"AAA": [10.0, 10.0]}), D(2026, 9, 22))

        assert series["cash"].iloc[-1] == pytest.approx(499.5)
        assert series["value"].iloc[-1] == pytest.approx(999.5)

    def test_no_trades_gives_an_empty_series(self):
        assert replay([], closes({"AAA": [1.0]}), D(2026, 9, 21)).empty

    def test_prices_are_never_back_filled(self):
        trades = opening(day=D(2026, 9, 22))
        panel = price_panel(trades, closes({"AAA": [float("nan"), float("nan"), 11.0]}),
                            pd.bdate_range("2026-09-21", periods=3))
        assert pd.isna(panel["AAA"].iloc[0])
        assert list(panel["AAA"].iloc[1:]) == [10.0, 11.0]


class TestHistoryApi:
    def test_history_from_the_portfolios_own_trades(self, api, create_portfolio, monkeypatch):
        import backend.data.prices as prices_mod
        client, _ = api
        pid = create_portfolio(client)
        today = pd.Timestamp(datetime.date.today())
        monkeypatch.setattr(prices_mod, "get_gbp_close_history", lambda tickers, start: pd.DataFrame(
            {"VUAG.L": [110.0], "IGLT.L": [10.0]}, index=[today]))

        body = client.get(f"/api/portfolio/{pid}/history").json()

        assert body["reason"] is None and body["points"]
        last = body["points"][-1]
        assert last["net_contributions"] == 10_000
        # 60% of £10,000 in VUAG rose 10% on the day: about +6% less the opening cost.
        assert last["cumulative_return"] == pytest.approx(0.059, abs=0.002)
        assert body["time_weighted_return"] == last["cumulative_return"]

    def test_portfolios_without_recorded_trades_explain_why_history_is_empty(self, api, create_portfolio):
        from backend.db.database import SessionLocal
        from backend.db.models import Transaction
        client, _ = api
        pid = create_portfolio(client)
        db = SessionLocal()
        db.query(Transaction).filter(Transaction.portfolio_id == pid).delete()
        db.commit()
        db.close()

        body = client.get(f"/api/portfolio/{pid}/history").json()
        assert body["points"] == [] and "before trades were recorded" in body["reason"]

    def test_unknown_portfolio_is_404(self, api):
        client, _ = api
        assert client.get("/api/portfolio/999999/history").status_code == 404
