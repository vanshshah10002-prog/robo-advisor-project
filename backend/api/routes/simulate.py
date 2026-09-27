"""
Simulation API Routes — Efficient Frontier & Monte Carlo
==========================================================
Endpoints for portfolio simulation, frontier visualization, and projections.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Portfolio
from backend.api.models import (
    EfficientFrontierResponse,
    EfficientFrontierPoint,
    MonteCarloRequest,
    MonteCarloResponse,
)
from backend.engine.optimizer import (
    OptimisationError,
    apply_cash_forward_rate,
    compute_efficient_frontier,
)
from backend.engine.policy import weight_bounds as policy_weight_bounds
from backend.engine.expected_returns import build_mu_cov
from backend.engine.monte_carlo import run_monte_carlo, quick_projection
from backend.engine.asset_universe import get_etf_by_ticker, resolve_ticker_map
from backend.data.rates import get_risk_free_rate

router = APIRouter()


@router.get("/efficient-frontier", response_model=EfficientFrontierResponse)
async def get_efficient_frontier(
    asset_classes: str = Query(..., description="Comma-separated asset classes"),
    risk_score: float = Query(default=5.0, ge=1.0, le=10.0),
):
    """
    Compute and return the efficient frontier for given asset classes.
    Also returns the current portfolio point for the given risk score.

    Parameters:
        asset_classes (str): Comma-separated asset class identifiers.
        risk_score (float): Current risk score to highlight.

    Returns:
        EfficientFrontierResponse: Frontier points and current portfolio.
    """
    classes = [c.strip() for c in asset_classes.split(",")]

    if len(classes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 asset classes")

    ticker_map, _ = resolve_ticker_map(classes)
    unknown = [c for c in classes if c not in ticker_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"No investable ETF for: {', '.join(unknown)}")
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}

    # Live GBP risk-free rate (yfinance proxy; config fallback)
    rf_live = get_risk_free_rate()

    expense_by_ticker = {t: get_etf_by_ticker(t)["expense_ratio"] for t in tickers}
    try:
        mu, cov_matrix, _ = build_mu_cov(
            tickers, expense_by_ticker, risk_free_rate=rf_live, asset_class_of=ac_by_ticker,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Same cash assumption as portfolio construction: forward return = live rate.
    mu = apply_cash_forward_rate(mu, ac_by_ticker, rf_live, expense_by_ticker)

    try:
        frontier = compute_efficient_frontier(
            mu, cov_matrix, policy_weight_bounds(list(mu.index), ac_by_ticker),
            risk_free_rate=rf_live, asset_class_of=ac_by_ticker,
        )
    except OptimisationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    frontier_points = [
        EfficientFrontierPoint(
            expected_return=p["expected_return"],
            volatility=p["volatility"],
            sharpe_ratio=p["sharpe_ratio"],
            weights=p["weights"],
        )
        for p in frontier
    ]

    return EfficientFrontierResponse(
        frontier_points=frontier_points,
        risk_free_rate=rf_live,
    )


@router.post("/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo_simulation(
    request: MonteCarloRequest,
    db: Session = Depends(get_db),
):
    """
    Run Monte Carlo simulation for a portfolio.

    Uses a saved portfolio (portfolio_id), ad-hoc fund weights, or
    portfolio-level annual_return and annual_volatility (an unsaved preview).
    Optional goal (in today's money) and real-terms output.

    Parameters:
        request (MonteCarloRequest): Simulation parameters.

    Returns:
        MonteCarloResponse: Percentile paths and statistics.
    """
    options = {"goal_amount": request.goal_amount, "real_terms": request.real_terms}
    if request.portfolio_id:
        # A saved portfolio: project with the figures stored when it was built.
        portfolio = db.query(Portfolio).filter(Portfolio.id == request.portfolio_id).first()
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        if portfolio.expected_return is None or not portfolio.expected_volatility:
            raise HTTPException(
                status_code=422,
                detail="This portfolio has no stored expected return and volatility to project from",
            )
        result = quick_projection(
            initial_investment=request.initial_investment,
            monthly_contribution=request.monthly_contribution,
            annual_return=portfolio.expected_return,
            annual_volatility=portfolio.expected_volatility,
            years=request.years,
            n_simulations=request.n_simulations,
            **options,
        )
    elif request.weights:
        # Ad-hoc weights: estimate inputs for those funds.
        tickers = list(request.weights.keys())
        try:
            mu, cov_matrix, _ = build_mu_cov(tickers, {})
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))

        result = run_monte_carlo(
            initial_investment=request.initial_investment,
            monthly_contribution=request.monthly_contribution,
            weights=request.weights,
            expected_returns=mu,
            cov_matrix=cov_matrix,
            years=request.years,
            n_simulations=request.n_simulations,
            **options,
        )
    elif request.annual_return is not None and request.annual_volatility is not None:
        # A preview not yet saved: project with its portfolio-level figures.
        result = quick_projection(
            initial_investment=request.initial_investment,
            monthly_contribution=request.monthly_contribution,
            annual_return=request.annual_return,
            annual_volatility=request.annual_volatility,
            years=request.years,
            n_simulations=request.n_simulations,
            **options,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide portfolio_id, weights, or annual_return with annual_volatility",
        )

    return MonteCarloResponse(**result)
