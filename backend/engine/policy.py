"""
Allocation Policy — risk score → constraints on the optimiser
==============================================================
The policy decides HOW MUCH risk (the growth share and the limits around it);
the optimiser only decides the MIX inside those limits. This keeps a given
risk score meaning the same thing over time, whatever recent returns did.

Constraints (docs/PORTFOLIO_REMEDIATION_PLAN.md §2.5):
  growth share      G = 10% × risk at construction (clipped to [0, 1]);
                    the portfolio may then drift ±5pp before a rebalance
  cash              ≤ 50% of the defensive sleeve
  regional equity   ≥ 75% of the growth sleeve
  each region       share of equity within reference ± max(5pp, 30% × ref);
                    UK within 10–25% of equity
  blocks            per-block maxima (gilts 35%, linkers 20%, hedged agg 35%,
                    IG credit 20%, property 10%, gold 5%)
All are linear, so pypfopt/cvxpy solves them exactly.
"""

from typing import Optional

import numpy as np

from backend.config import (
    ALLOCATION_CONSTRAINTS,
    BOND_ASSET_CLASSES,
    CASH_ASSET_CLASSES,
    CRISIS_CASH_BUFFER,
    EQUITY_REGION_REFERENCE,
    DEFENSIVE_ASSET_CLASSES,
    POLICY_BLOCK_MAX,
    POLICY_CASH_MAX_SHARE_OF_DEFENSIVE,
    POLICY_EQUITY_MIN_SHARE_OF_GROWTH,
    POLICY_GROWTH_PER_RISK_POINT,
    POLICY_GROWTH_TOLERANCE,
    REGION_BAND_ABS,
    REGION_BAND_REL,
    UK_EQUITY_SHARE_RANGE,
)


def sleeve_of(asset_class: str) -> str:
    """'growth' or 'defensive'. Satellite bond classes are defensive; everything else growth."""
    if asset_class in DEFENSIVE_ASSET_CLASSES or asset_class in BOND_ASSET_CLASSES \
            or asset_class in CASH_ASSET_CLASSES:
        return "defensive"
    return "growth"


def growth_target(risk_score: float) -> float:
    """Strategic growth share for a risk score (10% per point)."""
    return float(np.clip(POLICY_GROWTH_PER_RISK_POINT * risk_score, 0.0, 1.0))


def growth_range(risk_score: float, crisis: bool = False) -> tuple[float, float]:
    """
    Growth share the optimiser must hit when BUILDING a portfolio: exactly the
    target. A tolerance here would not be used as slack — a single risk
    aversion λ pushes every portfolio to the edge nearest the λ-optimal mix
    (up at low risk, down at high risk). In a crisis regime (overlay enabled)
    the target drops by CRISIS_CASH_BUFFER inside the optimiser, so every other
    constraint still holds.
    """
    g = growth_target(risk_score)
    if crisis:
        g = max(0.0, g - CRISIS_CASH_BUFFER)
    return g, g


def growth_tolerance_range(target_growth: float) -> tuple[float, float]:
    """Range the growth share may drift within before rebalancing (±5pp)."""
    return (max(0.0, target_growth - POLICY_GROWTH_TOLERANCE),
            min(1.0, target_growth + POLICY_GROWTH_TOLERANCE))


def region_bounds(present_regions: list[str]) -> dict[str, tuple[float, float]]:
    """
    Min/max share of total equity for each region present. The reference is
    renormalised over the regions actually available (if one had no data),
    so the bounds stay feasible.
    """
    ref = {r: EQUITY_REGION_REFERENCE[r] for r in present_regions if r in EQUITY_REGION_REFERENCE}
    total = sum(ref.values())
    if total <= 0:
        return {}
    out = {}
    for r, w in ref.items():
        w = w / total
        band = max(REGION_BAND_ABS, REGION_BAND_REL * w)
        out[r] = (max(0.0, w - band), min(1.0, w + band))
    if "uk_equity" in out:
        lo, hi = UK_EQUITY_SHARE_RANGE
        ref_uk = ref["uk_equity"] / total
        out["uk_equity"] = (min(lo, ref_uk), max(hi, ref_uk))
    # Guarantee feasibility after renormalisation: Σlo ≤ 1 ≤ Σhi.
    if sum(lo for lo, _ in out.values()) > 1.0 or sum(hi for _, hi in out.values()) < 1.0:
        return {r: (0.0, 1.0) for r in out}
    return out


def weight_bounds(tickers: list[str], asset_class_of: dict[str, str]) -> list[tuple[float, float]]:
    """Per-ticker (min, max): policy block maxima for core blocks, config caps for satellites."""
    bounds = []
    for t in tickers:
        ac = asset_class_of.get(t, "")
        if ac in POLICY_BLOCK_MAX:
            hi = POLICY_BLOCK_MAX[ac]
        elif ac in EQUITY_REGION_REFERENCE:
            hi = 1.0
        else:
            hi = ALLOCATION_CONSTRAINTS.get(ac, {"max": 0.10})["max"]
        bounds.append((0.0, hi))
    return bounds


