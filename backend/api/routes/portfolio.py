"""
Portfolio API Routes — Build & Manage Portfolios
==================================================
Handles portfolio construction, retrieval, and allocation adjustment.
"""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db, init_db
from backend.db.models import Portfolio, Holding, RiskProfile, User, Transaction
from backend.db.ledger_store import mark_to_market, record_fills
from backend.api.models import (
    AllocationItem, ArchiveResponse, ConstructionResponse, PortfolioListItem, PortfolioRequest, PortfolioResponse,
    PreviewAllocation, PreviewRequest, PreviewResponse,
)
from backend.engine.optimizer import OptimisationError, build_optimised_portfolio
from backend.engine.asset_universe import get_etf_by_ticker
from backend.engine.construction import (
    construction_cache, policy_summary, scaled_allocations, snapshot_from_result,
)
from backend.engine.ledger import open_portfolio, valuation
from backend.engine.policy import sleeve_of
from backend.data.prices import get_latest_gbp_prices
from backend.config import RISK_BANDS

router = APIRouter()


def _effective_risk(db: Session, user_id: Optional[int], requested: float) -> float:
    """
    The suitable risk level is the one assessed in the stored profile (with its
    short-horizon cap and conservative adjustments). A request may ask for
    LESS risk, never more.
    """
    if user_id is None:
        return requested
    profile = db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()
    if profile is not None and requested > profile.composite_score:
        return profile.composite_score
    return requested


def _construct(risk_score: float) -> dict:
    """
    The construction for this risk score, reused from a recent preview when
    there is one, so the portfolio opened is the one the investor was shown.
    Built per GBP 1; amounts are scaled per request.
    """
    try:
        result, _ = construction_cache.get_or_build(
            risk_score, lambda: build_optimised_portfolio(risk_score=risk_score, investment_amount=1.0),
        )
        return result
    except OptimisationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {str(e)}")


@router.post("/portfolio/preview", response_model=PreviewResponse)
async def preview_portfolio(request: PreviewRequest, db: Session = Depends(get_db)):
    """
    Build a portfolio without opening it: allocations, expected figures and the
    policy that shaped it. Nothing is stored and nothing is bought. Opening a
    portfolio at the same risk level within a few hours reuses this construction.
    """
    risk_score = _effective_risk(db, request.user_id, request.risk_score)
    result = _construct(risk_score)
    allocations = []
    for a in scaled_allocations(result, request.investment_amount):
        etf = get_etf_by_ticker(a["ticker"])
        allocations.append(PreviewAllocation(
            asset_class=a["asset_class"], sleeve=sleeve_of(a["asset_class"]), ticker=a["ticker"],
            etf_name=etf["name"] if etf else a["ticker"], weight=a["weight"],
            amount_gbp=a["amount_gbp"], expense_ratio=a["expense_ratio"],
        ))
    perf = result["performance"]
    ter = float(result.get("total_expense_ratio") or 0.0)
    return PreviewResponse(
        requested_risk_score=request.risk_score,
        risk_score=risk_score,
        capped=risk_score < request.risk_score,
        risk_band=RISK_BANDS.get(round(risk_score), "Unknown"),
        allocations=allocations,
        expected_annual_return=perf["expected_return"],
        expected_volatility=perf["volatility"],
        sharpe_ratio=perf["sharpe_ratio"],
        total_expense_ratio=ter,
        annual_fund_cost_gbp=round(ter * request.investment_amount, 2),
        risk_free_rate=result.get("risk_free_rate"),
        policy=policy_summary(result),
        as_of=datetime.date.today().isoformat(),
    )


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

    risk_score = _effective_risk(db, request.user_id, request.risk_score)
    result = _construct(risk_score)

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
    for alloc in scaled_allocations(result, request.investment_amount):
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
        construction=snapshot_from_result(result, risk_score),
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
        "archived": portfolio.is_active is False,  # an unset flag counts as on the list
        "archived_at": portfolio.archived_at.isoformat() if portfolio.archived_at else None,
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


