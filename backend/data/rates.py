"""
Live GBP Risk-Free Rate — yfinance Money-Market Proxy
======================================================
Replaces the old hardcoded rates (4% pricing rf / 6% hurdle) with a LIVE
GBP cash rate observed in the market:

    rf = trailing 12-month annualized return of a GBP ultrashort /
         money-market ETF (ERNS.L, fallback CSH2.L)

These funds hold overnight-to-3-month GBP paper, so their realized return IS
the investable GBP cash rate (≈ realized SONIA net of ~10bp fees). Using an
investable instrument keeps the rate currency-correct and live without a paid
rates API. The price ratio P_t/P_{t-12m} is unit-free, so GBp/GBP quoting on
the LSE does not matter.

Resilience chain:
    live yfinance fetch (cache-aware) → next proxy ticker → config fallback
The fetched rate is clamped to RISK_FREE_CLAMP — anything outside that band
is treated as a data error, not a market signal.
"""

import datetime
import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import (
    MVO_RISK_FREE_RATE,
    RISK_FREE_PROXY_TICKERS,
    RISK_FREE_LOOKBACK_MONTHS,
    RISK_FREE_CLAMP,
)
from backend.data.cache import get_or_fetch_prices
from backend.data.market_data import fetch_prices_yfinance

logger = logging.getLogger(__name__)

# In-process memo so one API process doesn't recompute per request.
_MEMO_TTL_SECONDS: float = 3600.0
_memo_rate: Optional[float] = None
_memo_at: Optional[datetime.datetime] = None


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def trailing_annualized_return(
    close: pd.Series,
    lookback_months: int = RISK_FREE_LOOKBACK_MONTHS,
) -> Optional[float]:
    """
    Annualized total return over the trailing `lookback_months` month-ends.

    Pure function (no network) so it is unit-testable on synthetic data.

    Parameters:
        close (pd.Series): Daily close prices indexed by date.
        lookback_months (int): Trailing window length in months.

    Returns:
        float or None: (P_end / P_start)^(12/n) - 1, or None if there is not
        enough history or prices are non-positive.
    """
    if close is None or close.empty:
        return None
    series = close.dropna()
    series.index = pd.to_datetime(series.index)
    monthly = series.resample("ME").last().dropna()
    if len(monthly) < lookback_months + 1:
        return None
    p_start = float(monthly.iloc[-(lookback_months + 1)])
    p_end = float(monthly.iloc[-1])
    if p_start <= 0 or p_end <= 0:
        return None
    return float((p_end / p_start) ** (12.0 / lookback_months) - 1.0)


def _fetch_live_rate() -> Optional[float]:
    """Try each proxy ticker in order; return the first clamped valid rate."""
    lo, hi = RISK_FREE_CLAMP
    for ticker in RISK_FREE_PROXY_TICKERS:
        # 10y window matches the estimation pipeline's request so both share
        # one cache entry (the rate itself only needs the trailing ~13 months)
        df = get_or_fetch_prices(ticker, fetch_prices_yfinance, period_years=10)
        if df is None or df.empty or "Close" not in df.columns:
            logger.warning(f"Risk-free proxy {ticker}: no price data")
            continue
        rate = trailing_annualized_return(df["Close"])
        if rate is None:
            logger.warning(f"Risk-free proxy {ticker}: insufficient history")
            continue
        clamped = float(np.clip(rate, lo, hi))
        if clamped != rate:
            logger.warning(
                f"Risk-free proxy {ticker}: rate {rate:.2%} outside "
                f"[{lo:.0%}, {hi:.0%}] — clamped to {clamped:.2%}"
            )
        logger.info(f"Live GBP risk-free rate from {ticker}: {clamped:.2%}")
        return clamped
    return None


def get_risk_free_rate(fallback: float = MVO_RISK_FREE_RATE) -> float:
    """
    Current GBP risk-free rate: live from yfinance, memoized for 1 hour,
    falling back to the config constant only if every live source fails.

    Parameters:
        fallback (float): Rate to use when no live source is available.

    Returns:
        float: Annual risk-free rate (e.g. 0.045 for 4.5%).
    """
    global _memo_rate, _memo_at
    now = _utcnow()
    if (
        _memo_rate is not None
        and _memo_at is not None
        and (now - _memo_at).total_seconds() < _MEMO_TTL_SECONDS
    ):
        return _memo_rate

    rate = _fetch_live_rate()
    if rate is None:
        logger.error(
            f"All live risk-free sources failed — using fallback {fallback:.2%}"
        )
        return float(fallback)

    _memo_rate = rate
    _memo_at = now
    return rate
