"""
Portfolio Optimizer — Mean-Variance Optimization + Efficient Frontier
======================================================================
Core algorithmic engine: constructs optimal portfolios using MVO with
optional Black-Litterman expected returns and Ledoit-Wolf covariance.

Reference:
- Markowitz (1952), "Portfolio Selection"
- He & Litterman (1999), Black-Litterman model
- PyPortfolioOpt (Robert Martin) for MVO implementation
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier
from pypfopt import objective_functions

from backend.config import (
    MVO_RISK_FREE_RATE,
    MVO_EFFICIENT_FRONTIER_POINTS,
    ALLOCATION_CONSTRAINTS,
    TRACKING_ERROR_WEIGHT,
    USE_DUAL_MOMENTUM,
    DUAL_MOMENTUM_LOOKBACK_MONTHS,
    DUAL_MOMENTUM_REDUCTION,
    CRISIS_CASH_BUFFER,
)
from backend.engine.expected_returns import get_expected_returns
from backend.engine.covariance import compute_covariance, detect_high_correlation_regime
from backend.engine.asset_universe import get_ticker_map, get_expense_ratios
from backend.data.market_data import build_close_price_matrix

logger = logging.getLogger(__name__)


def _get_weight_bounds(
    tickers: list[str],
    asset_class_map: dict[str, str],
) -> list[tuple[float, float]]:
    """
    Build per-asset weight bounds from config constraints.

    Parameters:
        tickers (list[str]): Ordered list of tickers in the portfolio.
        asset_class_map (dict[str, str]): {ticker: asset_class} mapping.

    Returns:
        list[tuple[float, float]]: (min_weight, max_weight) for each ticker.
    """
    bounds = []
    for ticker in tickers:
        ac = asset_class_map.get(ticker, "")
        constraint = ALLOCATION_CONSTRAINTS.get(ac, {"min": 0.0, "max": 1.0})
        bounds.append((constraint["min"], constraint["max"]))
    return bounds


def apply_dual_momentum(
    prices: pd.DataFrame,
    weights: dict[str, float],
    cash_ticker: Optional[str] = None,
) -> dict[str, float]:
    """
    Apply Gary Antonacci's dual momentum overlay.

    If an asset's 12-month momentum is negative AND worse than cash,
    reduce its allocation by DUAL_MOMENTUM_REDUCTION (default 50%).
    Redistribute reduced weight to cash or pro-rata to positive-momentum assets.

    Reference: Antonacci (2014), "Dual Momentum Investing"

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        weights (dict[str, float]): Current optimised weights.
        cash_ticker (str, optional): Ticker for cash equivalent.

    Returns:
        dict[str, float]: Momentum-adjusted weights.
    """
    if not USE_DUAL_MOMENTUM:
        return weights

    lookback_days = DUAL_MOMENTUM_LOOKBACK_MONTHS * 21  # ~21 trading days per month
    adjusted = dict(weights)
    total_reduced = 0.0

    for ticker, weight in weights.items():
        if ticker == cash_ticker:
            continue

        if ticker in prices.columns and len(prices) >= lookback_days:
            recent_return = (
                prices[ticker].iloc[-1] / prices[ticker].iloc[-lookback_days] - 1
            )
            if recent_return < 0:
                reduction = weight * DUAL_MOMENTUM_REDUCTION
                adjusted[ticker] = weight - reduction
                total_reduced += reduction
                logger.info(
                    f"Dual momentum: reduced {ticker} by {reduction:.3f} "
                    f"(12m return: {recent_return:.2%})"
                )

    # Redistribute to cash or pro-rata
    if total_reduced > 0:
        if cash_ticker and cash_ticker in adjusted:
            adjusted[cash_ticker] = adjusted.get(cash_ticker, 0) + total_reduced
        else:
            # Pro-rata redistribute to positive-weight assets
            positive_tickers = [t for t, w in adjusted.items() if w > 0 and t != cash_ticker]
            if positive_tickers:
                per_asset = total_reduced / len(positive_tickers)
                for t in positive_tickers:
                    adjusted[t] += per_asset

    return adjusted


def optimise_for_risk_level(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_level: float,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> dict[str, float]:
    """
    Find the optimal portfolio for a specific risk level (1–10).

    Maps risk_level to a target volatility on the efficient frontier,
    then optimises to minimise risk at or above the target return.

    Parameters:
        expected_returns (pd.Series): Expected returns per asset.
        cov_matrix (pd.DataFrame): Covariance matrix.
        risk_level (float): Risk score 1–10.
        weight_bounds (list): Per-asset (min, max) weight bounds.
        risk_free_rate (float): Risk-free rate.

    Returns:
        dict[str, float]: Optimal weights {ticker: weight}.
    """
    try:
        ef = EfficientFrontier(
            expected_returns,
            cov_matrix,
            weight_bounds=weight_bounds,
        )

        # Map risk level to target return
        min_ret = expected_returns.min()
        max_ret = expected_returns.max()
        # Scale: risk_level 1 → 10% of range, risk_level 10 → 95% of range
        target_frac = 0.10 + (risk_level - 1) / 9.0 * 0.85
        target_return = min_ret + target_frac * (max_ret - min_ret)

        try:
            ef.efficient_return(target_return=target_return)
        except Exception:
            # If target return infeasible, maximise Sharpe ratio instead
            ef = EfficientFrontier(
                expected_returns, cov_matrix, weight_bounds=weight_bounds,
            )
            ef.max_sharpe(risk_free_rate=risk_free_rate)

        weights = ef.clean_weights()
        return dict(weights)

    except Exception as e:
        logger.error(f"Optimisation failed for risk level {risk_level}: {e}")
        # Fallback: equal weight
        n = len(expected_returns)
        return {ticker: 1.0 / n for ticker in expected_returns.index}


def compute_efficient_frontier(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    n_points: int = MVO_EFFICIENT_FRONTIER_POINTS,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> list[dict]:
    """
    Compute the full efficient frontier as a list of portfolio points.

    Each point contains: expected_return, volatility, sharpe_ratio, weights.

    Parameters:
        expected_returns (pd.Series): Expected returns per asset.
        cov_matrix (pd.DataFrame): Covariance matrix.
        weight_bounds (list): Per-asset (min, max) bounds.
        n_points (int): Number of frontier points.
        risk_free_rate (float): Risk-free rate.

    Returns:
        list[dict]: Frontier points sorted by volatility ascending.
    """
    frontier = []
    min_ret = expected_returns.min()
    max_ret = expected_returns.max()

    target_returns = np.linspace(
        min_ret + 0.001,
        max_ret - 0.001,
        n_points,
    )

    for target in target_returns:
        try:
            ef = EfficientFrontier(
                expected_returns, cov_matrix, weight_bounds=weight_bounds,
            )
            ef.efficient_return(target_return=float(target))
            weights = ef.clean_weights()
            perf = ef.portfolio_performance(risk_free_rate=risk_free_rate)

            frontier.append({
                "expected_return": round(perf[0], 6),
                "volatility": round(perf[1], 6),
                "sharpe_ratio": round(perf[2], 4),
                "weights": {k: round(v, 4) for k, v in weights.items() if v > 0.001},
            })
        except Exception:
            continue

    # Sort by volatility
    frontier.sort(key=lambda p: p["volatility"])
    return frontier


def get_portfolio_performance(
    weights: dict[str, float],
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> dict:
    """
    Calculate expected performance metrics for given weights.

    Parameters:
        weights (dict): Portfolio weights {ticker: weight}.
        expected_returns (pd.Series): Expected returns.
        cov_matrix (pd.DataFrame): Covariance matrix.
        risk_free_rate (float): Risk-free rate.

    Returns:
        dict: {"expected_return", "volatility", "sharpe_ratio"}.
    """
    w = np.array([weights.get(t, 0) for t in expected_returns.index])
    mu = expected_returns.values

    port_return = float(np.dot(w, mu))
    port_vol = float(np.sqrt(np.dot(w.T, np.dot(cov_matrix.values, w))))
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

    return {
        "expected_return": round(port_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
    }


def build_optimised_portfolio(
    selected_asset_classes: list[str],
    risk_score: float,
    investment_amount: float,
) -> dict:
    """
    Full portfolio construction pipeline:
    1. Map asset classes → primary ETF tickers
    2. Fetch historical prices
    3. Compute covariance matrix (Ledoit-Wolf)
    4. Compute expected returns (CAPM or BL, cost-adjusted)
    5. Check for high-correlation regime
    6. Run MVO for the given risk level
    7. Apply dual momentum overlay (if enabled)
    8. Return allocations with performance metrics

    Parameters:
        selected_asset_classes (list[str]): User's selected asset classes (min 3).
        risk_score (float): Composite risk score (1–10).
        investment_amount (float): Total investment in GBP.

    Returns:
        dict: {
            "weights": {asset_class: weight},
            "ticker_weights": {ticker: weight},
            "allocations": [{asset_class, ticker, weight, amount_gbp, ...}],
            "performance": {expected_return, volatility, sharpe_ratio},
            "frontier": [...],
            "high_correlation_regime": bool,
        }
    """
    # Step 1: Map to tickers
    ticker_map = get_ticker_map(selected_asset_classes)
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}

    if len(tickers) < 2:
        raise ValueError("Need at least 2 asset classes with valid ETFs")

    # Step 2: Fetch prices
    prices = build_close_price_matrix(tickers)
    if prices is None or prices.empty:
        raise ValueError("Could not fetch price data for the selected ETFs")

    # Step 3: Covariance matrix
    cov_matrix = compute_covariance(prices)

    # Step 4: Expected returns (cost-adjusted)
    expense_ratios = get_expense_ratios(selected_asset_classes)
    expense_by_ticker = {ticker_map[ac]: er for ac, er in expense_ratios.items()}
    mu = get_expected_returns(prices, cov_matrix, expense_by_ticker)

    # Step 5: Regime detection
    high_corr = detect_high_correlation_regime(cov_matrix)

    # Step 6: Weight bounds
    weight_bounds = _get_weight_bounds(tickers, ac_by_ticker)

    # If high-correlation regime, increase cash minimum
    if high_corr:
        for i, ticker in enumerate(tickers):
            if ac_by_ticker.get(ticker) == "cash_equivalent":
                lo, hi = weight_bounds[i]
                weight_bounds[i] = (lo + CRISIS_CASH_BUFFER, min(hi + CRISIS_CASH_BUFFER, 1.0))

    # Step 7: Optimise
    weights = optimise_for_risk_level(mu, cov_matrix, risk_score, weight_bounds)

    # Step 8: Dual momentum overlay
    cash_ticker = ticker_map.get("cash_equivalent")
    weights = apply_dual_momentum(prices, weights, cash_ticker)

    # Performance
    perf = get_portfolio_performance(weights, mu, cov_matrix)

    # Efficient frontier
    frontier = compute_efficient_frontier(mu, cov_matrix, weight_bounds)

    # Build allocations
    allocations = []
    total_expense = 0.0
    for ticker, weight in weights.items():
        if weight < 0.001:
            continue
        ac = ac_by_ticker.get(ticker, "unknown")
        er_val = expense_by_ticker.get(ticker, 0)
        total_expense += weight * er_val
        allocations.append({
            "asset_class": ac,
            "ticker": ticker,
            "weight": round(weight, 4),
            "amount_gbp": round(weight * investment_amount, 2),
            "expense_ratio": er_val,
        })

    return {
        "weights": {ac_by_ticker.get(t, t): w for t, w in weights.items()},
        "ticker_weights": weights,
        "allocations": sorted(allocations, key=lambda a: a["weight"], reverse=True),
        "performance": perf,
        "total_expense_ratio": round(total_expense, 6),
        "frontier": frontier,
        "high_correlation_regime": high_corr,
    }
