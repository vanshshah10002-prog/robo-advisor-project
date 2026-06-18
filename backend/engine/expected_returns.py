"""
Expected Returns Estimator
============================
Computes expected returns using CAPM as the primary model with a proper
global market proxy, and optionally the Black-Litterman model for views.
Subtracts ETF expense ratios for cost-adjusted returns.

Algorithm (academically correct per CAPM + He & Litterman, 1999):
1. PRIMARY: CAPM with explicit global market proxy (VWRL.L / ISF.L)
      E[Ri] = Rf + βi * (E[Rm] - Rf)
   where E[Rm] is taken from the market proxy's 5-year historical CAGR.

2. OPTIONAL: Black-Litterman views blend into the CAPM prior as posterior.
   NOTE on BL dilution effect (root cause of previous 3-4% bug):
   The formula π = λ·Σ·w is only valid when w is the GLOBAL market portfolio
   (tens of thousands of assets). When w covers only 60-100 ETFs, each
   w_i ≈ 1-2%, making Cov(i, mkt) tiny → π_i collapses near zero.
   CAPM avoids this by directly using historical beta regression against
   an actual market index, not a weighted-ETF-average.

3. Subtract ETF expense ratios for net-of-fee returns.

Reference:
- CAPM: Sharpe (1964), Lintner (1965)
- Black-Litterman: He & Litterman (1999)
- Dilution flaw: Idzorek (2005) "A Step-by-Step Guide to the Black-Litterman Model"
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import expected_returns as er
from pypfopt import BlackLittermanModel

from backend.config import (
    MVO_RISK_FREE_RATE,
    BLACK_LITTERMAN_TAU,
    USE_BLACK_LITTERMAN,
    FACTOR_MODEL_LOOKBACK_YEARS,
    BENCHMARK_TICKER,
)
from backend.engine.asset_universe import get_all_etfs

logger = logging.getLogger(__name__)

# Market risk aversion coefficient λ — used only for BL views blending
# Standard literature value (He & Litterman, 1999)
MVO_RISK_AVERSION: float = 2.5

# Assumed annualised market return for the global equity benchmark (VWRL.L)
# Source: MSCI World / FTSE All-World 30-year average real return ~7%
# + ~3% inflation ≈ 10%. Conservative estimate for multi-asset portfolio = 8%.
ASSUMED_MARKET_RETURN: float = 0.08


def _get_market_caps_from_registry(tickers: list[str]) -> dict[str, float]:
    """
    Get market cap weights from the ETF registry's fund_size_gbp field.
    If fund_size_gbp is not available, use a sensible proxy based on
    the ETF's asset class.

    Parameters:
        tickers (list[str]): List of ETF tickers.

    Returns:
        dict[str, float]: {ticker: market_cap_proxy} for BL equilibrium.
    """
    registry = get_all_etfs()
    fund_sizes = {}

    # Build lookup by ticker
    registry_by_ticker = {etf["ticker"]: etf for etf in registry}

    # Default AUM proxies by asset class type (in millions GBP)
    AUM_DEFAULTS = {
        "equity": 15000,
        "bonds": 3000,
        "commodities": 500,
        "reits": 500,
        "cash": 200,
        "alternatives": 300,
    }

    for ticker in tickers:
        etf = registry_by_ticker.get(ticker, {})
        fund_size = etf.get("fund_size_gbp_mm", 0)

        if fund_size and fund_size > 0:
            fund_sizes[ticker] = fund_size  # Already in millions GBP
        else:
            # Proxy based on asset class
            ac = etf.get("asset_class", "")
            if "bond" in ac or "gilt" in ac or "treasury" in ac or "inflation" in ac:
                proxy = AUM_DEFAULTS["bonds"]
            elif "commodity" in ac or "gold" in ac or "silver" in ac:
                proxy = AUM_DEFAULTS["commodities"]
            elif "reit" in ac or "real_estate" in ac:
                proxy = AUM_DEFAULTS["reits"]
            elif "cash" in ac:
                proxy = AUM_DEFAULTS["cash"]
            elif "infrastructure" in ac or "value" in ac or "momentum" in ac or "quality" in ac:
                proxy = AUM_DEFAULTS["alternatives"]
            else:
                proxy = AUM_DEFAULTS["equity"]
            fund_sizes[ticker] = proxy

    logger.info(f"Market cap weights: {len(fund_sizes)} tickers, "
                f"total AUM={sum(fund_sizes.values()):,.0f}")
    return fund_sizes


def _fetch_market_proxy_prices(
    prices: pd.DataFrame,
    risk_free_rate: float,
) -> Optional[pd.Series]:
    """
    Fetch the market proxy (benchmark) price series aligned to the ETF prices.

    Uses BENCHMARK_TICKER (default: VWRL.L) from config. If not available, falls
    back to ISF.L (FTSE-100), then uses equal-weighted ETF average.

    Parameters:
        prices (pd.DataFrame): Already-fetched price matrix for all ETFs.
        risk_free_rate (float): For fallback market return estimate.

    Returns:
        pd.Series or None: Aligned market proxy close prices.
    """
    # Check if the benchmark is already in the price matrix
    if BENCHMARK_TICKER in prices.columns:
        logger.info(f"Using {BENCHMARK_TICKER} as market proxy (already in universe)")
        return prices[BENCHMARK_TICKER]

    # Try ISF.L (FTSE 100) as secondary proxy
    fallback_proxy = "ISF.L"
    if fallback_proxy in prices.columns:
        logger.info(f"Using {fallback_proxy} as market proxy fallback")
        return prices[fallback_proxy]

    # Fetch benchmark separately
    try:
        from backend.data.market_data import build_close_price_matrix
        benchmark_prices = build_close_price_matrix(
            [BENCHMARK_TICKER], period_years=FACTOR_MODEL_LOOKBACK_YEARS
        )
        if benchmark_prices is not None and not benchmark_prices.empty:
            aligned = benchmark_prices[BENCHMARK_TICKER].reindex(prices.index).ffill()
            logger.info(f"Fetched {BENCHMARK_TICKER} as standalone market proxy")
            return aligned
    except Exception as e:
        logger.warning(f"Could not fetch benchmark {BENCHMARK_TICKER}: {e}")

    logger.warning("No market proxy available — CAPM will use equal-weighted portfolio as market")
    return None


def compute_capm_returns(
    prices: pd.DataFrame,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    market_prices: Optional[pd.Series] = None,
    assumed_market_return: float = ASSUMED_MARKET_RETURN,
) -> pd.Series:
    """
    Compute expected returns using the Capital Asset Pricing Model (CAPM).

    E[Ri] = Rf + βi * (E[Rm] - Rf)

    where:
        - βi is estimated via OLS regression of asset returns on market returns
        - E[Rm] = historical CAGR of the market proxy (VWRL.L or ISF.L)
        - Rf = risk-free rate from config

    This model is robust to the "dilution effect" that plagues BL in small
    universes because beta is derived from actual price co-movement regressions,
    not from weighted covariance of a small ETF subset.

    Parameters:
        prices (pd.DataFrame): Historical close prices (columns = tickers).
        risk_free_rate (float): Annualised risk-free rate (UK base rate).
        market_prices (pd.Series, optional): Market proxy price series.
        assumed_market_return (float): Assumed annualised market return.

    Returns:
        pd.Series: Expected annual returns per asset.
    """
    try:
        if market_prices is not None:
            # Convert market proxy to DataFrame for pypfopt compatibility
            mkt_df = pd.DataFrame({"market": market_prices})
            mkt_df = mkt_df.reindex(prices.index).ffill().dropna()

            # Use pypfopt's CAPM which regresses each asset on the market proxy
            mu = er.capm_return(
                prices,
                market_prices=mkt_df,
                risk_free_rate=risk_free_rate,
                compounding=True,
                frequency=252,
            )
        else:
            # Fallback: no explicit market proxy — pypfopt uses equal-weighted portfolio
            # This is less ideal but still better than BL with diluted weights
            mu = er.capm_return(
                prices,
                risk_free_rate=risk_free_rate,
                compounding=True,
                frequency=252,
            )

        logger.info(f"CAPM returns: mean={mu.mean():.4f}, range=[{mu.min():.4f}, {mu.max():.4f}]")

        # Sanity check: returns should be in [-10%, +50%] range for ETFs
        if mu.max() > 0.60 or mu.min() < -0.15:
            logger.warning(f"CAPM returns seem extreme [{mu.min():.4f}, {mu.max():.4f}], clamping")
            mu = mu.clip(-0.10, 0.50)

        return mu

    except Exception as e:
        logger.error(f"CAPM return estimation failed: {e} — falling back to historical mean")
        hist = er.mean_historical_return(prices, compounding=True, frequency=252)
        return hist.clip(-0.05, 0.35)


def compute_black_litterman_returns(
    prices: pd.DataFrame,
    cov_matrix: pd.DataFrame,
    market_caps: Optional[dict[str, float]] = None,
    views: Optional[dict[str, float]] = None,
    view_confidence: Optional[list[float]] = None,
    tau: float = BLACK_LITTERMAN_TAU,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    Compute expected returns using the Black-Litterman model.

    NOTE: Without views, the pure BL prior π = λ·Σ·w suffers from the
    "dilution effect" in universes of 60-100+ assets: each w_i ≈ 1%,
    collapsing π_i to near zero. This function is most useful when
    investor views are provided to shift the prior meaningfully.

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        cov_matrix (pd.DataFrame): Covariance matrix of returns.
        market_caps (dict, optional): {ticker: AUM_gbp} for equilibrium weights.
        views (dict, optional): {ticker: expected_return_view} — absolute views.
        view_confidence (list, optional): Confidence levels for each view (0–1).
        tau (float): Scaling factor for uncertainty in the prior.
        risk_free_rate (float): Annualised risk-free rate.

    Returns:
        pd.Series: BL/equilibrium expected returns.
    """
    try:
        # Get market cap weights from registry if not provided
        if market_caps is None:
            market_caps = _get_market_caps_from_registry(list(prices.columns))

        # Filter to only tickers we have data for
        tickers = [t for t in cov_matrix.index if t in market_caps]
        if len(tickers) < 2:
            logger.warning("Not enough tickers with market caps, falling back to CAPM")
            return compute_capm_returns(prices, risk_free_rate)

        filtered_caps = {t: market_caps[t] for t in tickers}

        # Compute market weights: wₘ = AUM_i / Σ AUM_j
        total_aum = sum(filtered_caps.values())
        w_mkt = np.array([filtered_caps[t] / total_aum for t in tickers])

        # Compute equilibrium prior (EXCESS returns): π = λ · Σ · wₘ
        # This is what the market implies as the fair RISK PREMIUM.
        cov_sub = cov_matrix.loc[tickers, tickers].values
        pi = MVO_RISK_AVERSION * (cov_sub @ w_mkt)

        result = pd.Series(pi, index=tickers)

        logger.info(
            f"BL equilibrium prior π computed: mean={result.mean():.4f}, "
            f"range=[{result.min():.4f}, {result.max():.4f}]"
        )

        # If views are provided, use the full BL posterior
        if views and len(views) > 0:
            try:
                bl = BlackLittermanModel(
                    cov_matrix.loc[tickers, tickers],
                    pi=result,  # Pass our computed prior
                    absolute_views=views,
                )
                result = bl.bl_returns()
                logger.info(f"BL posterior with {len(views)} views applied")
            except Exception as ve:
                logger.warning(f"BL views integration failed ({ve}), using prior π only")

        # Add Risk-Free Rate back to the excess returns to get Total Expected Returns
        # E[R] = Rf + Premium
        result = result + risk_free_rate

        # Validate: returns should be reasonable
        if result.max() > 0.60 or result.min() < -0.10:
            logger.warning(
                f"BL returns extreme: [{result.min():.4f}, {result.max():.4f}], clamping"
            )
            result = result.clip(-0.05, 0.40)

        return result

    except Exception as e:
        logger.warning(f"Black-Litterman failed ({e}), falling back to CAPM")
        return compute_capm_returns(prices, risk_free_rate)


