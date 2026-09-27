"""
Walk-forward backtest: point-in-time inputs, execution timing, accounting and
the look-ahead test (change or delete every price after a date D; nothing
decided or executed on or before D may change). Synthetic prices, no network.
"""

import numpy as np
import pandas as pd
import pytest

from backend.config import CORE_UNIVERSE
from backend.eval.backtest_data import (
    PricePanel,
    causal_unit_fix,
    clean_ticker,
    fx_for_prices,
    gbp_prices,
    to_gbp,
    total_return_index,
    trading_calendar,
)
from backend.eval.backtest_metrics import (
    accuracy_summary,
    cagr,
    forecast_periods,
    max_drawdown,
    performance_summary,
)
from backend.eval.walkforward_backtest import (
    SimConfig,
    decide_policy_portfolio,
    fixed_mix_decider,
    month_end_prices,
    resolve_universe_at,
    risk_free_at,
    run_backtest,
    usable_at,
)

# (annual drift, annual vol, loading on the common equity factor)
_BLOCK_PARAMS = {
    "uk_equity": (0.06, 0.15, 0.8), "us_equity": (0.08, 0.16, 0.9),
    "europe_ex_uk_equity": (0.06, 0.17, 0.85), "japan_equity": (0.05, 0.16, 0.7),
    "asia_pacific_equity": (0.06, 0.18, 0.75), "emerging_market_equity": (0.07, 0.20, 0.75),
    "global_reits": (0.05, 0.18, 0.6), "commodities_gold": (0.03, 0.15, 0.0),
    "uk_gilts": (0.03, 0.07, -0.1), "uk_inflation_linked": (0.03, 0.09, -0.05),
    "global_bonds": (0.025, 0.05, -0.1), "corporate_bonds": (0.035, 0.07, 0.2),
    "cash_equivalent": (0.02, 0.004, 0.0),
}
_LATE_START = {"VUAG.L": "2016-06-01", "CSH2.L": "2018-06-01"}


