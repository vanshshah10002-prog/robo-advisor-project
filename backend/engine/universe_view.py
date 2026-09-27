"""
Universe view — the building blocks, in words an investor can read
===================================================================
Every portfolio is assembled from the same core building blocks
(`CORE_UNIVERSE`). For each block this module reports what it is, which
side of the portfolio it sits on (growth or defensive), the policy limit on
it, and the candidate funds in order of preference. Given a portfolio's
holdings it also marks which fund is held and at what weight.

Pure: reads config and the ETF registry only.
"""

from typing import Optional

from backend.config import (
    CORE_UNIVERSE,
    EQUITY_REGION_REFERENCE,
    POLICY_BLOCK_MAX,
    POLICY_CASH_MAX_SHARE_OF_DEFENSIVE,
)
from backend.engine.asset_universe import get_etfs_by_asset_class
from backend.engine.policy import region_bounds, sleeve_of

BLOCK_INFO: dict[str, tuple[str, str]] = {
    "us_equity": ("US shares", "The 500 largest US companies — about half of the world's stock markets by value."),
    "uk_equity": ("UK shares", "The FTSE 100's large UK companies; relatively high dividends, heavy in banks, energy and consumer staples."),
    "europe_ex_uk_equity": ("European shares", "Large and mid-sized companies across developed Europe, excluding the UK."),
    "japan_equity": ("Japanese shares", "Large and mid-sized Japanese companies."),
    "asia_pacific_equity": ("Asia-Pacific shares", "Developed Asia-Pacific outside Japan: mainly Australia, Hong Kong and Singapore."),
    "emerging_market_equity": ("Emerging-market shares", "China, India, Taiwan, Brazil and others: faster-growing economies, bigger swings."),
    "global_reits": ("Global property", "Listed property companies (REITs) around the world; rents behave differently from profits."),
    "commodities_gold": ("Gold", "Physical gold. Often holds up when shares fall, but pays no income."),
    "uk_gilts": ("UK government bonds", "Gilts: lending to the UK government in pounds. The main shock absorber."),
    "uk_inflation_linked": ("Index-linked gilts", "Gilts whose payments rise with UK inflation. Long maturities make them sensitive to interest rates."),
    "global_bonds": ("Global bonds, hedged to £", "Government and company bonds worldwide, with the currency risk removed."),
    "corporate_bonds": ("UK corporate bonds", "Lending to large companies in pounds; a little more income than gilts for a little more risk."),
    "cash_equivalent": ("Cash-like fund", "Tracks the Bank of England overnight rate. Very steady, and the liquidity buffer."),
}


def _rule(asset_class: str, equity_range: Optional[tuple[float, float]]) -> str:
    """One sentence stating the policy limit on this block."""
    if asset_class == "cash_equivalent":
        return f"At most {POLICY_CASH_MAX_SHARE_OF_DEFENSIVE:.0%} of the defensive part."
    if equity_range is not None:
        lo, hi = equity_range
        return f"Kept between {lo:.0%} and {hi:.0%} of the shares, close to its weight in world markets."
    cap = POLICY_BLOCK_MAX.get(asset_class)
    if cap is not None:
        return f"At most {cap:.0%} of the portfolio."
    return "No specific limit beyond the growth/defensive split."


def _fund(etf: dict, preferred: bool) -> dict:
    return {
        "ticker": etf["ticker"],
        "name": etf["name"],
        "expense_ratio": etf["expense_ratio"],
        "currency": etf.get("currency", "GBP"),
        "domicile": etf.get("domicile"),
        "fund_size_gbp_mm": etf.get("fund_size_gbp_mm"),
        "isin": etf.get("isin"),
        "benchmark": etf.get("benchmark"),
        "ucits": bool(etf.get("ucits", False)),
        "factsheet_url": etf.get("factsheet_url"),
        "preferred": preferred,
    }


def build_universe(
    held: Optional[dict[str, dict]] = None,
    targets: Optional[dict[str, float]] = None,
) -> list[dict]:
    """
    The core building blocks, growth first then defensive, each in config order.

    Parameters:
        held: {ticker: {"asset_class", "weight"}} for a portfolio's current holdings.
        targets: {asset_class: target weight} for that portfolio.

    Returns:
        list of blocks: asset_class, name, description, sleeve, rule, max_weight,
        equity_share_range, candidates (funds, preferred first), held_ticker,
        held_weight, target_weight.
    """
    held = held or {}
    targets = targets or {}
    ranges = region_bounds(list(EQUITY_REGION_REFERENCE))
    held_by_class: dict[str, tuple[str, float]] = {}
    for ticker, h in held.items():
        ac = h.get("asset_class", "")
        prev = held_by_class.get(ac)
        weight = float(h.get("weight") or 0.0)
        if prev is None or weight > prev[1]:
            held_by_class[ac] = (ticker, weight)

    blocks = []
    for ac in CORE_UNIVERSE:
        name, description = BLOCK_INFO.get(ac, (ac.replace("_", " ").capitalize(), ""))
        equity_range = ranges.get(ac)
        funds = get_etfs_by_asset_class(ac)
        held_ticker, held_weight = held_by_class.get(ac, (None, None))
        blocks.append({
            "asset_class": ac,
            "name": name,
            "description": description,
            "sleeve": sleeve_of(ac),
            "rule": _rule(ac, equity_range),
            "max_weight": POLICY_BLOCK_MAX.get(ac) if ac != "cash_equivalent" else None,
            "equity_share_range": list(equity_range) if equity_range else None,
            "candidates": [_fund(e, i == 0) for i, e in enumerate(funds)],
            "held_ticker": held_ticker,
            "held_weight": held_weight,
            "target_weight": targets.get(ac),
        })
    order = {"growth": 0, "defensive": 1}
    return sorted(blocks, key=lambda b: order[b["sleeve"]])
