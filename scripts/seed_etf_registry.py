"""
Seed ETF Registry — Fetch Initial Historical Prices
=====================================================
Populates the local SQLite price cache with historical data
for all ETFs in uk_etf_registry.json.

Usage: python -m scripts.seed_etf_registry
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.engine.asset_universe import get_all_etfs
from backend.data.market_data import fetch_prices
from backend.data.cache import save_to_cache


def seed():
    """Fetch and cache historical prices for all registered ETFs."""
    etfs = get_all_etfs()
    print(f"Seeding price cache for {len(etfs)} ETFs...")

    success = 0
    failed = []

    for etf in etfs:
        ticker = etf["ticker"]
        print(f"  Fetching {ticker} ({etf['name']})...", end=" ")

        df = fetch_prices(ticker, period_years=5)
        if df is not None and not df.empty:
            save_to_cache(ticker, df)
            print(f"✓ {len(df)} records")
            success += 1
        else:
            print("✗ FAILED")
            failed.append(ticker)

    print(f"\nDone: {success}/{len(etfs)} ETFs seeded successfully.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    seed()
