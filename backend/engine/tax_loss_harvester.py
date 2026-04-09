"""
Tax-Loss Harvesting Module
============================
Identifies tax-loss harvesting (TLH) opportunities and generates
substitute ETF swap trades.

Per Wealthfront methodology:
"Sell investments that declined below their purchase price to create
a tax loss, then purchase a highly correlated substitute asset to
maintain market exposure while capturing the tax benefit."

UK-specific rules:
- CGT allowance: £3,000/year (2024/25)
- No wash sale rule in UK, but HMRC has a 30-day bed-and-breakfast rule
- ISA accounts are exempt (no CGT in ISA)

Reference:
    - WL_WealthManagement.pdf (Tax-Loss Harvesting section)
    - uk_etf_registry.json (tlh_substitute field per ETF)
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from backend.engine.asset_universe import get_all_etfs

logger = logging.getLogger(__name__)

# Minimum loss threshold to trigger TLH (in GBP)
TLH_MIN_LOSS_GBP: float = 50.0

# Bed-and-breakfast rule: don't re-buy same ticker within 30 days
BED_AND_BREAKFAST_DAYS: int = 30

# UK CGT annual allowance
UK_CGT_ALLOWANCE_GBP: float = 3000.0


def get_tlh_substitute(ticker: str) -> Optional[str]:
    """
    Get the TLH substitute ticker for a given ETF from the registry.

    The substitute should be highly correlated but track a different index
    to avoid the HMRC bed-and-breakfast rule.

    Parameters:
        ticker (str): Current ETF ticker.

    Returns:
        str or None: Substitute ticker, or None if no substitute available.
    """
    registry = get_all_etfs()
    for etf in registry:
        if etf["ticker"] == ticker:
            sub = etf.get("tlh_substitute")
            return sub if sub else None
    return None


def scan_for_tlh_opportunities(
    holdings: list[dict],
    current_prices: dict[str, float],
    is_isa: bool = False,
    min_loss: float = TLH_MIN_LOSS_GBP,
) -> list[dict]:
    """
    Scan portfolio holdings for tax-loss harvesting opportunities.

    A TLH opportunity exists when:
    1. Current price < average cost basis (unrealised loss)
    2. Loss exceeds min_loss threshold
    3. A substitute ETF is available in the registry
    4. Account is NOT an ISA (no CGT in ISA)

    Parameters:
        holdings (list[dict]): Current holdings, each with:
            {ticker, quantity, average_cost, current_price, asset_class}
        current_prices (dict[str, float]): {ticker: latest_price}
        is_isa (bool): Whether the portfolio is in an ISA wrapper.
        min_loss (float): Minimum unrealised loss to trigger TLH.

    Returns:
        list[dict]: TLH opportunities, each with:
            {ticker, substitute_ticker, unrealised_loss, quantity,
             current_value, cost_basis, tax_saving_estimate}
    """
    if is_isa:
        logger.info("ISA account — TLH not applicable (no CGT in ISA)")
        return []

    opportunities = []

    for holding in holdings:
        ticker = holding.get("ticker", "")
        quantity = holding.get("quantity", 0)
        avg_cost = holding.get("average_cost", 0)
        current_price = current_prices.get(ticker, 0) or holding.get("current_price", 0)

        if not ticker or quantity <= 0 or avg_cost <= 0 or current_price <= 0:
            continue

        # Calculate unrealised loss
        cost_basis = quantity * avg_cost
        current_value = quantity * current_price
        unrealised_pnl = current_value - cost_basis

        # Only interested in losses
        if unrealised_pnl >= 0:
            continue

        loss_amount = abs(unrealised_pnl)
        if loss_amount < min_loss:
            continue

        # Check for substitute
        substitute = get_tlh_substitute(ticker)
        if not substitute:
            logger.debug(f"No TLH substitute for {ticker} — skipping")
            continue

        # Estimate tax saving (20% CGT rate × loss)
        tax_saving = loss_amount * 0.20

        opportunities.append({
            "ticker": ticker,
            "asset_class": holding.get("asset_class", ""),
            "substitute_ticker": substitute,
            "quantity": quantity,
            "average_cost": round(avg_cost, 2),
            "current_price": round(current_price, 2),
            "cost_basis": round(cost_basis, 2),
            "current_value": round(current_value, 2),
            "unrealised_loss": round(-loss_amount, 2),
            "tax_saving_estimate": round(tax_saving, 2),
        })

    # Sort by largest loss first
    opportunities.sort(key=lambda x: x["unrealised_loss"])

    if opportunities:
        total_loss = sum(o["unrealised_loss"] for o in opportunities)
        total_saving = sum(o["tax_saving_estimate"] for o in opportunities)
        logger.info(
            f"TLH scan: {len(opportunities)} opportunities, "
            f"total loss=£{abs(total_loss):,.2f}, "
            f"potential tax saving=£{total_saving:,.2f}"
        )

    return opportunities


def generate_tlh_trades(
    opportunities: list[dict],
    current_prices: dict[str, float],
    recently_sold: Optional[dict[str, datetime]] = None,
) -> list[dict]:
    """
    Generate the sell/buy trade pairs for TLH execution.

    For each opportunity:
    1. SELL the loss-making position
    2. BUY the substitute ETF with the same value

    Respects the 30-day bed-and-breakfast rule.

    Parameters:
        opportunities (list[dict]): From scan_for_tlh_opportunities.
        current_prices (dict[str, float]): Current prices for substitute ETFs.
        recently_sold (dict, optional): {ticker: sell_date} to enforce B&B rule.

    Returns:
        list[dict]: Trade pairs for execution.
    """
    if recently_sold is None:
        recently_sold = {}

    trades = []
    now = datetime.now()

    for opp in opportunities:
        ticker = opp["ticker"]
        substitute = opp["substitute_ticker"]

        # Check bed-and-breakfast rule
        last_sold = recently_sold.get(ticker)
        if last_sold and (now - last_sold).days < BED_AND_BREAKFAST_DAYS:
            logger.info(
                f"Skipping TLH for {ticker} — sold {(now - last_sold).days} days ago "
                f"(B&B rule: {BED_AND_BREAKFAST_DAYS} days)"
            )
            continue

        sub_price = current_prices.get(substitute, 0)
        if sub_price <= 0:
            logger.warning(f"No price for substitute {substitute} — skipping")
            continue

        trade_value = opp["current_value"]
        sub_quantity = trade_value / sub_price

        trades.append({
            "step": "sell",
            "ticker": ticker,
            "quantity": opp["quantity"],
            "price": opp["current_price"],
            "value": trade_value,
            "reason": "tax_loss_harvest",
            "unrealised_loss": opp["unrealised_loss"],
        })

        trades.append({
            "step": "buy",
            "ticker": substitute,
            "quantity": round(sub_quantity, 4),
            "price": sub_price,
            "value": round(trade_value, 2),
            "reason": "tlh_substitute",
            "replaces": ticker,
        })

    logger.info(f"Generated {len(trades)} TLH trades ({len(trades)//2} pairs)")
    return trades
