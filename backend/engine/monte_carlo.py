"""
Monte Carlo Simulation — Goal Planning Projections
====================================================
Simulates N portfolio paths using geometric Brownian motion with
correlated asset returns. Provides percentile fan charts for
financial goal planning.

Reference: Standard GBM simulation adapted from Wealthfront methodology.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import MONTE_CARLO_SIMULATIONS, MONTE_CARLO_YEARS

logger = logging.getLogger(__name__)


def run_monte_carlo(
    initial_investment: float,
    monthly_contribution: float,
    weights: dict[str, float],
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    years: int = MONTE_CARLO_YEARS,
    n_simulations: int = MONTE_CARLO_SIMULATIONS,
    goal_amount: Optional[float] = None,
) -> dict:
    """
    Run Monte Carlo simulation for portfolio projection.

    Uses multivariate geometric Brownian motion to simulate correlated
    asset returns, then aggregates to portfolio level using weights.

    Algorithm:
    1. Compute portfolio expected return and volatility from weights
    2. For each simulation:
       a. Generate random monthly returns from N(μ_monthly, σ_monthly)
       b. Apply compounding: V(t+1) = V(t) * (1 + r_t) + contribution
       c. Record portfolio value at each year-end
    3. Compute percentile paths (10th, 25th, 50th, 75th, 90th)

    Parameters:
        initial_investment (float): Starting capital in GBP.
        monthly_contribution (float): Monthly recurring investment in GBP.
        weights (dict[str, float]): Portfolio weights {ticker: weight}.
        expected_returns (pd.Series): Annualised expected returns per asset.
        cov_matrix (pd.DataFrame): Covariance matrix.
        years (int): Projection horizon in years.
        n_simulations (int): Number of simulation paths.
        goal_amount (float, optional): Target amount for probability calculation.

    Returns:
        dict: {
            "percentile_10": list[float],   # 10th percentile path (yearly values)
            "percentile_25": list[float],
            "percentile_50": list[float],
            "percentile_75": list[float],
            "percentile_90": list[float],
            "years": list[int],             # [0, 1, 2, ..., years]
            "expected_final_value": float,
            "median_final_value": float,
            "probability_of_goal": float or None,
        }
    """
    # Compute portfolio-level expected return and volatility
    valid_tickers = [t for t in expected_returns.index if t in weights and weights[t] > 0]
    w = np.array([weights.get(t, 0) for t in valid_tickers])
    mu = np.array([expected_returns[t] for t in valid_tickers])

    # Subset covariance matrix
    cov_sub = cov_matrix.loc[valid_tickers, valid_tickers].values

    # Portfolio-level parameters
    port_return = float(np.dot(w, mu))
    port_vol = float(np.sqrt(np.dot(w.T, np.dot(cov_sub, w))))

    # Monthly parameters
    monthly_return = port_return / 12
    monthly_vol = port_vol / np.sqrt(12)

    # Simulation
    months = years * 12
    rng = np.random.default_rng(seed=42)  # Reproducible for consistency
    all_paths = np.zeros((n_simulations, months + 1))
    all_paths[:, 0] = initial_investment

    random_returns = rng.normal(monthly_return, monthly_vol, size=(n_simulations, months))

    for m in range(months):
        all_paths[:, m + 1] = (
            all_paths[:, m] * (1 + random_returns[:, m]) + monthly_contribution
        )
        # Floor at 0 (can't go negative)
        all_paths[:, m + 1] = np.maximum(all_paths[:, m + 1], 0)

    # Extract year-end values
    year_indices = [0] + [i * 12 for i in range(1, years + 1)]
    yearly_values = all_paths[:, year_indices]

    # Percentiles
    percentiles = {
        10: np.percentile(yearly_values, 10, axis=0).tolist(),
        25: np.percentile(yearly_values, 25, axis=0).tolist(),
        50: np.percentile(yearly_values, 50, axis=0).tolist(),
        75: np.percentile(yearly_values, 75, axis=0).tolist(),
        90: np.percentile(yearly_values, 90, axis=0).tolist(),
    }

    final_values = yearly_values[:, -1]

    # Goal probability
    prob_goal = None
    if goal_amount is not None:
        prob_goal = float(np.mean(final_values >= goal_amount))

    return {
        "percentile_10": [round(v, 2) for v in percentiles[10]],
        "percentile_25": [round(v, 2) for v in percentiles[25]],
        "percentile_50": [round(v, 2) for v in percentiles[50]],
        "percentile_75": [round(v, 2) for v in percentiles[75]],
        "percentile_90": [round(v, 2) for v in percentiles[90]],
        "years": list(range(years + 1)),
        "expected_final_value": round(float(np.mean(final_values)), 2),
        "median_final_value": round(float(np.median(final_values)), 2),
        "probability_of_goal": prob_goal,
    }


def quick_projection(
    initial_investment: float,
    monthly_contribution: float,
    annual_return: float,
    annual_volatility: float,
    years: int = 30,
    n_simulations: int = 500,
) -> dict:
    """
    Simplified Monte Carlo using portfolio-level parameters directly.
    Useful for quick projections without full covariance data.

    Parameters:
        initial_investment (float): Starting capital in GBP.
        monthly_contribution (float): Monthly investment in GBP.
        annual_return (float): Expected annual return.
        annual_volatility (float): Expected annual volatility.
        years (int): Projection horizon.
        n_simulations (int): Number of paths.

    Returns:
        dict: Same structure as run_monte_carlo.
    """
    monthly_return = annual_return / 12
    monthly_vol = annual_volatility / np.sqrt(12)
    months = years * 12

    rng = np.random.default_rng(seed=42)
    all_paths = np.zeros((n_simulations, months + 1))
    all_paths[:, 0] = initial_investment

    random_returns = rng.normal(monthly_return, monthly_vol, size=(n_simulations, months))

    for m in range(months):
        all_paths[:, m + 1] = (
            all_paths[:, m] * (1 + random_returns[:, m]) + monthly_contribution
        )
        all_paths[:, m + 1] = np.maximum(all_paths[:, m + 1], 0)

    year_indices = [0] + [i * 12 for i in range(1, years + 1)]
    yearly_values = all_paths[:, year_indices]
    final_values = yearly_values[:, -1]

    return {
        "percentile_10": [round(v, 2) for v in np.percentile(yearly_values, 10, axis=0)],
        "percentile_25": [round(v, 2) for v in np.percentile(yearly_values, 25, axis=0)],
        "percentile_50": [round(v, 2) for v in np.percentile(yearly_values, 50, axis=0)],
        "percentile_75": [round(v, 2) for v in np.percentile(yearly_values, 75, axis=0)],
        "percentile_90": [round(v, 2) for v in np.percentile(yearly_values, 90, axis=0)],
        "years": list(range(years + 1)),
        "expected_final_value": round(float(np.mean(final_values)), 2),
        "median_final_value": round(float(np.median(final_values)), 2),
        "probability_of_goal": None,
    }
