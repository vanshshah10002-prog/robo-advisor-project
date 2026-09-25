"""
Holdings Ledger — units, cost basis and mark-to-market valuation
=================================================================
Pure functions (no database, no network) that keep a portfolio's book:

    position  = units held of one ETF
    avg_cost  = GBP paid per unit, average-cost basis (UK section 104 pooling)
    cash      = uninvested GBP (rounding, trading costs, unallocated inflows)

Values are always units × latest GBP price. Nothing here estimates or
simulates a return: if a price is missing the caller passes the last known
price and flags the ticker as stale.
"""

from dataclasses import dataclass, field

from backend.config import TRANSACTION_COST_BPS


@dataclass
class Book:
    """A portfolio's positions. `units` and `avg_cost` are keyed by ticker."""
    units: dict[str, float] = field(default_factory=dict)
    avg_cost: dict[str, float] = field(default_factory=dict)
    cash: float = 0.0


@dataclass
class Fill:
    """One executed trade."""
    ticker: str
    action: str          # "buy" | "sell"
    units: float
    price: float         # GBP per unit
    value: float         # units × price (gross, before cost)
    cost: float          # trading cost in GBP
    realised_gain: float = 0.0


def _cost(value: float, cost_bps: float) -> float:
    return abs(value) * cost_bps / 10_000.0


def valuation(book: Book, prices: dict[str, float]) -> dict:
    """
    Mark the book to market.

    Parameters:
        book: positions and cash.
        prices: {ticker: GBP price}. Every held ticker must be present — pass the
            last known price for tickers whose live price is unavailable.

    Returns:
        dict with `values` {ticker: GBP}, `invested` (sum of values), `cash`,
        `total` (invested + cash) and `weights` {ticker: value / total}.
    """
    missing = [t for t, u in book.units.items() if u > 0 and t not in prices]
    if missing:
        raise ValueError(f"No price for held tickers: {missing}")

    values = {t: u * prices[t] for t, u in book.units.items() if u > 0}
    invested = sum(values.values())
    total = invested + book.cash
    weights = {t: v / total for t, v in values.items()} if total > 0 else {}
    return {
        "values": values,
        "invested": invested,
        "cash": book.cash,
        "total": total,
        "weights": weights,
    }


def buy(book: Book, ticker: str, value_gbp: float, price: float,
        cost_bps: float = TRANSACTION_COST_BPS) -> Fill:
    """
    Spend `value_gbp` of cash on `ticker` (trading cost included in that spend).
    Updates average cost. Cash may not go negative beyond rounding.
    """
    if value_gbp <= 0 or price <= 0:
        raise ValueError("buy needs a positive value and price")
    if value_gbp > book.cash + 1e-6:
        raise ValueError(f"Insufficient cash: need £{value_gbp:.2f}, have £{book.cash:.2f}")

    cost = _cost(value_gbp, cost_bps)
    gross = value_gbp - cost
    units = gross / price

    old_u = book.units.get(ticker, 0.0)
    old_c = book.avg_cost.get(ticker, 0.0)
    new_u = old_u + units
    # Cost basis includes dealing costs (allowable for UK CGT).
    book.avg_cost[ticker] = (old_u * old_c + value_gbp) / new_u
    book.units[ticker] = new_u
    book.cash -= value_gbp
    return Fill(ticker, "buy", units, price, gross, cost)


def sell(book: Book, ticker: str, value_gbp: float, price: float,
         cost_bps: float = TRANSACTION_COST_BPS) -> Fill:
    """
    Sell `value_gbp` worth (gross) of `ticker`; proceeds net of cost go to cash.
    Realised gain uses average cost (section 104 pool).
    """
    held = book.units.get(ticker, 0.0)
    if value_gbp <= 0 or price <= 0:
        raise ValueError("sell needs a positive value and price")
    units = min(value_gbp / price, held)
    if units <= 0:
        raise ValueError(f"No units of {ticker} to sell")

    gross = units * price
    cost = _cost(gross, cost_bps)
    basis = units * book.avg_cost.get(ticker, 0.0)
    realised = gross - cost - basis

    book.units[ticker] = held - units
    if book.units[ticker] <= 1e-9:
        book.units.pop(ticker)
        book.avg_cost.pop(ticker, None)
    book.cash += gross - cost
    return Fill(ticker, "sell", units, price, gross, cost, realised)


def open_portfolio(amount_gbp: float, target_weights: dict[str, float],
                   prices: dict[str, float],
                   cost_bps: float = TRANSACTION_COST_BPS) -> tuple[Book, list[Fill]]:
    """
    Invest a lump sum at target weights. Every target ticker needs a price.

    Returns:
        (book, fills). Leftover cash is only floating-point dust.
    """
    missing = [t for t, w in target_weights.items() if w > 0 and t not in prices]
    if missing:
        raise ValueError(f"No price for: {missing}")
    book = Book(cash=float(amount_gbp))
    fills = []
    for t, w in target_weights.items():
        if w <= 0:
            continue
        fills.append(buy(book, t, amount_gbp * w, prices[t], cost_bps))
    if abs(book.cash) < 1e-6:
        book.cash = 0.0
    return book, fills