def add_policy_constraints(
    ef,
    tickers: list[str],
    asset_class_of: dict[str, str],
    growth_rng: Optional[tuple[float, float]] = None,
) -> None:
    """
    Attach the policy's linear constraints to a pypfopt EfficientFrontier.

    Parameters:
        growth_rng: (min, max) growth share; None leaves the growth share free
            (used to draw the whole policy-constrained frontier).
    """
    idx = {t: i for i, t in enumerate(tickers)}
    growth = [idx[t] for t in tickers if sleeve_of(asset_class_of.get(t, "")) == "growth"]
    defensive = [idx[t] for t in tickers if sleeve_of(asset_class_of.get(t, "")) == "defensive"]
    cash = [idx[t] for t in tickers if asset_class_of.get(t, "") in CASH_ASSET_CLASSES]
    regions = {asset_class_of[t]: idx[t] for t in tickers
               if asset_class_of.get(t, "") in EQUITY_REGION_REFERENCE}

    if growth_rng is not None:
        lo, hi = growth_rng
        if growth:
            ef.add_constraint(lambda w, g=growth, lo=lo: sum(w[i] for i in g) >= lo)
            ef.add_constraint(lambda w, g=growth, hi=hi: sum(w[i] for i in g) <= hi)
        elif lo > 0:
            raise ValueError("Policy needs growth assets but none are available")

    if cash and defensive:
        k = POLICY_CASH_MAX_SHARE_OF_DEFENSIVE
        ef.add_constraint(lambda w, c=cash, d=defensive, k=k:
                          sum(w[i] for i in c) <= k * sum(w[i] for i in d))

    if regions and growth:
        eq = list(regions.values())
        m = POLICY_EQUITY_MIN_SHARE_OF_GROWTH
        ef.add_constraint(lambda w, e=eq, g=growth, m=m:
                          sum(w[i] for i in e) >= m * sum(w[i] for i in g))
        for r, (lo, hi) in region_bounds(list(regions)).items():
            i = regions[r]
            ef.add_constraint(lambda w, i=i, e=eq, lo=lo: w[i] >= lo * sum(w[j] for j in e))
            ef.add_constraint(lambda w, i=i, e=eq, hi=hi: w[i] <= hi * sum(w[j] for j in e))


def check_policy(
    weights: dict[str, float],
    asset_class_of: dict[str, str],
    growth_rng: Optional[tuple[float, float]] = None,
    tol: float = 1e-4,
) -> list[str]:
    """
    Independent check of a finished portfolio against the policy. Returns a
    list of violations (empty when compliant). Used by tests and as a guard
    before a portfolio is returned.
    """
    problems = []
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        problems.append(f"weights sum to {total:.6f}")
    ac = {t: asset_class_of.get(t, "") for t in weights}
    g = sum(w for t, w in weights.items() if sleeve_of(ac[t]) == "growth")
    d = sum(w for t, w in weights.items() if sleeve_of(ac[t]) == "defensive")
    c = sum(w for t, w in weights.items() if ac[t] in CASH_ASSET_CLASSES)
    if growth_rng and not (growth_rng[0] - tol <= g <= growth_rng[1] + tol):
        problems.append(f"growth {g:.3f} outside {growth_rng}")
    if c > POLICY_CASH_MAX_SHARE_OF_DEFENSIVE * d + tol:
        problems.append(f"cash {c:.3f} above {POLICY_CASH_MAX_SHARE_OF_DEFENSIVE:.0%} of defensive {d:.3f}")
    for t, w in weights.items():
        cap = POLICY_BLOCK_MAX.get(ac[t])
        if cap is not None and w > cap + tol:
            problems.append(f"{t} {w:.3f} above block max {cap}")
    eq = {ac[t]: w for t, w in weights.items() if ac[t] in EQUITY_REGION_REFERENCE}
    e = sum(eq.values())
    # Bounds depend on the regions AVAILABLE in the universe, not just those held.
    available = sorted({a for a in asset_class_of.values() if a in EQUITY_REGION_REFERENCE})
    if e > 1e-6:
        if e < POLICY_EQUITY_MIN_SHARE_OF_GROWTH * g - tol:
            problems.append(f"equity {e:.3f} below {POLICY_EQUITY_MIN_SHARE_OF_GROWTH:.0%} of growth")
        for r, (lo, hi) in region_bounds(available).items():
            share = eq.get(r, 0.0) / e
            if not (lo - 1e-3 <= share <= hi + 1e-3):
                problems.append(f"{r} {share:.3f} of equity outside [{lo:.3f}, {hi:.3f}]")
    return problems
