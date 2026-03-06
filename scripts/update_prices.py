"""
Update Prices — Refresh Local Price Cache
============================================
Fetches the latest prices for all ETFs and updates the cache.
Designed to be run daily (e.g., via cron or APScheduler).

Usage: python -m scripts.update_prices
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.engine.asset_universe import get_all_etfs
from backend.data.market_data import fetch_prices
from backend.data.cache import save_to_cache, is_cache_fresh


def update():
    """Refresh prices for ETFs whose cache is stale."""
    etfs = get_all_etfs()
    print(f"Checking price freshness for {len(etfs)} ETFs...")

    updated = 0
    for etf in etfs:
        ticker = etf["ticker"]
        if is_cache_fresh(ticker):
            continue

        print(f"  Updating {ticker}...", end=" ")
        df = fetch_prices(ticker, period_years=5)
        if df is not None and not df.empty:
            save_to_cache(ticker, df)
            print(f"✓ {len(df)} records")
            updated += 1
        else:
            print("✗ FAILED")

    print(f"\nDone: {updated} ETFs updated.")


if __name__ == "__main__":
    update()
