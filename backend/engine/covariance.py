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

    IMPORTANT: Converts prices to daily returns first to avoid
    price-scale artifacts when ETF prices differ greatly
    (e.g., IGLT.L ~£10 vs SGLN.L ~£7500).

    Parameters:
        prices (pd.DataFrame): Historical close prices (columns = tickers).

    Returns:
        pd.DataFrame: Annualised shrinkage covariance matrix.
    """
    try:
        # Convert to daily percentage returns first
        returns = prices.pct_change().dropna()
        if returns.empty or len(returns) < 30:
            logger.warning("Insufficient return data for Ledoit-Wolf, using sample cov")
            return risk_models.sample_cov(prices)

        # Use returns_data=True so pypfopt knows these are returns, not prices
        cs = risk_models.CovarianceShrinkage(returns, returns_data=True)
        # cs.ledoit_wolf() already annualises based on daily frequency in our index
        cov = cs.ledoit_wolf()

        logger.info(
            f"Ledoit-Wolf covariance computed: {len(cov)} assets, "
            f"vol range [{np.sqrt(np.diag(cov)).min():.4f}, {np.sqrt(np.diag(cov)).max():.4f}]"
        )
        return cov
    except Exception as e:
        logger.error(f"Ledoit-Wolf shrinkage failed: {e}")
        # Fallback: manual returns-based sample covariance
        returns = prices.pct_change().dropna()
        cov = returns.cov() * 252  # Annualise
        return cov


def compute_covariance_oracle(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute covariance using Oracle Approximating Shrinkage (OAS).

    Parameters:
        prices (pd.DataFrame): Historical close prices.

    Returns:
        pd.DataFrame: OAS-estimated covariance matrix.
    """
    try:
        returns = prices.pct_change().dropna()
        cs = risk_models.CovarianceShrinkage(returns, returns_data=True)
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
        pd.DataFrame: Estimated annualised covariance matrix.
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
