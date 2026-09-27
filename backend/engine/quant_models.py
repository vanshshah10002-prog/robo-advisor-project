"""
Quant Models — Production Return/Risk Estimators (validated in Phases 1–2)
===========================================================================
Single source of truth for the estimators the engine runs in production.
The research harness (backend/eval/*) IMPORTS FROM HERE — never the reverse —
so the dependency direction is engine ← eval (research depends on production).

Locked decisions (docs/OPTIMIZATION_WALKTHROUGH.md):
    Expected returns : blend_trailing_bl (50% trailing mean, 50% BL equilibrium)
    Covariance       : ewma_lw_cov (50% EWMA halflife-12, 50% Ledoit-Wolf)
    Regime           : volatility_regime (vol z-score + drawdown, hysteresis)

All functions take MONTHLY LOG returns and output ANNUAL arithmetic E[R] /
ANNUAL covariance.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import (
    MVO_RISK_FREE_RATE,
    BENCHMARK_TICKER,
    REGIME_VOL_ENTER_Z,
    REGIME_VOL_EXIT_Z,
)

logger = logging.getLogger(__name__)

_ANNUALIZE = 12  # monthly -> annual

# Default AUM proxies (GBP mm) by asset-class keyword — used only when the
# registry lacks fund_size_gbp_mm. Varied across classes so cap weights are
# NOT near-uniform (the root cause of the old BL "dilution" collapse).
_AUM_DEFAULTS = {
    "equity": 15000, "bond": 3000, "gilt": 3000, "treasury": 3000,
    "inflation": 2000, "commodit": 500, "gold": 800, "silver": 200,
    "reit": 500, "real_estate": 500, "infrastructure": 300,
    "cash": 200, "value": 1000, "momentum": 1000, "quality": 1000,
}


# =============================================================================
# RETURN MODELS
# =============================================================================

def log_monthly_to_annual_geometric(mean_monthly_log: pd.Series) -> pd.Series:
    """
    Mean monthly log return → annual GEOMETRIC (compound) return, exp(12μ) − 1.
    This is a growth rate, not the arithmetic mean mean-variance needs; see
    `annual_arithmetic_mean`.
    """
    return np.exp(mean_monthly_log * 12.0) - 1.0


# Legacy name kept for the research scripts; it has always been geometric.
log_monthly_to_annual_arith = log_monthly_to_annual_geometric


def annual_arithmetic_mean(monthly_log_returns: pd.DataFrame) -> pd.Series:
    """
    Annual arithmetic expected return from monthly log returns (lognormal):
        E[1 + R_annual] = exp(12μ + 12σ²/2)
    i.e. the geometric rate plus roughly σ²/2 — the input mean-variance
    optimisation expects. Using the geometric rate instead understates
    volatile assets by about σ²/2 (≈1.3%/yr at 16% vol) relative to cash.
    """
    mu = monthly_log_returns.mean()
    var = monthly_log_returns.var()
    return np.exp(12.0 * mu + 6.0 * var) - 1.0


def mean_historical(train_log_returns: pd.DataFrame) -> pd.Series:
    """Trailing historical mean (annual arithmetic)."""
    return annual_arithmetic_mean(train_log_returns)


def ewma_historical(train_log_returns: pd.DataFrame, halflife: int = 24) -> pd.Series:
    """Exponentially-weighted trailing mean (annual geometric; research only)."""
    ewm_mean = train_log_returns.ewm(halflife=halflife, min_periods=12).mean().iloc[-1]
    return log_monthly_to_annual_geometric(ewm_mean)


def market_caps_for(tickers: list[str]) -> pd.Series:
    """
    Float-adjusted market-cap proxy (GBP mm) per ticker from the registry
    `fund_size_gbp_mm`, falling back to asset-class AUM defaults.
    """
    from backend.engine.asset_universe import get_etf_by_ticker

    caps = {}
    for t in tickers:
        etf = get_etf_by_ticker(t) or {}
        fs = etf.get("fund_size_gbp_mm", 0) or 0
        if fs > 0:
            caps[t] = float(fs)
            continue
        ac = (etf.get("asset_class") or "").lower()
        proxy = next((v for k, v in _AUM_DEFAULTS.items() if k in ac), 5000)
        caps[t] = float(proxy)
    return pd.Series(caps)


def black_litterman(
    train_log_returns: pd.DataFrame,
    benchmark: str = BENCHMARK_TICKER,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Black-Litterman equilibrium prior (no views):  E[R] = Rf + λ·Σ·w_mkt.

    Calibrated to avoid the dilution collapse:
        - w_mkt: cap weights from registry fund sizes (varied defaults)
        - Σ: annualized covariance from monthly log returns
        - λ = (E[Rm] − Rf) / σ²_m on the cap-weighted market portfolio, so λ
          exactly reprices the market to its historical mean.

    NOTE: `risk_free_annual` must be the PRICING risk-free rate (gilt-level),
    not the client hurdle — BL output is rf + premium, so an inflated rf
    mechanically inflates every expected return.
    """
    R = train_log_returns
    tickers = list(R.columns)

    caps = market_caps_for(tickers).reindex(tickers).dropna()
    tickers = list(caps.index)
    if len(tickers) < 2:
        return mean_historical(R)

    cov = (R[tickers].cov() * _ANNUALIZE)
    w = (caps / caps.sum()).reindex(tickers)

    port_monthly = (R[tickers] * w).sum(axis=1, min_count=1)
    rm_annual = float(np.exp(port_monthly.mean() * 12.0) - 1.0)

    var_m = float(w.values @ cov.values @ w.values)
    if not np.isfinite(var_m) or var_m <= 0:
        return mean_historical(R)

    # Market price of risk, floored/capped to an economically sane band.
    # A trailing market mean below rf would imply NEGATIVE risk aversion
    # (assets priced to lose vs cash) — an artifact of the sample window, not
    # equilibrium. He & Litterman (1999) used a fixed λ=2.5; we allow the data
    # to speak within [1, 6].
    lam_raw = (rm_annual - risk_free_annual) / var_m
    lam = float(np.clip(lam_raw, 1.0, 6.0))
    if lam != lam_raw:
        logger.warning(f"BL lambda clamped {lam_raw:.2f} → {lam:.2f} "
                       f"(trailing E[Rm]={rm_annual:.2%} vs rf={risk_free_annual:.2%})")
    pi = lam * (cov.values @ w.values)
    expected = risk_free_annual + pd.Series(pi, index=tickers)

    logger.debug(f"BL: lambda={lam:.2f}, E[Rm]={rm_annual:.3f}, "
                 f"premia=[{pi.min():.3f},{pi.max():.3f}]")
    return expected


