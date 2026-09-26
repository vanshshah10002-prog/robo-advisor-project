"""
Portfolio Optimizer — policy-constrained mean-variance
========================================================
Production construction (docs/PORTFOLIO_REMEDIATION_PLAN.md §2.5):

1. Universe: core building blocks, one ETF each with data-aware fallback.
2. Inputs: expected returns = equilibrium prior on a reference market
   portfolio (+ minority trailing weight); covariance = EWMA + Ledoit-Wolf.
3. Policy: the risk score fixes the growth share (10% per point, ±5pp) and
   the limits on cash, blocks and equity regions (backend/engine/policy.py).
4. Optimise: maximise quadratic utility μ'w − (λ/2)·w'Σw with the SAME λ as
   the prior, so with no binding constraints the answer is the reference
   portfolio; the policy constraints then shape it to the client's risk.
5. Positions under 0.5% are removed by re-solving with them fixed at zero.

References: He & Litterman (1999); Idzorek; Wealthfront and Betterment
methodology; Vanguard LifeStrategy.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier

from backend.config import (
    ALLOCATION_CONSTRAINTS,
    BL_RISK_AVERSION,
    CASH_ASSET_CLASSES,
    DUAL_MOMENTUM_LOOKBACK_MONTHS,
    DUAL_MOMENTUM_REDUCTION,
    EQUITY_REGION_REFERENCE,
    MVO_EFFICIENT_FRONTIER_POINTS,
    MVO_RISK_FREE_RATE,
    POLICY_MIN_POSITION,
    USE_DUAL_MOMENTUM,
    VOL_CALIBRATION_MULTIPLIER,
)
from backend.engine.asset_universe import (
    get_etf_by_ticker,
    get_primary_etf_for_class,
    resolve_ticker_map,
    strategic_asset_classes,
)
from backend.engine.covariance import detect_volatility_regime
from backend.engine.expected_returns import build_mu_cov
from backend.engine.policy import (
    add_policy_constraints,
    check_policy,
    growth_range,
    growth_target,
    sleeve_of,
    weight_bounds as policy_weight_bounds,
)
from backend.data.market_data import build_close_price_matrix
from backend.data.rates import get_risk_free_rate
from backend.engine.quant_models import reference_weights

logger = logging.getLogger(__name__)


class OptimisationError(ValueError):
    """The optimiser could not produce a portfolio that meets the policy."""


# =============================================================================
# UNIVERSE
# =============================================================================

def _build_strategic_universe() -> list[str]:
    """Core building blocks (plus satellites if enabled) that have an investable ETF."""
    universe = [ac for ac in strategic_asset_classes() if get_primary_etf_for_class(ac) is not None]
    logger.info(f"Strategic universe: {len(universe)} asset classes")
    return universe


STRATEGIC_UNIVERSE: list[str] = _build_strategic_universe()


def select_asset_classes_for_risk(risk_score: float) -> list[str]:
    """
    The strategic universe. The same building blocks serve every risk level;
    risk is expressed through the policy's growth share, not the universe.
    """
    return list(STRATEGIC_UNIVERSE)


# =============================================================================
# WEIGHT BOUNDS (legacy per-class caps; research scripts use these)
# =============================================================================

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
# POLICY OPTIMISATION
# =============================================================================

def apply_cash_forward_rate(mu: pd.Series, asset_class_of: dict[str, str], risk_free_rate: float,
                            expense_by_ticker: Optional[dict[str, float]] = None) -> pd.Series:
    """Cash's forward return is today's rate less fees, not its trailing average."""
    mu = mu.copy()
    for t in mu.index:
        if asset_class_of.get(t, "") in CASH_ASSET_CLASSES:
            mu.loc[t] = risk_free_rate - (expense_by_ticker or {}).get(t, 0.0)
    return mu


def _new_frontier(mu, cov, bounds, tickers, ac_of, growth_rng):
    ef = EfficientFrontier(mu, cov, weight_bounds=bounds)
    add_policy_constraints(ef, tickers, ac_of, growth_rng)
    return ef


def build_policy_portfolio(
    risk_score: float,
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    asset_class_of: dict[str, str],
    crisis: bool = False,
    risk_aversion: float = BL_RISK_AVERSION,
) -> dict:
    """
    Maximise quadratic utility inside the risk policy.

    Returns:
        dict: {"weights", "growth_range", "growth_target", "growth_weight",
               "removed_small_positions"}.

    Raises:
        OptimisationError: if the policy is infeasible for these assets.
    """
    tickers = list(expected_returns.index)
    rng = growth_range(risk_score, crisis)
    base_bounds = policy_weight_bounds(tickers, asset_class_of)

    zeroed: set[str] = set()
    weights: Optional[dict[str, float]] = None
    for _ in range(4):
        bounds = [(0.0, 0.0) if t in zeroed else b for t, b in zip(tickers, base_bounds)]
        try:
            ef = _new_frontier(expected_returns, cov_matrix, bounds, tickers, asset_class_of, rng)
            ef.max_quadratic_utility(risk_aversion=risk_aversion)
            candidate = {t: float(v) for t, v in ef.clean_weights(cutoff=1e-4, rounding=8).items()}
        except Exception as e:
            if weights is None:
                raise OptimisationError(f"No portfolio satisfies the risk policy: {e}") from e
            logger.info(f"Could not drop more small positions ({e}); keeping previous solution")
            break
        weights = candidate
        small = {t for t, v in weights.items() if 0 < v < POLICY_MIN_POSITION}
        if not small:
            break
        zeroed |= small

    weights = {t: v for t, v in weights.items() if v > 1e-4}  # solver zeros
    total = sum(weights.values())
    weights = {t: v / total for t, v in weights.items()}

    problems = check_policy(weights, {t: asset_class_of.get(t, "") for t in tickers}, rng)
    if problems:
        raise OptimisationError("Optimiser output breaks the risk policy: " + "; ".join(problems))

    g = sum(w for t, w in weights.items() if sleeve_of(asset_class_of.get(t, "")) == "growth")
    logger.info(f"Risk {risk_score}: growth {g:.1%} (policy {rng[0]:.0%}–{rng[1]:.0%}), "
                f"{len(weights)} positions")
    return {
        "weights": weights,
        "growth_range": rng,
        "growth_target": growth_target(risk_score),
        "growth_weight": g,
        "removed_small_positions": sorted(zeroed),
    }


def max_achievable_return(expected_returns, cov_matrix, bounds, tickers, asset_class_of,
                          growth_rng=None) -> Optional[float]:
    """Highest expected return any policy-compliant portfolio can reach (None if infeasible)."""
    try:
        ef = _new_frontier(expected_returns, cov_matrix, bounds, tickers, asset_class_of, growth_rng)
        return float(ef._max_return(return_value=True))
    except Exception as e:
        logger.warning(f"Max-return problem failed: {e}")
        return None


def compute_tangent_portfolio(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    asset_class_of: Optional[dict[str, str]] = None,
    **_legacy,
) -> Optional[dict[str, float]]:
    """
    Max-Sharpe portfolio under the policy's structural limits (growth share free).

    A tangency portfolio only exists if some ALLOWED portfolio beats the
    risk-free rate — checking the single best asset is not enough when that
    asset (e.g. cash) is capped. Returns None when no allowed portfolio does,
    instead of silently substituting another portfolio.
    """
    tickers = list(expected_returns.index)
    ac_of = asset_class_of or {}
    best = max_achievable_return(expected_returns, cov_matrix, weight_bounds, tickers, ac_of)
    if best is None or best <= risk_free_rate + 1e-6:
        logger.info(f"No tangency portfolio: best achievable return {best} ≤ rf {risk_free_rate:.4f}")
        return None
    # pypfopt's max_sharpe change of variables does not carry arbitrary custom
    # constraints reliably, so take the best Sharpe point on the constrained frontier.
    try:
        pts = compute_efficient_frontier(
            expected_returns, cov_matrix, weight_bounds, n_points=40,
            risk_free_rate=risk_free_rate, asset_class_of=ac_of,
        )
    except OptimisationError as e:
        logger.warning(f"No tangency portfolio: {e}")
        return None
    best_pt = max(pts, key=lambda p: p["sharpe_ratio"])
    return dict(best_pt["weights"])


# =============================================================================
# DUAL MOMENTUM OVERLAY (Optional)
# =============================================================================

def apply_dual_momentum(
    prices: pd.DataFrame,
    weights: dict[str, float],
    cash_ticker: Optional[str] = None,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
) -> dict[str, float]:
    """
    Apply Gary Antonacci's dual momentum overlay.

    If an asset's 12-month momentum is below the cash return over the same
    period (Antonacci's absolute-momentum test), reduce its allocation by
    DUAL_MOMENTUM_REDUCTION (default 50%). Off by default (plan P9); it runs
    after the optimiser, so it can move weights outside the policy ranges.
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
    safe_momentum = risk_free_rate * (DUAL_MOMENTUM_LOOKBACK_MONTHS / 12.0)

    adjusted = dict(weights)
    redistributed = 0.0

    for ticker, weight in list(adjusted.items()):
        if ticker == cash_ticker:
            continue
        if ticker in momentum.index:
            asset_mom = momentum[ticker]
            if asset_mom < safe_momentum:
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
    weight_bounds: Optional[list[tuple[float, float]]] = None,
    n_points: int = MVO_EFFICIENT_FRONTIER_POINTS,
    risk_free_rate: float = MVO_RISK_FREE_RATE,
    asset_class_of: Optional[dict[str, str]] = None,
) -> list[dict]:
    """
    The policy-constrained efficient frontier (all structural limits, growth
    share left free), from the minimum-variance portfolio to the highest
    achievable return.

    Raises:
        OptimisationError: if not even the minimum-variance portfolio is feasible.
    """
    tickers = list(expected_returns.index)
    ac_of = asset_class_of or {}
    bounds = weight_bounds or policy_weight_bounds(tickers, ac_of)

    try:
        ef_min = _new_frontier(expected_returns, cov_matrix, bounds, tickers, ac_of, None)
        ef_min.min_volatility()
        min_ret, _, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)
    except Exception as e:
        raise OptimisationError(f"No feasible portfolio for these asset classes: {e}") from e

    max_ret = max_achievable_return(expected_returns, cov_matrix, bounds, tickers, ac_of)
    if max_ret is None or max_ret <= min_ret:
        max_ret = min_ret

    frontier = []
    for target in np.linspace(min_ret, max_ret * 0.9999 + min_ret * 0.0001, n_points):
        try:
            ef = _new_frontier(expected_returns, cov_matrix, bounds, tickers, ac_of, None)
            ef.efficient_return(target_return=float(target))
            ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            frontier.append({
                "expected_return": round(ret, 6),
                "volatility": round(vol, 6),
                "sharpe_ratio": round(sharpe, 4),
                "weights": {k: round(v, 4) for k, v in ef.clean_weights().items() if v > 0.001},
            })
        except Exception:
            continue
    if not frontier:
        raise OptimisationError("Efficient frontier could not be computed for these asset classes")
    return sorted(frontier, key=lambda p: p["volatility"])


