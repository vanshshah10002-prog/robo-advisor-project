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
from backend.config import UK_CGT_HIGHER_RATE

logger = logging.getLogger(__name__)

# Minimum loss threshold to trigger TLH (in GBP)
TLH_MIN_LOSS_GBP: float = 50.0

# Bed-and-breakfast rule: don't re-buy same ticker within 30 days
BED_AND_BREAKFAST_DAYS: int = 30

# UK CGT annual exempt amount (2024/25 onwards)
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
    cgt_rate: float = UK_CGT_HIGHER_RATE,
    realised_gains_ytd: float = 0.0,
    allowance_remaining: float = UK_CGT_ALLOWANCE_GBP,
) -> list[dict]:
    """
    Scan portfolio holdings for tax-loss harvesting (TLH) opportunities.

    A TLH opportunity exists when:
    1. Current price < average cost basis (unrealised loss)
    2. Loss exceeds min_loss threshold
    3. A substitute ETF is available in the registry
    4. Account is NOT an ISA (no CGT inside an ISA)

    IMPORTANT — what TLH actually does (corrected rationale):
    Selling at a loss and buying a correlated substitute does NOT permanently
    eliminate tax: it lowers the substitute's cost basis, so the gain is merely
    DEFERRED. The real, bankable benefit is offsetting *currently realised gains*
    that exceed the annual exempt amount — saving `offsettable_loss × cgt_rate`
    this year — plus the time value of deferral. We therefore only count the
    portion of the loss that offsets net realised gains above the allowance, and
    label it a deferral benefit (not a permanent "saving").

    Parameters:
        holdings (list[dict]): {ticker, quantity, average_cost, current_price, asset_class}
        current_prices (dict[str, float]): {ticker: latest_price}
        is_isa (bool): Whether the portfolio is in an ISA wrapper.
        min_loss (float): Minimum unrealised loss to trigger TLH.
        cgt_rate (float): Investor's marginal CGT rate (basic 0.10 / higher 0.20).
        realised_gains_ytd (float): Net realised capital gains so far this tax year.
        allowance_remaining (float): Unused annual CGT exempt amount.

    Returns:
        list[dict]: opportunities with {..., tax_deferral_benefit}.
    """
    if is_isa:
        logger.info("ISA account — TLH not applicable (no CGT in ISA)")
        return []

    # Net gains that are actually taxable after the annual exempt amount — only
    # losses offsetting THIS are a bankable benefit this year (the rest defers).
    taxable_gains_available = max(0.0, realised_gains_ytd - max(0.0, allowance_remaining))

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

        # Bankable benefit this year = portion of loss that offsets taxable gains
        # (gains above the annual exempt amount), valued at the marginal CGT rate.
        offsettable = min(loss_amount, taxable_gains_available)
        taxable_gains_available -= offsettable
        tax_deferral_benefit = offsettable * cgt_rate

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
            "offsettable_loss": round(offsettable, 2),
            "cgt_rate": cgt_rate,
            "tax_deferral_benefit": round(tax_deferral_benefit, 2),
        })

    # Sort by largest loss first
    opportunities.sort(key=lambda x: x["unrealised_loss"])

    if opportunities:
        total_loss = sum(o["unrealised_loss"] for o in opportunities)
        total_benefit = sum(o["tax_deferral_benefit"] for o in opportunities)
        logger.info(
            f"TLH scan: {len(opportunities)} opportunities, "
            f"total loss=£{abs(total_loss):,.2f}, "
            f"bankable tax benefit this year=£{total_benefit:,.2f} "
            f"(remaining is deferral, not permanent saving)"
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
