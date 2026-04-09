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
)
from backend.engine.covariance import compute_covariance, detect_high_correlation_regime
from backend.engine.expected_returns import get_expected_returns
from backend.engine.asset_universe import get_ticker_map, get_expense_ratios
from backend.data.market_data import build_close_price_matrix

logger = logging.getLogger(__name__)


# =============================================================================
# RISK-BASED ASSET CLASS SELECTION
# =============================================================================

# Maps risk score ranges to appropriate asset class mixes
# The robo advisor selects these — the user provides risk tolerance, not classes
RISK_ASSET_PROFILES: dict[str, list[str]] = {
    # Conservative: primarily bonds + UK equity + gold + Indian bonds
    "conservative": [
        "uk_equity", "global_equity", "uk_gilts", "uk_bonds",
        "uk_inflation_linked", "global_bonds", "corporate_bonds",
        "commodities_gold", "indian_bonds", "indian_gold"
    ],
    # Balanced: diversified equity/bond mix + REITs + commodities + Indian large cap
    "balanced": [
        "uk_equity", "uk_mid_cap", "global_equity", "us_equity",
        "emerging_market_equity", "europe_equity",
        "uk_gilts", "uk_bonds", "global_bonds", "corporate_bonds",
        "commodities_gold", "uk_reits",
        "indian_large_cap", "indian_bonds", "indian_sector_financials", "indian_gold"
    ],
    # Growth: equity-heavy with some bonds + alternatives + Indian mid/small
    "growth": [
        "uk_equity", "uk_mid_cap", "global_equity", "us_equity",
        "us_tech", "emerging_market_equity", "japan_equity",
        "europe_equity", "asia_pacific_equity",
        "uk_gilts", "global_bonds",
        "commodities_gold", "commodities_broad",
        "uk_reits", "global_reits",
        "global_small_cap", "global_dividend",
        "indian_large_cap", "indian_mid_cap", "indian_sector_it",
        "indian_arbitrage_us_tech", "indian_arbitrage_us_equity"
    ],
    # Aggressive: maximum equity exposure + alternatives + Indian high risk
    "aggressive": [
        "uk_equity", "uk_mid_cap", "global_equity", "us_equity",
        "us_tech", "emerging_market_equity", "japan_equity",
        "europe_equity", "asia_pacific_equity",
        "uk_gilts",
        "commodities_gold", "commodities_broad",
        "uk_reits", "global_reits",
        "infrastructure",
        "global_small_cap", "global_dividend",
        "global_value", "global_momentum", "global_quality",
        "indian_large_cap", "indian_mid_cap", "indian_small_cap",
        "indian_factor_momentum", "indian_arbitrage_us_tech", "indian_arbitrage_us_equity"
    ],
}


def select_asset_classes_for_risk(risk_score: float) -> list[str]:
    """
    Automatically select appropriate asset classes for a given risk score.
    The ROBO ADVISOR makes this decision — not the user.

    Risk mapping:
        1-3  → conservative (bonds-heavy)
        4-5  → balanced
        6-7  → growth (equity-heavy)
        8-10 → aggressive (maximum equity, alternatives)

    Parameters:
        risk_score (float): Composite risk score 1–10.

    Returns:
        list[str]: Selected asset class identifiers.
    """
    if risk_score <= 3:
        profile = "conservative"
    elif risk_score <= 5:
        profile = "balanced"
    elif risk_score <= 7:
        profile = "growth"
    else:
        profile = "aggressive"

    selected = RISK_ASSET_PROFILES[profile]
    logger.info(
        f"Risk score {risk_score} → profile '{profile}' → {len(selected)} asset classes"
    )
    return selected


# =============================================================================
# WEIGHT BOUNDS
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
# ONE-FUND THEOREM: TANGENT PORTFOLIO COMPUTATION
# =============================================================================

