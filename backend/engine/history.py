"""
Portfolio history — value over time, replayed from the ledger
==============================================================
Rebuilds a portfolio's daily value from its own transactions and daily GBP
closes. Nothing is simulated: on each day the units held after that day's
trades are valued at that day's close (or the last close before it).

Returns are time-weighted, so a deposit does not show up as "growth":

    r_t = (V_t − V_{t−1} − F_t) / (V_{t−1} + F_t)

with F_t the external cash flow on day t (deposits positive, withdrawals
negative) assumed to arrive at the start of the day. On the first day
V_{−1} = 0, so r_0 = V_0 / F_0 − 1 captures the opening trading costs.

Pure: no database, no network.
"""

import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd

EXTERNAL_FLOWS = {"deposit": 1.0, "withdrawal": -1.0}


@dataclass(frozen=True)
class Trade:
    """One ledger row, reduced to what the replay needs."""
    day: datetime.date
    ticker: str
    action: str       # buy | sell | deposit | withdrawal | dividend
    units: float
    price: float      # GBP per unit (1.0 for cash rows)
    value: float      # GBP, gross
    cost: float       # GBP


def _cash_effect(t: Trade) -> float:
    if t.action == "buy":
        return -(t.value + t.cost)
    if t.action == "sell":
        return t.value - t.cost
    if t.action == "deposit" or t.action == "dividend":
        return t.value
    if t.action == "withdrawal":
        return -t.value
    return 0.0


def _unit_effect(t: Trade) -> float:
    if t.action == "buy":
        return t.units
    if t.action == "sell":
        return -t.units
    return 0.0


def price_panel(trades: list[Trade], closes: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Daily GBP prices on `calendar` for every traded ticker: the market close
    where there is one, otherwise the trade price on a trade day, carried
    forward. Never back-filled: before its first observation a ticker is NaN.
    """
    tickers = sorted({t.ticker for t in trades if t.action in ("buy", "sell")})
    panel = closes.reindex(columns=tickers).reindex(calendar)
    for t in trades:
        if t.action not in ("buy", "sell") or t.price <= 0:
            continue
        ts = pd.Timestamp(t.day)
        if ts in panel.index and pd.isna(panel.at[ts, t.ticker]):
            panel.at[ts, t.ticker] = t.price
    return panel.ffill()


def replay(trades: list[Trade], closes: pd.DataFrame, end: datetime.date) -> pd.DataFrame:
    """
    Daily value series from the first trade to `end`.

    Parameters:
        trades: every ledger row, any order.
        closes: daily GBP closes, index = dates, columns = tickers (NaN = no print).
        end: last day to value (usually today).

    Returns:
        DataFrame indexed by date with columns value, invested, cash,
        net_contributions and cumulative_return (time-weighted, a fraction).
        Empty when there are no trades.
    """
    if not trades:
        return pd.DataFrame(columns=["value", "invested", "cash", "net_contributions", "cumulative_return"])
    trades = sorted(trades, key=lambda t: t.day)
    start = pd.Timestamp(trades[0].day)
    stop = pd.Timestamp(max(end, trades[-1].day))

    market_days = closes.index[(closes.index >= start) & (closes.index <= stop)] if len(closes.index) else []
    trade_days = pd.DatetimeIndex([pd.Timestamp(t.day) for t in trades])
    calendar = pd.DatetimeIndex(sorted(set(market_days) | set(trade_days)))
    prices = price_panel(trades, closes, calendar)

    by_day: dict[pd.Timestamp, list[Trade]] = {}
    for t in trades:
        by_day.setdefault(pd.Timestamp(t.day), []).append(t)

    units: dict[str, float] = {}
    cash = 0.0
    contributed = 0.0
    prev_value = 0.0
    growth = 1.0
    rows = []
    for day in calendar:
        flow = 0.0
        for t in by_day.get(day, []):
            cash += _cash_effect(t)
            units[t.ticker] = units.get(t.ticker, 0.0) + _unit_effect(t)
            sign = EXTERNAL_FLOWS.get(t.action)
            if sign is not None:
                flow += sign * t.value
                contributed += sign * t.value
        row_prices = prices.loc[day]
        invested = float(sum(u * row_prices[tk] for tk, u in units.items()
                             if abs(u) > 1e-12 and tk in row_prices.index and not np.isnan(row_prices[tk])))
        value = invested + cash
        base = prev_value + flow
        if base > 0:
            growth *= 1.0 + (value - prev_value - flow) / base
        rows.append((day, value, invested, cash, contributed, growth - 1.0))
        prev_value = value

    out = pd.DataFrame(rows, columns=["date", "value", "invested", "cash", "net_contributions", "cumulative_return"])
    return out.set_index("date")