def _synthetic_panel(seed: int = 3) -> pd.DataFrame:
    """Daily GBP prices 2013–2019 for the first candidate of each block, plus
    VUSA.L (US fallback) and ERNS.L (cash / rf fallback). VUAG.L and CSH2.L start late."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2013-01-01", "2019-12-31")
    n = len(days)
    factor = rng.normal(0, 1, n)
    cols = {}
    blocks = [(ac, c[0]) for ac, c in CORE_UNIVERSE.items()]
    blocks += [("us_equity", "VUSA.L"), ("cash_equivalent", "ERNS.L")]
    for block, tk in blocks:
        mu, vol, beta = _BLOCK_PARAMS[block]
        eps = beta * factor + np.sqrt(max(0.0, 1 - beta ** 2)) * rng.normal(0, 1, n)
        r = (mu - 0.5 * vol ** 2) / 252 + vol / np.sqrt(252) * eps
        s = pd.Series(100 * np.exp(np.cumsum(r)), index=days)
        if tk in _LATE_START:
            s[s.index < _LATE_START[tk]] = np.nan
        cols[tk] = s
    return pd.DataFrame(cols)


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return _synthetic_panel()


def _decide5(history, t):
    return decide_policy_portfolio(history, t, risk_score=5)


# =============================================================================
# Point-in-time inputs
# =============================================================================

def test_month_end_prices_drop_the_incomplete_month(panel):
    t = pd.Timestamp("2016-03-17")
    m = month_end_prices(panel, t, years=10)
    assert m.index.max() == pd.Timestamp("2016-02-29")
    # Rows after t cannot influence the result.
    pd.testing.assert_frame_equal(m, month_end_prices(panel.loc[:t], t, years=10))


def test_month_end_prices_window_length(panel):
    t = pd.Timestamp("2019-06-30")
    m = month_end_prices(panel, t, years=2)
    assert m.index.min() > t - pd.DateOffset(years=2)
    assert len(m) == 24


def test_usable_needs_history_and_a_recent_price(panel):
    assert not usable_at(panel, "VUAG.L", pd.Timestamp("2018-06-01"))       # 24 months only
    assert usable_at(panel, "VUAG.L", pd.Timestamp("2019-07-01"))           # 36+ months
    stale = panel.copy()
    stale.loc["2019-06-15":, "VUAG.L"] = np.nan
    assert not usable_at(stale, "VUAG.L", pd.Timestamp("2019-07-01"))       # stopped printing


def test_universe_falls_back_then_switches_when_history_is_long_enough(panel):
    early, _ = resolve_universe_at(panel, pd.Timestamp("2018-01-02"))
    late, _ = resolve_universe_at(panel, pd.Timestamp("2019-07-01"))
    assert early["us_equity"] == "VUSA.L"
    assert late["us_equity"] == "VUAG.L"
    assert early["cash_equivalent"] == "ERNS.L"          # CSH2.L too young


def test_universe_ignores_the_registry_delisted_flag(panel):
    # CJPE.L is flagged delisted in the 2026 registry; in the past it was investable.
    p = panel.rename(columns={"VJPN.L": "CJPE.L"})
    ticker_map, _ = resolve_universe_at(p, pd.Timestamp("2018-01-02"))
    assert ticker_map["japan_equity"] == "CJPE.L"


def test_risk_free_uses_only_the_past_and_falls_back(panel):
    t = pd.Timestamp("2018-09-03")
    rate, src = risk_free_at(panel, t)
    assert src == "ERNS.L"                                  # CSH2.L has < 13 month-ends
    shocked = panel.copy()
    shocked.loc[shocked.index > t] *= 3.0
    assert risk_free_at(shocked, t) == (rate, src)
    later_rate, later_src = risk_free_at(panel, pd.Timestamp("2019-09-02"))
    assert later_src == "CSH2.L"


def test_risk_free_skips_a_proxy_that_stopped_printing(panel):
    stopped = panel.copy()
    stopped.loc["2019-08-01":, "CSH2.L"] = np.nan
    assert risk_free_at(stopped, pd.Timestamp("2019-09-02"))[1] == "ERNS.L"


# =============================================================================
# Causal data cleaning
# =============================================================================

def test_fx_is_forward_filled_only_and_lagged():
    idx = pd.bdate_range("2020-01-01", periods=6)
    fx = pd.Series([1.0, 2.0, 4.0], index=idx[2:5])
    aligned = fx_for_prices(fx, idx, strictly_before=True)
    assert aligned.iloc[:3].isna().all()                    # no back-fill before FX starts
    assert list(aligned.iloc[3:]) == [1.0, 2.0, 4.0]        # last FX print before each date
    gbp = to_gbp(pd.Series(8.0, index=idx), "USD", pd.DataFrame({"USD": fx}), strictly_before=False)
    assert gbp.iloc[:2].isna().all() and gbp.iloc[2] == 8.0 and gbp.iloc[-1] == 2.0


def test_unit_glitch_fix_is_causal():
    s = pd.Series([100.0] * 30 + [1.0, 1.02] + [101.0] * 10)   # two prints in pounds, not pence
    fixed, n = causal_unit_fix(s)
    assert n == 2 and fixed.iloc[30] == pytest.approx(100.0)
    prefix, _ = causal_unit_fix(s.iloc[:31])
    pd.testing.assert_series_equal(prefix, fixed.iloc[:31])


def test_total_return_reinvests_dividends_and_fixes_units():
    idx = pd.bdate_range("2020-01-01", periods=4)
    close = pd.Series([100.0, 100.0, 98.0, 98.0], index=idx)
    divs = pd.Series([2.0], index=[idx[2]])
    tr, n = total_return_index(close, divs)
    assert n == 0 and tr.iloc[-1] == pytest.approx(100.0)      # price drop offset by dividend
    tr_bad, n_bad = total_return_index(close, pd.Series([200.0], index=[idx[2]]))
    assert n_bad == 1 and tr_bad.iloc[-1] == pytest.approx(100.0)


def _raw_inputs(seed: int = 5):
    """Raw Yahoo-like inputs: a pence line with a glitch and dividends, a USD line, a GBP line, and FX with gaps."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2020-01-01", periods=400)
    walk = lambda s: pd.Series(s * np.exp(np.cumsum(rng.normal(0, 0.01, len(days)))), index=days)  # noqa: E731
    pence = walk(1500.0)
    pence.iloc[120:123] /= 100.0                                   # printed in pounds for three days
    raw = {
        "PEN.L": (pence, pd.Series([12.0, 14.0, 13.0], index=days[[60, 190, 330]]), "GBp"),
        "USD.L": (walk(50.0), pd.Series([0.3, 0.4], index=days[[100, 300]]), "USD"),
        "GBP.L": (walk(20.0), pd.Series([0.2], index=[days[250] + pd.Timedelta(days=1)]), "GBP"),
    }
    fx = walk(1.3).iloc[::2]                                       # FX prints every other day
    return raw, fx


def _clean_panel(raw, fx, cut=None) -> pd.DataFrame:
    """The full data chain (clean_ticker → gbp_prices → trading_calendar), optionally on data ≤ cut."""
    cl = lambda s: s if cut is None else s.loc[:cut]  # noqa: E731
    closes, ccy = {}, {}
    for tk, (close, divs, c) in raw.items():
        closes[tk], ccy[tk] = clean_ticker(cl(close).rename(tk), cl(divs), c)
    panel = PricePanel(pd.DataFrame(closes), ccy, pd.DataFrame({"USD": cl(fx)}))
    gbp = gbp_prices(panel)
    return gbp.loc[trading_calendar(gbp)]


