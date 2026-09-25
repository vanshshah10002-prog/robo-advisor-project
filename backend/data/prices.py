"""
Latest GBP Prices — valuation source for the holdings ledger
=============================================================
Every valuation (buying at creation, marking to market, sizing rebalance
trades) goes through this module so that all positions are priced in the
same unit: GBP per ETF unit, taken from the cache-backed daily series and
converted with the same FX path as the estimation data.

A price that cannot be obtained is reported as None. Callers must treat it
as missing (keep the last known price and flag it); they must never invent one.
"""

import datetime
import logging
from typing import Optional

import pandas as pd

from backend.data.cache import get_or_fetch_prices
from backend.data.fx import convert_to_gbp
from backend.data.market_data import fetch_prices_yfinance
from backend.data.returns import _ticker_currency

logger = logging.getLogger(__name__)

# Window fetched for valuation. Short on purpose: only the last close matters,
# and any cached window of at least this length satisfies it.
_VALUATION_WINDOW_YEARS = 1


def get_latest_gbp_price(ticker: str) -> Optional[tuple[float, datetime.date]]:
    """
    Latest close for `ticker` in GBP per unit, with the date of that close.

    Returns:
        (price_gbp, as_of_date), or None if no usable price exists.
    """
    df = get_or_fetch_prices(ticker, fetch_prices_yfinance, _VALUATION_WINDOW_YEARS)
    if df is None or df.empty or "Close" not in df.columns:
        logger.warning(f"No price available for {ticker}")
        return None

    close = df["Close"].dropna()
    if close.empty:
        return None
    close.index = pd.to_datetime(close.index)
    # Convert only the recent tail — enough for FX alignment, cheap to compute.
    gbp = convert_to_gbp(close.iloc[-10:], _ticker_currency(ticker, df)).dropna()
    if gbp.empty:
        return None

    price = float(gbp.iloc[-1])
    if not (price > 0):
        return None
    return price, gbp.index[-1].date()


def get_latest_gbp_prices(tickers: list[str]) -> dict[str, tuple[float, datetime.date]]:
    """Latest GBP prices for several tickers; tickers without a price are omitted."""
    out = {}
    for t in tickers:
        p = get_latest_gbp_price(t)
        if p is not None:
            out[t] = p
    return out
