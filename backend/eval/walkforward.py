"""
Walk-Forward Harness — Out-of-Sample Expected-Return Evaluation
================================================================
Drives any expected-return model through an expanding-window walk-forward:
at each month t the model sees only data up to t, predicts next-month
returns, and the realized next-month return is recorded. Produces the
predicted / realized / sigma panels and pooled standardized residuals that
feed backend.eval.metrics.

A true HOLD-OUT (most recent `holdout_months`) is sliced off and never
passed to model development; run the final model on it separately.

Model contract:
    model(train_log_returns: pd.DataFrame) -> pd.Series
        returns ANNUAL ARITHMETIC expected returns indexed by ticker.

Reference: docs/OPTIMIZATION_WALKTHROUGH.md (Phase 0 / Phase 1).
"""

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ModelFn = Callable[[pd.DataFrame], pd.Series]


@dataclass
class WalkForwardResult:
    """Panels and residuals from a walk-forward run."""
    predicted: pd.DataFrame      # index=rebalance date, cols=tickers — predicted monthly LOG return
    realized: pd.DataFrame       # realized next-month LOG return
    sigma: pd.DataFrame          # predicted monthly vol used to standardize
    residuals: pd.Series         # pooled standardized residuals (flattened)

    def pooled_residuals(self) -> np.ndarray:
        return self.residuals.to_numpy(dtype=float)