def test_data_chain_is_causal_end_to_end():
    raw, fx = _raw_inputs()
    cut = raw["PEN.L"][0].index[201]        # no FX print on the cut day: a back-fill would reach past it
    assert cut not in fx.index
    full = _clean_panel(raw, fx)
    assert full["PEN.L"].pct_change().abs().max() < 0.2            # glitch repaired, dividends reinvested
    # Deleting the future changes nothing up to the cut...
    pd.testing.assert_frame_equal(full.loc[:cut], _clean_panel(raw, fx, cut))
    # ...and neither does rewriting it: new prices, FX and dividends after the cut.
    rng = np.random.default_rng(9)
    shocked = {tk: (c.where(c.index <= cut, c * rng.uniform(0.5, 2.0, len(c))),
                    pd.concat([d, pd.Series([5.0], index=[cut + pd.Timedelta(days=3)])]), ccy)
               for tk, (c, d, ccy) in raw.items()}
    fx_shocked = fx.where(fx.index <= cut, fx * 1.5)
    pd.testing.assert_frame_equal(full.loc[:cut], _clean_panel(shocked, fx_shocked).loc[:cut])


# =============================================================================
# Simulation mechanics
# =============================================================================

@pytest.fixture(scope="module")
def two_fund_runs(panel):
    decide = fixed_mix_decider({"VUSA.L": 0.6, "IGLT.L": 0.4},
                               {"VUSA.L": "us_equity", "IGLT.L": "uk_gilts"})
    start, end = pd.Timestamp("2017-01-02"), pd.Timestamp("2019-12-31")
    return {m: run_backtest(panel, start, end, decide, SimConfig(mode=m)) for m in ("bands", "calendar")}


def test_orders_fill_at_the_next_days_close(panel, two_fund_runs):
    res = two_fund_runs["bands"]
    days = res.equity.index
    for ev in res.events.itertuples():
        assert days.get_loc(ev.executed) == days.get_loc(ev.decided) + 1
    for f in res.fills.itertuples():
        assert f.price == pytest.approx(panel.at[f.executed, f.ticker])


def test_execution_only_loses_trading_costs(two_fund_runs):
    for res in two_fund_runs.values():
        ev = res.events
        np.testing.assert_allclose(ev["value_before"] - ev["value_after"], ev["cost_gbp"], atol=1e-6)
        assert ev["cost_gbp"].sum() == pytest.approx(res.fills["cost_gbp"].sum())
        assert (res.equity["cash"] > -1e-6).all()


def test_costs_are_10bp_of_traded_value(two_fund_runs):
    f = two_fund_runs["calendar"].fills
    gross = np.where(f["action"] == "buy", f["value_gbp"] + f["cost_gbp"], f["value_gbp"])
    np.testing.assert_allclose(f["cost_gbp"], gross * 0.001, rtol=1e-9)


def test_calendar_mode_trades_more_often_than_bands(two_fund_runs):
    bands = performance_summary(two_fund_runs["bands"])
    cal = performance_summary(two_fund_runs["calendar"])
    assert cal["n_rebalances"] > bands["n_rebalances"]
    assert cal["rebalance_costs_gbp"] >= bands["rebalance_costs_gbp"]


def test_unpriced_target_skips_the_rebalance_instead_of_aborting(panel):
    late = panel.copy()
    late["LATE.L"] = late["IGLT.L"].where(late.index >= "2019-02-01")
    decide = fixed_mix_decider({"VUSA.L": 0.6, "LATE.L": 0.4}, {"VUSA.L": "us_equity", "LATE.L": "uk_gilts"})
    res = run_backtest(late, pd.Timestamp("2019-01-02"), pd.Timestamp("2019-06-28"), decide)
    first = res.checks.iloc[0]
    assert not first["traded"] and "LATE.L" in first["note"]
    assert res.events["executed"].min() > pd.Timestamp("2019-02-01")
    assert set(res.fills["ticker"]) == {"VUSA.L", "LATE.L"}


def test_fixed_commission_is_charged_per_fill(panel):
    decide = fixed_mix_decider({"VUSA.L": 0.6, "IGLT.L": 0.4},
                               {"VUSA.L": "us_equity", "IGLT.L": "uk_gilts"})
    res = run_backtest(panel, pd.Timestamp("2019-01-02"), pd.Timestamp("2019-12-31"), decide,
                       SimConfig(mode="calendar", commission_gbp=5.0))
    assert res.events["commission_gbp"].sum() == pytest.approx(5.0 * len(res.fills))


# =============================================================================
# Look-ahead test (the production pipeline, end to end)
# =============================================================================

