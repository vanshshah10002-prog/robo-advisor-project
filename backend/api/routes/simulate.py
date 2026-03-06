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
    compute_efficient_frontier,
    get_portfolio_performance,
    _get_weight_bounds,
)
from backend.engine.expected_returns import get_expected_returns
from backend.engine.covariance import compute_covariance
from backend.engine.monte_carlo import run_monte_carlo, quick_projection
from backend.engine.asset_universe import get_ticker_map, get_expense_ratios
from backend.data.market_data import build_close_price_matrix
from backend.config import MVO_RISK_FREE_RATE

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

    # Build price matrix
    ticker_map = get_ticker_map(classes)
    tickers = list(ticker_map.values())
    ac_by_ticker = {v: k for k, v in ticker_map.items()}

    prices = build_close_price_matrix(tickers)
    if prices is None:
        raise HTTPException(status_code=500, detail="Could not fetch price data")

    # Compute inputs
    cov_matrix = compute_covariance(prices)
    expense_ratios = get_expense_ratios(classes)
    expense_by_ticker = {ticker_map[ac]: er for ac, er in expense_ratios.items()}
    mu = get_expected_returns(prices, cov_matrix, expense_by_ticker)

    weight_bounds = _get_weight_bounds(tickers, ac_by_ticker)

    # Compute frontier
    frontier = compute_efficient_frontier(mu, cov_matrix, weight_bounds)

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
        risk_free_rate=MVO_RISK_FREE_RATE,
    )


@router.post("/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo_simulation(
    request: MonteCarloRequest,
    db: Session = Depends(get_db),
):
    """
    Run Monte Carlo simulation for a portfolio.

    Can use either a saved portfolio (by portfolio_id) or ad-hoc weights.

    Parameters:
        request (MonteCarloRequest): Simulation parameters.

    Returns:
        MonteCarloResponse: Percentile paths and statistics.
    """
    if request.portfolio_id:
        # Load portfolio weights
        portfolio = db.query(Portfolio).filter(Portfolio.id == request.portfolio_id).first()
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Use quick projection with saved performance metrics
        result = quick_projection(
            initial_investment=request.initial_investment,
            monthly_contribution=request.monthly_contribution,
            annual_return=portfolio.expected_return or 0.06,
            annual_volatility=portfolio.expected_volatility or 0.12,
            years=request.years,
            n_simulations=request.n_simulations,
        )
    elif request.weights:
        # Ad-hoc weights — need full computation
        tickers = list(request.weights.keys())
        prices = build_close_price_matrix(tickers)

        if prices is None:
            raise HTTPException(status_code=500, detail="Could not fetch price data")

        cov_matrix = compute_covariance(prices)
        mu = get_expected_returns(prices, cov_matrix, {})

        result = run_monte_carlo(
            initial_investment=request.initial_investment,
            monthly_contribution=request.monthly_contribution,
            weights=request.weights,
            expected_returns=mu,
            cov_matrix=cov_matrix,
            years=request.years,
            n_simulations=request.n_simulations,
        )
    else:
        raise HTTPException(status_code=400, detail="Provide portfolio_id or weights")

    return MonteCarloResponse(**result)