def split_holdout(
    monthly_log_returns: pd.DataFrame,
    holdout_months: int = 18,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split the most recent `holdout_months` rows into an untouched hold-out set.

    Returns:
        (development_set, holdout_set)
    """
    if holdout_months <= 0 or holdout_months >= len(monthly_log_returns):
        return monthly_log_returns, monthly_log_returns.iloc[0:0]
    dev = monthly_log_returns.iloc[:-holdout_months]
    hold = monthly_log_returns.iloc[-holdout_months:]
    logger.info(f"Hold-out split: dev={dev.shape[0]} months, holdout={hold.shape[0]} months")
    return dev, hold


def _arith_annual_to_log_monthly(
    mu_annual_arith: pd.Series,
    sigma_annual: pd.Series,
) -> pd.Series:
    """
    Convert annual ARITHMETIC expected returns to monthly LOG expected returns,
    applying the volatility-drag correction so residuals are unbiased:

        mu_monthly_arith = (1 + mu_annual)^(1/12) - 1
        mu_monthly_log   = ln(1 + mu_monthly_arith) - 0.5 * sigma_monthly^2
    """
    sigma_monthly = sigma_annual / np.sqrt(12.0)
    mu_monthly_arith = np.power(1.0 + mu_annual_arith, 1.0 / 12.0) - 1.0
    mu_monthly_log = np.log1p(mu_monthly_arith) - 0.5 * (sigma_monthly ** 2)
    return mu_monthly_log


def run_walk_forward_portfolio(
    monthly_log_returns: pd.DataFrame,
    model: ModelFn,
    min_train_months: int = 36,
    vol_lookback_months: int = 36,
    max_weight: float = 0.30,
    risk_free_annual: float = 0.04,
) -> pd.Series:
    """
    Realized out-of-sample portfolio returns from a model's expected returns.

    At each month: train → mu_annual = model(train); build a long-only max-Sharpe
    portfolio (weights in [0, max_weight]) from mu + sample covariance; hold for
    the next month and record the realized portfolio LOG return. The resulting
    series feeds backend.eval.metrics.realized_sharpe — the "ultimate test".

    Falls back to inverse-variance weights if the optimizer fails.

    Returns:
        pd.Series: realized monthly portfolio log returns indexed by month.
    """
    try:
        from pypfopt import EfficientFrontier
    except Exception:
        EfficientFrontier = None

    R = monthly_log_returns.sort_index()
    dates = R.index
    n = len(dates)
    realized_returns: dict[pd.Timestamp, float] = {}

    t = min_train_months
    while t + 1 <= n:
        train = R.iloc[:t]
        valid = train.columns[train.count() >= min_train_months]
        if len(valid) < 2:
            t += 1
            continue
        train_v = train[valid]

        try:
            mu_annual = model(train_v).reindex(valid).dropna()
        except Exception:
            t += 1
            continue
        cols = mu_annual.index
        if len(cols) < 2:
            t += 1
            continue

        # Use the PRODUCTION covariance (EWMA+LW) so model selection happens
        # under the same risk model production runs (was: sample cov).
        from backend.engine.quant_models import ewma_lw_cov
        cov_annual = ewma_lw_cov(train_v[cols].iloc[-vol_lookback_months:])
        cov_annual = cov_annual.reindex(index=cols, columns=cols)
        # small diagonal shrinkage for numerical stability
        cov_annual = cov_annual + np.eye(len(cols)) * 1e-6

        weights = None
        if EfficientFrontier is not None:
            try:
                ef = EfficientFrontier(mu_annual, cov_annual, weight_bounds=(0.0, max_weight))
                ef.max_sharpe(risk_free_rate=risk_free_annual)
                w = ef.clean_weights()
                weights = pd.Series(w).reindex(cols).fillna(0.0)
            except Exception:
                weights = None
        if weights is None or weights.sum() <= 0:
            inv_var = 1.0 / np.diag(cov_annual.values)
            weights = pd.Series(inv_var / inv_var.sum(), index=cols)

        realized_simple = np.expm1(R.iloc[t][cols])  # next-month simple returns
        port_simple = float((weights * realized_simple).sum())
        realized_returns[dates[t]] = float(np.log1p(port_simple))
        t += 1

    return pd.Series(realized_returns).sort_index()


def run_walk_forward_gmv(
    monthly_log_returns: pd.DataFrame,
    cov_fn: Callable[[pd.DataFrame], pd.DataFrame],
    min_train_months: int = 36,
    max_weight: float = 0.30,
) -> dict:
    """
    Evaluate a covariance estimator via the global minimum-variance (GMV)
    portfolio held out of sample — the Ledoit-Wolf (2004) standard test.

    At each month: train → cov = cov_fn(train) → long-only GMV weights
    (in [0, max_weight]) → record realized next-month portfolio return and the
    predicted (annualized) portfolio vol. The estimator whose GMV has the
    LOWEST realized out-of-sample volatility is best; the realized/predicted
    vol ratio measures calibration (≈ 1 is well-calibrated).

    Returns:
        dict: {"realized": pd.Series(monthly log returns),
                "pred_vol_annual": pd.Series, "n": int}
    """
    try:
        from pypfopt import EfficientFrontier
    except Exception:
        EfficientFrontier = None

    R = monthly_log_returns.sort_index()
    dates = R.index
    n = len(dates)
    realized: dict[pd.Timestamp, float] = {}
    pred_vol: dict[pd.Timestamp, float] = {}

    t = min_train_months
    while t + 1 <= n:
        train = R.iloc[:t]
        valid = train.columns[train.count() >= min_train_months]
        if len(valid) < 2:
            t += 1
            continue
        train_v = train[valid]

        try:
            cov_annual = cov_fn(train_v)
        except Exception:
            t += 1
            continue
        cols = list(cov_annual.columns)
        if len(cols) < 2:
            t += 1
            continue
        cov_annual = cov_annual + np.eye(len(cols)) * 1e-8

        weights = None
        if EfficientFrontier is not None:
            try:
                mu_dummy = pd.Series(0.0, index=cols)  # GMV ignores returns
                ef = EfficientFrontier(mu_dummy, cov_annual, weight_bounds=(0.0, max_weight))
                ef.min_volatility()
                w = ef.clean_weights()
                weights = pd.Series(w).reindex(cols).fillna(0.0)
            except Exception:
                weights = None
        if weights is None or weights.sum() <= 0:
            inv_var = 1.0 / np.diag(cov_annual.values)
            weights = pd.Series(inv_var / inv_var.sum(), index=cols)

        wv = weights.values
        pred_vol[dates[t]] = float(np.sqrt(wv @ cov_annual.values @ wv))
        realized_simple = np.expm1(R.iloc[t][cols])
        port_simple = float((weights * realized_simple).sum())
        realized[dates[t]] = float(np.log1p(port_simple))
        t += 1

    return {
        "realized": pd.Series(realized).sort_index(),
        "pred_vol_annual": pd.Series(pred_vol).sort_index(),
        "n": len(realized),
    }


def run_walk_forward(
    monthly_log_returns: pd.DataFrame,
    model: ModelFn,
    min_train_months: int = 36,
    step_months: int = 1,
    vol_lookback_months: int = 36,
) -> WalkForwardResult:
    """
    Run an expanding-window walk-forward over monthly log returns.

    At each rebalance month t (t >= min_train_months):
        - train = returns[:t]  (expanding)
        - mu_annual = model(train)
        - sigma_annual = trailing sample std (vol_lookback) annualized
        - convert mu to monthly-log space (vol-drag corrected)
        - record realized log return at t+step and standardized residual

    Parameters:
        monthly_log_returns (pd.DataFrame): cols=tickers, index=month-end.
        model (ModelFn): train_returns -> annual arithmetic E[R] per ticker.
        min_train_months (int): minimum history before first prediction.
        step_months (int): forecast horizon / step (1 = next month).
        vol_lookback_months (int): window for sigma estimate.

    Returns:
        WalkForwardResult.
    """
    R = monthly_log_returns.sort_index()
    dates = R.index
    n = len(dates)

    pred_rows: dict[pd.Timestamp, pd.Series] = {}
    real_rows: dict[pd.Timestamp, pd.Series] = {}
    sig_rows: dict[pd.Timestamp, pd.Series] = {}
    resid_chunks: list[pd.Series] = []

    t = min_train_months
    while t + step_months <= n:
        rebal_date = dates[t - 1]
        train = R.iloc[:t]

        # Only assets with enough history at this point
        valid = train.columns[train.count() >= min_train_months]
        if len(valid) < 2:
            t += step_months
            continue
        train_v = train[valid]

        try:
            mu_annual = model(train_v).reindex(valid).dropna()
        except Exception as e:
            logger.warning(f"Model failed at {rebal_date:%Y-%m}: {e}")
            t += step_months
            continue
        if mu_annual.empty:
            t += step_months
            continue

        # Trailing annualized sigma
        recent = train_v.iloc[-vol_lookback_months:]
        sigma_annual = recent.std(ddof=1) * np.sqrt(12.0)
        sigma_annual = sigma_annual.reindex(mu_annual.index)

        mu_monthly_log = _arith_annual_to_log_monthly(mu_annual, sigma_annual)
        sigma_monthly = sigma_annual / np.sqrt(12.0)

        # Realized next-step log return (sum of intervening months if step>1)
        future = R.iloc[t:t + step_months][mu_annual.index]
        realized = future.sum(axis=0, min_count=1)

        pred_rows[rebal_date] = mu_monthly_log
        real_rows[rebal_date] = realized
        sig_rows[rebal_date] = sigma_monthly

        z = ((realized - mu_monthly_log) / sigma_monthly).replace([np.inf, -np.inf], np.nan).dropna()
        if not z.empty:
            resid_chunks.append(z)

        t += step_months

    predicted = pd.DataFrame(pred_rows).T.sort_index()
    realized_df = pd.DataFrame(real_rows).T.sort_index()
    sigma_df = pd.DataFrame(sig_rows).T.sort_index()
    residuals = pd.concat(resid_chunks, ignore_index=True) if resid_chunks else pd.Series(dtype=float)

    logger.info(
        f"Walk-forward complete: {predicted.shape[0]} rebalance dates, "
        f"{residuals.size} pooled residuals"
    )
    return WalkForwardResult(predicted, realized_df, sigma_df, residuals)