def blend_trailing_bl(
    train_log_returns: pd.DataFrame,
    w_trailing: float = 0.5,
    benchmark: str = BENCHMARK_TICKER,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    PRODUCTION expected-return model (Phase 1 locked):
        E[R] = w·trailing_mean + (1−w)·BL_equilibrium
    """
    hist = mean_historical(train_log_returns)
    bl = black_litterman(train_log_returns, benchmark, risk_free_annual)
    idx = hist.index.union(bl.index)
    return (w_trailing * hist.reindex(idx) + (1 - w_trailing) * bl.reindex(idx)).dropna()


def reference_weights(tickers: list[str], asset_class_of: dict[str, str]) -> pd.Series:
    """
    Neutral weights for the prior from REFERENCE_MARKET_WEIGHTS, renormalised
    over the asset classes present. Tickers outside the reference get 0 (they
    are still priced through their covariance with the reference portfolio).
    If none of the tickers is in the reference, equal weights are used.
    """
    from backend.config import REFERENCE_MARKET_WEIGHTS

    w = pd.Series({t: REFERENCE_MARKET_WEIGHTS.get(asset_class_of.get(t, ""), 0.0) for t in tickers})
    if w.sum() <= 0:
        return pd.Series(1.0 / len(tickers), index=tickers)
    return w / w.sum()


def equilibrium_returns(
    cov_annual: pd.DataFrame,
    w_ref: pd.Series,
    risk_free_annual: float,
    risk_aversion: Optional[float] = None,
) -> pd.Series:
    """
    Reverse-optimised equilibrium returns: E[R] = rf + λ·Σ·w_ref (He & Litterman).
    With the same λ in a quadratic-utility optimiser and no constraints, the
    optimal portfolio is w_ref itself.
    """
    from backend.config import BL_RISK_AVERSION

    lam = BL_RISK_AVERSION if risk_aversion is None else risk_aversion
    cols = list(cov_annual.columns)
    w = w_ref.reindex(cols).fillna(0.0).values
    pi = lam * (cov_annual.values @ w)
    return risk_free_annual + pd.Series(pi, index=cols)


def production_expected_returns(
    monthly_log_returns: pd.DataFrame,
    cov_annual: pd.DataFrame,
    asset_class_of: dict[str, str],
    expense_ratios: Optional[dict[str, float]] = None,
    risk_free_annual: float = MVO_RISK_FREE_RATE,
    w_trailing: Optional[float] = None,
) -> tuple[pd.Series, dict]:
    """
    PRODUCTION expected returns (remediation plan §2.4):

        E[R] = w_eff · trailing + (1 − w_eff) · (equilibrium − TER)

    - trailing: ARITHMETIC annual mean over the COMMON window (every asset
      measured over the same months); ETF prices are already net of fees, so
      no fee is deducted from it.
    - equilibrium: rf + λ·Σ·w_ref on the reference market portfolio, less TER.
    - w_eff = w_trailing × min(1, common months / TRAILING_FULL_WEIGHT_MONTHS):
      a shorter common history earns less trust.

    Returns:
        (mu, diagnostics)
    """
    from backend.config import EXPECTED_RETURN_TRAILING_WEIGHT, TRAILING_FULL_WEIGHT_MONTHS

    tickers = list(cov_annual.columns)
    R = monthly_log_returns[tickers]
    common = R.dropna(how="any")
    n_common = len(common)

    w_base = EXPECTED_RETURN_TRAILING_WEIGHT if w_trailing is None else w_trailing
    w_eff = w_base * min(1.0, n_common / float(TRAILING_FULL_WEIGHT_MONTHS)) if n_common >= 12 else 0.0

    w_ref = reference_weights(tickers, asset_class_of)
    prior = equilibrium_returns(cov_annual, w_ref, risk_free_annual)
    fees = pd.Series({t: (expense_ratios or {}).get(t, 0.0) for t in tickers})
    prior_net = prior - fees

    if w_eff > 0:
        trailing = annual_arithmetic_mean(common)
        mu = w_eff * trailing + (1.0 - w_eff) * prior_net
    else:
        trailing = pd.Series(np.nan, index=tickers)
        mu = prior_net

    diagnostics = {
        "common_months": n_common,
        "trailing_weight": round(w_eff, 4),
        "reference_weights": {t: round(float(v), 4) for t, v in w_ref.items()},
        "prior": prior.round(4).to_dict(),
        "trailing": trailing.round(4).to_dict(),
    }
    return mu, diagnostics


# =============================================================================
# COVARIANCE MODELS
# =============================================================================

def _clean(returns: pd.DataFrame) -> pd.DataFrame:
    """Complete-case rows over the window (drops ragged-history leading NaNs)."""
    return returns.dropna(how="any")


def sample_cov(returns: pd.DataFrame) -> pd.DataFrame:
    R = _clean(returns)
    return R.cov() * _ANNUALIZE


def ledoit_wolf_cov(returns: pd.DataFrame) -> pd.DataFrame:
    R = _clean(returns)
    try:
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf().fit(R.values)
        return pd.DataFrame(lw.covariance_ * _ANNUALIZE, index=R.columns, columns=R.columns)
    except Exception as e:
        logger.warning(f"LedoitWolf failed ({e}); sample cov")
        return sample_cov(returns)


def ewma_cov(returns: pd.DataFrame, halflife: int = 12) -> pd.DataFrame:
    """Exponentially-weighted covariance (annualized). halflife in months."""
    R = _clean(returns)
    n = len(R)
    if n < 12:
        return sample_cov(returns)
    decay = 1.0 - np.exp(np.log(0.5) / halflife)
    w = (1.0 - decay) ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    X = R.values
    mu = np.average(X, axis=0, weights=w)
    Xc = X - mu
    cov = Xc.T @ (Xc * w[:, None])
    return pd.DataFrame(cov * _ANNUALIZE, index=R.columns, columns=R.columns)


def _ewma_var_own_history(series: pd.Series, halflife: int = 12) -> float:
    """Annualized EWMA variance of one column over its OWN non-NaN history."""
    x = series.dropna().values
    n = len(x)
    if n < 6:
        return float("nan")
    decay = 1.0 - np.exp(np.log(0.5) / halflife)
    w = (1.0 - decay) ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    mu = float(np.average(x, weights=w))
    return float(np.average((x - mu) ** 2, weights=w) * _ANNUALIZE)


def ewma_lw_cov(returns: pd.DataFrame, halflife: int = 12) -> pd.DataFrame:
    """
    PRODUCTION covariance (Phase 2 locked; variance re-anchor June 2026):
    correlations from the 50/50 EWMA + Ledoit-Wolf blend (complete-case),
    variances re-anchored to each asset's OWN full history.

    Why the re-anchor: with a WIDE universe (~30 assets) the complete-case
    window shrinks to the youngest fund's history (~36m) and LW shrinkage
    toward its scaled-identity target pulls every variance toward the
    cross-asset MEAN — the 0.5%-vol cash sleeve was being assigned ~14% vol,
    making the constrained min-variance portfolio impossible (σ_min jumped
    from ~3% to ~8.6%). Re-anchoring D in  Σ = D·Corr·D  to per-asset EWMA
    variances over each column's own history restores true asset risk levels
    while keeping the validated correlation structure. PSD is preserved
    (congruence transform of a PSD matrix).
    """
    e = ewma_cov(returns, halflife)
    lw = ledoit_wolf_cov(returns)
    cols = e.columns.intersection(lw.columns)
    blend = 0.5 * e.loc[cols, cols] + 0.5 * lw.loc[cols, cols]

    # Correlation from the blend
    d_blend = np.sqrt(np.diag(blend.values))
    d_blend[d_blend <= 0] = np.nan
    corr = blend.values / np.outer(d_blend, d_blend)
    np.fill_diagonal(corr, 1.0)
    corr = np.clip(corr, -1.0, 1.0)

    # Per-asset vols from each column's own history (not the joint window)
    d_own = np.array([
        np.sqrt(_ewma_var_own_history(returns[c], halflife)) for c in cols
    ])
    own_ok = np.isfinite(d_own) & (d_own > 0)
    d_final = np.where(own_ok, d_own, d_blend)

    cov = corr * np.outer(d_final, d_final)
    return pd.DataFrame(cov, index=cols, columns=cols)


# =============================================================================
# GARCH VOLATILITY DYNAMICS
# =============================================================================

def fit_garch_t(returns: pd.Series) -> dict:
    """
    Fit a GARCH(1,1) with Student-t innovations to a (log) return series and
    report honest diagnostics — including whether the data actually supports
    volatility clustering at this frequency.

    Empirical note (VWRL, 10y): clustering is overwhelming at DAILY frequency
    (α+β≈0.96, p<0.001) but weak at MONTHLY (β insignificant, persistence
    ≈0.35 — consistent with the daily process aggregated: 0.96^21≈0.42).
    `clustering_significant` tells the caller whether GARCH-mode simulation is
    statistically justified at the fitted frequency.

    Parameters:
        returns (pd.Series): log returns (any frequency).

    Returns:
        dict: {omega, alpha, beta, nu, persistence, uncond_var,
               p_alpha, p_beta, clustering_significant, n}
        Variance quantities are in the SAME periodicity as the input returns.
    """
    from arch import arch_model

    r = returns.dropna()
    scaled = r * 100.0  # arch is numerically happier in % units
    am = arch_model(scaled, vol="Garch", p=1, q=1, dist="t", mean="Constant")
    res = am.fit(disp="off")
    p, pv = res.params, res.pvalues

    omega_pct, alpha, beta = float(p["omega"]), float(p["alpha[1]"]), float(p["beta[1]"])
    nu = float(p["nu"])
    persistence = alpha + beta
    # back to raw return units: omega scales by 1/100^2
    omega = omega_pct / 10000.0
    uncond_var = omega / max(1e-12, 1.0 - persistence) if persistence < 1 else float("nan")

    clustering_significant = bool(pv["alpha[1]"] < 0.05 and persistence > 0.1)
    return {
        "omega": omega, "alpha": alpha, "beta": beta, "nu": nu,
        "persistence": persistence, "uncond_var": uncond_var,
        "p_alpha": float(pv["alpha[1]"]), "p_beta": float(pv["beta[1]"]),
        "clustering_significant": clustering_significant, "n": int(len(r)),
    }


# =============================================================================
# REGIME DETECTION
# =============================================================================

def rolling_avg_correlation(
    returns: pd.DataFrame,
    window: int = 6,
    min_assets: int = 3,
) -> pd.Series:
    """Rolling average pairwise |correlation| (legacy diagnostic)."""
    out = {}
    idx = returns.index
    for i in range(window, len(idx) + 1):
        sub = returns.iloc[i - window:i].dropna(axis=1, how="any")
        if sub.shape[1] < min_assets:
            continue
        corr = sub.corr().values
        n = corr.shape[0]
        mask = ~np.eye(n, dtype=bool)
        out[idx[i - 1]] = float(np.nanmean(np.abs(corr[mask])))
    return pd.Series(out).sort_index()


def volatility_regime(
    returns: pd.DataFrame,
    market: Optional[pd.Series] = None,
    short_window: int = 3,
    long_window: int = 36,
    z_threshold: float = REGIME_VOL_ENTER_Z,
    exit_z: float = REGIME_VOL_EXIT_Z,
) -> pd.DataFrame:
    """
    PRODUCTION regime detector (Phase 2 locked, with hysteresis).

    Signal = z-score of short-term realized vol vs its trailing long-run level.
    State machine: ENTER crisis when vol_z > z_threshold; REMAIN in crisis
    until vol_z < exit_z (prevents monthly whipsaw around the trigger).

    Returns:
        pd.DataFrame: columns [short_vol, vol_z, drawdown, crisis(bool)].
    """
    if market is None:
        market = returns.mean(axis=1)
    market = market.dropna()

    short_vol = market.rolling(short_window).std() * np.sqrt(12)
    base_mean = short_vol.rolling(long_window, min_periods=12).mean()
    base_std = short_vol.rolling(long_window, min_periods=12).std()
    vol_z = (short_vol - base_mean) / base_std

    cum = np.exp(market.cumsum())
    drawdown = cum / cum.cummax() - 1.0

    df = pd.DataFrame({
        "short_vol": short_vol, "vol_z": vol_z, "drawdown": drawdown,
    }).dropna(subset=["vol_z"])

    # Hysteresis state machine
    crisis = []
    state = False
    for z in df["vol_z"]:
        if not state and z > z_threshold:
            state = True
        elif state and z < exit_z:
            state = False
        crisis.append(state)
    df["crisis"] = crisis
    return df
