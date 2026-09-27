"""
Market Data Fetcher — yfinance Primary, Alpha Vantage Fallback
===============================================================
Fetches historical OHLCV price data for UK-listed ETFs from Yahoo Finance.
Falls back to Alpha Vantage if yfinance fails.
All prices are cached locally in SQLite to minimise API calls.

Reference: Uses yfinance (free, no key) for LSE tickers (suffix .L).
"""

import datetime
import logging
from typing import Optional

import pandas as pd
import yfinance as yf
import httpx

from backend.config import (
    ALPHA_VANTAGE_API_KEY,
    PRICE_HISTORY_YEARS,
    YFINANCE_TICKER_SUFFIX,
)

logger = logging.getLogger(__name__)


def fetch_prices_yfinance(
    ticker: str,
    period_years: int = PRICE_HISTORY_YEARS,
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV data from Yahoo Finance.

    Parameters:
        ticker (str): LSE ticker with .L suffix (e.g., "VWRL.L").
        period_years (int): Number of years of history to fetch.
        interval (str): Data granularity ("1d", "1wk", "1mo").

    Returns:
        pd.DataFrame or None: DataFrame with columns [Open, High, Low, Close, Volume],
                               indexed by Date. None if fetch fails.
    """
    try:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=period_years * 365)

        data = yf.download(
            ticker,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval=interval,
            progress=False,
            auto_adjust=True,
        )

        if data is None or data.empty:
            logger.warning(f"yfinance returned empty data for {ticker}")
            return None

        # Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.index = pd.to_datetime(data.index)
        data.index.name = "Date"

        out = data[["Open", "High", "Low", "Close", "Volume"]].dropna()
        currency = _yahoo_quote_currency(ticker)
        return normalise_quote_units(out, currency)

    except Exception as e:
        logger.error(f"yfinance fetch failed for {ticker}: {e}")
        return None


_PENCE_CODES = {"GBp", "GBX", "GBx"}


def _yahoo_quote_currency(ticker: str) -> Optional[str]:
    """The listing's trading currency as Yahoo reports it (e.g. GBp, USD), or None."""
    try:
        return yf.Ticker(ticker).fast_info["currency"]
    except Exception as e:
        logger.debug(f"No quote currency for {ticker}: {e}")
        return None


def normalise_quote_units(df: pd.DataFrame, currency: Optional[str]) -> pd.DataFrame:
    """
    Put OHLC prices in whole currency units and record the currency.

    - Pence listings (GBp) are divided by 100 and tagged GBP, so an LSE line
      that trades in sterling is never FX-converted as if it were USD.
    - Yahoo occasionally switches a pence series to pounds (or back) for a few
      days; points more than 30× away from the series median are rescaled.

    The detected currency is stored in `df.attrs["currency"]` (None when
    unknown — callers then fall back to the registry).
    """
    df = df.copy()
    price_cols = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    if currency in _PENCE_CODES:
        df[price_cols] = df[price_cols] / 100.0
        currency = "GBP"
    if "Close" in df.columns and len(df) > 5:
        med = float(df["Close"].median())
        if med > 0:
            hi = df["Close"] > 30 * med
            lo = df["Close"] < med / 30
            if hi.any() or lo.any():
                logger.warning(f"Rescaling {int(hi.sum() + lo.sum())} price points with a 100× unit glitch")
                df.loc[hi, price_cols] = df.loc[hi, price_cols] / 100.0
                df.loc[lo, price_cols] = df.loc[lo, price_cols] * 100.0
    df.attrs["currency"] = currency
    return df


def fetch_prices_alpha_vantage(
    ticker: str,
    output_size: str = "full",
) -> Optional[pd.DataFrame]:
    """
    Fallback: Fetch daily prices from Alpha Vantage.

    Parameters:
        ticker (str): LSE ticker (may need conversion — AV uses different symbols).
        output_size (str): "compact" (100 days) or "full" (20+ years).

    Returns:
        pd.DataFrame or None: OHLCV DataFrame, or None if fetch fails.
    """
    if not ALPHA_VANTAGE_API_KEY:
        logger.warning("Alpha Vantage API key not set — skipping fallback")
        return None

    try:
        # Alpha Vantage uses different ticker formats for LSE
        av_ticker = ticker.replace(".L", ".LON")

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": av_ticker,
            "outputsize": output_size,
            "apikey": ALPHA_VANTAGE_API_KEY,
        }

        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        ts_key = "Time Series (Daily)"
        if ts_key not in result:
            logger.warning(f"Alpha Vantage: no time series data for {ticker}")
            return None

        ts = result[ts_key]
        records = []
        for date_str, values in ts.items():
            records.append({
                "Date": pd.Timestamp(date_str),
                "Open": float(values["1. open"]),
                "High": float(values["2. high"]),
                "Low": float(values["3. low"]),
                "Close": float(values["4. close"]),
                "Volume": int(values["5. volume"]),
            })

        df = pd.DataFrame(records).set_index("Date").sort_index()
        return df

    except Exception as e:
        logger.error(f"Alpha Vantage fetch failed for {ticker}: {e}")
        return None


def fetch_prices(
    ticker: str,
    period_years: int = PRICE_HISTORY_YEARS,
) -> Optional[pd.DataFrame]:
    """
    Fetch prices with automatic fallback.
    Tries yfinance first, then Alpha Vantage.

    Parameters:
        ticker (str): LSE ticker (e.g., "VWRL.L").
        period_years (int): Years of history to fetch.

    Returns:
        pd.DataFrame or None: OHLCV data.
    """
    # Try yfinance first (free, no key)
    df = fetch_prices_yfinance(ticker, period_years)
    if df is not None and not df.empty:
        return df

    # Fallback to Alpha Vantage
    logger.info(f"Falling back to Alpha Vantage for {ticker}")
    return fetch_prices_alpha_vantage(ticker)


def fetch_multiple_prices(
    tickers: list[str],
    period_years: int = PRICE_HISTORY_YEARS,
) -> dict[str, pd.DataFrame]:
    """
    Fetch prices for multiple tickers. Returns only successful fetches.

    Parameters:
        tickers (list[str]): List of LSE tickers.
        period_years (int): Years of history.

    Returns:
        dict[str, pd.DataFrame]: {ticker: OHLCV DataFrame} for successful fetches.
    """
    results = {}
    for ticker in tickers:
        df = fetch_prices(ticker, period_years)
        if df is not None and not df.empty:
            results[ticker] = df
        else:
            logger.warning(f"Could not fetch data for {ticker} — skipping")
    return results


def build_close_price_matrix(
    tickers: list[str],
    period_years: int = PRICE_HISTORY_YEARS,
) -> Optional[pd.DataFrame]:
    """
    Build a DataFrame of adjusted close prices for multiple tickers,
    aligned on common dates.

    Parameters:
        tickers (list[str]): LSE tickers.
        period_years (int): Years of history.

    Returns:
        pd.DataFrame or None: Columns = tickers, index = dates, values = close prices.
    """
    price_data = fetch_multiple_prices(tickers, period_years)

    if not price_data:
        return None

    close_series = {}
    for ticker, df in price_data.items():
        close_series[ticker] = df["Close"]

    matrix = pd.DataFrame(close_series).dropna()

    if matrix.empty:
        logger.warning("Price matrix is empty after aligning dates")
        return None

    return matrix
