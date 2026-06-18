"""
Expected-Return Model Registry (for walk-forward bake-off)
==========================================================
Each model maps a panel of monthly LOG returns (training window) to a Series
of ANNUAL ARITHMETIC expected returns per ticker — the contract expected by
backend.eval.walkforward.run_walk_forward.

Phase 0 ships the baselines (historical mean, CAPM). Phase 1 adds the
Black-Litterman variants and the trailing+BL blend.

Reference: docs/OPTIMIZATION_WALKTHROUGH.md.
"""

import logging
from functools import partial

import numpy as np
import pandas as pd

from backend.config import MVO_RISK_FREE_RATE, BENCHMARK_TICKER

# Production-validated models live in the engine; research imports them
# (dependency direction: engine ← eval). Re-exported here for back-compat.
from backend.engine.quant_models import (  # noqa: F401
    log_monthly_to_annual_arith as _log_monthly_to_annual_arith,
    mean_historical,
    ewma_historical,
    black_litterman,
    blend_trailing_bl,
    market_caps_for as _market_caps,
)

logger = logging.getLogger(__name__)


def capm(
    train_log_returns: pd.DataFrame,
    benchmark: str = BENCHMARK_TICKER,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    CAPM expected returns: E[Ri] = Rf + βi * (E[Rm] - Rf).

    β estimated by OLS of each asset's monthly log returns on the market
    proxy's monthly log returns. E[Rm] from the proxy's trailing mean.
    Falls back to the equal-weighted portfolio as the market if the
    benchmark column is absent.

    Returns annual arithmetic expected returns.
    """
    R = train_log_returns
    if benchmark in R.columns:
        mkt = R[benchmark]
    else:
        mkt = R.mean(axis=1)  # equal-weighted proxy
        logger.debug("CAPM: benchmark absent, using equal-weighted market proxy")

    mkt_var = mkt.var(ddof=1)
    if not np.isfinite(mkt_var) or mkt_var <= 0:
        return mean_historical(R)

    # Market expected return (annual arithmetic) and excess premium (annual)
    rm_annual = float(np.exp(mkt.mean() * 12.0) - 1.0)
    premium = rm_annual - risk_free_annual

    betas = {}
    for col in R.columns:
        pair = pd.concat([R[col], mkt], axis=1).dropna()
        if len(pair) < 12:
            continue
        cov = pair.iloc[:, 0].cov(pair.iloc[:, 1])
        betas[col] = cov / mkt_var

    beta_s = pd.Series(betas)
    expected = risk_free_annual + beta_s * premium
    return expected


# (black_litterman / blend_trailing_bl / _market_caps now live in
#  backend.engine.quant_models and are imported above.)


# Convenience registries for the runners
def get_baseline_models() -> dict:
    """Return the Phase 0 baseline model callables keyed by name."""
    return {
        "hist_mean": mean_historical,
        "ewma_24m": partial(ewma_historical, halflife=24),
        "capm": capm,
    }


def james_stein_mean(train_log_returns: pd.DataFrame) -> pd.Series:
    """
    James-Stein shrinkage of the sample mean toward the grand (cross-sectional)
    mean. Reduces estimation error in the means — the classic fix for MVO's
    error-maximization. Returns annual arithmetic.
    """
    R = train_log_returns
    mu = R.mean()                      # monthly log mean per asset
    grand = mu.mean()
    T = R.count().mean()
    # average sampling variance of the mean
    sigma2 = (R.var().mean() / max(T, 1.0))
    disp = float(((mu - grand) ** 2).sum())
    n = len(mu)
    if disp <= 0 or n <= 3:
        phi = 0.0
    else:
        phi = 1.0 - ((n - 3) * sigma2) / disp
        phi = float(np.clip(phi, 0.0, 1.0))
    shrunk = grand + phi * (mu - grand)
    return _log_monthly_to_annual_arith(shrunk)


def cross_sectional_momentum(train_log_returns: pd.DataFrame, lookback: int = 12, skip: int = 1) -> pd.Series:
    """
    Expected return = annualized 12-1 momentum (cumulative log return over the
    last `lookback` months excluding the most recent `skip`). A pure trend signal.
    """
    R = train_log_returns
    window = R.iloc[-(lookback + skip):-skip] if skip > 0 else R.iloc[-lookback:]
    mom_log = window.sum()             # cumulative log return over window
    # annualize the per-month average of that window
    return _log_monthly_to_annual_arith(mom_log / max(len(window), 1))


def bl_momentum(
    train_log_returns: pd.DataFrame,
    tilt: float = 0.03,
    benchmark: str = BENCHMARK_TICKER,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Black-Litterman equilibrium tilted by a cross-sectional momentum view:
        E[R] = BL_equilibrium + tilt * z(momentum)
    where z is the cross-sectionally standardized 12-1 momentum. A lightweight
    stand-in for BL absolute views. Returns annual arithmetic.
    """
    bl = black_litterman(train_log_returns, benchmark, risk_free_annual)
    mom = cross_sectional_momentum(train_log_returns)
    mom = mom.reindex(bl.index)
    z = (mom - mom.mean()) / (mom.std(ddof=1) if mom.std(ddof=1) > 0 else 1.0)
    return bl + tilt * z


def build_factor_returns(
    period_years: int = 10,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.DataFrame:
    """
    Construct monthly GBP factor return series from the universe's own factor
    ETFs (no external data dependency):
        MKT = benchmark excess return
        SMB = global small-cap  − benchmark
        HML = global value      − benchmark
        MOM = global momentum   − benchmark
        QMJ = global quality    − benchmark
    Long-short ETF spreads are crude factor mimics but fully investable & GBP-native.

    Returns:
        pd.DataFrame: monthly factor returns (columns = factor names).
    """
    from backend.data.returns import build_monthly_gbp_log_returns
    from backend.engine.asset_universe import get_ticker_map

    classes = ["global_equity", "global_small_cap", "global_value",
               "global_momentum", "global_quality"]
    tmap = get_ticker_map(classes)
    mkt_t = BENCHMARK_TICKER
    tickers = sorted(set(tmap.values()) | {mkt_t})

    R = build_monthly_gbp_log_returns(tickers, period_years, min_obs=24)
    if R is None or mkt_t not in R.columns:
        logger.warning("Could not build factor returns (benchmark missing)")
        return pd.DataFrame()

    rf_m = np.log1p(risk_free_annual) / 12.0
    factors: dict[str, pd.Series] = {"MKT": R[mkt_t] - rf_m}
    spread_map = {
        "SMB": tmap.get("global_small_cap"),
        "HML": tmap.get("global_value"),
        "MOM": tmap.get("global_momentum"),
        "QMJ": tmap.get("global_quality"),
    }
    for fname, tk in spread_map.items():
        if tk and tk in R.columns:
            factors[fname] = R[tk] - R[mkt_t]

    F = pd.DataFrame(factors).dropna(how="all")
    logger.info(f"Factor returns built: {list(F.columns)}, {F.shape[0]} months")
    return F


def factor_model(
    train_log_returns: pd.DataFrame,
    factor_returns: pd.DataFrame,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Multi-factor (APT/Fama-French-style) expected returns:
        E[Ri] = Rf + Σ_k β_ik · λ_k
    β_ik from time-series OLS of asset excess returns on factor returns (train
    window only); λ_k = in-sample mean factor return. Returns annual arithmetic.
    """
    R = train_log_returns
    F = factor_returns.reindex(R.index).dropna(how="any")
    if len(F) < 24:
        return mean_historical(R)

    rf_m = np.log1p(risk_free_annual) / 12.0
    premia = F.mean().values                       # monthly log factor premia
    design = np.column_stack([np.ones(len(F)), F.values])

    out = {}
    for col in R.columns:
        y = (R[col] - rf_m).reindex(F.index)
        ok = y.notna().values
        if ok.sum() < 24:
            continue
        try:
            beta, *_ = np.linalg.lstsq(design[ok], y.values[ok], rcond=None)
        except Exception:
            continue
        exp_excess_m = float(beta[1:] @ premia)    # exclude intercept (alpha)
        exp_m_log = rf_m + exp_excess_m
        out[col] = float(np.exp(exp_m_log * 12.0) - 1.0)

    return pd.Series(out) if out else mean_historical(R)


def get_phase1_models() -> dict:
    """Core Phase 1 candidates (CAPM bar + BL + one blend) — used by run_phase1_bl."""
    return {
        "capm": capm,
        "black_litterman": black_litterman,
        "blend_50_50": partial(blend_trailing_bl, w_trailing=0.5),
    }


def get_phase1_full_models() -> dict:
    """Wider Phase 1 bake-off: more methods + a blend-weight sweep."""
    return {
        "capm": capm,
        "hist_mean": mean_historical,
        "ewma_24m": partial(ewma_historical, halflife=24),
        "james_stein": james_stein_mean,
        "xs_momentum": cross_sectional_momentum,
        "black_litterman": black_litterman,
        "bl_momentum": bl_momentum,
        "blend_25bl": partial(blend_trailing_bl, w_trailing=0.25),
        "blend_50_50": partial(blend_trailing_bl, w_trailing=0.50),
        "blend_75tr": partial(blend_trailing_bl, w_trailing=0.75),
    }
