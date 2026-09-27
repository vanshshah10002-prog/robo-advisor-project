"""
Track record — the walk-forward backtest, packaged for the app
===============================================================
Turns backtest results into the compact artefact served by
GET /api/strategy/track-record (backend/data/track_record.json): per risk
level, a weekly value series against the same-growth two-fund benchmark,
calendar-year returns, headline metrics, and forecast-vs-realised accuracy.

Pure: takes BacktestResult objects, returns plain dicts.
"""

from typing import TypedDict

import numpy as np
import pandas as pd

from backend.config import BENCHMARK_TICKER
from backend.engine.asset_universe import get_etf_by_ticker
from backend.eval.backtest_metrics import accuracy_summary, forecast_periods, performance_summary
from backend.eval.walkforward_backtest import BacktestResult

SERIES_STEP_DAYS = 5          # one point per trading week
BOND_BENCHMARK_TICKER = "AGBP.L"   # iShares Core Global Aggregate Bond, hedged to pounds

NOTES = [
    "Simulated, not this portfolio's own history: the same construction rules run on real London "
    "prices, deciding each date only with data available on that date.",
    "Starts with £100,000, checked every 10 trading days and rebuilt every 12 months; each trade costs 0.10%.",
    "The comparison holds two funds, world shares (VWRL) and global bonds hedged to pounds (AGBP), "
    "with the same share in shares.",
    "The fund list and costs were chosen in 2026 from funds that exist today, which flatters the past a little.",
    "Past performance, simulated or real, is not a reliable guide to future returns.",
]


def benchmark_weights(growth: float) -> dict[str, float]:
    """World shares for `growth`, hedged global bonds for the rest; a fund at 0% is left out."""
    weights = {BENCHMARK_TICKER: round(growth, 4), BOND_BENCHMARK_TICKER: round(1 - growth, 4)}
    return {ticker: w for ticker, w in weights.items() if w > 0}


def benchmark_mix(risk: int) -> dict[str, float]:
    """The comparison at a risk level: the same growth share as the policy, 10% per level."""
    return benchmark_weights(min(1.0, 0.1 * risk))


class BenchmarkFund(TypedDict):
    ticker: str
    name: str
    weight: float


def benchmark_funds(risk: int) -> list[BenchmarkFund]:
    """The comparison's funds with their registry names, shares before bonds."""
    return [
        {"ticker": ticker, "name": (get_etf_by_ticker(ticker) or {}).get("name", ticker), "weight": weight}
        for ticker, weight in benchmark_mix(risk).items()
    ]


def _summary(result: BacktestResult) -> dict:
    s = performance_summary(result)
    return {k: float(s[k]) for k in ("end_value", "total_return", "cagr", "volatility", "max_drawdown", "sharpe")}


def weekly_series(strategy: pd.Series, benchmark: pd.Series, step: int = SERIES_STEP_DAYS) -> list[dict]:
    """Every `step`-th common day plus the last, values rounded to pence."""
    both = pd.concat([strategy.rename("s"), benchmark.rename("b")], axis=1).dropna()
    if both.empty:
        return []
    idx = list(range(0, len(both), step))
    if idx[-1] != len(both) - 1:
        idx.append(len(both) - 1)
    sampled = both.iloc[idx]
    return [{"date": d.date().isoformat(), "strategy": round(float(r.s), 2), "benchmark": round(float(r.b), 2)}
            for d, r in sampled.iterrows()]


def calendar_years(strategy: pd.Series, benchmark: pd.Series) -> list[dict]:
    """
    Return in each calendar year, from the last value of the previous year (or
    the start) to the last value of the year. A year the window only partly
    covers is flagged `partial`.
    """
    both = pd.concat([strategy.rename("s"), benchmark.rename("b")], axis=1).dropna()
    if both.empty:
        return []
    start, end = both.index[0], both.index[-1]
    rows = []
    prev = both.iloc[0]
    for year, block in both.groupby(both.index.year):
        last = block.iloc[-1]
        starts_late = block.index[0] == start and start > pd.Timestamp(year=year, month=1, day=7)
        ends_early = block.index[-1] == end and end < pd.Timestamp(year=year, month=12, day=24)
        partial = bool(starts_late or ends_early)
        rows.append({
            "year": int(year),
            "strategy": float(last.s / prev.s - 1.0),
            "benchmark": float(last.b / prev.b - 1.0),
            "partial": partial,
        })
        prev = last
    return rows


def track_record_entry(strategy: BacktestResult, benchmark: BacktestResult, benchmark_label: str) -> dict:
    """One risk level's entry in the artefact (see TrackRecordResponse)."""
    perf = performance_summary(strategy)
    periods = forecast_periods(strategy)
    acc = accuracy_summary(periods, strategy) if not periods.empty else {}
    weights = periods["years"] / periods["years"].sum() if not periods.empty else None
    forecast_vol = float((periods["vol_calibrated"] * weights).sum()) if weights is not None else None
    s_val, b_val = strategy.equity["value"], benchmark.equity["value"]
    return {
        "benchmark_label": benchmark_label,
        "strategy": _summary(strategy),
        "benchmark": _summary(benchmark),
        "costs_gbp": float(perf["total_costs_gbp"]),
        "rebalances": int(perf["n_rebalances"]),
        "turnover_per_year": float(perf["turnover_per_year"]),
        "forecast_return": acc.get("forecast_arith_time_weighted"),
        "forecast_volatility": forecast_vol,
        "within_one_sigma": acc.get("coverage_1sd_calibrated"),
        "series": weekly_series(s_val, b_val),
        "calendar_years": calendar_years(s_val, b_val),
    }


def _clean(x):
    """JSON-safe: NaN and infinities become None."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def build_artefact(entries: dict[int, dict], start: str, end: str, initial: float,
                   generated_at: str, prices_downloaded_at: str) -> dict:
    return _clean({
        "start": start, "end": end, "initial": initial,
        "generated_at": generated_at, "prices_downloaded_at": prices_downloaded_at,
        "notes": NOTES,
        "risks": {str(r): e for r, e in sorted(entries.items())},
    })