def compute_tangent_portfolio(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    weight_bounds: list[tuple[float, float]],
    risk_free_rate: float = MVO_RISK_FREE_RATE,
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

def get_target_volatility(risk_score: float) -> float:
    """
    Map Risk Score 1-10 to a Target Volatility percentage.
    Risk 1 (Conservative)  ≈ 5% annual volatility
    Risk 5 (Balanced)      ≈ 12% annual volatility
    Risk 10 (Aggressive)   ≈ 22% annual volatility
    """
    # Linear interpolation between 5% and 22%
    min_vol, max_vol = 0.05, 0.22
    target = min_vol + (float(risk_score) - 1.0) / 9.0 * (max_vol - min_vol)
    return round(target, 4)


def select_target_risk_portfolio(
    frontier_points: list[dict],
    risk_score: float,
    investment_horizon_years: int = 10,
) -> dict[str, float]:
    """
    Select the portfolio point on the efficient frontier closest to the target volatility.
    The ROBO ADVISOR matches the risk profile to the MPT-optimal weights.

    Parameters:
        frontier_points (list[dict]): E.F. points sorted by volatility.
        risk_score (float): 1-10.
        investment_horizon_years (int): Time horizon.

    Returns:
        dict[str, float]: Chosen ticker weights.
    """
    if not frontier_points:
        return {}

    # Target Volatility from Risk Score
    target_vol = get_target_volatility(risk_score)

    # Find the point in frontier closest to target_vol
    # frontier_points is already sorted by volatility
    best_match = frontier_points[0]
    min_diff = float('inf')

    for point in frontier_points:
        diff = abs(point["volatility"] - target_vol)
        if diff < min_diff:
            min_diff = diff
            best_match = point
        else:
            # Since it's sorted, if diff start increasing, we found our local min
            break

    logger.info(f"Risk Score {risk_score} -> Target Vol {target_vol:.2%} "
                f"-> Selected Point Vol {best_match['volatility']:.2%}")
    return best_match["weights"]


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
    port_vol = float(np.sqrt(np.dot(w.T, np.dot(cov_sub, w))))
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

    return {
        "expected_return": round(port_return, 6),
        "volatility": round(port_vol, 6),
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

    max_ret = expected_returns.max()
    if max_ret <= risk_free_rate:
        safe_rf = max_ret - 0.01 if max_ret > 0.01 else 0.0
        risk_free_rate = safe_rf

    try:
        # Find min and max achievable returns
        ef_min = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        ef_min.min_volatility()
        min_ret, min_vol, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

        ef_max = EfficientFrontier(expected_returns, cov_matrix, weight_bounds=weight_bounds)
        ef_max.max_sharpe(risk_free_rate=risk_free_rate)
        max_ret, _, _ = ef_max.portfolio_performance(risk_free_rate=risk_free_rate)

        # Extend slightly beyond max Sharpe
        target_returns = np.linspace(min_ret, max_ret * 1.1, n_points)

        for target in target_returns:
            try:
                ef = EfficientFrontier(
                    expected_returns, cov_matrix, weight_bounds=weight_bounds,
                )
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
    asset_classes = select_asset_classes_for_risk(risk_score)
    logger.info(f"Strictly selected {len(asset_classes)} asset classes for risk={risk_score}")

    # ── Step 2: Map to ETF tickers ──
    ticker_map = get_ticker_map(asset_classes)
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}

    if len(tickers) < 2:
        raise ValueError("Need at least 2 asset classes with valid ETFs")

    # ── Step 3: Fetch prices ──
    prices = build_close_price_matrix(tickers)
    if prices is None or prices.empty:
        raise ValueError("Could not fetch price data for the selected ETFs")

    # Drop tickers with insufficient data
    min_days = 60
    valid_cols = [c for c in prices.columns if prices[c].dropna().shape[0] >= min_days]
    if len(valid_cols) < 2:
        raise ValueError(f"Only {len(valid_cols)} ETFs have sufficient price history")
    prices = prices[valid_cols]
    tickers = valid_cols

    # ── Step 4: Covariance matrix (Ledoit-Wolf shrinkage) ──
    cov_matrix = compute_covariance(prices)

    # ── Step 5: Expected returns (CAPM/BL, cost-adjusted) ──
    expense_ratios = get_expense_ratios(asset_classes)
    expense_by_ticker = {ticker_map[ac]: er for ac, er in expense_ratios.items()
                         if ac in ticker_map and ticker_map[ac] in tickers}
    mu = get_expected_returns(prices, cov_matrix, expense_by_ticker)

    # Filter to only tickers still in our prices DataFrame
    mu = mu.reindex(tickers).dropna()
    cov_matrix = cov_matrix.loc[mu.index, mu.index]

    if len(mu) < 2:
        raise ValueError("Insufficient return data after filtering")

    # ── Step 6: Regime detection ──
    high_corr = detect_high_correlation_regime(cov_matrix)

    # ── Step 7: Weight bounds ──
    weight_bounds = _get_weight_bounds(list(mu.index), ac_by_ticker)

    # ── Step 8: Efficient frontier computation first (to replace one fund caching) ──
    frontier = compute_efficient_frontier(mu, cov_matrix, weight_bounds)

    # Fallback to tangent if frontier is empty
    tangent_weights = {}
    if not frontier:
        tangent_weights = compute_tangent_portfolio(mu, cov_matrix, weight_bounds)
        frontier = [{"weights": tangent_weights, "expected_return": 0, "volatility": 0, "sharpe_ratio": 0}]
    else:
        # Reconstruct tangent from max sharpe logic if needed, but for metric
        tangent_weights = compute_tangent_portfolio(mu, cov_matrix, weight_bounds)

    # ── Step 9: 100% ETF Risk Targeting ──
    optimal_weights = select_target_risk_portfolio(frontier, risk_score, investment_horizon_years)
    blended = dict(optimal_weights)

    # ── Step 10: Apply crisis safe-bond buffer (replaced cash) ──
    safe_bond_ticker = ticker_map.get("indian_bonds") or ticker_map.get("uk_gilts")
    if high_corr and safe_bond_ticker and safe_bond_ticker in mu.index:
        current_safe = blended.get(safe_bond_ticker, 0)
        blended[safe_bond_ticker] = current_safe + CRISIS_CASH_BUFFER
        # Reduce proportionally from risky active positions
        total = sum(w for t, w in blended.items() if t != safe_bond_ticker)
        if total > 0:
            scale = (total - CRISIS_CASH_BUFFER) / total
            for t in list(blended.keys()):
                if t != safe_bond_ticker:
                    blended[t] *= scale
        logger.warning(f"Crisis bond buffer applied: +{CRISIS_CASH_BUFFER:.0%} {safe_bond_ticker}")

    # ── Step 11: Dual momentum overlay ──
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

    # ── Performance metrics ──
    perf = get_portfolio_performance(final_weights, mu, cov_matrix)

    # ── Efficient frontier ──
    frontier = compute_efficient_frontier(mu, cov_matrix, weight_bounds)

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
        "asset_classes_used": asset_classes,
    }
