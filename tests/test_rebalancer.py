"""
Rebalancer: tolerance bands, portfolio drift, cash-flow allocation, netted
trade plans, and the API flow (drift → plan → execute → deposit).
"""

import pytest

from backend.engine.rebalancer import (
    check_drift,
    plan_inflow,
    plan_rebalance,
    portfolio_drift,
    tolerance_band,
)


class TestBands:
    def test_large_sleeve_uses_absolute_band(self):
        assert tolerance_band(0.40) == pytest.approx(0.05)

    def test_small_sleeve_uses_relative_band(self):
        assert tolerance_band(0.08) == pytest.approx(0.02)

    def test_band_never_below_floor(self):
        assert tolerance_band(0.02) == pytest.approx(0.01)
        assert tolerance_band(0.0) == pytest.approx(0.01)

    def test_small_sleeve_that_doubles_triggers(self):
        # 4% target drifting to 7%: absolute 5pp rule would miss it.
        r = check_drift({"A": 0.93, "B": 0.07}, {"A": 0.96, "B": 0.04})
        assert "B" in r.out_of_band
        assert r.needs_rebalance

    def test_zero_weight_is_drift_not_on_target(self):
        r = check_drift({"A": 1.0}, {"A": 0.9, "B": 0.1})
        assert r.drift["B"] == pytest.approx(-0.1)
        assert r.needs_rebalance

    def test_portfolio_drift_is_half_sum_abs(self):
        assert portfolio_drift({"A": 0.62, "B": 0.38}, {"A": 0.6, "B": 0.4}) == pytest.approx(0.02)

    def test_within_bands_no_trigger(self):
        r = check_drift({"A": 0.61, "B": 0.39}, {"A": 0.6, "B": 0.4})
        assert not r.needs_rebalance

    def test_group_range_breach_triggers(self):
        r = check_drift(
            {"EQ": 0.64, "BD": 0.36}, {"EQ": 0.6, "BD": 0.4},
            group_of={"EQ": "growth", "BD": "defensive"},
            group_ranges={"growth": (0.55, 0.63)},
        )
        assert r.groups_out_of_range == ["growth"]
        assert r.needs_rebalance


class TestInflow:
    def test_fills_most_underweight_first(self):
        # Value 10k: A 7k (target 60%), B 3k (target 40%). Deposit £500.
        plan = plan_inflow(500, {"A": 7_000, "B": 3_000}, {"A": 0.6, "B": 0.4})
        assert plan == pytest.approx({"B": 500})

    def test_remainder_spread_by_target_after_deficits(self):
        # At £12k total: A deficit 200, B deficit 1,800 — the deposit fills both exactly
        plan = plan_inflow(2_000, {"A": 7_000, "B": 3_000}, {"A": 0.6, "B": 0.4})
        assert sum(plan.values()) == pytest.approx(2_000)
        total = 12_000
        after = {"A": 7_000 + plan.get("A", 0), "B": 3_000 + plan["B"]}
        assert after["B"] / total == pytest.approx(0.4)

    def test_never_overfills_when_cash_exceeds_deficit(self):
        plan = plan_inflow(10_000, {"A": 7_000, "B": 3_000}, {"A": 0.6, "B": 0.4})
        after = {"A": 7_000 + plan["A"], "B": 3_000 + plan["B"]}
        assert after["A"] / 20_000 == pytest.approx(0.6)
        assert after["B"] / 20_000 == pytest.approx(0.4)


