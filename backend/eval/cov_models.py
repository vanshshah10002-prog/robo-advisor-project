"""
Covariance Estimator Registry (Phase 2 bake-off) — research layer.

The validated production estimators (sample/LW/EWMA/EWMA+LW, volatility
regime) live in backend.engine.quant_models; this module re-exports them for
back-compat and adds research-only candidates (OAS) plus the bake-off registry.

Dependency direction: engine ← eval (research imports production, never the
reverse).
"""

import logging
from functools import partial

import pandas as pd

# Re-exports from the production layer (back-compat for scripts)
from backend.engine.quant_models import (  # noqa: F401
    sample_cov,
    ledoit_wolf_cov,
    ewma_cov,
    ewma_lw_cov,
    rolling_avg_correlation,
    volatility_regime,
    _clean,
)

logger = logging.getLogger(__name__)

_ANNUALIZE = 12


def oas_cov(returns: pd.DataFrame) -> pd.DataFrame:
    """Oracle Approximating Shrinkage covariance (research candidate)."""
    R = _clean(returns)
    try:
        from sklearn.covariance import OAS
        oas = OAS().fit(R.values)
        return pd.DataFrame(oas.covariance_ * _ANNUALIZE, index=R.columns, columns=R.columns)
    except Exception as e:
        logger.warning(f"OAS failed ({e}); Ledoit-Wolf")
        return ledoit_wolf_cov(returns)


def get_cov_models() -> dict:
    """Covariance estimators for the Phase 2 bake-off."""
    return {
        "sample": sample_cov,
        "ledoit_wolf": ledoit_wolf_cov,
        "oas": oas_cov,
        "ewma_12": partial(ewma_cov, halflife=12),
        "ewma_24": partial(ewma_cov, halflife=24),
        "ewma_lw_12": partial(ewma_lw_cov, halflife=12),
    }
