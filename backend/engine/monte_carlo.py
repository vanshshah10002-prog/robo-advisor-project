"""
Monte Carlo Simulation — Goal Planning Projections
====================================================
Simulates N portfolio paths in LOG-return space using Student-t innovations
(fat tails) with a volatility-drag-correct drift. Contributions grow with
inflation. Provides percentile fan charts for financial goal planning.

Math (Phase 4, corrected):
  Given annual arithmetic expected return μ_a and annual vol σ_a:
    σ_m   = σ_a / √12                                   (monthly vol)
    m_log = (1/12)·ln(1+μ_a) − ½·σ_m²                   (vol-drag-correct drift)
  Innovations are standardised Student-t(ν) scaled to unit variance:
    ε = t_raw / √(ν/(ν−2)),  log_r = m_log + σ_m·ε
  Wealth compounds as  V_{t+1} = V_t·exp(log_r) + contribution_t,
  with contribution_t grown at the monthly inflation rate.

Why Student-t: Phases 1–2 confirmed monthly return residuals are fat-tailed
(ν≈6 in stress, ≈11 in calm; Jarque-Bera rejects normality). Normal draws
understate tail/drawdown risk and overstate P(goal).

Reference: lognormal/GBM with Student-t innovations; vol-drag per Markowitz.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import (
    MONTE_CARLO_SIMULATIONS,
    MONTE_CARLO_YEARS,
    MONTE_CARLO_T_DOF,
    MONTE_CARLO_INFLATION,
    MONTE_CARLO_SEED,
)

logger = logging.getLogger(__name__)

# Back-compat aliases (constants now live in config)
STUDENT_T_DOF: float = MONTE_CARLO_T_DOF
INFLATION_RATE: float = MONTE_CARLO_INFLATION


def _simulate_paths(
    initial_investment: float,
    monthly_contribution: float,
    annual_return: float,
    annual_vol: float,
    years: int,
    n_simulations: int,
    t_dof: float = STUDENT_T_DOF,
    inflation_rate: float = INFLATION_RATE,
    seed: int = MONTE_CARLO_SEED,
) -> np.ndarray:
    """
    Core path simulator in log-return space with Student-t innovations,
    vol-drag-correct drift, and inflation-growing contributions.

    Returns:
        np.ndarray: shape (n_simulations, months+1) of portfolio values.
    """
    months = years * 12
    sigma_m = annual_vol / np.sqrt(12.0)
    # Vol-drag-correct monthly LOG drift so the compounded annual arithmetic
    # expectation equals `annual_return`.
    m_log = (np.log1p(annual_return) / 12.0) - 0.5 * sigma_m ** 2

    rng = np.random.default_rng(seed=seed)
    if t_dof > 2:
        t_raw = rng.standard_t(t_dof, size=(n_simulations, months))
        eps = t_raw / np.sqrt(t_dof / (t_dof - 2.0))   # standardise to unit variance
    else:
        eps = rng.standard_normal(size=(n_simulations, months))
    log_r = m_log + sigma_m * eps

    infl_m = (1.0 + inflation_rate) ** (1.0 / 12.0) - 1.0
    paths = np.zeros((n_simulations, months + 1))
    paths[:, 0] = initial_investment
    for m in range(months):
        contrib = monthly_contribution * (1.0 + infl_m) ** m
        paths[:, m + 1] = paths[:, m] * np.exp(log_r[:, m]) + contrib
        paths[:, m + 1] = np.maximum(paths[:, m + 1], 0.0)
    return paths


def _simulate_paths_garch(
    initial_investment: float,
    monthly_contribution: float,
    annual_return: float,
    garch_params: dict,
    years: int,
    n_simulations: int,
    inflation_rate: float = INFLATION_RATE,
    seed: int = MONTE_CARLO_SEED,
) -> np.ndarray:
    """
    Path simulator with GARCH(1,1)-t conditional volatility (vol clustering).

    Dynamics per month:
        σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
        ε_t  = σ_t · z_t,   z_t ~ standardized Student-t(ν), unit variance
        r_t  = ln(1+μ_a)/12 − ½σ²_t + ε_t          (vol-drag-correct drift)
        V_t  = V_{t-1}·exp(r_t) + contribution_t   (inflation-grown)

    `garch_params` must be MONTHLY-frequency (from quant_models.fit_garch_t on
    monthly returns). Use only when `clustering_significant`; otherwise the
    i.i.d.-t simulator is the data-supported default at monthly step.

    Returns:
        np.ndarray: shape (n_simulations, months+1) of portfolio values.
    """
    omega = float(garch_params["omega"])
    alpha = float(garch_params["alpha"])
    beta = float(garch_params["beta"])
    nu = max(2.5, float(min(garch_params.get("nu", 8.0), 100.0)))
    var0 = float(garch_params.get("uncond_var")) if garch_params.get("uncond_var") else omega / max(1e-12, 1 - alpha - beta)

    months = years * 12
    rng = np.random.default_rng(seed=seed)
    z = rng.standard_t(nu, size=(n_simulations, months)) / np.sqrt(nu / (nu - 2.0))

    base_drift = np.log1p(annual_return) / 12.0
    infl_m = (1.0 + inflation_rate) ** (1.0 / 12.0) - 1.0

    paths = np.zeros((n_simulations, months + 1))
    paths[:, 0] = initial_investment
    var_t = np.full(n_simulations, var0)
    for m in range(months):
        sigma_t = np.sqrt(var_t)
        eps = sigma_t * z[:, m]
        log_r = base_drift - 0.5 * var_t + eps
        contrib = monthly_contribution * (1.0 + infl_m) ** m
        paths[:, m + 1] = np.maximum(paths[:, m] * np.exp(log_r) + contrib, 0.0)
        var_t = omega + alpha * eps ** 2 + beta * var_t
    return paths


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
    # Renormalise in case some weights were dropped (keeps μ,σ on the actual book)
    if w.sum() > 0:
        w = w / w.sum()
    mu = np.array([expected_returns[t] for t in valid_tickers])

    # Subset covariance matrix
    cov_sub = cov_matrix.loc[valid_tickers, valid_tickers].values

    # Portfolio-level parameters (annual)
    port_return = float(np.dot(w, mu))
    port_vol = float(np.sqrt(np.dot(w.T, np.dot(cov_sub, w))))

    # Simulate with Student-t innovations + vol-drag drift + inflation-grown contributions
    all_paths = _simulate_paths(
        initial_investment, monthly_contribution, port_return, port_vol,
        years, n_simulations,
    )

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

    # Goal probability — REAL-TERMS consistent: contributions grow with
    # inflation, so the goal is also inflated to the horizon. Comparing
    # inflation-grown wealth against a frozen nominal goal would overstate
    # P(goal) on long horizons.
    prob_goal = None
    if goal_amount is not None:
        goal_at_horizon = goal_amount * (1.0 + INFLATION_RATE) ** years
        prob_goal = float(np.mean(final_values >= goal_at_horizon))

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
    all_paths = _simulate_paths(
        initial_investment, monthly_contribution, annual_return, annual_volatility,
        years, n_simulations,
    )

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
