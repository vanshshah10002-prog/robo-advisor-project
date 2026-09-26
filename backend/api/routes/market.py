"""
Market Data API Routes — ETF Info & Prices
============================================
Endpoints for ETF registry lookup and price data access.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.api.models import ETFInfo, PriceData
from backend.engine.asset_universe import (
    get_all_etfs,
    get_etf_by_ticker,
    get_etfs_by_asset_class,
)
from backend.data.market_data import fetch_prices
from backend.data.prices import get_latest_gbp_price
from backend.data.cache import get_or_fetch_prices
from backend.config import ASSET_CLASSES

router = APIRouter()


@router.get("/etfs")
async def list_etfs(asset_class: Optional[str] = Query(default=None)):
    """
    List all ETFs in the registry, optionally filtered by asset class.

    Parameters:
        asset_class (str, optional): Filter by asset class.

    Returns:
        list[dict]: ETF metadata.
    """
    if asset_class:
        if asset_class not in ASSET_CLASSES:
            raise HTTPException(status_code=400, detail=f"Unknown asset class: {asset_class}")
        return get_etfs_by_asset_class(asset_class)
    return get_all_etfs()


@router.get("/etf/{ticker}", response_model=ETFInfo)
async def get_etf_info(ticker: str):
    """
    Get detailed metadata for a specific ETF.

    Parameters:
        ticker (str): ETF ticker (e.g., "VWRL.L").

    Returns:
        ETFInfo: Full ETF metadata.
    """
    etf = get_etf_by_ticker(ticker)
    if not etf:
        raise HTTPException(status_code=404, detail=f"ETF not found: {ticker}")
    return ETFInfo(**etf)


@router.get("/asset-classes")
async def list_asset_classes():
    """
    List all available asset classes with their primary ETF.
    Dynamically discovers asset classes from the ETF registry.

    Returns:
        list[dict]: Asset classes with descriptions and primary ETF info.
    """
    descriptions = {
        "uk_equity": {"name": "UK Equity", "description": "FTSE 100 — UK large-cap stocks", "risk_level": 4},
        "uk_mid_cap": {"name": "UK Mid-Cap", "description": "FTSE 250 — UK medium companies", "risk_level": 4},
        "global_equity": {"name": "Global Equity", "description": "Worldwide diversified equities", "risk_level": 4},
        "us_equity": {"name": "US Equity", "description": "S&P 500 — US large-cap stocks", "risk_level": 4},
        "us_tech": {"name": "US Tech (NASDAQ)", "description": "NASDAQ-100 — US technology stocks", "risk_level": 5},
        "emerging_market_equity": {"name": "Emerging Markets", "description": "Developing economies — high growth potential", "risk_level": 5},
        "japan_equity": {"name": "Japan Equity", "description": "Japanese stock market — MSCI Japan", "risk_level": 4},
        "europe_equity": {"name": "Europe Equity", "description": "Developed Europe including the UK", "risk_level": 4},
        "europe_ex_uk_equity": {"name": "Europe ex-UK Equity", "description": "Developed Europe — France, Germany, etc.", "risk_level": 4},
        "asia_pacific_equity": {"name": "Asia Pacific ex-Japan", "description": "Australia, Hong Kong, Singapore", "risk_level": 4},
        "uk_bonds": {"name": "UK Government Bonds", "description": "UK gilts — sterling government bonds", "risk_level": 2},
        "uk_gilts": {"name": "UK Gilts (Core)", "description": "Core UK government bonds — safe haven", "risk_level": 1},
        "uk_inflation_linked": {"name": "UK Inflation-Linked", "description": "Index-linked gilts — inflation protection", "risk_level": 2},
        "global_bonds": {"name": "Global Bonds", "description": "International fixed income — GBP hedged", "risk_level": 2},
        "corporate_bonds": {"name": "Corporate Bonds", "description": "Investment-grade corporate debt — higher yield", "risk_level": 3},
        "high_yield_bonds": {"name": "High Yield Bonds", "description": "Sub-investment-grade — significantly higher yield", "risk_level": 4},
        "us_treasury": {"name": "US Treasuries", "description": "US government bonds — 7-10yr duration", "risk_level": 2},
        "commodities_gold": {"name": "Gold", "description": "Physical gold — inflation hedge, safe haven", "risk_level": 3},
        "commodities_silver": {"name": "Silver", "description": "Physical silver — industrial + precious metal", "risk_level": 4},
        "commodities_broad": {"name": "Broad Commodities", "description": "Diversified commodities basket — oil, metals, agriculture", "risk_level": 4},
        "uk_reits": {"name": "UK Real Estate", "description": "UK property investment trusts (REITs)", "risk_level": 4},
        "global_reits": {"name": "Global Real Estate", "description": "Developed markets property yield — global REITs", "risk_level": 4},
        "infrastructure": {"name": "Infrastructure", "description": "Global infrastructure — utilities, transport", "risk_level": 3},
        "cash_equivalent": {"name": "Cash Equivalent", "description": "Ultra-short bonds — near-cash stability", "risk_level": 1},
        "global_dividend": {"name": "Global Dividend", "description": "High dividend yield equities — income focus", "risk_level": 3},
        "uk_dividend": {"name": "UK Dividend", "description": "UK high dividend stocks — FTSE UK Dividend+", "risk_level": 3},
        "esg_global": {"name": "ESG Global", "description": "ESG-screened world equities — sustainable investing", "risk_level": 4},
        "esg_uk": {"name": "ESG UK", "description": "UK ESG leaders — responsible UK exposure", "risk_level": 4},
        "global_small_cap": {"name": "Global Small-Cap", "description": "MSCI World Small Cap — higher growth potential", "risk_level": 5},
        "global_value": {"name": "Value Factor", "description": "Value factor tilt — undervalued stocks", "risk_level": 4},
        "global_momentum": {"name": "Momentum Factor", "description": "Momentum factor tilt — trending stocks", "risk_level": 5},
        "global_quality": {"name": "Quality Factor", "description": "Quality factor tilt — stable, profitable companies", "risk_level": 3},
    }

    # Dynamically discover asset classes from the ETF registry
    all_etfs = get_all_etfs()
    seen_classes = set()
    result = []

    for etf in all_etfs:
        ac = etf["asset_class"]
        if ac in seen_classes:
            continue
        seen_classes.add(ac)

        info = descriptions.get(ac, {"name": ac.replace("_", " ").title(), "description": "", "risk_level": 3})
        etfs_in_class = get_etfs_by_asset_class(ac)
        primary = etfs_in_class[0] if etfs_in_class else None
        result.append({
            "id": ac,
            **info,
            "primary_etf": primary["ticker"] if primary else None,
            "primary_etf_name": primary["name"] if primary else None,
            "expense_ratio": primary["expense_ratio"] if primary else None,
            "factsheet_url": primary.get("factsheet_url") if primary else None,
            "etf_count": len(etfs_in_class),
        })

    return result


@router.get("/prices/{ticker}")
async def get_prices(
    ticker: str,
    period_years: int = Query(default=5, ge=1, le=20),
):
    """
    Get historical price data for an ETF.

    Parameters:
        ticker (str): ETF ticker (e.g., "VWRL.L").
        period_years (int): Years of history (1–20).

    Returns:
        list[PriceData]: OHLCV price history.
    """
    from backend.data.market_data import fetch_prices as _fetch
    df = get_or_fetch_prices(ticker, _fetch, period_years)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")

    return [
        PriceData(
            date=date.isoformat()[:10],
            open=round(row["Open"], 4),
            high=round(row["High"], 4),
            low=round(row["Low"], 4),
            close=round(row["Close"], 4),
            volume=int(row["Volume"]),
        )
        for date, row in df.iterrows()
    ]


@router.get("/price/{ticker}")
async def get_latest_price(ticker: str):
    """
    Latest close for an ETF in GBP per unit — the same price the ledger uses.

    Returns:
        dict: {ticker, price_gbp, as_of}.
    """
    quote = get_latest_gbp_price(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No price available for {ticker}")
    price, as_of = quote
    return {"ticker": ticker, "price_gbp": round(price, 4), "price": round(price, 4),
            "as_of": as_of.isoformat()}
