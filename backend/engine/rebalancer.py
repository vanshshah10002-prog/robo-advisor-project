"""
Rebalancing Engine — Threshold-Based Portfolio Rebalancing
===========================================================
Monitors portfolio drift and generates rebalancing trades when
any asset class deviates beyond the configured threshold.

Reference: Wealthfront Step 5 — threshold-based rebalancing
to minimise taxes and trading costs.
"""

import logging
from typing import Optional

from backend.config import REBALANCE_DRIFT_THRESHOLD

logger = logging.getLogger(__name__)


def compute_drift(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
) -> dict[str, float]:
    """
    Compute the allocation drift for each asset class.

    Drift = current_weight - target_weight.
    Positive drift means overweight, negative means underweight.

    Parameters:
        current_weights (dict[str, float]): {asset_class: current_weight}.
        target_weights (dict[str, float]): {asset_class: target_weight}.

    Returns:
        dict[str, float]: {asset_class: drift_amount}.
    """
    all_classes = set(list(current_weights.keys()) + list(target_weights.keys()))
    drift = {}
    for ac in all_classes:
        current = current_weights.get(ac, 0.0)
        target = target_weights.get(ac, 0.0)
        drift[ac] = round(current - target, 6)
    return drift


def needs_rebalance(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    threshold: float = REBALANCE_DRIFT_THRESHOLD,
) -> bool:
    """
    Check if any asset class has drifted beyond the threshold.

    Parameters:
        current_weights (dict): Current allocation weights.
        target_weights (dict): Target allocation weights.
        threshold (float): Max allowed drift (default 5%).

    Returns:
        bool: True if rebalancing is needed.
    """
    drift = compute_drift(current_weights, target_weights)
    max_drift = max(abs(d) for d in drift.values()) if drift else 0
    return max_drift > threshold


def max_drift_value(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
) -> float:
    """
    Get the maximum absolute drift across all asset classes.

    Parameters:
        current_weights (dict): Current allocation weights.
        target_weights (dict): Target allocation weights.

    Returns:
        float: Maximum absolute drift.
    """
    drift = compute_drift(current_weights, target_weights)
    return max(abs(d) for d in drift.values()) if drift else 0.0


def generate_rebalance_trades(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    total_portfolio_value: float,
    ticker_map: dict[str, str],
    prices: dict[str, float],
) -> list[dict]:
    """
    Generate the specific trades needed to rebalance the portfolio.

    Strategy:
    - Overweight assets are sold
    - Underweight assets are bought
    - Cash inflows should preferentially buy underweight classes

    Parameters:
        current_weights (dict[str, float]): Current allocation.
        target_weights (dict[str, float]): Target allocation.
        total_portfolio_value (float): Current total portfolio value in GBP.
        ticker_map (dict[str, str]): {asset_class: ticker}.
        prices (dict[str, float]): {ticker: current_price}.

    Returns:
        list[dict]: Trades to execute, each with:
            {ticker, etf_name, action, current_weight, target_weight,
             trade_value_gbp, quantity}
    """
    drift = compute_drift(current_weights, target_weights)
    trades = []

    for ac, drift_val in drift.items():
        if abs(drift_val) < 0.005:  # Skip trivial drifts (<0.5%)
            continue

        ticker = ticker_map.get(ac)
        if not ticker:
            continue

        price = prices.get(ticker, 0)
        if price <= 0:
            continue

        trade_value = abs(drift_val) * total_portfolio_value
        quantity = trade_value / price

        trades.append({
            "ticker": ticker,
            "asset_class": ac,
            "action": "sell" if drift_val > 0 else "buy",
            "current_weight": round(current_weights.get(ac, 0), 4),
            "target_weight": round(target_weights.get(ac, 0), 4),
            "drift": round(drift_val, 4),
            "trade_value_gbp": round(trade_value, 2),
            "quantity": round(quantity, 4),
        })

    # Sort: sells first (to generate cash), then buys
    trades.sort(key=lambda t: (0 if t["action"] == "sell" else 1, -t["trade_value_gbp"]))
    return trades


def allocate_cash_inflow(
    cash_amount: float,
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    ticker_map: dict[str, str],
    prices: dict[str, float],
) -> list[dict]:
    """
    Allocate a cash deposit to underweight asset classes (Wealthfront approach).

    Instead of buying proportionally, directs cash to the most underweight
    classes first, naturally correcting drift without selling.

    Parameters:
        cash_amount (float): Cash to invest in GBP.
        current_weights (dict): Current allocation.
        target_weights (dict): Target allocation.
        ticker_map (dict[str, str]): {asset_class: ticker}.
        prices (dict[str, float]): {ticker: price}.

    Returns:
        list[dict]: Buy orders for underweight asset classes.
    """
    drift = compute_drift(current_weights, target_weights)

    # Sort by most underweight first (most negative drift)
    underweight = [(ac, d) for ac, d in drift.items() if d < -0.005]
    underweight.sort(key=lambda x: x[1])

    if not underweight:
        # No underweight classes; distribute proportionally to targets
        orders = []
        for ac, target in target_weights.items():
            if target <= 0:
                continue
            ticker = ticker_map.get(ac)
            if not ticker:
                continue
            price = prices.get(ticker, 0)
            if price <= 0:
                continue
            amount = cash_amount * target
            orders.append({
                "ticker": ticker,
                "asset_class": ac,
                "action": "buy",
                "trade_value_gbp": round(amount, 2),
                "quantity": round(amount / price, 4),
            })
        return orders

    # Direct cash to underweight classes proportionally to their deficit
    total_deficit = sum(abs(d) for _, d in underweight)
    orders = []

    for ac, deficit in underweight:
        ticker = ticker_map.get(ac)
        if not ticker:
            continue
        price = prices.get(ticker, 0)
        if price <= 0:
            continue

        proportion = abs(deficit) / total_deficit if total_deficit > 0 else 0
        amount = cash_amount * proportion

        orders.append({
            "ticker": ticker,
            "asset_class": ac,
            "action": "buy",
            "trade_value_gbp": round(amount, 2),
            "quantity": round(amount / price, 4),
        })

    return orders
