"""
Asset Universe — UK ETF Registry Manager
==========================================
Loads, queries, and manages the UK ETF registry (uk_etf_registry.json).
Provides lookup by asset class, ticker, and substitute ticker for TLH.

Reference: Static registry of UK-listed UCITS ETFs on the London Stock Exchange.
"""

import json
import os
from typing import Optional

_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "uk_etf_registry.json"
)

_registry_cache: Optional[list] = None


def _load_registry() -> list:
    """
    Load the ETF registry from disk (cached after first load).

    Returns:
        list: Full list of ETF metadata dictionaries.
    """
    global _registry_cache
    if _registry_cache is None:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Support both flat array and {"etfs": [...]} formats
            if isinstance(data, list):
                _registry_cache = data
            else:
                _registry_cache = data.get("etfs", [])
    return _registry_cache


def get_all_etfs() -> list[dict]:
    """
    Return all ETFs in the registry.

    Returns:
        list[dict]: List of ETF metadata dictionaries.
    """
    return _load_registry()


def get_etf_by_ticker(ticker: str) -> Optional[dict]:
    """
    Look up a single ETF by its ticker symbol.

    Parameters:
        ticker (str): The ETF ticker (e.g., "VWRL.L").

    Returns:
        dict or None: ETF metadata, or None if not found.
    """
    for etf in get_all_etfs():
        if etf["ticker"] == ticker:
            return etf
    return None


def get_etfs_by_asset_class(asset_class: str) -> list[dict]:
    """
    Get all ETFs belonging to a given asset class.

    Parameters:
        asset_class (str): Asset class identifier (e.g., "uk_equity").

    Returns:
        list[dict]: Matching ETFs sorted by expense ratio (lowest first).
    """
    matches = [etf for etf in get_all_etfs() if etf["asset_class"] == asset_class]
    return sorted(matches, key=lambda e: e["expense_ratio"])


def get_primary_etf_for_class(asset_class: str) -> Optional[dict]:
    """
    Get the cheapest (lowest expense ratio) ETF for an asset class.
    This is the primary ETF used for portfolio construction.

    Parameters:
        asset_class (str): Asset class identifier.

    Returns:
        dict or None: The primary ETF, or None if no ETF covers this class.
    """
    etfs = get_etfs_by_asset_class(asset_class)
    return etfs[0] if etfs else None


def get_substitute_ticker(ticker: str) -> Optional[str]:
    """
    Get the tax-loss harvesting substitute ticker for a given ETF.

    Parameters:
        ticker (str): Primary ETF ticker.

    Returns:
        str or None: Substitute ticker, or None if no substitute exists.
    """
    etf = get_etf_by_ticker(ticker)
    if etf:
        return etf.get("tlh_substitute")
    return None


def get_ticker_map(asset_classes: list[str]) -> dict[str, str]:
    """
    Build a mapping from asset class to primary ETF ticker.

    Parameters:
        asset_classes (list[str]): List of asset class identifiers.

    Returns:
        dict[str, str]: {asset_class: ticker} for each class with a primary ETF.
    """
    ticker_map = {}
    for ac in asset_classes:
        etf = get_primary_etf_for_class(ac)
        if etf:
            ticker_map[ac] = etf["ticker"]
    return ticker_map


def get_expense_ratios(asset_classes: list[str]) -> dict[str, float]:
    """
    Get expense ratios for the primary ETF in each asset class.

    Parameters:
        asset_classes (list[str]): Asset class identifiers.

    Returns:
        dict[str, float]: {asset_class: expense_ratio}.
    """
    ratios = {}
    for ac in asset_classes:
        etf = get_primary_etf_for_class(ac)
        if etf:
            ratios[ac] = etf["expense_ratio"]
    return ratios
