"""
Portfolio Optimizer — One-Fund Theorem + Mean-Variance Optimization
=====================================================================
Core algorithmic engine implementing the academically correct approach:

1. Compute the TANGENT portfolio (max Sharpe ratio on the efficient frontier)
2. Blend tangent portfolio with cash using the One-Fund Theorem:
       w_final = α · w_tangent + (1 − α) · w_cash
   where α = risk_score / 10
3. Auto-select asset classes based on risk profile (the robo advisor decides)

References:
    - Markowitz (1952): Portfolio Selection
    - He & Litterman (1999): Black-Litterman Model
    - Sharpe (1964): CAPM
    - Luenberger: Investment Science — One-Fund Theorem
    - WBS Lecture: Investment Science 101 (Moris Strub)
    - Wealthfront Methodology (Steps 1-5)
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier

from backend.config import (
    ASSET_CLASSES,
    ALLOCATION_CONSTRAINTS,
    MVO_RISK_FREE_RATE,
    MVO_EFFICIENT_FRONTIER_POINTS,
    USE_DUAL_MOMENTUM,
    DUAL_MOMENTUM_LOOKBACK_MONTHS,
    DUAL_MOMENTUM_REDUCTION,
    CRISIS_CASH_BUFFER,
    RISK_DECAY_ENABLED,
    RISK_DECAY_HORIZON_YEARS,
    RISK_DECAY_MAX_RISK,
    ASSET_GROUP_CAPS,
    BOND_ASSET_CLASSES,
    GOLD_ASSET_CLASSES,
    CASH_ASSET_CLASSES,
    VOL_CALIBRATION_MULTIPLIER,
)
from backend.engine.covariance import detect_volatility_regime
from backend.engine.expected_returns import build_mu_cov
from backend.engine.asset_universe import (
    get_etf_by_ticker,
    get_primary_etf_for_class,
    resolve_ticker_map,
    strategic_asset_classes,
)
from backend.data.market_data import build_close_price_matrix
from backend.data.rates import get_risk_free_rate

logger = logging.getLogger(__name__)


# =============================================================================
# SINGLE STRATEGIC UNIVERSE (Phase 3; revised in PM overhaul; now DYNAMIC)
# =============================================================================
# One universe for ALL risk levels; risk is expressed via a target-volatility
# ladder on the constrained efficient frontier (Betterment-style), not by
# swapping universes. cash_equivalent (ultrashort GBP, ~0.5% vol) is the
# de-risking sleeve — exempt from the 20% term-bond cap so conservative
# portfolios are actually conservative.
#
# The universe is built dynamically from the FULL ETF registry: every asset
# class whose cheapest fund is UK-retail investable (UCITS, or an ISA-eligible
# LSE ETC for gold/silver) is included. Non-investable classes (NSE-listed .NS
# lines) resolve to no ticker and drop out; India exposure comes via the UCITS
# FLXI.L under indian_large_cap. Short-history funds are filtered downstream
# by the min_obs guard in the returns builder, and per-class ALLOCATION_
# CONSTRAINTS plus the bond/gold group caps bound every member.


def _build_strategic_universe() -> list[str]:
    """Core building blocks (plus satellites if enabled) that have an investable ETF."""
    universe = [ac for ac in strategic_asset_classes() if get_primary_etf_for_class(ac) is not None]
    logger.info(f"Strategic universe: {len(universe)} asset classes")
    return universe


STRATEGIC_UNIVERSE: list[str] = _build_strategic_universe()


def select_asset_classes_for_risk(risk_score: float) -> list[str]:
    """
    Return the single strategic asset-class universe used for ALL risk levels.

    Phase 3 change: risk is expressed via the two-fund glide (see
    `build_two_fund_portfolio`), NOT by swapping the universe. The `risk_score`
    argument is retained for signature compatibility but no longer alters the set.

    Parameters:
        risk_score (float): Composite risk score 1–10 (unused; kept for compat).

    Returns:
        list[str]: The strategic asset-class universe.
    """
    logger.info(f"Strategic universe: {len(STRATEGIC_UNIVERSE)} asset classes (risk={risk_score})")
    return list(STRATEGIC_UNIVERSE)


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


# =============================================================================
# WEIGHT BOUNDS
# =============================================================================

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


def _get_weight_bounds(
    tickers: list[str],
    asset_class_map: dict[str, str],
) -> list[tuple[float, float]]:
    """
    Build per-asset weight bounds from config constraints.

    Parameters:
        tickers (list[str]): Ordered list of tickers in the portfolio.
        asset_class_map (dict[str, str]): {ticker: asset_class} mapping.

    Returns:
        list[tuple[float, float]]: (min_weight, max_weight) for each ticker.
    """
    bounds = []
    for ticker in tickers:
        ac = asset_class_map.get(ticker, "")
        constraint = ALLOCATION_CONSTRAINTS.get(ac, {"min": 0.0, "max": 1.0})
        bounds.append((constraint["min"], constraint["max"]))
    return bounds


# =============================================================================
# ONE-FUND THEOREM: TANGENT PORTFOLIO COMPUTATION
# =============================================================================

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


# =============================================================================
# RISK TARGETING ON THE EFFICIENT FRONTIER
# =============================================================================

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


# =============================================================================
# DUAL MOMENTUM OVERLAY (Optional)
# =============================================================================

def apply_dual_momentum(
    prices: pd.DataFrame,
    weights: dict[str, float],
    cash_ticker: Optional[str] = None,
) -> dict[str, float]:
    """
    Apply Gary Antonacci's dual momentum overlay.

    If an asset's 12-month momentum is negative AND worse than cash,
    reduce its allocation by DUAL_MOMENTUM_REDUCTION (default 50%).
    Redistributed weight goes to cash.

    Parameters:
        prices (pd.DataFrame): Historical prices.
        weights (dict[str, float]): Current portfolio weights.
        cash_ticker (str, optional): Cash ETF ticker.

    Returns:
        dict[str, float]: Momentum-adjusted weights.
    """
    if not USE_DUAL_MOMENTUM:
        return weights

    lookback_days = DUAL_MOMENTUM_LOOKBACK_MONTHS * 21  # Approx trading days
    if len(prices) < lookback_days:
        return weights

    recent = prices.iloc[-lookback_days:]
    momentum = (recent.iloc[-1] / recent.iloc[0]) - 1  # 12-month return

    # Safe bond momentum baseline
    safe_momentum = MVO_RISK_FREE_RATE * (DUAL_MOMENTUM_LOOKBACK_MONTHS / 12.0)

    adjusted = dict(weights)
    redistributed = 0.0

    for ticker, weight in list(adjusted.items()):
        if ticker == cash_ticker:
            continue
        if ticker in momentum.index:
            asset_mom = momentum[ticker]
            if asset_mom < 0 and asset_mom < safe_momentum:
                reduction = weight * DUAL_MOMENTUM_REDUCTION
                adjusted[ticker] = weight - reduction
                redistributed += reduction
                logger.info(
                    f"Dual momentum: {ticker} reduced by {reduction:.4f} "
                    f"(momentum: {asset_mom:.2%})"
                )

    # Add redistributed to safe bonds
    if redistributed > 0:
        if cash_ticker:
            adjusted[cash_ticker] = adjusted.get(cash_ticker, 0.0) + redistributed
        else:
            # Rebalance proportionally if no safe asset designated
            total = sum(adjusted.values())
            if total > 0:
                adjusted = {k: v / total for k, v in adjusted.items()}

    return adjusted


# =============================================================================
# PORTFOLIO PERFORMANCE METRICS
# =============================================================================

def get_portfolio_performance(
    weights: dict[str, float],
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> dict:
    """
    Calculate expected performance metrics for given weights.

    Parameters:
        weights (dict): Portfolio weights {ticker: weight}.
        expected_returns (pd.Series): Expected returns.
        cov_matrix (pd.DataFrame): Covariance matrix.
        risk_free_rate (float): Risk-free rate.

    Returns:
        dict: {"expected_return", "volatility", "sharpe_ratio"}.
    """
    # Filter to only risky assets (exclude __CASH__)
    risky_tickers = [t for t in weights if t != "__CASH__" and t in expected_returns.index]
    if not risky_tickers:
        return {"expected_return": risk_free_rate, "volatility": 0.0, "sharpe_ratio": 0.0}

    w = np.array([weights.get(t, 0) for t in risky_tickers])
    mu = np.array([expected_returns[t] for t in risky_tickers])
    cov_sub = cov_matrix.loc[risky_tickers, risky_tickers].values

    cash_w = weights.get("__CASH__", 0)

    port_return = float(np.dot(w, mu)) + cash_w * risk_free_rate
    # Client-facing vol is scaled by the measured realized/predicted calibration
    # ratio (Phase 2: EWMA+LW under-predicts realized vol by ~10–20%).
    port_vol_model = float(np.sqrt(np.dot(w.T, np.dot(cov_sub, w))))
    port_vol = port_vol_model * VOL_CALIBRATION_MULTIPLIER
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

    return {
        "expected_return": round(port_return, 6),
        "volatility": round(port_vol, 6),
        "volatility_model": round(port_vol_model, 6),
        "sharpe_ratio": round(sharpe, 4),
    }


# =============================================================================
# EFFICIENT FRONTIER
# =============================================================================

def compute_efficient_frontier(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    n_points: int = MVO_EFFICIENT_FRONTIER_POINTS,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    asset_class_map: Optional[dict[str, str]] = None,
) -> list[dict]:
    """
    Compute the full efficient frontier as a list of portfolio points.

    Each point contains: expected_return, volatility, sharpe_ratio, weights.

    Parameters:
        expected_returns (pd.Series): Expected returns per asset.
        cov_matrix (pd.DataFrame): Covariance matrix.
        weight_bounds (list): Per-asset weight constraints.
        n_points (int): Number of points on the frontier (default 50).
        risk_free_rate (float): Risk-free rate.

    Returns:
        list[dict]: Frontier points sorted by volatility.
    """
    frontier = []

    # Group caps (bonds ≤ 20%, gold ≤ 10%) if an asset-class map is given
    sm = sl = su = None
    if asset_class_map is not None:
        sm, sl, su = build_sector_caps(list(expected_returns.index), asset_class_map)

    max_ret = expected_returns.max()
    if max_ret <= risk_free_rate:
        safe_rf = max_ret - 0.01 if max_ret > 0.01 else 0.0
        risk_free_rate = safe_rf

    try:
        # Find min and max achievable returns
        ef_min = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        _apply_sector_caps(ef_min, sm, sl, su)
        ef_min.min_volatility()
        min_ret, min_vol, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

        ef_max = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        _apply_sector_caps(ef_max, sm, sl, su)
        ef_max.max_sharpe(risk_free_rate=risk_free_rate)
        max_ret, _, _ = ef_max.portfolio_performance(risk_free_rate=risk_free_rate)

        # Extend slightly beyond max Sharpe
        target_returns = np.linspace(min_ret, max_ret * 1.1, n_points)

        for target in target_returns:
            try:
                ef = EfficientFrontier(
                    expected_returns, cov_matrix, weight_bounds=weight_bounds,
                )
                _apply_sector_caps(ef, sm, sl, su)
                ef.efficient_return(target_return=target)
                ret, vol, sharpe = ef.portfolio_performance(
                    risk_free_rate=risk_free_rate,
                )
                weights = ef.clean_weights()
                frontier.append({
                    "expected_return": round(ret, 6),
                    "volatility": round(vol, 6),
                    "sharpe_ratio": round(sharpe, 4),
                    "weights": {k: round(v, 4) for k, v in weights.items() if v > 0.001},
                })
            except Exception:
                continue

    except Exception as e:
        logger.error(f"Efficient frontier computation failed: {e}")

    return sorted(frontier, key=lambda p: p["volatility"])


# =============================================================================
# MAIN PIPELINE: BUILD OPTIMISED PORTFOLIO
# =============================================================================

def build_optimised_portfolio(
    risk_score: float,
    investment_amount: float,
    selected_asset_classes: Optional[list[str]] = None,
    investment_horizon_years: int = 10,
) -> dict:
    """
    Full portfolio construction pipeline using the One-Fund Theorem.

    Algorithm (per Investment Science lecture + Wealthfront methodology):
    1. Auto-select asset classes from risk score (robo advisor decides)
    2. Map asset classes → primary ETF tickers
    3. Fetch 5yr historical prices
    4. Compute Ledoit-Wolf covariance matrix
    5. Compute expected returns (CAPM → Black-Litterman, cost-adjusted)
    6. Compute TANGENT portfolio (max Sharpe — the ONE FUND)
    7. Blend tangent with cash using One-Fund Theorem (α = risk_score/10)
    8. Apply dual momentum overlay (if enabled)
    9. Check regime; apply crisis cash buffer if needed
    10. Return final allocations with efficient frontier

    Parameters:
        risk_score (float): Composite risk score (1–10).
        investment_amount (float): Total investment in GBP.
        selected_asset_classes (list[str], optional): Override auto-selection.
        investment_horizon_years (int): Investment time horizon in years.

    Returns:
        dict: {
            "weights": {asset_class: weight},
            "ticker_weights": {ticker: weight},
            "allocations": [{asset_class, ticker, weight, amount_gbp, ...}],
            "performance": {expected_return, volatility, sharpe_ratio},
            "frontier": [...],
            "high_correlation_regime": bool,
            "tangent_portfolio": {ticker: weight},
            "risk_allocation_alpha": float,
        }
    """
    # ── Step 1: Asset Class Selection (STRICT ROBO-CONTROL) ──
    # User choice is eliminated to ensure adherence to MPT principles.
    if selected_asset_classes:
        logger.warning(
            "selected_asset_classes is no longer honoured (single strategic "
            "universe since Phase 3) — proceeding with the robo-selected universe"
        )
    asset_classes = select_asset_classes_for_risk(risk_score)
    logger.info(f"Strictly selected {len(asset_classes)} asset classes for risk={risk_score}")

    # ── Step 2: Map to ETF tickers (fall back within a class if data is unusable) ──
    from backend.data.returns import has_usable_history
    from backend.config import MIN_HISTORY_MONTHS
    ticker_map, skipped_etfs = resolve_ticker_map(
        asset_classes, usable=lambda t: has_usable_history(t, min_months=MIN_HISTORY_MONTHS)
    )
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}

    if len(tickers) < 2:
        raise ValueError("Need at least 2 asset classes with valid ETFs")

    # ── Live GBP risk-free rate (yfinance money-market proxy; config fallback) ──
    # Drives BOTH the pricing math (BL equilibrium, tangency) and Sharpe
    # reporting — no hardcoded hurdle.
    rf_live = get_risk_free_rate()
    logger.info(f"Using live risk-free rate: {rf_live:.2%}")

    # ── Steps 3–5: Monthly GBP-unhedged returns → locked Phase 1/2 inputs ──
    # Expected returns = trailing+BL blend; covariance = EWMA+Ledoit-Wolf hybrid.
    expense_by_ticker = {t: get_etf_by_ticker(t)["expense_ratio"] for t in tickers}
    mu, cov_matrix, monthly_returns = build_mu_cov(
        tickers, expense_by_ticker, risk_free_rate=rf_live, asset_class_of=ac_by_ticker,
    )
    tickers = list(mu.index)

    # Cash sleeve E[R] = LIVE cash rate net of fees. The trailing mean of a
    # money-market fund is a stale forecast across rate regimes (the 10y
    # window still contains the 2016-21 zero-rate era); its forward return is
    # today's rate by construction.
    mu = mu.copy()
    for tk in mu.index:
        if ac_by_ticker.get(tk, "") in CASH_ASSET_CLASSES:
            mu.loc[tk] = rf_live - expense_by_ticker.get(tk, 0.0)

    if len(mu) < 2:
        raise ValueError("Insufficient return data after filtering")

    # ── Step 6: Regime detection (volatility/drawdown-based, Phase 2) ──
    high_corr = detect_volatility_regime(monthly_returns)

    # ── Step 7: Weight bounds ──
    weight_bounds = _get_weight_bounds(list(mu.index), ac_by_ticker)

    # ── Step 9: Risk via target-volatility ladder on the constrained frontier ──
    risk_targeted = build_risk_targeted_portfolio(
        risk_score, mu, cov_matrix, weight_bounds,
        risk_free_rate=rf_live, asset_class_map=ac_by_ticker,
    )
    optimal_weights = risk_targeted["weights"]
    tangent_weights = risk_targeted["growth_fund"]
    blended = dict(optimal_weights)

    # ── Step 10: Crisis buffer → CASH haven (gilts fallback), caps respected ──
    # Haven priority: cash_equivalent (exempt from bond cap → no violation),
    # then uk_gilts (bond cap re-checked and clamped). Never EM/INR duration.
    safe_bond_ticker = ticker_map.get("cash_equivalent") or ticker_map.get("uk_gilts")
    if high_corr and safe_bond_ticker and safe_bond_ticker in mu.index:
        blended = apply_crisis_buffer(
            blended, safe_bond_ticker, ac_by_ticker, CRISIS_CASH_BUFFER
        )
        logger.warning(f"Crisis buffer applied: +{CRISIS_CASH_BUFFER:.0%} → {safe_bond_ticker}")

    # ── Step 11: Dual momentum overlay (optional; fetches daily prices only if enabled) ──
    if USE_DUAL_MOMENTUM:
        prices = build_close_price_matrix(tickers)
        if prices is not None and not prices.empty:
            blended = apply_dual_momentum(prices, blended, safe_bond_ticker)

    # ── Step 12: Build final allocations ──
    final_weights = {}
    for ticker, weight in blended.items():
        if weight >= 0.001:
            final_weights[ticker] = final_weights.get(ticker, 0) + weight

    # Normalize
    total_w = sum(final_weights.values())
    if total_w > 0 and abs(total_w - 1.0) > 0.001:
        final_weights = {k: v / total_w for k, v in final_weights.items()}

    # ── Performance metrics (Sharpe reported against the LIVE risk-free rate) ──
    perf = get_portfolio_performance(
        final_weights, mu, cov_matrix, risk_free_rate=rf_live
    )

    # ── Efficient frontier (bonds ≤20% / gold ≤10% group caps) ──
    frontier = compute_efficient_frontier(
        mu, cov_matrix, weight_bounds,
        risk_free_rate=rf_live, asset_class_map=ac_by_ticker,
    )
    if not frontier:
        frontier = [{"weights": tangent_weights, "expected_return": 0,
                     "volatility": 0, "sharpe_ratio": 0}]

    # ── Build allocation list ──
    allocations = []
    total_expense = 0.0
    for ticker, weight in final_weights.items():
        if weight < 0.001:
            continue
        ac = ac_by_ticker.get(ticker, "unknown")
        er_val = expense_by_ticker.get(ticker, 0)
        total_expense += weight * er_val
        allocations.append({
            "asset_class": ac,
            "ticker": ticker,
            "weight": round(weight, 4),
            "amount_gbp": round(weight * investment_amount, 2),
            "expense_ratio": er_val,
        })

    return {
        "weights": {ac_by_ticker.get(t, t): w for t, w in final_weights.items()},
        "ticker_weights": final_weights,
        "allocations": sorted(allocations, key=lambda a: a["weight"], reverse=True),
        "performance": perf,
        "total_expense_ratio": round(total_expense, 6),
        "frontier": frontier,
        "high_correlation_regime": high_corr,
        "tangent_portfolio": {ac_by_ticker.get(t, t): round(w, 4)
                              for t, w in tangent_weights.items() if w > 0.001},
        "risk_allocation_alpha": risk_score / 10.0,
        "target_volatility": risk_targeted.get("target_volatility"),
        "volatility_ladder": [risk_targeted.get("sigma_min"), risk_targeted.get("sigma_max")],
        "asset_classes_used": [ac_by_ticker[t] for t in tickers],
        "etf_fallbacks": skipped_etfs,
        "risk_free_rate": round(rf_live, 6),
    }
