"""
Backtesting Engine — Historical Portfolio Simulation
=====================================================
Simulates how a portfolio allocation would have performed historically.
Supports custom date ranges, periodic rebalancing, and benchmark comparison.

Reference: Uses historical price data to compute time-weighted returns,
drawdowns, and risk metrics. Inspired by bt library (pmorissette/bt).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import MVO_RISK_FREE_RATE, BENCHMARK_TICKER, TRANSACTION_COST_BPS
from backend.data.market_data import build_close_price_matrix, fetch_prices

logger = logging.getLogger(__name__)


def backtest_portfolio(
    weights: dict[str, float],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_investment: float = 10000.0,
    rebalance_frequency: str = "quarterly",
    benchmark_ticker: str = BENCHMARK_TICKER,
    transaction_cost_bps: float = TRANSACTION_COST_BPS,
) -> dict:
    """
    Run a historical backtest on a portfolio allocation.

    Algorithm:
    1. Fetch historical prices for all tickers in the portfolio
    2. Compute daily portfolio returns based on weights
    3. Apply periodic rebalancing (reset to target weights)
    4. Calculate performance metrics (CAGR, vol, Sharpe, max drawdown)
    5. Compare against benchmark

    Parameters:
        weights (dict[str, float]): {ticker: target_weight}.
        start_date (str, optional): Start date "YYYY-MM-DD" (default: 5yr ago).
        end_date (str, optional): End date "YYYY-MM-DD" (default: today).
        initial_investment (float): Starting capital for the simulation.
        rebalance_frequency (str): "monthly" | "quarterly" | "annually" | "none".
        benchmark_ticker (str): Benchmark ETF ticker for comparison.

    Returns:
        dict: {
            "portfolio_values": list[{date, value}],
            "benchmark_values": list[{date, value}],
            "metrics": {cagr, volatility, sharpe, max_drawdown, ...},
            "benchmark_metrics": {cagr, volatility, sharpe, max_drawdown},
        }
    """
    tickers = [t for t, w in weights.items() if w > 0]

    # Fetch all prices including benchmark
    all_tickers = tickers + [benchmark_ticker]
    prices = build_close_price_matrix(all_tickers)

    if prices is None or prices.empty:
        raise ValueError("Could not fetch historical prices for backtest")

    # Filter date range
    if start_date:
        prices = prices[prices.index >= start_date]
    if end_date:
        prices = prices[prices.index <= end_date]

    if len(prices) < 20:
        raise ValueError("Insufficient price data for backtest")

    # Separate benchmark
    benchmark_prices = prices[benchmark_ticker] if benchmark_ticker in prices.columns else None
    portfolio_prices = prices[[t for t in tickers if t in prices.columns]]

    # Daily returns
    returns = portfolio_prices.pct_change().dropna()

    # Rebalancing schedule
    rebalance_days = _get_rebalance_dates(returns.index, rebalance_frequency)

    # Simulate portfolio
    w = np.array([weights.get(t, 0) for t in portfolio_prices.columns])
    w = w / w.sum()  # Normalise

    portfolio_values = [initial_investment]
    current_weights = w.copy()
    cost_rate = transaction_cost_bps / 10000.0  # one-way cost per unit turnover

    for i in range(len(returns)):
        date = returns.index[i]
        daily_ret = returns.iloc[i].values

        # Update weights based on daily returns
        new_weights = current_weights * (1 + daily_ret)
        portfolio_return = new_weights.sum() / current_weights.sum() - 1
        portfolio_values.append(portfolio_values[-1] * (1 + portfolio_return))

        # Normalise weights (drifted)
        current_weights = new_weights / new_weights.sum()

        # Rebalance if scheduled — charge transaction costs on the traded turnover
        if date in rebalance_days:
            one_way_turnover = 0.5 * float(np.sum(np.abs(w - current_weights)))
            cost = one_way_turnover * cost_rate
            portfolio_values[-1] *= (1.0 - cost)
            current_weights = w.copy()

    dates = [returns.index[0] - pd.Timedelta(days=1)] + list(returns.index)

    # Benchmark values
    benchmark_values = None
    if benchmark_prices is not None:
        bm_returns = benchmark_prices.pct_change().dropna()
        bm_aligned = bm_returns.loc[bm_returns.index.isin(returns.index)]
        bm_values = [initial_investment]
        for r in bm_aligned:
            bm_values.append(bm_values[-1] * (1 + r))
        benchmark_values = bm_values

    # Compute metrics
    pv = np.array(portfolio_values)
    metrics = _compute_metrics(pv, dates)

    bm_metrics = None
    if benchmark_values:
        bm_metrics = _compute_metrics(np.array(benchmark_values), dates[:len(benchmark_values)])

    return {
        "portfolio_values": [
            {"date": d.isoformat()[:10], "value": round(v, 2)}
            for d, v in zip(dates, portfolio_values)
        ],
        "benchmark_values": [
            {"date": d.isoformat()[:10], "value": round(v, 2)}
            for d, v in zip(dates[:len(benchmark_values)], benchmark_values)
        ] if benchmark_values else None,
        "metrics": metrics,
        "benchmark_metrics": bm_metrics,
    }


def _get_rebalance_dates(index: pd.DatetimeIndex, frequency: str) -> set:
    """Generate a set of rebalancing dates."""
    if frequency == "none":
        return set()

    dates = set()
    if frequency == "monthly":
        for i in range(1, len(index)):
            if index[i].month != index[i - 1].month:
                dates.add(index[i])
    elif frequency == "quarterly":
        for i in range(1, len(index)):
            if index[i].quarter != index[i - 1].quarter:
                dates.add(index[i])
    elif frequency == "annually":
        for i in range(1, len(index)):
            if index[i].year != index[i - 1].year:
                dates.add(index[i])

    return dates


def _compute_metrics(
    values: np.ndarray,
    dates: list,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> dict:
    """
    Compute portfolio performance metrics.

    Parameters:
        values (np.ndarray): Portfolio value time series.
        dates (list): Corresponding dates.
        risk_free_rate (float): Annualised risk-free rate.

    Returns:
        dict: Performance metrics.
    """
    if len(values) < 2:
        return {}

    total_return = (values[-1] / values[0]) - 1
    n_days = (dates[-1] - dates[0]).days if len(dates) > 1 else 1
    n_years = n_days / 365.25

    # CAGR
    cagr = (values[-1] / values[0]) ** (1 / max(n_years, 0.01)) - 1

    # Daily returns
    daily_returns = np.diff(values) / values[:-1]

    # Annualised volatility
    volatility = float(np.std(daily_returns) * np.sqrt(252))

    # Sharpe ratio
    sharpe = (cagr - risk_free_rate) / volatility if volatility > 0 else 0

    # Max drawdown
    peak = np.maximum.accumulate(values)
    drawdown = (values - peak) / peak
    max_drawdown = float(np.min(drawdown))

    return {
        "total_return": round(float(total_return), 4),
        "cagr": round(float(cagr), 4),
        "volatility": round(volatility, 4),
        "sharpe_ratio": round(float(sharpe), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "n_years": round(n_years, 2),
        "final_value": round(float(values[-1]), 2),
    }
