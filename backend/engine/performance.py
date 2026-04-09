"""
Portfolio Performance Metrics — Rolling Analytics
===================================================
Computes 7 rolling performance metrics over a configurable window:
1. Annualised return (geometric mean)
2. Annualised volatility (σ × √252)
3. Sharpe ratio ((R - Rf) / σ)
4. Sortino ratio ((R - Rf) / σ_downside)
5. Maximum drawdown (peak-to-trough)
6. Portfolio beta (cov(Rp, Rm) / var(Rm))
7. Tracking error (vol of Rp - Rb)

Reference:
    - Wealthfront Methodology (portfolio analytics)
    - Investment Science 101 (CAPM beta, Sharpe ratio)
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import MVO_RISK_FREE_RATE, BENCHMARK_TICKER

logger = logging.getLogger(__name__)

# Default rolling window
PERFORMANCE_WINDOW_DAYS = 252  # 1 year of trading days


def compute_annualised_return(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Compute annualised return using geometric compounding.

    Parameters:
        returns (pd.Series): Daily returns.
        periods_per_year (int): Trading days per year.

    Returns:
        float: Annualised geometric return.
    """
    if returns.empty:
        return 0.0
    total_return = (1 + returns).prod()
    n_years = len(returns) / periods_per_year
    if n_years <= 0:
        return 0.0
    return float(total_return ** (1 / n_years) - 1)


def compute_annualised_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Compute annualised volatility.

    Parameters:
        returns (pd.Series): Daily returns.
        periods_per_year (int): Trading days per year.

    Returns:
        float: Annualised standard deviation.
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    return float(returns.std() * np.sqrt(periods_per_year))


def compute_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    periods_per_year: int = 252,
) -> float:
    """
    Compute the Sharpe ratio.

    Sharpe = (Annualised Return - Rf) / Annualised Volatility

    Parameters:
        returns (pd.Series): Daily returns.
        risk_free_rate (float): Annualised risk-free rate.
        periods_per_year (int): Trading days per year.

    Returns:
        float: Sharpe ratio.
    """
    ann_ret = compute_annualised_return(returns, periods_per_year)
    ann_vol = compute_annualised_volatility(returns, periods_per_year)
    if ann_vol == 0:
        return 0.0
    return float((ann_ret - risk_free_rate) / ann_vol)


def compute_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    periods_per_year: int = 252,
) -> float:
    """
    Compute the Sortino ratio (uses downside deviation only).

    Sortino = (Annualised Return - Rf) / Downside Volatility

    Parameters:
        returns (pd.Series): Daily returns.
        risk_free_rate (float): Annualised risk-free rate.
        periods_per_year (int): Trading days per year.

    Returns:
        float: Sortino ratio.
    """
    ann_ret = compute_annualised_return(returns, periods_per_year)
    daily_rf = risk_free_rate / periods_per_year
    downside = returns[returns < daily_rf]
    if downside.empty or len(downside) < 2:
        return 0.0
    downside_vol = float(downside.std() * np.sqrt(periods_per_year))
    if downside_vol == 0:
        return 0.0
    return float((ann_ret - risk_free_rate) / downside_vol)


def compute_max_drawdown(returns: pd.Series) -> float:
    """
    Compute maximum drawdown (worst peak-to-trough decline).

    Parameters:
        returns (pd.Series): Daily returns.

    Returns:
        float: Maximum drawdown as a negative fraction (e.g., -0.15 = -15%).
    """
    if returns.empty:
        return 0.0
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdowns = cumulative / running_max - 1
    return float(drawdowns.min())


