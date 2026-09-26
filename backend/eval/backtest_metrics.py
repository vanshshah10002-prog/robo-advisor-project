"""
Backtest Metrics — realised performance and forecast accuracy
=============================================================
Everything here is ex-post evaluation of a finished BacktestResult, so it may
use the whole test period; nothing feeds back into decisions.

Forecast accuracy compares, per re-optimisation period k (from the day decision
k's trades executed to the day decision k+1's did):
  - expected arithmetic return E_a with the realised annualised return;
  - the geometric equivalent E_g = E_a − σ²/2 (σ = model vol) with realised CAGR;
  - predicted volatility (model, and ×1.15 calibrated) with realised volatility;
  - coverage: |realised − E_a| ≤ σ/√τ, where τ is the period length in years
    (the standard deviation of an annualised return over τ years).
"""

import numpy as np
import pandas as pd

from backend.eval.walkforward_backtest import BacktestResult

TRADING_DAYS: int = 252
DAYS_PER_YEAR: float = 365.25


def _years(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return max((end - start).days / DAYS_PER_YEAR, 1e-9)


def max_drawdown(values: pd.Series) -> float:
    return float((values / values.cummax() - 1.0).min())


def cagr(values: pd.Series) -> float:
    return float((values.iloc[-1] / values.iloc[0]) ** (1.0 / _years(values.index[0], values.index[-1])) - 1.0)


def sharpe(values: pd.Series, rf_annual: pd.Series) -> float:
    """Annualised Sharpe of daily returns over the rf known at each day (point in time)."""
    r = values.pct_change().dropna()
    rf_daily = (1.0 + rf_annual.reindex(r.index).ffill().fillna(0.0)) ** (1.0 / TRADING_DAYS) - 1.0
    ex = r - rf_daily
    sd = float(ex.std())
    return float(ex.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def performance_summary(result: BacktestResult) -> dict:
    """Headline statistics for one run. Rebalance counts and turnover exclude the initial purchase."""
    v = result.equity["value"]
    years = _years(v.index[0], v.index[-1])
    ev = result.events
    rebal = ev[ev["reason"] != "initial"] if not ev.empty else ev
    avg_value = float(v.mean())
    total_cost = float(ev["cost_gbp"].sum()) if not ev.empty else 0.0
    rebal_cost = float(rebal["cost_gbp"].sum()) if not rebal.empty else 0.0
    return {
        "start": v.index[0].date().isoformat(),
        "end": v.index[-1].date().isoformat(),
        "start_value": float(v.iloc[0]),
        "end_value": float(v.iloc[-1]),
        "total_return": float(v.iloc[-1] / v.iloc[0] - 1.0),
        "cagr": cagr(v),
        "volatility": float(v.pct_change().std() * np.sqrt(TRADING_DAYS)),
        "sharpe": sharpe(v, result.equity["rf"]),
        "max_drawdown": max_drawdown(v),
        "total_costs_gbp": total_cost,
        "rebalance_costs_gbp": rebal_cost,
        "costs_bp_per_year": total_cost / avg_value / years * 1e4,
        "rebalance_costs_bp_per_year": rebal_cost / avg_value / years * 1e4,
        "n_rebalances": int(len(rebal)),
        "n_fills": int(len(result.fills)),
        "turnover_per_year": float(rebal["turnover"].sum()) / years if not rebal.empty else 0.0,
        "n_decisions": len(result.decisions),
    }


def _period_bounds(result: BacktestResult) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Execution day of each decision's trades → execution day of the next decision's."""
    days = result.equity.index
    starts = [days[min(days.searchsorted(d.date, side="right"), len(days) - 1)] for d in result.decisions]
    ends = starts[1:] + [days[-1]]
    return list(zip(starts, ends))


def forecast_periods(result: BacktestResult) -> pd.DataFrame:
    """One row per decision: the forecast made then and what the portfolio actually did."""
    rows = []
    v = result.equity["value"]
    for d, (s, e) in zip(result.decisions, _period_bounds(result)):
        seg = v.loc[s:e]
        if len(seg) < 2 or d.expected_return is None:
            continue
        tau = _years(s, e)
        realised = float((seg.iloc[-1] / seg.iloc[0]) ** (1.0 / tau) - 1.0)
        daily = seg.pct_change().dropna()
        e_a, sd_m, sd_c = d.expected_return, d.volatility_model, d.volatility
        rows.append({
            "decided": d.date, "start": s, "end": e, "years": tau,
            "risk_free": d.risk_free, "common_months": d.common_months,
            "expected_arith": e_a, "expected_geo": e_a - 0.5 * sd_m ** 2,
            "vol_model": sd_m, "vol_calibrated": sd_c,
            "realised_ann": realised,
            "realised_arith": float(daily.mean() * TRADING_DAYS),
            "realised_vol": float(daily.std() * np.sqrt(TRADING_DAYS)),
            "error": realised - e_a,
            "z_calibrated": (realised - e_a) / (sd_c / np.sqrt(tau)),
            "z_model": (realised - e_a) / (sd_m / np.sqrt(tau)),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["within_1sd_calibrated"] = df["z_calibrated"].abs() <= 1.0
        df["within_1sd_model"] = df["z_model"].abs() <= 1.0
    return df


def accuracy_summary(periods: pd.DataFrame, result: BacktestResult) -> dict:
    """Bias, error and coverage over all periods, plus whole-window CAGR vs forecast."""
    if periods.empty:
        return {}
    v = result.equity["value"]
    s = periods["start"].iloc[0]
    weights = periods["years"] / periods["years"].sum()
    return {
        "n_periods": int(len(periods)),
        "bias_mean_error": float(periods["error"].mean()),
        "mean_abs_error": float(periods["error"].abs().mean()),
        "rmse": float(np.sqrt((periods["error"] ** 2).mean())),
        "mean_z_calibrated": float(periods["z_calibrated"].mean()),
        "coverage_1sd_calibrated": float(periods["within_1sd_calibrated"].mean()),
        "coverage_1sd_model": float(periods["within_1sd_model"].mean()),
        "vol_ratio_realised_to_model": float((periods["realised_vol"] / periods["vol_model"]).mean()),
        "vol_ratio_realised_to_calibrated": float((periods["realised_vol"] / periods["vol_calibrated"]).mean()),
        "forecast_arith_time_weighted": float((periods["expected_arith"] * weights).sum()),
        "forecast_geo_time_weighted": float((periods["expected_geo"] * weights).sum()),
        "realised_cagr_after_first_trade": cagr(v.loc[s:]),
    }


def asset_forecast_periods(result: BacktestResult, prices: pd.DataFrame) -> pd.DataFrame:
    """Per decision and held ETF: expected return (μ) vs realised annualised GBP return."""
    rows = []
    marks = prices.ffill()
    for d, (s, e) in zip(result.decisions, _period_bounds(result)):
        tau = _years(s, e)
        for tk, w in d.weights.items():
            p0, p1 = float(marks.at[s, tk]), float(marks.at[e, tk])
            realised = (p1 / p0) ** (1.0 / tau) - 1.0
            rows.append({"decided": d.date, "ticker": tk, "asset_class": d.asset_class_of.get(tk, ""),
                         "weight": w, "expected": d.mu.get(tk, np.nan), "realised_ann": realised,
                         "error": realised - d.mu.get(tk, np.nan), "years": tau})
    return pd.DataFrame(rows)