@router.get("/portfolios/user/{user_id}", response_model=list[PortfolioListItem])
async def get_user_portfolios(user_id: int, db: Session = Depends(get_db)):
    """
    A user's portfolios, newest first, each valued at its last stored prices
    (no network). A portfolio never valued since the ledger was introduced
    reports no value rather than a guessed one.
    """
    return _list_portfolios(db, user_id, archived=False)


@router.get("/portfolios/user/{user_id}/archived", response_model=list[PortfolioListItem])
async def get_archived_portfolios(user_id: int, db: Session = Depends(get_db)):
    """The portfolios a user has archived, newest first, valued as on their list."""
    return _list_portfolios(db, user_id, archived=True)


def _list_portfolios(db: Session, user_id: int, archived: bool) -> list[PortfolioListItem]:
    from backend.db.ledger_store import is_legacy_holding, last_prices, load_book

    # An unset flag counts as on the list, so no portfolio is ever in neither list.
    on_list = Portfolio.is_active.is_not(False)
    portfolios = db.query(Portfolio).filter(
        Portfolio.user_id == user_id,
        ~on_list if archived else on_list,
    ).order_by(Portfolio.created_at.desc()).all()

    items = []
    for p in portfolios:
        holdings = db.query(Holding).filter(Holding.portfolio_id == p.id).all()
        total_value = None
        if not any(is_legacy_holding(h) for h in holdings):
            book = load_book(p, holdings)
            prices = last_prices(holdings)
            if all(t in prices for t in book.units):
                total_value = round(valuation(book, prices)["total"], 2)
        contrib = p.net_contributions or None
        items.append(PortfolioListItem(
            portfolio_id=p.id,
            name=p.name,
            risk_score=p.risk_score,
            investment_amount=p.investment_amount,
            monthly_contribution=p.monthly_contribution or 0.0,
            uses_isa=bool(p.uses_isa),
            expected_return=p.expected_return,
            created_at=p.created_at.isoformat() if p.created_at else None,
            total_value=total_value,
            net_contributions=contrib,
            total_return_pct=(total_value - contrib) / contrib if total_value is not None and contrib else None,
            last_valued_at=p.last_valued_at.isoformat() if p.last_valued_at else None,
            holdings_count=sum(1 for h in holdings if (h.quantity or 0.0) > 0),
            archived_at=p.archived_at.isoformat() if p.archived_at else None,
        ))
    return items


def _set_archived(db: Session, portfolio_id: int, archived: bool) -> ArchiveResponse:
    """Archives or restores; repeating either is harmless and keeps the first archive date."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if archived and portfolio.archived_at is None:
        portfolio.is_active = False
        portfolio.archived_at = datetime.datetime.utcnow()
    elif not archived:
        portfolio.is_active = True
        portfolio.archived_at = None
    db.commit()
    return ArchiveResponse(
        portfolio_id=portfolio.id,
        archived_at=portfolio.archived_at.isoformat() if portfolio.archived_at else None,
    )


@router.post("/portfolio/{portfolio_id}/archive", response_model=ArchiveResponse)
async def archive_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """Takes a portfolio off its owner's list. Nothing is deleted: it still opens, and can be restored."""
    return _set_archived(db, portfolio_id, archived=True)


@router.post("/portfolio/{portfolio_id}/restore", response_model=ArchiveResponse)
async def restore_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """Puts an archived portfolio back on its owner's list."""
    return _set_archived(db, portfolio_id, archived=False)


@router.get("/portfolio/{portfolio_id}/construction", response_model=ConstructionResponse)
async def get_construction(portfolio_id: int, db: Session = Depends(get_db)):
    """
    How the portfolio was built, as recorded when it was opened: per-fund
    estimates, correlations, the policy and the efficient frontier. Portfolios
    opened before this was recorded return `recorded: false`.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    snapshot = portfolio.construction
    return ConstructionResponse(portfolio_id=portfolio.id, recorded=snapshot is not None, snapshot=snapshot)


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
