"""
Evaluation Metrics — Expected-Return Forecast Quality & Residual Diagnostics
=============================================================================
Implements the three-pronged acceptance criteria from the Phase 1 gate:

  1. LEVEL / BIAS      — is the mean forecast unbiased?      (mean standardized residual)
  2. RANKING           — does it rank assets correctly?      (cross-sectional Spearman IC)
  3. TAIL FIT (QQ)     — are residuals Student-t shaped?     (t-fit ν + KS p-value, QQ R²)
  4. ULTIMATE          — does it make money out-of-sample?   (realized portfolio Sharpe)

Reference: docs/OPTIMIZATION_WALKTHROUGH.md (Phase 1).
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# =============================================================================
# RESIDUALS & DISTRIBUTION FIT
# =============================================================================

@dataclass(frozen=True)
class TailFitResult:
    """Result of fitting a Student-t to pooled standardized residuals."""
    nu: float               # degrees of freedom (fat-tail parameter)
    loc: float
    scale: float
    ks_stat_t: float        # KS statistic vs fitted Student-t (lower = better)
    ks_p_t: float           # KS p-value vs fitted Student-t (higher = better fit)
    ks_p_normal: float      # KS p-value vs standard normal (for comparison)
    jarque_bera_p: float    # JB normality p-value (low = reject normality)
    qq_r2_t: float          # R^2 of QQ points vs Student-t (closer to 1 = better)
    n: int


def standardized_residuals(
    realized_log: pd.Series,
    mu_pred_log: pd.Series,
    sigma_pred: pd.Series,
) -> pd.Series:
    """
    z = (realized_log - mu_pred_log) / sigma_pred, aligned on a common index.

    All three inputs must already be in the SAME (monthly log) units.
    """
    idx = realized_log.index.intersection(mu_pred_log.index).intersection(sigma_pred.index)
    z = (realized_log.reindex(idx) - mu_pred_log.reindex(idx)) / sigma_pred.reindex(idx)
    return z.replace([np.inf, -np.inf], np.nan).dropna()


def fit_student_t(residuals: np.ndarray) -> TailFitResult:
    """
    Fit a Student-t to pooled standardized residuals and assess goodness of fit.

    Parameters:
        residuals (np.ndarray): Pooled standardized residuals (across assets/time).

    Returns:
        TailFitResult: ν, fit params, KS/JB p-values, QQ R².
    """
    r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < 20:
        logger.warning(f"Only {n} residuals — tail fit unreliable")

    # MLE fit of Student-t (df, loc, scale)
    nu, loc, scale = stats.t.fit(r)

    # KS vs fitted Student-t
    ks_t = stats.kstest(r, "t", args=(nu, loc, scale))
    # KS vs standard normal (z is already standardized)
    ks_n = stats.kstest(r, "norm", args=(np.mean(r), np.std(r, ddof=1)))
    # Jarque-Bera normality
    try:
        jb = stats.jarque_bera(r)
        jb_p = float(jb.pvalue)
    except Exception:
        jb_p = float("nan")

    # QQ R^2 vs fitted Student-t
    qq_r2 = _qq_r2(r, dist=stats.t, dist_args=(nu, loc, scale))

    return TailFitResult(
        nu=float(nu), loc=float(loc), scale=float(scale),
        ks_stat_t=float(ks_t.statistic), ks_p_t=float(ks_t.pvalue),
        ks_p_normal=float(ks_n.pvalue), jarque_bera_p=jb_p,
        qq_r2_t=float(qq_r2), n=int(n),
    )


def residual_ttest(residuals: np.ndarray) -> dict:
    """
    One-sample t-test of pooled standardized residuals against H0: mean = 0.

    A forecast is UNBIASED ("accepted") if we FAIL to reject H0 (p > 0.05):
    the model's predicted level is not systematically off.

    Returns:
        dict: {t_stat, p_value, mean, n, unbiased(bool)}.
    """
    r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 3:
        return {"t_stat": float("nan"), "p_value": float("nan"),
                "mean": float("nan"), "n": int(r.size), "unbiased": False}
    res = stats.ttest_1samp(r, popmean=0.0)
    return {
        "t_stat": float(res.statistic), "p_value": float(res.pvalue),
        "mean": float(np.mean(r)), "n": int(r.size),
        "unbiased": bool(res.pvalue > 0.05),
    }


def _qq_r2(sample: np.ndarray, dist, dist_args: tuple) -> float:
    """R^2 between empirical quantiles and a reference distribution's quantiles."""
    s = np.sort(sample[np.isfinite(sample)])
    n = s.size
    if n < 3:
        return float("nan")
    probs = (np.arange(1, n + 1) - 0.5) / n
    theo = dist.ppf(probs, *dist_args)
    mask = np.isfinite(theo)
    if mask.sum() < 3:
        return float("nan")
    r = np.corrcoef(theo[mask], s[mask])[0, 1]
    return r * r