@pytest.fixture(scope="module")
def lookahead_runs(panel):
    start, end, cut = pd.Timestamp("2018-01-02"), pd.Timestamp("2019-12-31"), pd.Timestamp("2019-01-15")
    rng = np.random.default_rng(11)
    shocked = panel.copy()
    after = shocked.index > cut
    shocks = np.exp(np.cumsum(rng.normal(0, 0.03, size=(after.sum(), shocked.shape[1])), axis=0))
    shocked.loc[after] = shocked.loc[after].to_numpy() * shocks
    cfg = SimConfig(reopt_months=6)
    return {
        "cut": cut,
        "base": run_backtest(panel, start, end, _decide5, cfg),
        "shocked": run_backtest(shocked, start, end, _decide5, cfg),
        "truncated": run_backtest(panel.loc[:cut], start, cut, _decide5, cfg),
    }


def test_nothing_on_or_before_the_cut_depends_on_later_prices(lookahead_runs):
    cut, a, b = lookahead_runs["cut"], lookahead_runs["base"], lookahead_runs["shocked"]
    da = [d for d in a.decisions if d.date <= cut]
    assert len(da) >= 2
    assert da == [d for d in b.decisions if d.date <= cut]
    assert [o for o in a.orders if o.decided <= cut] == [o for o in b.orders if o.decided <= cut]
    pd.testing.assert_frame_equal(a.fills[a.fills["executed"] <= cut].reset_index(drop=True),
                                  b.fills[b.fills["executed"] <= cut].reset_index(drop=True))
    pd.testing.assert_frame_equal(a.equity.loc[:cut], b.equity.loc[:cut])


def test_the_shock_does_change_later_decisions(lookahead_runs):
    cut, a, b = lookahead_runs["cut"], lookahead_runs["base"], lookahead_runs["shocked"]
    later_a = [d for d in a.decisions if d.date > cut]
    assert later_a and later_a != [d for d in b.decisions if d.date > cut]
    assert not np.allclose(a.equity.loc[cut:, "value"], b.equity.loc[cut:, "value"])


def test_deleting_the_future_changes_nothing_before_the_cut(lookahead_runs):
    # The truncated run ends at the cut, and no decision is taken on a final day
    # (there is no next day to trade on), so compare what came strictly before it.
    cut, a, t = lookahead_runs["cut"], lookahead_runs["base"], lookahead_runs["truncated"]
    assert len(t.decisions) >= 2
    assert [d for d in a.decisions if d.date < cut] == t.decisions
    assert [o for o in a.orders if o.decided < cut] == t.orders
    pd.testing.assert_frame_equal(a.equity.loc[:cut].iloc[:-1], t.equity.iloc[:-1])
    pd.testing.assert_frame_equal(a.equity.loc[[cut], ["value", "cash"]], t.equity.loc[[cut], ["value", "cash"]])


def test_decisions_never_touch_live_data(panel, monkeypatch):
    import backend.data.rates as rates
    import yfinance

    def boom(*a, **k):
        raise AssertionError("live data called during a backtest decision")
    monkeypatch.setattr(rates, "get_risk_free_rate", boom)
    monkeypatch.setattr(yfinance, "download", boom)
    d = decide_policy_portfolio(panel.loc[:"2018-01-02"], pd.Timestamp("2018-01-02"), risk_score=7)
    assert abs(sum(d.weights.values()) - 1.0) < 1e-9
    assert d.expected_return is not None and d.volatility > d.volatility_model > 0


def test_policy_targets_track_the_risk_score(lookahead_runs):
    d = lookahead_runs["base"].decisions[0]
    growth = sum(w for tk, w in d.weights.items()
                 if d.asset_class_of[tk] not in ("uk_gilts", "uk_inflation_linked", "global_bonds",
                                                 "corporate_bonds", "cash_equivalent"))
    assert growth == pytest.approx(0.5, abs=1e-4)


# =============================================================================
# Metrics
# =============================================================================

def test_drawdown_and_cagr():
    idx = pd.to_datetime(["2020-01-01", "2020-07-01", "2021-01-01"])
    v = pd.Series([100.0, 80.0, 110.0], index=idx)
    assert max_drawdown(v) == pytest.approx(-0.2)
    assert cagr(v) == pytest.approx(0.1, abs=2e-3)


def test_forecast_periods_cover_every_decision(lookahead_runs):
    res = lookahead_runs["base"]
    periods = forecast_periods(res)
    assert len(periods) == len(res.decisions)
    assert (periods["start"].iloc[1:].to_numpy() == periods["end"].iloc[:-1].to_numpy()).all()
    summary = accuracy_summary(periods, res)
    assert 0.0 <= summary["coverage_1sd_calibrated"] <= 1.0
    assert summary["bias_mean_error"] == pytest.approx(periods["error"].mean())
