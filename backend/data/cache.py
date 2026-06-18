"""
SQLite Price Cache — Zero-Cost Local Caching
==============================================
Caches fetched OHLCV data in a local SQLite database to minimise API calls.
Only re-fetches if cache is stale (older than PRICE_STALE_HOURS).

Reference: Local-first architecture — no paid APIs for cached data.
"""

import datetime
import logging
import sqlite3
import os
from typing import Optional

import pandas as pd

from backend.config import PRICE_STALE_HOURS

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = os.path.join(
    os.path.dirname(__file__), "price_cache.db"
)


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the cache database, creating tables if needed."""
    conn = sqlite3.connect(_CACHE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_metadata (
            ticker TEXT PRIMARY KEY,
            last_fetched TEXT NOT NULL,
            records_count INTEGER
        )
    """)
    # Window awareness: a cache entry fetched for 3y must NOT satisfy a 10y
    # request (different callers request different windows; serving the
    # shorter one silently truncates estimation history).
    try:
        conn.execute("ALTER TABLE cache_metadata ADD COLUMN period_years INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    return conn


def is_cache_fresh(ticker: str, period_years: int = 0) -> bool:
    """
    Check if the cached data for a ticker is still fresh AND covers at least
    the requested history window.

    Parameters:
        ticker (str): The ETF ticker.
        period_years (int): Requested history window; cache must have been
            fetched with a window >= this to count as fresh.

    Returns:
        bool: True if cache exists, is younger than PRICE_STALE_HOURS, and
              was fetched with a sufficient window.
    """
    try:
        conn = _get_connection()
        cursor = conn.execute(
            "SELECT last_fetched, period_years FROM cache_metadata WHERE ticker = ?",
            (ticker,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return False
        if int(row[1] or 0) < period_years:
            return False

        last_fetched = datetime.datetime.fromisoformat(row[0])
        age = datetime.datetime.utcnow() - last_fetched
        return age.total_seconds() < PRICE_STALE_HOURS * 3600

    except Exception as e:
        logger.error(f"Cache freshness check failed for {ticker}: {e}")
        return False


def get_cached_prices(ticker: str) -> Optional[pd.DataFrame]:
    """
    Retrieve cached price data for a ticker.

    Parameters:
        ticker (str): The ETF ticker.

    Returns:
        pd.DataFrame or None: OHLCV DataFrame, or None if not cached.
    """
    try:
        conn = _get_connection()
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM price_cache WHERE ticker = ? ORDER BY date",
            conn,
            params=(ticker,),
            parse_dates=["date"],
        )
        conn.close()

        if df.empty:
            return None

        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df = df.set_index("Date")
        return df

    except Exception as e:
        logger.error(f"Cache read failed for {ticker}: {e}")
        return None


def save_to_cache(ticker: str, df: pd.DataFrame, period_years: int = 0) -> None:
    """
    Save OHLCV data to the cache, replacing any existing data for the ticker.

    Parameters:
        ticker (str): The ETF ticker.
        df (pd.DataFrame): OHLCV DataFrame with Date index.
        period_years (int): History window the data was fetched with.
    """
    try:
        conn = _get_connection()

        # Clear existing data for this ticker
        conn.execute("DELETE FROM price_cache WHERE ticker = ?", (ticker,))

        now = datetime.datetime.utcnow().isoformat()
        records = []
        for date, row in df.iterrows():
            records.append((
                ticker,
                date.isoformat()[:10],
                float(row.get("Open", 0)),
                float(row.get("High", 0)),
                float(row.get("Low", 0)),
                float(row.get("Close", 0)),
                int(row.get("Volume", 0)),
                now,
            ))

        conn.executemany(
            "INSERT OR REPLACE INTO price_cache (ticker, date, open, high, low, close, volume, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            records,
        )

        # Update metadata
        conn.execute(
            "INSERT OR REPLACE INTO cache_metadata "
            "(ticker, last_fetched, records_count, period_years) VALUES (?, ?, ?, ?)",
            (ticker, now, len(records), int(period_years)),
        )

        conn.commit()
        conn.close()
        logger.info(f"Cached {len(records)} price records for {ticker}")

    except Exception as e:
        logger.error(f"Cache write failed for {ticker}: {e}")


def get_or_fetch_prices(ticker: str, fetcher_func, period_years: int = 5) -> Optional[pd.DataFrame]:
    """
    Get prices from cache if fresh, otherwise fetch and cache.

    Parameters:
        ticker (str): The ETF ticker.
        fetcher_func: Callable(ticker, period_years) -> pd.DataFrame.
        period_years (int): Years of history if fetching fresh.

    Returns:
        pd.DataFrame or None: OHLCV data.
    """
    if is_cache_fresh(ticker, period_years):
        cached = get_cached_prices(ticker)
        if cached is not None and not cached.empty:
            logger.info(f"Using cached data for {ticker}")
            return cached

    # Fetch fresh data
    df = fetcher_func(ticker, period_years)
    if df is not None and not df.empty:
        save_to_cache(ticker, df, period_years)
        return df

    # Last resort: return stale cache if available
    return get_cached_prices(ticker)
