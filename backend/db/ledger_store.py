"""
Ledger persistence — moves a portfolio's book between the ORM rows and the
pure `backend.engine.ledger.Book`, and records fills as Transactions.
"""

import datetime
import logging

from sqlalchemy.orm import Session

from backend.db.models import Holding, Portfolio, Transaction
from backend.engine.ledger import Book, Fill

logger = logging.getLogger(__name__)


def is_legacy_holding(h: Holding) -> bool:
    """
    Portfolios created before the ledger stored the GBP amount in `quantity`
    and never recorded a price, so they have no unit count or cost basis.
    """
    return (h.average_cost or 0.0) <= 0.0 and (h.quantity or 0.0) > 0.0


def upgrade_legacy_holdings(holdings: list[Holding], prices: dict[str, float]) -> list[str]:
    """
    Convert legacy rows to units at today's price. The original purchase price
    is unknown, so the cost basis is set to today's price and past performance
    starts from zero. Returns the tickers converted.
    """
    converted = []
    for h in holdings:
        if is_legacy_holding(h) and h.ticker in prices:
            amount_gbp = h.quantity
            h.quantity = amount_gbp / prices[h.ticker]
            h.average_cost = prices[h.ticker]
            converted.append(h.ticker)
    if converted:
        logger.warning(f"Converted legacy GBP-amount holdings to units at current price: {converted}")
    return converted


def load_book(portfolio: Portfolio, holdings: list[Holding]) -> Book:
    """Build a Book from the portfolio's holding rows (legacy rows excluded)."""
    book = Book(cash=float(portfolio.cash_gbp or 0.0))
    for h in holdings:
        if is_legacy_holding(h) or (h.quantity or 0.0) <= 0:
            continue
        book.units[h.ticker] = float(h.quantity)
        book.avg_cost[h.ticker] = float(h.average_cost)
    return book


def save_book(db: Session, portfolio: Portfolio, holdings: list[Holding], book: Book,
              asset_class_of: dict[str, str]) -> None:
    """
    Write units, cost basis and cash back. Rows for tickers no longer held are
    kept at zero units so their target weight stays visible; new tickers get rows.
    """
    by_ticker = {h.ticker: h for h in holdings}
    for t, u in book.units.items():
        h = by_ticker.get(t)
        if h is None:
            h = Holding(
                portfolio_id=portfolio.id, ticker=t,
                asset_class=asset_class_of.get(t, "unknown"),
                target_weight=0.0,
            )
            db.add(h)
            by_ticker[t] = h
        h.quantity = u
        h.average_cost = book.avg_cost.get(t, 0.0)
    for t, h in by_ticker.items():
        if t not in book.units:
            h.quantity = 0.0
    portfolio.cash_gbp = book.cash


def record_fills(db: Session, portfolio_id: int, fills: list[Fill], notes: str) -> None:
    now = datetime.datetime.utcnow()
    for f in fills:
        db.add(Transaction(
            portfolio_id=portfolio_id, ticker=f.ticker, action=f.action,
            quantity=f.units, price=f.price, value=f.value,
            cost=f.cost, realised_gain=f.realised_gain,
            timestamp=now, notes=notes,
        ))


def apply_prices(holdings: list[Holding], quotes: dict[str, tuple[float, datetime.date]]) -> list[str]:
    """
    Store the latest prices on the rows. Returns tickers held with units but
    no fresh quote — these keep their previous price and are reported stale.
    """
    stale = []
    for h in holdings:
        q = quotes.get(h.ticker)
        if q is not None:
            h.current_price = q[0]
            h.price_as_of = datetime.datetime.combine(q[1], datetime.time())
        elif (h.quantity or 0.0) > 0:
            stale.append(h.ticker)
    return stale


def last_prices(holdings: list[Holding]) -> dict[str, float]:
    """Last stored GBP price per ticker (only rows that have one)."""
    return {h.ticker: h.current_price for h in holdings if h.current_price}


def mark_to_market(portfolio: Portfolio, holdings: list[Holding], fetch: bool = True) -> dict:
    """
    Value a portfolio from its ledger and store the result on the rows.

    Parameters:
        fetch: True pulls the latest GBP prices first; False values at the last
            stored prices (no network).

    Returns:
        dict: valuation (see engine.ledger.valuation) plus `stale_tickers`
        (held but not freshly priced), `unpriced_tickers` (no price ever — the
        valuation excludes them and says so) and `total_return_pct`.
    """
    from backend.data.prices import get_latest_gbp_prices
    from backend.engine.ledger import valuation

    stale: list[str] = []
    if fetch:
        wanted = [h.ticker for h in holdings if (h.quantity or 0.0) > 0]
        quotes = get_latest_gbp_prices(wanted)
        converted = upgrade_legacy_holdings(holdings, {t: q[0] for t, q in quotes.items()})
        if converted and not portfolio.net_contributions:
            # Legacy portfolio: no record of what was paid, so returns start today.
            portfolio.net_contributions = sum(
                h.quantity * quotes[h.ticker][0] for h in holdings if h.ticker in converted
            ) + (portfolio.cash_gbp or 0.0)
        stale = apply_prices(holdings, quotes)

    book = load_book(portfolio, holdings)
    prices = last_prices(holdings)
    unpriced = [t for t in book.units if t not in prices]
    for t in unpriced:
        book.units.pop(t)
    val = valuation(book, prices)

    for h in holdings:
        h.current_weight = val["weights"].get(h.ticker, 0.0)

    contrib = portfolio.net_contributions or 0.0
    total_return = (val["total"] - contrib) / contrib if contrib > 0 else 0.0
    portfolio.total_return_pct = total_return
    portfolio.last_valued_at = datetime.datetime.utcnow()

    val.update({
        "stale_tickers": stale,
        "unpriced_tickers": unpriced,
        "total_return_pct": total_return,
        "net_contributions": contrib,
    })
    return val
