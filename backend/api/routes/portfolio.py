"""
Portfolio API Routes — Build & Manage Portfolios
==================================================
Handles portfolio construction, retrieval, and allocation adjustment.
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db, init_db
from backend.db.models import Portfolio, Holding, RiskProfile, User, Transaction
from backend.db.ledger_store import mark_to_market, record_fills
from backend.api.models import PortfolioRequest, PortfolioResponse, AllocationItem
from backend.engine.optimizer import OptimisationError, build_optimised_portfolio
from backend.engine.asset_universe import get_etf_by_ticker
from backend.engine.ledger import open_portfolio, valuation
from backend.data.prices import get_latest_gbp_prices
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

    # The suitable risk level is the one assessed in the stored profile (with
    # its short-horizon cap and conservative adjustments). A request may ask
    # for LESS risk, never more.
    risk_score = request.risk_score
    profile = db.query(RiskProfile).filter(RiskProfile.user_id == request.user_id).first()
    if profile is not None and risk_score > profile.composite_score:
        risk_score = profile.composite_score

    try:
        result = build_optimised_portfolio(
            risk_score=risk_score,
            investment_amount=request.investment_amount,
            selected_asset_classes=getattr(request, 'selected_asset_classes', None),
        )
    except OptimisationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {str(e)}")

    # Price every line in GBP before anything is stored: a portfolio is only
    # opened at real prices, never at an assumed one.
    target_by_ticker = result["ticker_weights"]
    quotes = get_latest_gbp_prices(list(target_by_ticker))
    missing = [t for t in target_by_ticker if t not in quotes]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"No current price for {', '.join(missing)}; portfolio not opened. Try again later.",
        )
    prices = {t: q[0] for t, q in quotes.items()}
    book, fills = open_portfolio(request.investment_amount, target_by_ticker, prices)
    val = valuation(book, prices)

    excess_return = result["performance"]["expected_return"] - result["risk_free_rate"]

    # Build allocation items (name taken from the ticker actually bought)
    allocations = []
    for alloc in result["allocations"]:
        etf = get_etf_by_ticker(alloc["ticker"])
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
        risk_score=risk_score,
        target_allocations=result["weights"],
        selected_asset_classes=result.get("asset_classes_used", request.selected_asset_classes),
        investment_amount=request.investment_amount,
        monthly_contribution=request.monthly_contribution,
        uses_isa=request.uses_isa,
        expected_return=result["performance"]["expected_return"],
        expected_volatility=result["performance"]["volatility"],
        sharpe_ratio=result["performance"]["sharpe_ratio"],
        alpha=excess_return,  # expected return over the live risk-free rate
        total_return_pct=0.0,
        cash_gbp=book.cash,
        net_contributions=request.investment_amount,
        last_valued_at=datetime.datetime.utcnow(),
    )
    db.add(portfolio)
    db.flush()

    # Save holdings: units, GBP cost per unit and the price they were bought at
    ac_by_ticker = {a["ticker"]: a["asset_class"] for a in result["allocations"]}
    for ticker, weight in target_by_ticker.items():
        price, as_of = quotes[ticker]
        db.add(Holding(
            portfolio_id=portfolio.id,
            ticker=ticker,
            asset_class=ac_by_ticker.get(ticker, "unknown"),
            quantity=book.units.get(ticker, 0.0),
            average_cost=book.avg_cost.get(ticker, 0.0),
            target_weight=weight,
            current_weight=val["weights"].get(ticker, 0.0),
            current_price=price,
            price_as_of=datetime.datetime.combine(as_of, datetime.time()),
        ))

    db.add(Transaction(
        portfolio_id=portfolio.id, ticker="CASH", action="deposit", quantity=0.0,
        price=1.0, value=request.investment_amount, notes="Initial investment",
    ))
    record_fills(db, portfolio.id, fills, notes="Initial purchase")
    db.commit()

    risk_band = RISK_BANDS.get(round(risk_score), "Unknown")

    return PortfolioResponse(
        portfolio_id=portfolio.id,
        risk_score=risk_score,
        risk_band=risk_band,
        allocations=allocations,
        expected_annual_return=result["performance"]["expected_return"],
        expected_volatility=result["performance"]["volatility"],
        sharpe_ratio=result["performance"]["sharpe_ratio"],
        alpha=excess_return,
        total_return_pct=0.0,
        total_expense_ratio=result["total_expense_ratio"],
        investment_amount=request.investment_amount,
        tangent_portfolio=result.get("tangent_portfolio"),
        risk_allocation_alpha=result.get("risk_allocation_alpha"),
        asset_classes_used=result.get("asset_classes_used"),
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
        "monthly_contribution": portfolio.monthly_contribution or 0.0,
        "uses_isa": bool(portfolio.uses_isa),
        "expected_return": portfolio.expected_return,
        "expected_volatility": portfolio.expected_volatility,
        "sharpe_ratio": portfolio.sharpe_ratio,
        "cash": portfolio.cash_gbp or 0.0,
        "net_contributions": portfolio.net_contributions or 0.0,
        "total_return_pct": portfolio.total_return_pct or 0.0,
        "last_valued_at": portfolio.last_valued_at.isoformat() if portfolio.last_valued_at else None,
        "holdings": [
            {
                "ticker": h.ticker,
                "asset_class": h.asset_class,
                "units": h.quantity,
                "average_cost": h.average_cost,
                "current_price": h.current_price,
                "price_as_of": h.price_as_of.date().isoformat() if h.price_as_of else None,
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


@router.post("/portfolio/{portfolio_id}/refresh")
async def refresh_portfolio_prices(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Mark the portfolio to market at the latest GBP prices.

    Value = units × price for each holding, plus cash. Return is measured on
    net contributions. Holdings that could not be priced keep their last price
    and are listed in `stale_tickers`.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    val = mark_to_market(portfolio, holdings, fetch=True)
    db.commit()

    return {
        "portfolio_id": portfolio.id,
        "total_value": round(val["total"], 2),
        "invested_value": round(val["invested"], 2),
        "cash": round(val["cash"], 2),
        "net_contributions": round(val["net_contributions"], 2),
        "total_return_pct": val["total_return_pct"],
        "stale_tickers": val["stale_tickers"],
        "unpriced_tickers": val["unpriced_tickers"],
        "valued_at": portfolio.last_valued_at.isoformat(),
        "status": "refreshed",
    }
