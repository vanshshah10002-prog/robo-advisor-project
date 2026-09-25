"""
Performance API Routes — Dashboard Data
==========================================
Endpoints for portfolio valuation, drift checks, rebalancing and deposits.
All figures come from the holdings ledger (units × GBP price); see
backend/engine/ledger.py and backend/engine/rebalancer.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Portfolio, Holding, Transaction
from backend.db.ledger_store import load_book, mark_to_market, record_fills, save_book
from backend.api.models import (
    ContributionRequest,
    RebalanceResponse,
    RebalanceTrade,
)
from backend.engine.asset_universe import get_etf_by_ticker
from backend.engine.ledger import buy, sell
from backend.engine.policy import growth_tolerance_range, sleeve_of
from backend.engine.rebalancer import (
    check_drift,
    max_drift_value,
    plan_inflow,
    plan_rebalance,
)

router = APIRouter()


def _load(db: Session, portfolio_id: int) -> tuple[Portfolio, list[Holding]]:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    return portfolio, holdings


def _targets(holdings: list[Holding]) -> dict[str, float]:
    """Target weights keyed by the ticker actually held (not the registry's current pick)."""
    return {h.ticker: h.target_weight for h in holdings if (h.target_weight or 0.0) > 0}


def _drift_report(weights: dict[str, float], targets: dict[str, float], holdings: list[Holding]):
    """Band, portfolio-drift and growth-share (policy ±5pp) triggers."""
    group_of = {h.ticker: sleeve_of(h.asset_class) for h in holdings}
    target_growth = sum(w for t, w in targets.items() if group_of.get(t) == "growth")
    return check_drift(weights, targets, group_of, {"growth": growth_tolerance_range(target_growth)})


def _asset_class_weights(weights: dict[str, float], holdings: list[Holding]) -> dict[str, float]:
    ac = {h.ticker: h.asset_class for h in holdings}
    out: dict[str, float] = {}
    for t, w in weights.items():
        out[ac.get(t, t)] = out.get(ac.get(t, t), 0.0) + w
    return {k: round(v, 4) for k, v in out.items()}


@router.get("/performance/{portfolio_id}")
async def get_performance(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Portfolio value, return and drift at the last marked prices (call
    POST /portfolio/{id}/refresh first for live prices).
    """
    portfolio, holdings = _load(db, portfolio_id)
    val = mark_to_market(portfolio, holdings, fetch=False)
    targets = _targets(holdings)
    report = _drift_report(val["weights"], targets, holdings)
    db.commit()

    return {
        "portfolio_id": portfolio.id,
        "investment_amount": portfolio.investment_amount,
        "net_contributions": round(val["net_contributions"], 2),
        "total_value": round(val["total"], 2),
        "cash": round(val["cash"], 2),
        "total_return_pct": val["total_return_pct"],
        "valued_at": portfolio.last_valued_at.isoformat() if portfolio.last_valued_at else None,
        "expected_return": portfolio.expected_return,
        "expected_volatility": portfolio.expected_volatility,
        "sharpe_ratio": portfolio.sharpe_ratio,
        "holdings": [
            {
                "ticker": h.ticker,
                "asset_class": h.asset_class,
                "units": h.quantity,
                "average_cost": h.average_cost,
                "current_price": h.current_price,
                "current_value": round(val["values"].get(h.ticker, 0.0), 2),
                "unrealised_pnl": round(
                    val["values"].get(h.ticker, 0.0) - (h.quantity or 0.0) * (h.average_cost or 0.0), 2
                ),
                "target_weight": h.target_weight,
                "current_weight": val["weights"].get(h.ticker, 0.0),
                "band": round(report.bands.get(h.ticker, 0.0), 4),
            }
            for h in holdings
        ],
        "drift": report.drift,
        "portfolio_drift": round(report.portfolio_drift, 4),
        "needs_rebalance": report.needs_rebalance,
        "rebalance_reasons": report.reasons,
        "max_drift": round(max_drift_value(val["weights"], targets), 4),
        "target_allocations": portfolio.target_allocations,
        "unpriced_tickers": val["unpriced_tickers"],
    }


def _plan(portfolio: Portfolio, holdings: list[Holding], val: dict):
    targets = _targets(holdings)
    report = _drift_report(val["weights"], targets, holdings)
    trades = []
    if report.needs_rebalance:
        book = load_book(portfolio, holdings)
        prices = {h.ticker: h.current_price for h in holdings if h.current_price}
        trades = plan_rebalance(val["values"], val["cash"], targets, prices, book.avg_cost)
    return targets, report, trades


def _response(portfolio, holdings, val, targets, report, trades, executed=False) -> RebalanceResponse:
    out = []
    for t in trades:
        etf = get_etf_by_ticker(t.ticker)
        out.append(RebalanceTrade(
            ticker=t.ticker,
            etf_name=etf["name"] if etf else t.ticker,
            action=t.action,
            current_weight=round(t.current_weight, 4),
            target_weight=round(t.target_weight, 4),
            trade_value_gbp=round(t.value_gbp, 2),
            quantity=round(t.units, 6),
            price_gbp=round(t.price, 4),
            est_cost_gbp=round(t.est_cost_gbp, 2),
            est_realised_gain_gbp=round(t.est_realised_gain_gbp, 2),
        ))
    return RebalanceResponse(
        needs_rebalance=report.needs_rebalance,
        max_drift=round(max_drift_value(val["weights"], targets), 4),
        portfolio_drift=round(report.portfolio_drift, 4),
        reasons=report.reasons,
        out_of_band=report.out_of_band,
        trades=out,
        before_allocations=_asset_class_weights(val["weights"], holdings),
        after_allocations=_asset_class_weights(targets, holdings),
        total_value_gbp=round(val["total"], 2),
        est_total_cost_gbp=round(sum(t.est_cost_gbp for t in trades), 2),
        est_realised_gain_gbp=round(sum(t.est_realised_gain_gbp for t in trades), 2),
        cgt_applies=not bool(portfolio.uses_isa),
        stale_tickers=val["stale_tickers"],
        executed=executed,
    )


@router.get("/rebalance/{portfolio_id}", response_model=RebalanceResponse)
async def check_rebalance(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Mark to market, check the tolerance bands and, if triggered, return the
    trade plan (nothing is executed). Trades are only proposed when every
    holding has a fresh price.
    """
    portfolio, holdings = _load(db, portfolio_id)
    val = mark_to_market(portfolio, holdings, fetch=True)
    db.commit()
    if val["stale_tickers"] or val["unpriced_tickers"]:
        targets = _targets(holdings)
        report = _drift_report(val["weights"], targets, holdings)
        report.reasons.append("trade plan withheld: some holdings have no current price")
        return _response(portfolio, holdings, val, targets, report, [])
    try:
        targets, report, trades = _plan(portfolio, holdings, val)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _response(portfolio, holdings, val, targets, report, trades)


@router.post("/rebalance/{portfolio_id}/execute", response_model=RebalanceResponse)
async def execute_rebalance(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Execute the rebalance plan on the paper ledger: sells first, then buys,
    each recorded as a Transaction. Refused if any price is stale.
    """
    portfolio, holdings = _load(db, portfolio_id)
    val = mark_to_market(portfolio, holdings, fetch=True)
    if val["stale_tickers"] or val["unpriced_tickers"]:
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Rebalance refused: no current price for "
                   f"{', '.join(val['stale_tickers'] + val['unpriced_tickers'])}",
        )
    try:
        targets, report, trades = _plan(portfolio, holdings, val)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if trades:
        book = load_book(portfolio, holdings)
        fills = []
        for t in trades:  # plan lists sells before buys
            if t.action == "sell":
                fills.append(sell(book, t.ticker, t.value_gbp, t.price))
            else:
                fills.append(buy(book, t.ticker, min(t.value_gbp, book.cash), t.price))
        ac_of = {h.ticker: h.asset_class for h in holdings}
        save_book(db, portfolio, holdings, book, ac_of)
        record_fills(db, portfolio.id, fills, notes="Rebalance")
        db.flush()
        holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
        val_after = mark_to_market(portfolio, holdings, fetch=False)
        db.commit()
        return _response(portfolio, holdings, val_after, targets, report, trades, executed=True)

    db.commit()
    return _response(portfolio, holdings, val, targets, report, [], executed=False)


@router.post("/portfolio/{portfolio_id}/contribute")
async def contribute(portfolio_id: int, request: ContributionRequest, db: Session = Depends(get_db)):
    """
    Deposit cash and invest it where the portfolio is most underweight
    (cash-flow rebalancing): deficits are filled first, any remainder is
    spread by target weight. Refused if any price is stale.
    """
    portfolio, holdings = _load(db, portfolio_id)
    val = mark_to_market(portfolio, holdings, fetch=True)
    if val["stale_tickers"] or val["unpriced_tickers"]:
        db.commit()
        raise HTTPException(status_code=409, detail="Deposit not invested: some holdings have no current price")

    targets = _targets(holdings)
    missing = [t for t in targets if not any(h.ticker == t and h.current_price for h in holdings)]
    if missing:
        raise HTTPException(status_code=409, detail=f"No price for target holdings: {', '.join(missing)}")

    book = load_book(portfolio, holdings)
    book.cash += request.amount_gbp
    db.add(Transaction(portfolio_id=portfolio.id, ticker="CASH", action="deposit",
                       quantity=0.0, price=1.0, value=request.amount_gbp, notes="Deposit"))
    portfolio.net_contributions = (portfolio.net_contributions or 0.0) + request.amount_gbp

    prices = {h.ticker: h.current_price for h in holdings}
    plan = plan_inflow(book.cash, val["values"], targets)
    fills = [buy(book, t, min(v, book.cash), prices[t]) for t, v in plan.items() if v > 0.005]
    save_book(db, portfolio, holdings, book, {h.ticker: h.asset_class for h in holdings})
    record_fills(db, portfolio.id, fills, notes="Deposit investment")
    db.flush()
    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    after = mark_to_market(portfolio, holdings, fetch=False)
    report = _drift_report(after["weights"], targets, holdings)
    db.commit()

    return {
        "portfolio_id": portfolio.id,
        "deposited_gbp": request.amount_gbp,
        "buys": [{"ticker": f.ticker, "value_gbp": round(f.value + f.cost, 2), "units": f.units} for f in fills],
        "total_value": round(after["total"], 2),
        "portfolio_drift": round(report.portfolio_drift, 4),
        "needs_rebalance": report.needs_rebalance,
    }


@router.get("/transactions/{portfolio_id}")
async def get_transactions(portfolio_id: int, db: Session = Depends(get_db)):
    """Transaction history for a portfolio, newest first."""
    transactions = db.query(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).order_by(Transaction.timestamp.desc(), Transaction.id.desc()).all()

    return [
        {
            "id": t.id,
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": t.price,
            "value": t.value,
            "cost": t.cost or 0.0,
            "realised_gain": t.realised_gain or 0.0,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "notes": t.notes,
        }
        for t in transactions
    ]