def adjust_for_costs(
    expected_returns: pd.Series,
    expense_ratios: dict[str, float],
) -> pd.Series:
    """
    Subtract ETF expense ratios from expected returns.

    This cost adjustment ensures that cheaper ETFs are slightly favoured
    in the optimisation, all else being equal. Critical for UK UCITS ETFs
    where expense ratios vary widely (0.07% to 0.65%).

    Parameters:
        expected_returns (pd.Series): Pre-cost expected returns.
        expense_ratios (dict[str, float]): {ticker: expense_ratio}.

    Returns:
        pd.Series: Cost-adjusted expected returns.
    """
    adjusted = expected_returns.copy()
    for ticker in adjusted.index:
        if ticker in expense_ratios:
            adjusted[ticker] -= expense_ratios[ticker]
    return adjusted


def get_blend_expected_returns(
    monthly_log_returns: pd.DataFrame,
    expense_ratios: Optional[dict[str, float]] = None,
    w_trailing: float = 0.5,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> pd.Series:
    """
    PRODUCTION expected-returns model (Phase 1 locked): trailing historical mean
    blended 50/50 with the calibrated Black-Litterman equilibrium prior, on
    monthly GBP-unhedged log returns, then cost-adjusted.

    Validated in docs/OPTIMIZATION_WALKTHROUGH.md (Phase 1 hold-out gate). Uses
    the exact `blend_trailing_bl` implementation from the eval harness to
    guarantee parity with the validated research.

    Parameters:
        monthly_log_returns (pd.DataFrame): month-end GBP log returns per ticker.
        expense_ratios (dict, optional): {ticker: annual_expense_ratio}.
        w_trailing (float): blend weight on trailing mean (locked at 0.5).
        risk_free_rate (float): annual risk-free rate.

    Returns:
        pd.Series: net-of-fee annual arithmetic expected returns per ticker,
        clamped to EXPECTED_RETURN_CLAMP (CMA sanity bounds).
    """
    from backend.engine.quant_models import blend_trailing_bl
    from backend.config import EXPECTED_RETURN_CLAMP

    mu = blend_trailing_bl(
        monthly_log_returns, w_trailing=w_trailing, risk_free_annual=risk_free_rate
    )
    if expense_ratios:
        mu = adjust_for_costs(mu, expense_ratios)

    # CMA sanity clamp: trailing-heavy estimates outside professional
    # capital-market-assumption ranges are estimation error, not signal.
    lo, hi = EXPECTED_RETURN_CLAMP
    n_clamped = int(((mu < lo) | (mu > hi)).sum())
    if n_clamped:
        logger.warning(f"Clamping {n_clamped} expected returns to [{lo:.0%}, {hi:.0%}]")
    mu = mu.clip(lo, hi)

    logger.info(
        f"Blend(trailing+BL) returns: mean={mu.mean():.4f}, "
        f"range=[{mu.min():.4f}, {mu.max():.4f}]"
    )
    return mu


def build_mu_cov(
    tickers: list[str],
    expense_by_ticker: Optional[dict[str, float]] = None,
    w_trailing: float = 0.5,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    period_years: int = 10,
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """
    Production input builder (Phases 0–2 integrated): fetches month-end,
    GBP-unhedged, outer-joined log returns and returns the locked expected
    returns (trailing+BL blend) and covariance (EWMA+Ledoit-Wolf hybrid),
    index-aligned and ready for the optimizer.

    Parameters:
        tickers (list[str]): ETF tickers.
        expense_by_ticker (dict, optional): {ticker: expense_ratio} for net-of-fee mu.
        w_trailing (float): blend weight on trailing mean.
        risk_free_rate (float): annual risk-free rate.
        period_years (int): years of history to fetch.

    Returns:
        (mu, cov, monthly_returns): annual arithmetic E[R], annual covariance,
        and the underlying monthly log-return panel (for regime detection).
    """
    from backend.data.returns import build_monthly_gbp_log_returns
    from backend.engine.quant_models import ewma_lw_cov

    monthly = build_monthly_gbp_log_returns(tickers, period_years=period_years, min_obs=24)
    if monthly is None or monthly.shape[1] < 2:
        raise ValueError("Insufficient monthly return data for selected ETFs")

    cov = ewma_lw_cov(monthly)
    # Defensive: a ticker whose covariance column is NaN/Inf (e.g. no
    # overlapping complete-case rows) would crash the solver — drop it.
    bad = cov.columns[~np.isfinite(cov.values).all(axis=0)].tolist()
    if bad:
        logger.warning(f"Dropping {len(bad)} tickers with non-finite covariance: {bad}")
        keep = [c for c in cov.columns if c not in bad]
        cov = cov.loc[keep, keep]

    mu = get_blend_expected_returns(monthly, expense_by_ticker, w_trailing, risk_free_rate)

    # Align mu and cov on common tickers
    common = [t for t in mu.index if t in cov.columns]
    if len(common) < 2:
        raise ValueError("Fewer than 2 tickers shared between returns and covariance")
    mu = mu.reindex(common).dropna()
    cov = cov.loc[mu.index, mu.index]
    return mu, cov, monthly


def get_expected_returns(
    prices: pd.DataFrame,
    cov_matrix: pd.DataFrame,
    expense_ratios: dict[str, float],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    use_bl: bool = USE_BLACK_LITTERMAN,
) -> pd.Series:
    """
    Full expected returns pipeline: CAPM (primary) → optional BL overlay → cost-adjusted.

    MODEL SELECTION RATIONALE:
    - CAPM is primary: robust β-regression against a real market index avoids
      the BL dilution effect that collapses returns to 3-4% in large universes.
    - BL is secondary: only activated if explicit analyst views are injected.
      Without views, BL degenerates to a noisy scaled-covariance estimate.

    Parameters:
        prices (pd.DataFrame): Historical close prices.
        cov_matrix (pd.DataFrame): Covariance matrix.
        expense_ratios (dict): {ticker: annual_expense_ratio}.
        risk_free_rate (float): UK base rate.
        use_bl (bool): Legacy flag — BL is only used if views are injected.

    Returns:
        pd.Series: Net-of-fee expected annual returns.
    """
    # Step 1: Fetch/align market proxy for CAPM beta regression
    market_prices = _fetch_market_proxy_prices(prices, risk_free_rate)

    # Step 2: PRIMARY MODEL — CAPM with explicit market proxy
    mu = compute_capm_returns(prices, risk_free_rate, market_prices=market_prices)

    # Step 3: Cost adjustment (net-of-fee returns)
    mu = adjust_for_costs(mu, expense_ratios)

    logger.info(
        f"Final expected returns (CAPM, net-of-fee): "
        f"mean={mu.mean():.4f}, range=[{mu.min():.4f}, {mu.max():.4f}]"
    )
    return mu
