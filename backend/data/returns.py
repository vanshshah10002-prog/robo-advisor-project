"""
Monthly GBP Returns Builder — Clean Estimation Inputs
======================================================
Builds the canonical estimation dataset for the optimization stack:
    - Month-end sampling (neutralizes UK/US/India calendar mismatch)
    - Per-ticker FX conversion to GBP, unhedged (uses registry `currency`)
    - OUTER join across tickers (ragged histories preserved — no global dropna)
    - Monthly log returns

This replaces the old inner-join `dropna()` price matrix for all
expected-return and covariance estimation. Downstream estimators must
handle NaNs per-asset (e.g. pairwise covariance, per-asset means).

Reference: docs/OPTIMIZATION_WALKTHROUGH.md (Phase 0).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import PRICE_HISTORY_YEARS
from backend.data.cache import get_or_fetch_prices
from backend.data.market_data import fetch_prices_yfinance
from backend.data.fx import convert_to_gbp
from backend.engine.asset_universe import get_etf_by_ticker

logger = logging.getLogger(__name__)

# pandas month-end resample alias (pandas >= 2.1 uses "ME"; "M" is deprecated)
_MONTH_END = "ME"


def _ticker_currency(ticker: str) -> str:
    """Look up a ticker's quoting currency from the registry (default GBP)."""
    etf = get_etf_by_ticker(ticker)
    return (etf.get("currency") if etf else "GBP") or "GBP"


def build_monthly_gbp_prices(
    tickers: list[str],
    period_years: int = PRICE_HISTORY_YEARS,
) -> Optional[pd.DataFrame]:
    """
    Build a month-end, GBP-converted (unhedged) price matrix.

    Each ticker is fetched (cache-aware), FX-converted to GBP using its
    registry currency, resampled to month-end, then OUTER-joined so that
    differing histories and trading calendars are preserved as NaNs.

    Parameters:
        tickers (list[str]): ETF tickers (mix of .L and .NS).
        period_years (int): Years of history to fetch.

    Returns:
        pd.DataFrame or None: Columns = tickers, index = month-end dates,
                              values = GBP close prices (NaN where no data).
    """
    monthly_series: dict[str, pd.Series] = {}

    for ticker in tickers:
        df = get_or_fetch_prices(ticker, fetch_prices_yfinance, period_years)
        if df is None or df.empty or "Close" not in df.columns:
            logger.warning(f"No price data for {ticker} — skipping")
            continue

        close = df["Close"].copy()
        close.index = pd.to_datetime(close.index)
        close = close[~close.index.duplicated(keep="last")].sort_index()

        # FX-convert to GBP (unhedged) BEFORE resampling
        currency = _ticker_currency(ticker)
        gbp_close = convert_to_gbp(close, currency, period_years)

        # Month-end sampling
        monthly = gbp_close.resample(_MONTH_END).last()
        monthly_series[ticker] = monthly

    if not monthly_series:
        logger.error("No monthly series built for any ticker")
        return None

    # OUTER join — preserve ragged histories (do NOT dropna globally)
    matrix = pd.DataFrame(monthly_series).sort_index()
    logger.info(
        f"Monthly GBP price matrix: {matrix.shape[0]} months x {matrix.shape[1]} tickers, "
        f"range [{matrix.index.min():%Y-%m} .. {matrix.index.max():%Y-%m}]"
    )
    return matrix


def build_monthly_gbp_log_returns(
    tickers: list[str],
    period_years: int = PRICE_HISTORY_YEARS,
    min_obs: int = 12,
    max_stale_months: int = 3,
) -> Optional[pd.DataFrame]:
    """
    Build month-end GBP log returns for the given tickers.

    Log return r_t = ln(P_t / P_{t-1}), computed per-column so that each
    asset's returns start when its own history starts (ragged preserved).
    Columns with fewer than `min_obs` non-NaN returns are dropped.

    LIVENESS filter: a column with no data in the final `max_stale_months`
    months of the panel is dropped — a fund that stopped printing prices is
    delisted/suspended and not investable, and its stale column would poison
    complete-case covariance estimation (e.g. VVAL.L/VMOM.L, liquidated 2021,
    still pass `min_obs` on old data alone).

    Parameters:
        tickers (list[str]): ETF tickers.
        period_years (int): Years of history.
        min_obs (int): Minimum number of monthly return observations to keep a ticker.
        max_stale_months (int): Drop tickers with no data this close to the panel end.

    Returns:
        pd.DataFrame or None: Monthly log returns (columns = tickers).
    """
    prices = build_monthly_gbp_prices(tickers, period_years)
    if prices is None or prices.empty:
        return None

    log_returns = np.log(prices / prices.shift(1))

    # Drop tickers with too little history
    counts = log_returns.count()
    keep = counts[counts >= min_obs].index.tolist()
    dropped = [t for t in log_returns.columns if t not in keep]
    if dropped:
        logger.info(f"Dropping {len(dropped)} tickers with < {min_obs} monthly returns: {dropped}")

    log_returns = log_returns[keep]
    # Drop the first all-NaN row created by shift
    log_returns = log_returns.dropna(how="all")
    if log_returns.empty:
        return log_returns

    # Liveness: no prints near the panel end ⇒ delisted/suspended, not investable
    panel_end = log_returns.index.max().to_period("M")
    stale = [
        c for c in log_returns.columns
        if log_returns[c].last_valid_index() is None
        or (panel_end - log_returns[c].last_valid_index().to_period("M")).n > max_stale_months
    ]
    if stale:
        logger.warning(
            f"Dropping {len(stale)} stale/delisted tickers "
            f"(no data in last {max_stale_months} months): {stale}"
        )
        log_returns = log_returns.drop(columns=stale)
    return log_returns


def annualize_log_returns(monthly_log_returns: pd.Series) -> pd.Series:
    """
    Annualize a series of mean monthly log returns to arithmetic annual returns.

    Converts mean monthly LOG return → annual ARITHMETIC return:
        r_annual_arith = exp(mean_monthly_log * 12) - 1

    Parameters:
        monthly_log_returns (pd.Series): Mean monthly log return per asset.

    Returns:
        pd.Series: Annualized arithmetic returns.
    """
    return np.exp(monthly_log_returns * 12.0) - 1.0
