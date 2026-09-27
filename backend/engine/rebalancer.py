"""
Rebalancing Engine — tolerance bands, cash-flow first, netted trades
====================================================================
Pure functions: they take weights/values in GBP and return a drift report or
a trade plan. The API layer supplies ledger values and executes the plan.

Method (see docs/PORTFOLIO_REMEDIATION_PLAN.md, P6/P7):

Triggers (any one):
  1. A holding is outside its tolerance band
         band(target) = max(MIN_BAND, min(ABS_BAND, REL_BAND × target))
     i.e. ±5pp for large sleeves, ±25% of target for small ones, never below
     ±1pp. Absolute bands alone let small sleeves double or vanish unnoticed
     (Vanguard: ~5pp; Daryanani 2008: ~20–25% relative bands).
  2. Portfolio drift  ½·Σ|current − target|  exceeds 3% (Betterment's measure
     and default threshold).
  3. A group (e.g. growth assets) is outside its policy range.

Execution:
  - Reactive: new cash buys the most underweight holdings first; only what is
    left after every deficit is filled goes pro rata to target.
  - Proactive: trade to target, drop trades below the minimum size, then scale
    buys so they are fully funded by sell proceeds (after costs) plus cash.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from backend.config import (
    REBALANCE_ABS_BAND,
    REBALANCE_REL_BAND,
    REBALANCE_MIN_BAND,
    REBALANCE_PORTFOLIO_DRIFT,
    REBALANCE_MIN_TRADE_GBP,
    REBALANCE_MIN_TRADE_PCT,
    TRANSACTION_COST_BPS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DRIFT
# =============================================================================

def tolerance_band(target: float) -> float:
    """Allowed |current − target| for a holding with this target weight."""
    return max(REBALANCE_MIN_BAND, min(REBALANCE_ABS_BAND, REBALANCE_REL_BAND * target))


def compute_drift(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
) -> dict[str, float]:
    """current − target for every key in either dict (missing counts as 0)."""
    keys = set(current_weights) | set(target_weights)
    return {k: round(current_weights.get(k, 0.0) - target_weights.get(k, 0.0), 6) for k in keys}


def portfolio_drift(current_weights: dict[str, float], target_weights: dict[str, float]) -> float:
    """Betterment's portfolio drift: half the sum of absolute drifts (= one-way turnover)."""
    return 0.5 * sum(abs(d) for d in compute_drift(current_weights, target_weights).values())


def max_drift_value(current_weights: dict[str, float], target_weights: dict[str, float]) -> float:
    """Largest absolute drift of any single holding."""
    d = compute_drift(current_weights, target_weights)
    return max((abs(v) for v in d.values()), default=0.0)


@dataclass
class DriftReport:
    drift: dict[str, float]
    bands: dict[str, float]
    out_of_band: list[str]
    portfolio_drift: float
    group_weights: dict[str, float] = field(default_factory=dict)
    groups_out_of_range: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_rebalance(self) -> bool:
        return bool(self.reasons)


def check_drift(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    group_of: Optional[dict[str, str]] = None,
    group_ranges: Optional[dict[str, tuple[float, float]]] = None,
) -> DriftReport:
    """
    Evaluate all three triggers.

    Parameters:
        current_weights / target_weights: {ticker: weight}. Uninvested cash is
            simply absent from current_weights, so it shows up as underweight.
        group_of: optional {ticker: group}.
        group_ranges: optional {group: (min, max)} policy ranges.
    """
    drift = compute_drift(current_weights, target_weights)
    bands = {k: tolerance_band(target_weights.get(k, 0.0)) for k in drift}
    out = sorted(k for k, d in drift.items() if abs(d) > bands[k] + 1e-12)
    pdrift = portfolio_drift(current_weights, target_weights)

    reasons = []
    if out:
        reasons.append(f"{len(out)} holding(s) outside tolerance band: {', '.join(out)}")
    if pdrift > REBALANCE_PORTFOLIO_DRIFT:
        reasons.append(f"portfolio drift {pdrift:.1%} exceeds {REBALANCE_PORTFOLIO_DRIFT:.0%}")

    group_w: dict[str, float] = {}
    groups_out: list[str] = []
    if group_of and group_ranges:
        for t, w in current_weights.items():
            g = group_of.get(t)
            if g:
                group_w[g] = group_w.get(g, 0.0) + w
        for g, (lo, hi) in group_ranges.items():
            w = group_w.get(g, 0.0)
            if w < lo - 1e-9 or w > hi + 1e-9:
                groups_out.append(g)
                reasons.append(f"{g} weight {w:.1%} outside policy range {lo:.0%}–{hi:.0%}")

    return DriftReport(drift, bands, out, pdrift, group_w, groups_out, reasons)


