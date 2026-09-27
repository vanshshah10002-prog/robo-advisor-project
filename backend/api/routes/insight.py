"""
Insight API Routes — universe, history, track record
=====================================================
Read-only views that explain a portfolio:

- GET /universe                   the building blocks and candidate funds
- GET /portfolio/{id}/history     value since opening, replayed from the ledger
- GET /strategy/track-record      the walk-forward backtest at a risk level

Every figure is labelled by what it is: history is measured from real prices
and the portfolio's own transactions; the track record is a simulation of the
same construction on past data, with no look-ahead (docs/WALKFORWARD_BACKTEST.md).
"""

import datetime
import json
import os
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.models import HistoryResponse, TrackRecordResponse, UniverseResponse
from backend.data import prices as price_data
from backend.db.database import get_db
from backend.db.models import Holding, Portfolio, Transaction
from backend.engine.history import Trade, replay
from backend.engine.universe_view import build_universe
from backend.eval.track_record import benchmark_funds

router = APIRouter()

TRACK_RECORD_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "track_record.json")


@router.get("/universe", response_model=UniverseResponse)
async def get_universe(portfolio_id: Optional[int] = Query(default=None), db: Session = Depends(get_db)):
    """
    The core building blocks every portfolio is assembled from, growth first:
    what each is, its policy limit and the candidate funds in order of
    preference. With `portfolio_id`, marks the fund held and its weights.
    """
    held, targets = None, None
    if portfolio_id is not None:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
        held = {h.ticker: {"asset_class": h.asset_class, "weight": h.current_weight}
                for h in holdings if (h.quantity or 0.0) > 0}
        targets = dict(portfolio.target_allocations or {})
    return UniverseResponse(portfolio_id=portfolio_id, blocks=build_universe(held, targets))


def _trades(rows: list[Transaction]) -> list[Trade]:
    out = []
    for r in rows:
        if r.timestamp is None:
            continue
        out.append(Trade(
            day=r.timestamp.date(), ticker=r.ticker, action=r.action,
            units=float(r.quantity or 0.0), price=float(r.price or 0.0),
            value=float(r.value or 0.0), cost=float(r.cost or 0.0),
        ))
    return out


@router.get("/portfolio/{portfolio_id}/history", response_model=HistoryResponse)
async def get_history(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Daily value since the portfolio was opened, rebuilt from its transactions
    and daily GBP closes, with the time-weighted return (deposits excluded).
    Portfolios opened before transactions were recorded have no history.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    rows = (db.query(Transaction).filter(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.timestamp).all())
    trades = _trades(rows)
    if not any(t.action == "buy" for t in trades):
        return HistoryResponse(
            portfolio_id=portfolio_id, points=[],
            reason="This portfolio was opened before trades were recorded, so its history starts from its next valuation.",
        )

    traded = sorted({t.ticker for t in trades if t.action in ("buy", "sell")})
    closes = price_data.get_gbp_close_history(traded, trades[0].day)
    series = replay(trades, closes, datetime.date.today())
    unpriced = [t for t in traded if t not in closes.columns]
    points = [
        {"date": d.date().isoformat(), "value": round(r.value, 2),
         "net_contributions": round(r.net_contributions, 2),
         "cumulative_return": round(r.cumulative_return, 6)}
        for d, r in series.iterrows()
    ]
    return HistoryResponse(
        portfolio_id=portfolio_id,
        points=points,
        start_date=points[0]["date"] if points else None,
        end_date=points[-1]["date"] if points else None,
        time_weighted_return=points[-1]["cumulative_return"] if points else None,
        unpriced_tickers=unpriced,
    )


@lru_cache(maxsize=1)
def _load_track_record(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_track_record() -> Optional[dict]:
    """The committed backtest artefact, or None if it has not been built."""
    path = os.path.abspath(TRACK_RECORD_PATH)
    if not os.path.exists(path):
        return None
    return _load_track_record(path)


@router.get("/strategy/track-record", response_model=TrackRecordResponse)
async def get_track_record(risk: int = Query(..., ge=1, le=10)):
    """
    How this construction would have done over the last five years at the given
    risk level, against a two-fund portfolio with the same share in shares,
    whose funds `benchmark_funds` names with their weights. A simulation on
    real prices with no look-ahead — not this portfolio's own history. Built
    by scripts/build_track_record.py.
    """
    data = load_track_record()
    if data is None:
        raise HTTPException(status_code=503, detail="The track record has not been built yet.")
    entry = data["risks"].get(str(risk))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No track record for risk {risk}")
    return TrackRecordResponse(
        risk=risk, benchmark_funds=benchmark_funds(risk), **entry,
        notes=data["notes"], generated_at=data["generated_at"],
        prices_downloaded_at=data.get("prices_downloaded_at"),
        start=data["start"], end=data["end"], initial=data["initial"],
    )
