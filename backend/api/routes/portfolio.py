"""
Portfolio API Routes — Build & Manage Portfolios
==================================================
Handles portfolio construction, retrieval, and allocation adjustment.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db, init_db
from backend.db.models import Portfolio, Holding, User
from backend.api.models import PortfolioRequest, PortfolioResponse, AllocationItem
from backend.engine.optimizer import build_optimised_portfolio
from backend.engine.asset_universe import get_primary_etf_for_class
from backend.config import RISK_BANDS

router = APIRouter()


@router.post("/portfolio", response_model=PortfolioResponse)
async def create_portfolio(
    request: PortfolioRequest,
    db: Session = Depends(get_db),
):
    """
    Build an optimised portfolio for a user based on their risk score
    and selected asset classes.

    Runs the full MVO pipeline: fetch prices → compute expected returns
    (CAPM/BL) → compute covariance (Ledoit-Wolf) → optimise → apply
    overlays (dual momentum, regime detection).

    Parameters:
        request (PortfolioRequest): Risk score, asset classes, investment amount.

    Returns:
        PortfolioResponse: Optimised allocations with performance metrics.
    """
    init_db()

    # Auto-create user if not found (allows anonymous optimization)
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        user = User(id=request.user_id, name="Advisor User")
        db.add(user)
        db.flush()

    # Run optimisation
    try:
        result = build_optimised_portfolio(
            selected_asset_classes=request.selected_asset_classes,
            risk_score=request.risk_score,
            investment_amount=request.investment_amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {str(e)}")

    # Build allocation items
    allocations = []
    for alloc in result["allocations"]:
        etf = get_primary_etf_for_class(alloc["asset_class"])
        allocations.append(AllocationItem(
            asset_class=alloc["asset_class"],
            weight=alloc["weight"],
            ticker=alloc["ticker"],
            etf_name=etf["name"] if etf else alloc["ticker"],
            expense_ratio=alloc["expense_ratio"],
            amount_gbp=alloc["amount_gbp"],
        ))

    # Save portfolio to database
    portfolio = Portfolio(
        user_id=request.user_id,
        risk_score=request.risk_score,
        target_allocations=result["weights"],
        selected_asset_classes=request.selected_asset_classes,
        investment_amount=request.investment_amount,
        monthly_contribution=request.monthly_contribution,
        uses_isa=request.uses_isa,
        expected_return=result["performance"]["expected_return"],
        expected_volatility=result["performance"]["volatility"],
        sharpe_ratio=result["performance"]["sharpe_ratio"],
    )
    db.add(portfolio)
    db.flush()

    # Save holdings
    for alloc in result["allocations"]:
        holding = Holding(
            portfolio_id=portfolio.id,
            ticker=alloc["ticker"],
            asset_class=alloc["asset_class"],
            quantity=alloc["amount_gbp"],  # Simplified: store as value
            target_weight=alloc["weight"],
            current_weight=alloc["weight"],
        )
        db.add(holding)

    db.commit()

    risk_band = RISK_BANDS.get(round(request.risk_score), "Unknown")

    return PortfolioResponse(
        portfolio_id=portfolio.id,
        risk_score=request.risk_score,
        risk_band=risk_band,
        allocations=allocations,
        expected_annual_return=result["performance"]["expected_return"],
        expected_volatility=result["performance"]["volatility"],
        sharpe_ratio=result["performance"]["sharpe_ratio"],
        total_expense_ratio=result["total_expense_ratio"],
        investment_amount=request.investment_amount,
    )


@router.get("/portfolio/{portfolio_id}")
async def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a saved portfolio by ID.

    Parameters:
        portfolio_id (int): Portfolio ID.

    Returns:
        dict: Portfolio data with allocations and metrics.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()

    return {
        "portfolio_id": portfolio.id,
        "risk_score": portfolio.risk_score,
        "target_allocations": portfolio.target_allocations,
        "selected_asset_classes": portfolio.selected_asset_classes,
        "investment_amount": portfolio.investment_amount,
        "monthly_contribution": portfolio.monthly_contribution,
        "uses_isa": portfolio.uses_isa,
        "expected_return": portfolio.expected_return,
        "expected_volatility": portfolio.expected_volatility,
        "sharpe_ratio": portfolio.sharpe_ratio,
        "holdings": [
            {
                "ticker": h.ticker,
                "asset_class": h.asset_class,
                "target_weight": h.target_weight,
                "current_weight": h.current_weight,
            }
            for h in holdings
        ],
    }


@router.get("/portfolios/user/{user_id}")
async def get_user_portfolios(user_id: int, db: Session = Depends(get_db)):
    """
    List all portfolios for a user.

    Parameters:
        user_id (int): User ID.

    Returns:
        list[dict]: Summary of each portfolio.
    """
    portfolios = db.query(Portfolio).filter(
        Portfolio.user_id == user_id,
        Portfolio.is_active == True,
    ).all()

    return [
        {
            "portfolio_id": p.id,
            "name": p.name,
            "risk_score": p.risk_score,
            "investment_amount": p.investment_amount,
            "expected_return": p.expected_return,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in portfolios
    ]