def qq_points(sample: np.ndarray, dist: str = "t", dist_args: Optional[tuple] = None) -> dict:
    """
    Compute QQ-plot coordinates (theoretical vs sample quantiles).

    Parameters:
        sample (np.ndarray): Standardized residuals.
        dist (str): "t" or "norm".
        dist_args (tuple, optional): Distribution params; if None, fitted.

    Returns:
        dict: {"theoretical": list, "sample": list, "dist": str, "args": tuple}.
    """
    s = np.sort(np.asarray(sample, dtype=float))
    s = s[np.isfinite(s)]
    n = s.size
    probs = (np.arange(1, n + 1) - 0.5) / n
    d = stats.t if dist == "t" else stats.norm
    if dist_args is None:
        dist_args = d.fit(s)
    theo = d.ppf(probs, *dist_args)
    return {"theoretical": theo.tolist(), "sample": s.tolist(), "dist": dist, "args": tuple(dist_args)}


# =============================================================================
# FORECAST QUALITY (LEVEL + RANKING)
# =============================================================================

@dataclass(frozen=True)
class ForecastMetrics:
    """Cross-sectional / time-series forecast quality metrics."""
    bias: float             # mean(realized - predicted); ~0 desired
    mae: float
    rmse: float
    mean_std_residual: float  # mean standardized residual; ~0 desired (unbiased)
    rank_ic: float          # mean cross-sectional Spearman corr(pred, realized)
    rank_ic_t: float        # t-stat of the per-period rank ICs
    n_periods: int


def forecast_metrics(
    predicted: pd.DataFrame,
    realized: pd.DataFrame,
    sigma: Optional[pd.DataFrame] = None,
) -> ForecastMetrics:
    """
    Compute forecast quality metrics from aligned predicted vs realized panels.

    Parameters:
        predicted (pd.DataFrame): index=rebalance date, columns=tickers, values=predicted return.
        realized (pd.DataFrame): same shape; realized next-period return.
        sigma (pd.DataFrame, optional): predicted vol for standardized residual.

    Returns:
        ForecastMetrics.
    """
    common_cols = predicted.columns.intersection(realized.columns)
    common_idx = predicted.index.intersection(realized.index)
    pred = predicted.loc[common_idx, common_cols]
    real = realized.loc[common_idx, common_cols]

    err = real - pred
    flat = err.values[np.isfinite(err.values)]
    bias = float(np.nanmean(flat)) if flat.size else float("nan")
    mae = float(np.nanmean(np.abs(flat))) if flat.size else float("nan")
    rmse = float(np.sqrt(np.nanmean(flat ** 2))) if flat.size else float("nan")

    # Standardized residual mean
    if sigma is not None:
        sig = sigma.loc[common_idx, common_cols]
        z = (real - pred) / sig
        zflat = z.values[np.isfinite(z.values)]
        mean_std_res = float(np.nanmean(zflat)) if zflat.size else float("nan")
    else:
        mean_std_res = float("nan")

    # Cross-sectional Spearman rank IC per period
    ics = []
    for dt in common_idx:
        p = pred.loc[dt]
        a = real.loc[dt]
        ok = p.notna() & a.notna()
        if ok.sum() >= 3:
            ic, _ = stats.spearmanr(p[ok], a[ok])
            if np.isfinite(ic):
                ics.append(ic)
    ics = np.array(ics)
    rank_ic = float(np.mean(ics)) if ics.size else float("nan")
    rank_ic_t = (
        float(np.mean(ics) / (np.std(ics, ddof=1) / np.sqrt(ics.size)))
        if ics.size > 1 and np.std(ics, ddof=1) > 0 else float("nan")
    )

    return ForecastMetrics(
        bias=bias, mae=mae, rmse=rmse, mean_std_residual=mean_std_res,
        rank_ic=rank_ic, rank_ic_t=rank_ic_t, n_periods=int(common_idx.size),
    )


# =============================================================================
# REALIZED PORTFOLIO PERFORMANCE (ULTIMATE TEST)
# =============================================================================

def realized_sharpe(
    portfolio_log_returns: pd.Series,
    risk_free_annual: float = 0.04,
    periods_per_year: int = 12,
) -> dict:
    """
    Annualized realized Sharpe and summary stats from a series of periodic
    portfolio log returns.

    Parameters:
        portfolio_log_returns (pd.Series): Periodic (monthly) portfolio log returns.
        risk_free_annual (float): Annual risk-free rate.
        periods_per_year (int): 12 for monthly.

    Returns:
        dict: {cagr, vol, sharpe, max_drawdown, n_periods}.
    """
    r = portfolio_log_returns.dropna()
    if r.empty:
        return {"cagr": 0.0, "vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "n_periods": 0}

    mean_log = r.mean()
    cagr = float(np.exp(mean_log * periods_per_year) - 1.0)
    vol = float(r.std(ddof=1) * np.sqrt(periods_per_year))
    sharpe = float((cagr - risk_free_annual) / vol) if vol > 0 else 0.0

    # Max drawdown on cumulative simple value
    cum = np.exp(r.cumsum())
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    max_dd = float(dd.min())

    return {
        "cagr": round(cagr, 4), "vol": round(vol, 4), "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4), "n_periods": int(r.size),
    }