# =============================================================================
# MAIN PIPELINE: BUILD OPTIMISED PORTFOLIO
# =============================================================================

def build_optimised_portfolio(
    risk_score: float,
    investment_amount: float,
    selected_asset_classes: Optional[list[str]] = None,
    investment_horizon_years: Optional[int] = None,
) -> dict:
    """
    Full construction pipeline (see module docstring).

    Parameters:
        risk_score (float): Composite risk score (1–10). Horizon limits are
            already applied to it by the risk profiler.
        investment_amount (float): Total investment in GBP.
        selected_asset_classes (list[str], optional): not honoured — the
            building blocks are fixed by policy; a warning is logged.
        investment_horizon_years: accepted for compatibility; horizon acts
            through the risk score.

    Returns:
        dict: weights by asset class and ticker, allocations, performance,
        frontier, policy details and data diagnostics.
    """
    if selected_asset_classes:
        logger.warning("selected_asset_classes is not honoured: building blocks are fixed by policy")
    asset_classes = select_asset_classes_for_risk(risk_score)

    # ── Tickers, with fallback within a class when data is unusable ──
    from backend.data.returns import has_usable_history
    from backend.config import MIN_HISTORY_MONTHS
    ticker_map, skipped_etfs = resolve_ticker_map(
        asset_classes, usable=lambda t: has_usable_history(t, min_months=MIN_HISTORY_MONTHS)
    )
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}
    if len(tickers) < 2:
        raise ValueError("Need at least 2 asset classes with valid ETFs")

    # ── Inputs ──
    rf_live = get_risk_free_rate()
    expense_by_ticker = {t: get_etf_by_ticker(t)["expense_ratio"] for t in tickers}
    mu, cov_matrix, monthly_returns = build_mu_cov(
        tickers, expense_by_ticker, risk_free_rate=rf_live, asset_class_of=ac_by_ticker,
    )
    mu = apply_cash_forward_rate(mu, ac_by_ticker, rf_live, expense_by_ticker)
    if len(mu) < 2:
        raise ValueError("Insufficient return data after filtering")

    # ── Optional tactical overlay: regime measured on the equity sleeve only ──
    equity_cols = [t for t in monthly_returns.columns if ac_by_ticker.get(t) in EQUITY_REGION_REFERENCE]
    market = None
    if equity_cols:
        w_eq = reference_weights(equity_cols, ac_by_ticker)
        market = (monthly_returns[equity_cols] * w_eq).sum(axis=1, min_count=1)
    crisis = detect_volatility_regime(monthly_returns, market=market)

    # ── Optimise inside the policy ──
    policy = build_policy_portfolio(risk_score, mu, cov_matrix, ac_by_ticker, crisis=crisis)
    final_weights = policy["weights"]

    if USE_DUAL_MOMENTUM:
        prices = build_close_price_matrix(list(mu.index))
        if prices is not None and not prices.empty:
            cash_ticker = next((t for t in mu.index if ac_by_ticker.get(t) in CASH_ASSET_CLASSES), None)
            final_weights = apply_dual_momentum(prices, final_weights, cash_ticker, rf_live)

    perf = get_portfolio_performance(final_weights, mu, cov_matrix, risk_free_rate=rf_live)

    bounds = policy_weight_bounds(list(mu.index), ac_by_ticker)
    tangent = compute_tangent_portfolio(mu, cov_matrix, bounds, rf_live, asset_class_of=ac_by_ticker)
    try:
        frontier = compute_efficient_frontier(
            mu, cov_matrix, bounds, risk_free_rate=rf_live, asset_class_of=ac_by_ticker,
        )
    except OptimisationError as e:
        logger.warning(f"Frontier unavailable: {e}")
        frontier = []

    allocations = []
    total_expense = 0.0
    for ticker, weight in final_weights.items():
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

    by_sleeve: dict[str, float] = {}
    for t, w in final_weights.items():
        s = sleeve_of(ac_by_ticker.get(t, ""))
        by_sleeve[s] = by_sleeve.get(s, 0.0) + w
    cash_w = sum(w for t, w in final_weights.items() if ac_by_ticker.get(t) in CASH_ASSET_CLASSES)

    # Estimation inputs, kept so a portfolio can later show how it was built.
    # Volatilities carry the same client-facing calibration as `perf`.
    tickers_used = list(mu.index)
    cov_used = cov_matrix.loc[tickers_used, tickers_used].to_numpy(dtype=float)
    sd = np.sqrt(np.clip(np.diag(cov_used), 0.0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(np.outer(sd, sd) > 0, cov_used / np.outer(sd, sd), 0.0)
    inputs = {
        "expected_returns": {t: round(float(mu[t]), 6) for t in tickers_used},
        "volatilities": {t: round(float(v) * VOL_CALIBRATION_MULTIPLIER, 6) for t, v in zip(tickers_used, sd)},
        "correlation": {"tickers": tickers_used, "matrix": np.round(corr, 4).tolist()},
        "vol_calibration": VOL_CALIBRATION_MULTIPLIER,
    }

    return {
        "weights": {ac_by_ticker.get(t, t): w for t, w in final_weights.items()},
        "ticker_weights": final_weights,
        "allocations": sorted(allocations, key=lambda a: a["weight"], reverse=True),
        "performance": perf,
        "total_expense_ratio": round(total_expense, 6),
        "frontier": frontier,
        "high_correlation_regime": crisis,
        "crisis_regime": crisis,
        "tangent_portfolio": (
            {ac_by_ticker.get(t, t): round(w, 4) for t, w in tangent.items() if w > 0.001}
            if tangent else None
        ),
        "risk_allocation_alpha": round(policy["growth_weight"], 4),
        "policy": {
            "growth_target": policy["growth_target"],
            "growth_range": list(policy["growth_range"]),
            "growth_weight": round(by_sleeve.get("growth", 0.0), 4),
            "defensive_weight": round(by_sleeve.get("defensive", 0.0), 4),
            "cash_weight": round(cash_w, 4),
        },
        "asset_classes_used": [ac_by_ticker[t] for t in mu.index],
        "etf_fallbacks": skipped_etfs,
        "risk_free_rate": round(rf_live, 6),
        "inputs": inputs,
    }