# =============================================================================
# TRADE PLANNING
# =============================================================================

def min_trade_size(total_value: float) -> float:
    return max(REBALANCE_MIN_TRADE_GBP, REBALANCE_MIN_TRADE_PCT * total_value)


def plan_inflow(
    cash: float,
    values: dict[str, float],
    target_weights: dict[str, float],
) -> dict[str, float]:
    """
    Split new cash across buys so it corrects drift before anything else.

    Deficit_i = target_i × (portfolio value + cash) − value_i  (only positive ones).
    If cash covers all deficits, fill them and spread the rest by target
    weight; otherwise share the cash in proportion to the deficits.

    Returns:
        {ticker: GBP to buy}; sums to `cash`.
    """
    if cash <= 0:
        return {}
    total_after = sum(values.values()) + cash
    deficits = {
        t: w * total_after - values.get(t, 0.0)
        for t, w in target_weights.items()
        if w * total_after - values.get(t, 0.0) > 1e-9
    }
    need = sum(deficits.values())
    if need <= 0:
        tw = sum(target_weights.values())
        return {t: cash * w / tw for t, w in target_weights.items() if w > 0}
    if cash <= need:
        return {t: cash * d / need for t, d in deficits.items()}
    # Every deficit filled; spread what is left by target weight.
    rest = cash - need
    tw = sum(target_weights.values())
    out = dict(deficits)
    for t, w in target_weights.items():
        if w > 0:
            out[t] = out.get(t, 0.0) + rest * w / tw
    return out


@dataclass
class PlannedTrade:
    ticker: str
    action: str             # "buy" | "sell"
    value_gbp: float        # gross trade value
    units: float
    price: float
    current_weight: float
    target_weight: float
    est_cost_gbp: float
    est_realised_gain_gbp: float = 0.0


def plan_rebalance(
    values: dict[str, float],
    cash: float,
    target_weights: dict[str, float],
    prices: dict[str, float],
    avg_cost: Optional[dict[str, float]] = None,
    cost_bps: float = TRANSACTION_COST_BPS,
) -> list[PlannedTrade]:
    """
    Trades that move every holding to target, funded internally.

    - Holdings not in the target are sold in full.
    - Trades smaller than the minimum size are skipped.
    - Buys are scaled so that Σbuys = cash + Σsells × (1 − cost); the plan
      never needs money the portfolio does not have.

    Raises:
        ValueError: if a ticker that needs trading has no price.
    """
    total = sum(values.values()) + cash
    if total <= 0:
        return []
    c = cost_bps / 10_000.0
    floor = min_trade_size(total)
    current_w = {t: v / total for t, v in values.items()}

    raw = {}
    for t in set(values) | set(target_weights):
        delta = target_weights.get(t, 0.0) * total - values.get(t, 0.0)
        if t not in target_weights and values.get(t, 0.0) > 0:
            delta = -values[t]  # exit fully, whatever its size
        elif abs(delta) < floor:
            continue
        if abs(delta) > 1e-9:
            raw[t] = delta

    no_price = [t for t in raw if not prices.get(t)]
    if no_price:
        raise ValueError(f"Cannot plan trades without prices for: {', '.join(sorted(no_price))}")

    sells = {t: -d for t, d in raw.items() if d < 0}
    buys = {t: d for t, d in raw.items() if d > 0}
    funding = cash + sum(sells.values()) * (1 - c)
    want = sum(buys.values())
    scale = min(1.0, funding / want) if want > 0 else 0.0

    trades = []
    for t, v in sorted(sells.items(), key=lambda kv: -kv[1]):
        units = v / prices[t]
        gain = 0.0
        if avg_cost and t in avg_cost:
            gain = v * (1 - c) - units * avg_cost[t]
        trades.append(PlannedTrade(t, "sell", v, units, prices[t],
                                   current_w.get(t, 0.0), target_weights.get(t, 0.0),
                                   v * c, gain))
    for t, v in sorted(buys.items(), key=lambda kv: -kv[1]):
        v = v * scale
        if v <= 1e-9:
            continue
        trades.append(PlannedTrade(t, "buy", v, v * (1 - c) / prices[t], prices[t],
                                   current_w.get(t, 0.0), target_weights.get(t, 0.0),
                                   v * c))
    return trades
