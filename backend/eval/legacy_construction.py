"""
Legacy construction methods (superseded September 2026)
========================================================
The target-volatility ladder, two-fund blend, flat bond/gold group caps and
post-hoc crisis buffer that production used before the remediation plan
(docs/PORTFOLIO_REMEDIATION_PLAN.md §2.5). Kept only so the research scripts
in scripts/ can reproduce earlier results. Production code must not import
from here.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier

from backend.config import (
    ASSET_GROUP_CAPS,
    BOND_ASSET_CLASSES,
    CRISIS_CASH_BUFFER,
    GOLD_ASSET_CLASSES,
    MVO_RISK_FREE_RATE,
)

logger = logging.getLogger(__name__)


def compute_tangent_portfolio(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    sector_mapper: Optional[dict[str, str]] = None,
    sector_lower: Optional[dict[str, float]] = None,
    sector_upper: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """
    Compute the TANGENT portfolio — the single fund F of risky assets that
    maximizes the Sharpe Ratio on the efficient frontier.

    This is the ONE FUND from the One-Fund Theorem:
    "There is a single fund F of risky assets such that any efficient
    portfolio can be a combination of F and the risk-free asset."
    — Luenberger, Investment Science

    Parameters:
        expected_returns (pd.Series): Expected returns per asset.
        cov_matrix (pd.DataFrame): Covariance matrix.
        weight_bounds (list): Per-asset (min, max) weight constraints.
        risk_free_rate (float): Risk-free rate (UK base rate).

    Returns:
        dict[str, float]: Optimal risky weights {ticker: weight} at max Sharpe.
    """
    max_ret = expected_returns.max()
    if max_ret <= risk_free_rate:
        # Dynamically lower rf to allow for theoretical optimization to converge
        safe_rf = max_ret - 0.01 if max_ret > 0.01 else 0.0
        logger.warning(f"max_expected_return ({max_ret:.4f}) <= risk_free_rate ({risk_free_rate:.4f}). Auto-adjusting rf to {safe_rf:.4f}")
        risk_free_rate = safe_rf

    try:
        ef = EfficientFrontier(
            expected_returns,
            cov_matrix,
            weight_bounds=weight_bounds,
        )
        _apply_sector_caps(ef, sector_mapper, sector_lower, sector_upper)
        ef.max_sharpe(risk_free_rate=risk_free_rate)
        weights = ef.clean_weights()
        logger.info(f"Tangent portfolio computed — max Sharpe weights: "
                     f"{sum(1 for w in weights.values() if w > 0.001)} active positions")
        return dict(weights)

    except Exception as e:
        logger.warning(f"max_sharpe failed ({e}), trying min_volatility as fallback")
        try:
            ef2 = EfficientFrontier(
                expected_returns,
                cov_matrix,
                weight_bounds=weight_bounds,
            )
            _apply_sector_caps(ef2, sector_mapper, sector_lower, sector_upper)
            ef2.min_volatility()
            weights = ef2.clean_weights()
            logger.info("Using min-volatility portfolio as tangent proxy")
            return dict(weights)
        except Exception as e2:
            logger.error(f"min_volatility also failed ({e2}), using risk-parity proxy")
            # Risk parity fallback: weight inversely proportional to volatility
            vols = np.sqrt(np.diag(cov_matrix.values))
            inv_vol = 1.0 / vols
            w = inv_vol / inv_vol.sum()
            return {ticker: float(w[i]) for i, ticker in enumerate(cov_matrix.columns)}


def build_two_fund_portfolio(
    risk_score: float,
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    asset_class_map: Optional[dict[str, str]] = None,
) -> dict:
    """
    Express risk via the Two-Fund Separation theorem: every efficient portfolio
    is a combination of two frontier funds. We use:
        - DEFENSIVE fund = global minimum-variance portfolio (bonds/gold heavy)
        - GROWTH fund    = tangency / max-Sharpe portfolio
    and blend them by α = risk_score / 10:
        w = α · w_growth + (1 − α) · w_defensive

    This guarantees a MONOTONIC risk dial and ensures low-risk portfolios hold
    real defensive assets (the min-variance fund ignores returns, so bonds
    appear even after a weak bond decade — unlike pure target-vol MVO).

    Parameters:
        risk_score (float): 1–10.
        expected_returns (pd.Series): annual expected returns.
        cov_matrix (pd.DataFrame): annual covariance.
        weight_bounds (list): per-asset (min, max) bounds.
        risk_free_rate (float): annual risk-free rate.

    Returns:
        dict: {"weights", "defensive_fund", "growth_fund", "alpha"}.
    """
    alpha = float(np.clip(risk_score / 10.0, 0.0, 1.0))

    # Build group caps (bonds ≤ 20%, gold ≤ 10%) if an asset-class map is given
    sector_mapper = sector_lower = sector_upper = None
    if asset_class_map is not None:
        sector_mapper, sector_lower, sector_upper = build_sector_caps(
            list(expected_returns.index), asset_class_map
        )

    # Defensive fund: global minimum variance (with group caps)
    try:
        ef_def = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        _apply_sector_caps(ef_def, sector_mapper, sector_lower, sector_upper)
        ef_def.min_volatility()
        w_def = dict(ef_def.clean_weights())
    except Exception as e:
        logger.warning(f"min_volatility failed ({e}); inverse-variance defensive fund")
        inv = 1.0 / np.diag(cov_matrix.values)
        w_def = {t: float(inv[i] / inv.sum()) for i, t in enumerate(cov_matrix.columns)}

    # Growth fund: tangency (max Sharpe), with the same group caps
    w_growth = compute_tangent_portfolio(
        expected_returns, cov_matrix, weight_bounds, risk_free_rate,
        sector_mapper=sector_mapper, sector_lower=sector_lower, sector_upper=sector_upper,
    )

    tickers = list(expected_returns.index)
    blended = {
        t: alpha * w_growth.get(t, 0.0) + (1.0 - alpha) * w_def.get(t, 0.0)
        for t in tickers
    }
    total = sum(blended.values())
    if total > 0:
        blended = {k: v / total for k, v in blended.items() if v / total > 1e-4}

    logger.info(f"Two-fund glide: risk={risk_score} → α={alpha:.2f} "
                f"({sum(1 for w in blended.values() if w > 0.001)} positions)")
    return {
        "weights": blended,
        "defensive_fund": w_def,
        "growth_fund": dict(w_growth),
        "alpha": alpha,
    }


def build_sector_caps(
    tickers: list[str],
    asset_class_map: dict[str, str],
) -> tuple[dict[str, str], dict[str, float], dict[str, float]]:
    """
    Build pypfopt sector-constraint inputs enforcing group caps (bonds ≤ 20%,
    gold ≤ 10%) across all members, regardless of per-asset bounds.

    Parameters:
        tickers (list[str]): Ordered tickers in the portfolio.
        asset_class_map (dict[str, str]): {ticker: asset_class}.

    Returns:
        (sector_mapper, sector_lower, sector_upper):
            sector_mapper {ticker: group}, and lower/upper {group: weight}.
            Only groups actually present among the tickers are constrained.
    """
    mapper: dict[str, str] = {}
    for t in tickers:
        ac = asset_class_map.get(t, "")
        if ac in BOND_ASSET_CLASSES:
            mapper[t] = "bonds"
        elif ac in GOLD_ASSET_CLASSES:
            mapper[t] = "gold"
        else:
            mapper[t] = "other"

    present = set(mapper.values())
    upper = {g: c for g, c in ASSET_GROUP_CAPS.items() if g in present}
    lower = {g: 0.0 for g in upper}
    return mapper, lower, upper


def _apply_sector_caps(ef, sector_mapper, sector_lower, sector_upper) -> None:
    """Attach group caps to an EfficientFrontier instance (no-op if none)."""
    if sector_mapper and sector_upper:
        ef.add_sector_constraints(sector_mapper, sector_lower, sector_upper)


def _max_return_corner(
    expected_returns: pd.Series,
    weight_bounds: list[tuple[float, float]],
    sector_mapper: Optional[dict[str, str]],
    sector_upper: Optional[dict[str, float]],
) -> pd.Series:
    """
    Exact greedy solution of the max-return LP under box bounds + group caps:
    fill assets in descending E[R], respecting per-asset max and the remaining
    group capacity, until weights sum to 1. (Greedy is optimal here because
    each asset belongs to exactly one group — a continuous knapsack with
    nested capacity constraints.)

    Returns:
        pd.Series: weights of the maximum-return corner portfolio.
    """
    tickers = list(expected_returns.index)
    ub = {t: weight_bounds[i][1] for i, t in enumerate(tickers)}
    group_of = sector_mapper or {t: "other" for t in tickers}
    group_left = dict(sector_upper or {})

    w = {t: 0.0 for t in tickers}
    remaining = 1.0
    for t in sorted(tickers, key=lambda x: -float(expected_returns[x])):
        if remaining <= 1e-12:
            break
        g = group_of.get(t, "other")
        cap_g = group_left.get(g, 1.0)
        take = min(ub.get(t, 1.0), remaining, cap_g)
        if take <= 0:
            continue
        w[t] = take
        remaining -= take
        if g in group_left:
            group_left[g] -= take

    total = sum(w.values())
    if total < 0.999:
        logger.warning(f"Max-return corner only fills {total:.3f} of weight (caps too tight)")
    return pd.Series(w)


def build_risk_targeted_portfolio(
    risk_score: float,
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    asset_class_map: Optional[dict[str, str]] = None,
) -> dict:
    """
    PRODUCTION risk mapping (PM overhaul): a target-volatility ladder solved
    directly ON the constrained efficient frontier — the Betterment approach
    ("expected returns are maximized for target volatilities assigned to each
    risk level").

    Method:
        σ_min = vol of the constrained minimum-variance portfolio
        σ_max = vol of the constrained maximum-return corner (greedy LP)
        σ_target(risk) = σ_min + (risk−1)/9 · (σ_max − σ_min)
        weights = EfficientFrontier.efficient_risk(σ_target)   [caps applied]

    This is monotone in risk by construction AND efficient under the
    constraints — unlike the previous α-blend of two frontier funds, which is
    generally interior to the constrained frontier.

    Falls back to the two-fund α-blend if the solver fails.

    Returns:
        dict: {"weights", "target_volatility", "sigma_min", "sigma_max",
               "growth_fund", "alpha"}.
    """
    risk_score = float(np.clip(risk_score, 1.0, 10.0))

    sector_mapper = sector_lower = sector_upper = None
    if asset_class_map is not None:
        sector_mapper, sector_lower, sector_upper = build_sector_caps(
            list(expected_returns.index), asset_class_map
        )

    def _vol(w: pd.Series) -> float:
        w = w.reindex(cov_matrix.columns).fillna(0.0)
        return float(np.sqrt(w.values @ cov_matrix.values @ w.values))

    # σ_min from constrained min-variance
    try:
        ef_min = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        _apply_sector_caps(ef_min, sector_mapper, sector_lower, sector_upper)
        ef_min.min_volatility()
        w_min = pd.Series(ef_min.clean_weights())
        sigma_min = _vol(w_min)
    except Exception as e:
        logger.warning(f"min_volatility failed ({e}); falling back to two-fund blend")
        return build_two_fund_portfolio(
            risk_score, expected_returns, cov_matrix, weight_bounds,
            risk_free_rate, asset_class_map,
        )

    # σ_max from the max-return corner under the same constraints
    w_corner = _max_return_corner(expected_returns, weight_bounds, sector_mapper, sector_upper)
    sigma_max = _vol(w_corner)
    if sigma_max <= sigma_min:
        sigma_max = sigma_min * 1.5  # degenerate guard

    # Linear vol ladder
    sigma_target = sigma_min + (risk_score - 1.0) / 9.0 * (sigma_max - sigma_min)
    sigma_target = float(np.clip(sigma_target, sigma_min * 1.0001, sigma_max * 0.9999))

    # Growth fund (tangency) retained for reporting
    w_growth = compute_tangent_portfolio(
        expected_returns, cov_matrix, weight_bounds, risk_free_rate,
        sector_mapper=sector_mapper, sector_lower=sector_lower, sector_upper=sector_upper,
    )

    # Solve max-return at the target volatility on the constrained frontier
    weights = None
    if risk_score <= 1.0 + 1e-9:
        weights = {t: float(v) for t, v in w_min.items()}
    else:
        try:
            from pypfopt import objective_functions
            ef = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
            _apply_sector_caps(ef, sector_mapper, sector_lower, sector_upper)
            # L2 regularization spreads weight across assets (pypfopt's
            # documented remedy for corner solutions) — prevents 3-position
            # portfolios when clamped expected returns tie at the cap.
            ef.add_objective(objective_functions.L2_reg, gamma=0.1)
            ef.efficient_risk(target_volatility=sigma_target)
            weights = dict(ef.clean_weights())
        except Exception as e:
            logger.warning(f"efficient_risk(σ={sigma_target:.3f}) failed ({e}); two-fund fallback")
            return build_two_fund_portfolio(
                risk_score, expected_returns, cov_matrix, weight_bounds,
                risk_free_rate, asset_class_map,
            )

    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items() if v / total > 1e-4}

    logger.info(
        f"Risk {risk_score} → σ_target={sigma_target:.2%} "
        f"(ladder [{sigma_min:.2%}, {sigma_max:.2%}]), "
        f"{sum(1 for w in weights.values() if w > 0.001)} positions"
    )
    return {
        "weights": weights,
        "target_volatility": round(sigma_target, 4),
        "sigma_min": round(sigma_min, 4),
        "sigma_max": round(sigma_max, 4),
        "growth_fund": dict(w_growth),
        "alpha": risk_score / 10.0,
    }


def apply_crisis_buffer(
    weights: dict[str, float],
    haven_ticker: str,
    asset_class_map: dict[str, str],
    buffer: float = CRISIS_CASH_BUFFER,
) -> dict[str, float]:
    """
    Shift `buffer` of the portfolio into the haven asset during a crisis
    regime, WITHOUT violating the group caps (the old implementation could
    push bonds above the 20% mandate cap).

    If the haven is a bond-class asset, the shift is limited to the remaining
    bond-cap headroom. Cash havens (cash_equivalent) are exempt by design.
    Reduction is taken proportionally from non-haven positions; output sums to 1.

    Returns:
        dict[str, float]: adjusted weights (new dict; input not mutated).
    """
    adjusted = dict(weights)
    haven_ac = asset_class_map.get(haven_ticker, "")

    effective_buffer = buffer
    if haven_ac in BOND_ASSET_CLASSES:
        bond_total = sum(
            w for t, w in adjusted.items()
            if asset_class_map.get(t, "") in BOND_ASSET_CLASSES
        )
        headroom = max(0.0, ASSET_GROUP_CAPS.get("bonds", 1.0) - bond_total)
        effective_buffer = min(buffer, headroom)
        if effective_buffer < buffer:
            logger.info(
                f"Crisis buffer limited to {effective_buffer:.1%} by bond-cap headroom"
            )
    if effective_buffer <= 0:
        return adjusted

    others_total = sum(w for t, w in adjusted.items() if t != haven_ticker)
    if others_total <= 0:
        return adjusted
    scale = (others_total - effective_buffer) / others_total
    for t in list(adjusted.keys()):
        if t != haven_ticker:
            adjusted[t] *= scale
    adjusted[haven_ticker] = adjusted.get(haven_ticker, 0.0) + effective_buffer

    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}
    return adjusted
