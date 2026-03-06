"""
Performance API Routes — Dashboard Data
==========================================
Endpoints for portfolio performance tracking, rebalancing checks, and analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Portfolio, Holding, Transaction
from backend.api.models import RebalanceResponse, RebalanceTrade
from backend.engine.rebalancer import (
    needs_rebalance,
    max_drift_value,
    compute_drift,
    generate_rebalance_trades,
)
from backend.engine.asset_universe import get_ticker_map, get_primary_etf_for_class
from backend.data.market_data import get_current_price

router = APIRouter()


@router.get("/performance/{portfolio_id}")
async def get_performance(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Get portfolio performance metrics and current holdings.

    Parameters:
        portfolio_id (int): Portfolio ID.

    Returns:
        dict: Performance data including holdings, metrics, and drift analysis.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    target_allocations = portfolio.target_allocations or {}

    # Compute current weights (simplified — uses target as proxy if no live data)
    current_weights = {}
    for h in holdings:
        current_weights[h.asset_class] = h.current_weight or h.target_weight

    # Drift analysis
    drift = compute_drift(current_weights, target_allocations)
    rebalance_needed = needs_rebalance(current_weights, target_allocations)
    max_d = max_drift_value(current_weights, target_allocations)

    return {
        "portfolio_id": portfolio.id,
        "investment_amount": portfolio.investment_amount,
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
        "drift": drift,
        "needs_rebalance": rebalance_needed,
        "max_drift": round(max_d, 4),
        "target_allocations": target_allocations,
    }


@router.get("/rebalance/{portfolio_id}", response_model=RebalanceResponse)
async def check_rebalance(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Check if a portfolio needs rebalancing and generate trade suggestions.

    Parameters:
        portfolio_id (int): Portfolio ID.

    Returns:
        RebalanceResponse: Rebalancing analysis with suggested trades.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    target_allocations = portfolio.target_allocations or {}

    current_weights = {}
    for h in holdings:
        current_weights[h.asset_class] = h.current_weight or h.target_weight

    rebalance_needed = needs_rebalance(current_weights, target_allocations)
    max_d = max_drift_value(current_weights, target_allocations)

    trades = []
    if rebalance_needed:
        ticker_map = get_ticker_map(list(target_allocations.keys()))

        # Get current prices
        prices = {}
        for ac, ticker in ticker_map.items():
            price = get_current_price(ticker)
            if price:
                prices[ticker] = price

        raw_trades = generate_rebalance_trades(
            current_weights=current_weights,
            target_weights=target_allocations,
            total_portfolio_value=portfolio.investment_amount,
            ticker_map=ticker_map,
            prices=prices,
        )

        for t in raw_trades:
            etf = get_primary_etf_for_class(t["asset_class"])
            trades.append(RebalanceTrade(
                ticker=t["ticker"],
                etf_name=etf["name"] if etf else t["ticker"],
                action=t["action"],
                current_weight=t["current_weight"],
                target_weight=t["target_weight"],
                trade_value_gbp=t["trade_value_gbp"],
                quantity=t["quantity"],
            ))

    return RebalanceResponse(
        needs_rebalance=rebalance_needed,
        max_drift=round(max_d, 4),
        trades=trades,
        before_allocations=current_weights,
        after_allocations=target_allocations,
    )


@router.get("/transactions/{portfolio_id}")
async def get_transactions(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Get transaction history for a portfolio.

    Parameters:
        portfolio_id (int): Portfolio ID.

    Returns:
        list[dict]: Transaction records.
    """
    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).order_by(Transaction.timestamp.desc()).all()

    return [
        {
            "id": t.id,
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": t.price,
            "value": t.value,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "notes": t.notes,
        }
        for t in transactions
    ]