class TestPlan:
    PRICES = {"A": 10.0, "B": 20.0, "C": 5.0}

    def test_trades_net_to_zero_after_costs(self):
        trades = plan_rebalance({"A": 7_000, "B": 3_000}, 0.0, {"A": 0.6, "B": 0.4},
                                self.PRICES, cost_bps=10)
        sells = sum(t.value_gbp for t in trades if t.action == "sell")
        buys = sum(t.value_gbp for t in trades if t.action == "buy")
        assert buys == pytest.approx(sells * (1 - 0.001), abs=0.01)

    def test_sizes_from_market_value(self):
        trades = plan_rebalance({"A": 14_000, "B": 6_000}, 0.0, {"A": 0.6, "B": 0.4},
                                self.PRICES, cost_bps=0)
        sell = next(t for t in trades if t.action == "sell")
        assert sell.value_gbp == pytest.approx(2_000)  # 70% → 60% of £20k

    def test_small_trades_skipped(self):
        trades = plan_rebalance({"A": 6_010, "B": 3_990}, 0.0, {"A": 0.6, "B": 0.4},
                                self.PRICES, cost_bps=0)
        assert trades == []  # £10 < max(£25, 0.25% × £10k)

    def test_untargeted_holding_sold_in_full(self):
        trades = plan_rebalance({"A": 6_000, "B": 3_990, "C": 10}, 0.0, {"A": 0.6, "B": 0.4},
                                self.PRICES, cost_bps=0)
        c = next(t for t in trades if t.ticker == "C")
        assert c.action == "sell" and c.value_gbp == pytest.approx(10)

    def test_realised_gain_estimated(self):
        trades = plan_rebalance({"A": 7_000, "B": 3_000}, 0.0, {"A": 0.6, "B": 0.4},
                                self.PRICES, avg_cost={"A": 8.0}, cost_bps=0)
        sell = next(t for t in trades if t.action == "sell")
        assert sell.est_realised_gain_gbp == pytest.approx(1_000 - 100 * 8.0)

    def test_missing_price_refuses(self):
        with pytest.raises(ValueError):
            plan_rebalance({"A": 7_000, "B": 3_000}, 0.0, {"A": 0.6, "B": 0.4}, {"A": 10.0})


class TestRebalanceApi:
    def test_price_move_triggers_and_execute_restores_target(self, api, create_portfolio):
        client, state = api
        pid = create_portfolio(client)
        assert client.get(f"/api/rebalance/{pid}").json()["needs_rebalance"] is False

        state["prices"] = {"VUAG.L": 140.0, "IGLT.L": 10.0}  # equity +40%
        plan = client.get(f"/api/rebalance/{pid}").json()
        assert plan["needs_rebalance"] is True
        assert any(r.startswith("growth weight") for r in plan["reasons"])  # 60% → ~68%, beyond ±5pp
        assert {t["action"] for t in plan["trades"]} == {"buy", "sell"}
        assert plan["cgt_applies"] is False  # ISA

        done = client.post(f"/api/rebalance/{pid}/execute").json()
        assert done["executed"] is True
        after = client.get(f"/api/performance/{pid}").json()
        weights = {h["ticker"]: h["current_weight"] for h in after["holdings"]}
        assert weights["VUAG.L"] == pytest.approx(0.6, abs=0.002)
        assert after["needs_rebalance"] is False
        # Trading costs are the only loss of value
        assert after["total_value"] == pytest.approx(plan["total_value_gbp"] - done["est_total_cost_gbp"], abs=0.05)

    def test_execute_refused_with_stale_price(self, api, create_portfolio):
        client, state = api
        pid = create_portfolio(client)
        state["prices"] = {"VUAG.L": 140.0}
        r = client.post(f"/api/rebalance/{pid}/execute")
        assert r.status_code == 409

    def test_deposit_goes_to_underweight(self, api, create_portfolio):
        client, state = api
        pid = create_portfolio(client)
        state["prices"] = {"VUAG.L": 120.0, "IGLT.L": 10.0}
        r = client.post(f"/api/portfolio/{pid}/contribute", json={"amount_gbp": 500}).json()
        assert [b["ticker"] for b in r["buys"]] == ["IGLT.L"]
        perf = client.get(f"/api/performance/{pid}").json()
        assert perf["net_contributions"] == pytest.approx(10_500)
