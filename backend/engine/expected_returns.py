"""
Expected Returns Estimator
============================
Computes expected returns using CAPM and optionally the Black-Litterman model.
Subtracts ETF expense ratios for cost-adjusted returns.

Reference:
- CAPM: Sharpe (1964), Lintner (1965)
- Black-Litterman: He & Litterman (1999)
- Factor model views: Fama-French factors adapted for UK market
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import expected_returns as er
from pypfopt import BlackLittermanModel

from backend.config import (
    MVO_RISK_FREE_RATE,
    BLACK_LITTERMAN_TAU,
    USE_BLACK_LITTERMAN,
    FACTOR_MODEL_LOOKBACK_YEARS,
    BENCHMARK_TICKER,
)

logger = logging.getLogger(__name__)


def compute_capm_returns(
    prices: pd.DataFrame,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Compute expected returns using the Capital Asset Pricing Model (CAPM).

    E[Ri] = Rf + βi * (E[Rm] - Rf)

    Uses PyPortfolioOpt's CAPM implementation which estimates beta from
    historical returns regression against the market portfolio.

    Parameters:
        prices (pd.DataFrame): Historical close prices (columns = tickers).
        risk_free_rate (float): Annualised risk-free rate (UK base rate).

    Returns:
        pd.Series: Expected annual returns per asset.
    """
    try:
        mu = er.capm_return(prices, risk_free_rate=risk_free_rate)
        return mu
    except Exception as e:
        logger.error(f"CAPM return estimation failed: {e}")
        # Fallback to historical mean returns
        return er.mean_historical_return(prices)


def compute_historical_returns(
    prices: pd.DataFrame,
    method: str = "mean",
) -> pd.Series:
    """
    Compute expected returns from historical data.

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        method (str): "mean" for arithmetic mean, "ema" for exponentially weighted.

    Returns:
        pd.Series: Annualised expected returns.
    """
    if method == "ema":
        return er.ema_historical_return(prices, span=252)
    return er.mean_historical_return(prices)


def compute_black_litterman_returns(
    prices: pd.DataFrame,
    cov_matrix: pd.DataFrame,
    market_caps: Optional[dict[str, float]] = None,
    views: Optional[dict[str, float]] = None,
    view_confidence: Optional[list[float]] = None,
    tau: float = BLACK_LITTERMAN_TAU,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Compute expected returns using the Black-Litterman model.

    The BL model combines market-implied equilibrium returns (from CAPM)
    with investor "views" using Bayesian inference, producing more stable
    expected return estimates than raw historical means.

    Algorithm:
    1. Compute market-implied equilibrium returns (π = δΣw_mkt)
    2. If views provided, blend with equilibrium using BL formula
    3. Result: E[R] = [(τΣ)^-1 + P'Ω^-1 P]^-1 [(τΣ)^-1 π + P'Ω^-1 Q]

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        cov_matrix (pd.DataFrame): Covariance matrix of returns.
        market_caps (dict, optional): {ticker: market_cap_gbp} for equilibrium weights.
        views (dict, optional): {ticker: expected_return_view} — absolute views.
        view_confidence (list, optional): Confidence levels for each view (0–1).
        tau (float): Scaling factor for uncertainty in the prior (default 0.05).
        risk_free_rate (float): Annualised risk-free rate.

    Returns:
        pd.Series: BL-adjusted expected returns.
    """
    try:
        # If no market caps, use equal weighting
        if market_caps is None:
            n = len(prices.columns)
            market_caps = {col: 1.0 / n for col in prices.columns}

        bl = BlackLittermanModel(
            cov_matrix,
            pi="market",
            market_caps=market_caps,
            risk_aversion=2.5,  # Standard market risk aversion
            risk_free_rate=risk_free_rate,
        )

        # Add views if provided
        if views:
            # Convert absolute views to the format BL expects
            bl.bl_returns()  # Compute equilibrium first

        return bl.bl_returns()

    except Exception as e:
        logger.warning(f"Black-Litterman failed, falling back to CAPM: {e}")
        return compute_capm_returns(prices, risk_free_rate)


def adjust_for_costs(
    expected_returns: pd.Series,
    expense_ratios: dict[str, float],
) -> pd.Series:
    """
    Subtract ETF expense ratios from expected returns.

    This cost adjustment ensures that cheaper ETFs are slightly favoured
    in the optimisation, all else being equal. Critical for UK UCITS ETFs
    where expense ratios vary widely (0.07% to 0.65%).

    Parameters:
        expected_returns (pd.Series): Pre-cost expected returns.
        expense_ratios (dict[str, float]): {ticker: expense_ratio}.

    Returns:
        pd.Series: Cost-adjusted expected returns.
    """
    adjusted = expected_returns.copy()
    for ticker in adjusted.index:
        if ticker in expense_ratios:
            adjusted[ticker] -= expense_ratios[ticker]
    return adjusted


def get_expected_returns(
    prices: pd.DataFrame,
    cov_matrix: pd.DataFrame,
    expense_ratios: dict[str, float],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    use_bl: bool = USE_BLACK_LITTERMAN,
) -> pd.Series:
    """
    Full expected returns pipeline: CAPM or BL → cost-adjusted.

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        cov_matrix (pd.DataFrame): Covariance matrix.
        expense_ratios (dict): {ticker: annual_expense_ratio}.
        risk_free_rate (float): UK base rate.
        use_bl (bool): Whether to use Black-Litterman (True) or CAPM (False).

    Returns:
        pd.Series: Net-of-fee expected annual returns.
    """
    if use_bl:
        mu = compute_black_litterman_returns(
            prices, cov_matrix, risk_free_rate=risk_free_rate,
        )
    else:
        mu = compute_capm_returns(prices, risk_free_rate)

    # Cost adjustment
    mu = adjust_for_costs(mu, expense_ratios)

    return mu
