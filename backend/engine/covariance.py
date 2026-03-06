"""
Covariance Matrix Estimator — Ledoit-Wolf Shrinkage
=====================================================
Computes the covariance matrix of asset returns using shrinkage estimation
for numerical stability in portfolio optimisation.

Reference:
- Ledoit & Wolf (2004), "A well-conditioned estimator for large-dimensional covariance matrices"
- PyPortfolioOpt: CovarianceShrinkage implementation
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import risk_models

from backend.config import SHRINKAGE_METHOD, REGIME_DETECTION_ENABLED, REGIME_HIGH_CORR_THRESHOLD

logger = logging.getLogger(__name__)


def compute_covariance_ledoit_wolf(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the Ledoit-Wolf shrinkage covariance matrix.

    The Ledoit-Wolf estimator shrinks the sample covariance matrix toward
    a structured target (constant correlation model), producing a more
    stable estimate that performs better in optimisation.

    Separates into systematic + idiosyncratic components implicitly
    via the shrinkage procedure.

    Parameters:
        prices (pd.DataFrame): Historical close prices (columns = tickers).

    Returns:
        pd.DataFrame: Shrinkage-estimated covariance matrix.
    """
    try:
        cs = risk_models.CovarianceShrinkage(prices)
        return cs.ledoit_wolf()
    except Exception as e:
        logger.error(f"Ledoit-Wolf shrinkage failed: {e}")
        return risk_models.sample_cov(prices)


def compute_covariance_oracle(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute covariance using Oracle Approximating Shrinkage (OAS).

    An alternative shrinkage method that can outperform Ledoit-Wolf
    in some conditions.

    Parameters:
        prices (pd.DataFrame): Historical close prices.

    Returns:
        pd.DataFrame: OAS-estimated covariance matrix.
    """
    try:
        cs = risk_models.CovarianceShrinkage(prices)
        return cs.oracle_approximating()
    except Exception as e:
        logger.error(f"Oracle shrinkage failed, falling back to Ledoit-Wolf: {e}")
        return compute_covariance_ledoit_wolf(prices)


def compute_covariance(
    prices: pd.DataFrame,
    method: str = SHRINKAGE_METHOD,
) -> pd.DataFrame:
    """
    Compute the covariance matrix using the configured shrinkage method.

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        method (str): "ledoit_wolf" | "oracle_approx" | "identity".

    Returns:
        pd.DataFrame: Estimated covariance matrix.
    """
    if method == "oracle_approx":
        return compute_covariance_oracle(prices)
    elif method == "identity":
        # Identity matrix (no correlation): useful for debugging
        n = len(prices.columns)
        returns = prices.pct_change().dropna()
        vols = returns.std() * np.sqrt(252)
        cov = pd.DataFrame(
            np.diag(vols.values ** 2),
            index=prices.columns,
            columns=prices.columns,
        )
        return cov
    else:
        return compute_covariance_ledoit_wolf(prices)


def compute_correlation_matrix(cov_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Derive the correlation matrix from a covariance matrix.

    Parameters:
        cov_matrix (pd.DataFrame): Covariance matrix.

    Returns:
        pd.DataFrame: Correlation matrix.
    """
    std_devs = np.sqrt(np.diag(cov_matrix.values))
    std_outer = np.outer(std_devs, std_devs)
    corr = cov_matrix.values / std_outer
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=cov_matrix.index, columns=cov_matrix.columns)


def detect_high_correlation_regime(cov_matrix: pd.DataFrame) -> bool:
    """
    Detect if we're in a high-correlation regime (e.g., 2022-style crisis
    where everything sells off together).

    In high-correlation regimes, diversification benefits diminish.
    The config can trigger an increased cash allocation via CRISIS_CASH_BUFFER.

    Parameters:
        cov_matrix (pd.DataFrame): Current covariance matrix.

    Returns:
        bool: True if average pairwise correlation exceeds threshold.
    """
    if not REGIME_DETECTION_ENABLED:
        return False

    corr = compute_correlation_matrix(cov_matrix)
    n = len(corr)

    # Average off-diagonal correlation
    mask = np.ones((n, n), dtype=bool)
    np.fill_diagonal(mask, False)
    avg_corr = np.abs(corr.values[mask]).mean()

    is_high = avg_corr > REGIME_HIGH_CORR_THRESHOLD
    if is_high:
        logger.warning(
            f"HIGH CORRELATION REGIME DETECTED: avg pairwise correlation = {avg_corr:.3f} "
            f"(threshold: {REGIME_HIGH_CORR_THRESHOLD})"
        )
    return is_high
