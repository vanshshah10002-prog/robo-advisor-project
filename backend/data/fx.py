"""
FX Cross-Rate Fetcher — GBP Base Conversion
============================================
Fetches GBP cross rates (units of foreign currency per 1 GBP) so that
non-GBP ETF prices can be converted to GBP for a UK investor on an
*unhedged* basis. FX return is a genuine component of an unhedged
investor's total return, so we convert prices BEFORE computing returns.

Convention (Yahoo Finance "GBPXXX=X"):
    GBPUSD=X = USD per 1 GBP
    GBPINR=X = INR per 1 GBP
    GBPEUR=X = EUR per 1 GBP

Conversion to GBP:
    price_gbp = price_local / (units_of_local_per_gbp)
    (GBP prices pass through unchanged.)

Note: Return computations are scale-invariant, so the LSE GBX (pence) vs
GBP quoting quirk does not affect results — only true FX matters.
"""

import datetime
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.config import PRICE_HISTORY_YEARS

logger = logging.getLogger(__name__)

# Map registry currency code → Yahoo FX symbol (units of currency per 1 GBP)
_FX_SYMBOLS: dict[str, str] = {
    "USD": "GBPUSD=X",
    "INR": "GBPINR=X",
    "EUR": "GBPEUR=X",
    "JPY": "GBPJPY=X",
}

_fx_cache: dict[str, pd.Series] = {}


def fetch_fx_series(
    currency: str,
    period_years: int = PRICE_HISTORY_YEARS,
) -> Optional[pd.Series]:
    """
    Fetch a daily FX series of (units of `currency` per 1 GBP).

    Parameters:
        currency (str): ISO code, e.g. "USD", "INR", "EUR".
        period_years (int): Years of history to fetch.

    Returns:
        pd.Series or None: Daily FX close indexed by date, or None on failure.
                           GBP returns a constant series of 1.0 (handled by caller).
    """
    currency = (currency or "GBP").upper()
    if currency == "GBP":
        return None  # caller treats None as identity (no conversion)

    if currency in _fx_cache:
        return _fx_cache[currency]

    symbol = _FX_SYMBOLS.get(currency)
    if symbol is None:
        logger.warning(f"No FX symbol mapping for currency {currency}; treating as GBP (no conversion)")
        return None

    try:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=period_years * 365)
        data = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if data is None or data.empty:
            logger.warning(f"FX fetch returned empty for {symbol}")
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        series = data["Close"].copy()
        series.index = pd.to_datetime(series.index)
        series.name = currency
        _fx_cache[currency] = series
        logger.info(f"Fetched FX {symbol}: {len(series)} obs, "
                    f"latest={float(series.iloc[-1]):.4f} {currency}/GBP")
        return series

    except Exception as e:
        logger.error(f"FX fetch failed for {symbol}: {e}")
        return None


def convert_to_gbp(
    price: pd.Series,
    currency: str,
    period_years: int = PRICE_HISTORY_YEARS,
) -> pd.Series:
    """
    Convert a local-currency price series to GBP (unhedged).

    For non-GBP currencies, aligns the FX series to the price dates
    (forward-filling FX gaps from non-overlapping calendars) and divides.

    Parameters:
        price (pd.Series): Local-currency close prices indexed by date.
        currency (str): The price series' currency (registry `currency` field).
        period_years (int): Years of FX history to fetch if needed.

    Returns:
        pd.Series: GBP-denominated price series (same index as input).
    """
    currency = (currency or "GBP").upper()
    if currency == "GBP":
        return price

    fx = fetch_fx_series(currency, period_years)
    if fx is None:
        logger.warning(f"No FX series for {currency}; returning unconverted prices")
        return price

    # Align FX to price index; ffill across calendar gaps, then bfill any leading NaN
    fx_aligned = fx.reindex(price.index.union(fx.index)).ffill().bfill()
    fx_aligned = fx_aligned.reindex(price.index)

    gbp_price = price / fx_aligned
    return gbp_price