def compute_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    Compute portfolio beta against a benchmark.

    β = Cov(Rp, Rb) / Var(Rb)

    Per Investment Science lecture: "Beta measures sensitivity to
    systematic (market) risk."

    Parameters:
        portfolio_returns (pd.Series): Daily portfolio returns.
        benchmark_returns (pd.Series): Daily benchmark returns.

    Returns:
        float: Portfolio beta.
    """
    if portfolio_returns.empty or benchmark_returns.empty:
        return 1.0

    # Align dates
    aligned = pd.DataFrame({
        "portfolio": portfolio_returns,
        "benchmark": benchmark_returns,
    }).dropna()

    if len(aligned) < 10:
        return 1.0

    cov = aligned["portfolio"].cov(aligned["benchmark"])
    var_benchmark = aligned["benchmark"].var()
    if var_benchmark == 0:
        return 1.0
    return float(cov / var_benchmark)


def compute_tracking_error(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Compute annualised tracking error.

    TE = σ(Rp - Rb) × √252

    Parameters:
        portfolio_returns (pd.Series): Daily portfolio returns.
        benchmark_returns (pd.Series): Daily benchmark returns.
        periods_per_year (int): Trading days per year.

    Returns:
        float: Annualised tracking error.
    """
    if portfolio_returns.empty or benchmark_returns.empty:
        return 0.0

    aligned = pd.DataFrame({
        "portfolio": portfolio_returns,
        "benchmark": benchmark_returns,
    }).dropna()

    if len(aligned) < 10:
        return 0.0

    diff = aligned["portfolio"] - aligned["benchmark"]
    return float(diff.std() * np.sqrt(periods_per_year))


def compute_all_metrics(
    portfolio_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    window_days: int = PERFORMANCE_WINDOW_DAYS,
) -> dict:
    """
    Compute all 7 performance metrics for a portfolio.

    Parameters:
        portfolio_returns (pd.Series): Daily portfolio returns.
        benchmark_returns (pd.Series, optional): Daily benchmark returns.
        risk_free_rate (float): Annualised risk-free rate.
        window_days (int): Rolling window in trading days.

    Returns:
        dict: {
            "annualised_return": float,
            "annualised_volatility": float,
            "sharpe_ratio": float,
            "sortino_ratio": float,
            "max_drawdown": float,
            "beta": float,
            "tracking_error": float,
            "window_days": int,
        }
    """
    # Use most recent window_days
    if len(portfolio_returns) > window_days:
        windowed = portfolio_returns.iloc[-window_days:]
    else:
        windowed = portfolio_returns

    metrics = {
        "annualised_return": round(compute_annualised_return(windowed), 4),
        "annualised_volatility": round(compute_annualised_volatility(windowed), 4),
        "sharpe_ratio": round(compute_sharpe_ratio(windowed, risk_free_rate), 4),
        "sortino_ratio": round(compute_sortino_ratio(windowed, risk_free_rate), 4),
        "max_drawdown": round(compute_max_drawdown(windowed), 4),
        "beta": 1.0,
        "tracking_error": 0.0,
        "window_days": len(windowed),
    }

    if benchmark_returns is not None and not benchmark_returns.empty:
        if len(benchmark_returns) > window_days:
            bench_windowed = benchmark_returns.iloc[-window_days:]
        else:
            bench_windowed = benchmark_returns

        metrics["beta"] = round(compute_beta(windowed, bench_windowed), 4)
        metrics["tracking_error"] = round(
            compute_tracking_error(windowed, bench_windowed), 4
        )

    logger.info(
        f"Performance metrics: Sharpe={metrics['sharpe_ratio']}, "
        f"Sortino={metrics['sortino_ratio']}, MaxDD={metrics['max_drawdown']:.1%}, "
        f"ß={metrics['beta']}"
    )
    return metrics


def compute_portfolio_returns(
    prices: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    """
    Compute daily portfolio returns from individual asset prices and weights.

    Parameters:
        prices (pd.DataFrame): Daily close prices (columns = tickers).
        weights (dict[str, float]): Portfolio weights {ticker: weight}.

    Returns:
        pd.Series: Daily portfolio returns.
    """
    returns = prices.pct_change().dropna()
    valid_tickers = [t for t in weights if t in returns.columns and t != "__CASH__"]
    if not valid_tickers:
        return pd.Series(dtype=float)

    w = np.array([weights.get(t, 0) for t in valid_tickers])
    asset_returns = returns[valid_tickers].values

    portfolio_returns = asset_returns @ w
    return pd.Series(portfolio_returns, index=returns.index, name="portfolio")
