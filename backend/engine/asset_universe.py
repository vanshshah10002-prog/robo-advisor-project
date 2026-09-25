"""
Asset Universe — UK ETF Registry Manager
==========================================
Loads, queries, and manages the UK ETF registry (uk_etf_registry.json).
Provides lookup by asset class, ticker, and substitute ticker for TLH.

Reference: Static registry of UK-listed UCITS ETFs on the London Stock Exchange.
"""

import json
import logging
import os
from typing import Callable, Optional

from backend.config import (
    CORE_UNIVERSE,
    UK_RETAIL_UCITS_ONLY,
    USE_SATELLITE_CLASSES,
    ASSET_CLASSES,
)

logger = logging.getLogger(__name__)

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


def _is_investable(etf: dict, ucits_only: bool) -> bool:
    if etf.get("delisted", False):
        return False
    if ucits_only:
        # LSE physical gold/silver ETCs are not UCITS funds but are ISA-eligible
        # with PRIIPs KIDs; the registry marks them `uk_retail_investable`.
        return bool(etf.get("ucits", False) or etf.get("uk_retail_investable", False))
    return True


def _registry_rank(etf: dict) -> tuple:
    """Satellite ranking: large funds (≥ £500m) first, then lowest TER."""
    return ((etf.get("fund_size_gbp_mm") or 0) < 500, etf["expense_ratio"])


def get_etfs_by_asset_class(asset_class: str, ucits_only: bool = UK_RETAIL_UCITS_ONLY) -> list[dict]:
    """
    Investable ETFs for an asset class, in order of preference.

    Core classes follow the explicit candidate order in CORE_UNIVERSE (chosen
    on cost, size, history and GBP line — not TER alone). Other classes are
    ranked by size then TER. Delisted funds and, for UK retail, NSE-listed
    (non-UCITS) lines are excluded.

    Parameters:
        asset_class (str): Asset class identifier (e.g., "uk_equity").
        ucits_only (bool): Restrict to funds investable by UK retail.

    Returns:
        list[dict]: Candidate ETFs, most preferred first.
    """
    if asset_class in CORE_UNIVERSE:
        by_ticker = {e["ticker"]: e for e in get_all_etfs()}
        ordered = [by_ticker[t] for t in CORE_UNIVERSE[asset_class] if t in by_ticker]
        return [e for e in ordered if _is_investable(e, ucits_only)]
    matches = [
        etf for etf in get_all_etfs()
        if etf["asset_class"] == asset_class and _is_investable(etf, ucits_only)
    ]
    return sorted(matches, key=_registry_rank)


def get_primary_etf_for_class(asset_class: str) -> Optional[dict]:
    """
    The preferred ETF for an asset class, before any data check (see
    `resolve_ticker_map` for the data-aware choice).

    Parameters:
        asset_class (str): Asset class identifier.

    Returns:
        dict or None: The preferred ETF, or None if no investable ETF exists.
    """
    etfs = get_etfs_by_asset_class(asset_class)
    return etfs[0] if etfs else None


def strategic_asset_classes() -> list[str]:
    """Asset classes the optimiser uses: the core set, plus satellites if enabled."""
    classes = list(CORE_UNIVERSE)
    if USE_SATELLITE_CLASSES:
        classes += [ac for ac in ASSET_CLASSES
                    if ac not in CORE_UNIVERSE and get_primary_etf_for_class(ac) is not None]
    return classes


def resolve_ticker_map(
    asset_classes: list[str],
    usable: Optional[Callable[[str], bool]] = None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    Pick one ETF per asset class, falling back down the candidate list when
    the preferred fund fails `usable` (e.g. too little or stale price data).

    Returns:
        (ticker_map, skipped): {asset_class: ticker} for classes that resolved,
        and {asset_class: [tickers rejected]} for every fallback or drop, so
        callers can report them instead of silently losing a class.
    """
    ticker_map: dict[str, str] = {}
    skipped: dict[str, list[str]] = {}
    for ac in asset_classes:
        for etf in get_etfs_by_asset_class(ac):
            t = etf["ticker"]
            if usable is None or usable(t):
                ticker_map[ac] = t
                break
            skipped.setdefault(ac, []).append(t)
        if ac in skipped:
            if ac in ticker_map:
                logger.warning(f"{ac}: fell back to {ticker_map[ac]} (unusable: {skipped[ac]})")
            else:
                logger.warning(f"{ac}: no usable ETF (tried {skipped[ac]}) — class excluded")
    return ticker_map, skipped


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
