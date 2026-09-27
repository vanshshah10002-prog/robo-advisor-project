"""
Walk-Forward Backtest — the production construction, decided point in time
===========================================================================
Replays the live pipeline over history (docs/SESSION_HANDOFF_2026-09.md §3).
Every `check_every` trading days, at day i's close, using ONLY prices dated ≤ day i:

  - when targets are due (start, then every `reopt_months`): universe → month-end
    GBP log returns → point-in-time rf → estimate_mu_cov → apply_cash_forward_rate
    → build_policy_portfolio → forecast with get_portfolio_performance;
  - otherwise mark to market and run check_drift ("bands", the app's behaviour)
    or always trade to target ("calendar");
  - size the trades with plan_rebalance at day i's prices.

The plan is executed at day i+1's close through the holdings ledger: sells in
the planned UNITS, then buys scaled to the cash those sells actually raised.

Look-ahead guards:
  - The decision function receives `prices.loc[:t]`; later rows do not exist for it.
  - Month-end sampling drops the current, incomplete month.
  - rf is the cash proxy's trailing return up to t — never today's live rate.
  - The universe uses price availability at t, not the registry's `delisted`
    flag (which records what is known in 2026).
  - Orders are sized at day i and filled at day i+1.
tests/test_walkforward_backtest.py changes every price after a date D and
checks that nothing decided or executed on or before D changes.

Remaining bias (disclosed, not removable here): survivorship — CORE_UNIVERSE and
its fallback order were chosen in 2026 from funds that exist today, with today's TERs.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from backend.config import (
    CORE_UNIVERSE,
    MIN_HISTORY_MONTHS,
    MVO_RISK_FREE_RATE,
    RISK_FREE_CLAMP,
    RISK_FREE_PROXY_TICKERS,
    TRANSACTION_COST_BPS,
    UK_RETAIL_UCITS_ONLY,
)
from backend.data.rates import trailing_annualized_return
from backend.engine import ledger
from backend.engine.asset_universe import get_etf_by_ticker
from backend.engine.expected_returns import estimate_mu_cov
from backend.engine.optimizer import (
    apply_cash_forward_rate,
    build_policy_portfolio,
    get_portfolio_performance,
)
from backend.engine.policy import growth_tolerance_range, sleeve_of
from backend.engine.rebalancer import check_drift, plan_rebalance

logger = logging.getLogger(__name__)

DEFAULT_MAX_STALE_DAYS: int = 10       # a candidate must have printed within this many days of t
DEFAULT_ESTIMATION_YEARS: int = 10     # the live app estimates on 10 years of history


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class Decision:
    """Targets and forecast produced at one decision date from data ≤ date."""
    date: pd.Timestamp
    weights: dict[str, float]
    asset_class_of: dict[str, str]
    growth_target: float
    risk_free: float
    risk_free_source: str = ""
    expected_return: Optional[float] = None     # annual arithmetic
    volatility_model: Optional[float] = None
    volatility: Optional[float] = None          # × VOL_CALIBRATION_MULTIPLIER (client-facing)
    mu: dict[str, float] = field(default_factory=dict)
    common_months: int = 0
    fallbacks: dict[str, list[str]] = field(default_factory=dict)


DecideFn = Callable[[pd.DataFrame, pd.Timestamp], Decision]


@dataclass(frozen=True)
class SimConfig:
    initial_cash: float = 100_000.0
    check_every: int = 10                # trading days between checks
    reopt_months: int = 12               # months between target rebuilds
    mode: str = "bands"                  # "bands" | "calendar"
    cost_bps: float = TRANSACTION_COST_BPS
    commission_gbp: float = 0.0          # fixed fee per fill


@dataclass(frozen=True)
class Order:
    """Trades decided at `decided` (day i), executed at the next trading day's close."""
    decided: pd.Timestamp
    reason: str
    sells: dict[str, float]              # ticker -> units
    buys: dict[str, float]               # ticker -> GBP to spend (trading cost included)
    target: dict[str, float]
    value_at_decision: float


@dataclass
class BacktestResult:
    equity: pd.DataFrame                 # date -> value, cash, rf
    decisions: list[Decision]
    orders: list[Order]
    checks: pd.DataFrame
    events: pd.DataFrame
    fills: pd.DataFrame


# =============================================================================
# POINT-IN-TIME INPUTS
# =============================================================================

def month_end_prices(history: pd.DataFrame, t: pd.Timestamp, years: int) -> pd.DataFrame:
    """Month-end prices from data ≤ t, over the last `years`; the incomplete month of t is dropped."""
    m = history.loc[:t].resample("ME").last()
    m = m[m.index <= t]
    return m[m.index > t - pd.DateOffset(years=years)]


def monthly_log_returns(month_end: pd.DataFrame) -> pd.DataFrame:
    return np.log(month_end / month_end.shift(1)).dropna(how="all")


def usable_at(
    history: pd.DataFrame,
    ticker: str,
    t: pd.Timestamp,
    min_months: int = MIN_HISTORY_MONTHS,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> bool:
    """≥ `min_months` complete month-ends by t and a price within `max_stale_days` of t."""
    if ticker not in history.columns:
        return False
    s = history[ticker].loc[:t].dropna()
    if s.empty or (t - s.index[-1]).days > max_stale_days:
        return False
    months = s.resample("ME").last().dropna()
    return int((months.index <= t).sum()) >= min_months


def _structurally_investable(ticker: str) -> bool:
    """UCITS / UK-retail eligibility (a fund's legal form). Ignores `delisted`, which is hindsight."""
    etf = get_etf_by_ticker(ticker)
    if etf is None:
        return False
    return bool(etf.get("ucits") or etf.get("uk_retail_investable")) if UK_RETAIL_UCITS_ONLY else True


def resolve_universe_at(
    history: pd.DataFrame,
    t: pd.Timestamp,
    candidates: Optional[dict[str, list[str]]] = None,
    min_months: int = MIN_HISTORY_MONTHS,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    First usable candidate per block at t, in CORE_UNIVERSE order. Same rule as
    asset_universe.resolve_ticker_map, but without its registry `delisted`
    filter (a fund delisted in 2024 was investable in 2021).
    """
    ticker_map: dict[str, str] = {}
    skipped: dict[str, list[str]] = {}
    for ac, tickers in (candidates or CORE_UNIVERSE).items():
        for tk in tickers:
            if _structurally_investable(tk) and usable_at(history, tk, t, min_months, max_stale_days):
                ticker_map[ac] = tk
                break
            skipped.setdefault(ac, []).append(tk)
    return ticker_map, skipped


def risk_free_at(history: pd.DataFrame, t: pd.Timestamp,
                 max_stale_days: int = DEFAULT_MAX_STALE_DAYS) -> tuple[float, str]:
    """
    Trailing 12-month return of the first cash proxy that is still printing
    (a price within `max_stale_days` of t) and has enough history by t, clamped.
    """
    lo, hi = RISK_FREE_CLAMP
    for proxy in RISK_FREE_PROXY_TICKERS:
        if proxy not in history.columns:
            continue
        s = history[proxy].loc[:t].dropna()
        if s.empty or (t - s.index[-1]).days > max_stale_days:
            continue
        rate = trailing_annualized_return(s)
        if rate is not None:
            return float(np.clip(rate, lo, hi)), proxy
    return float(MVO_RISK_FREE_RATE), "config fallback"


# =============================================================================
# DECISIONS
# =============================================================================

def decide_policy_portfolio(
    history: pd.DataFrame,
    t: pd.Timestamp,
    risk_score: int,
    estimation_years: int = DEFAULT_ESTIMATION_YEARS,
    min_months: int = MIN_HISTORY_MONTHS,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> Decision:
    """The production construction at date t, from `history` rows dated ≤ t only."""
    history = history.loc[:t]
    ticker_map, skipped = resolve_universe_at(history, t, None, min_months, max_stale_days)
    if len(ticker_map) < 2:
        raise ValueError(f"{t:%Y-%m-%d}: fewer than 2 usable building blocks")
    ac_of = {tk: ac for ac, tk in ticker_map.items()}
    tickers = list(ac_of)

    monthly = monthly_log_returns(month_end_prices(history[tickers], t, estimation_years))
    rf, rf_source = risk_free_at(history, t)
    fees = {tk: float((get_etf_by_ticker(tk) or {}).get("expense_ratio", 0.0)) for tk in tickers}

    mu, cov = estimate_mu_cov(monthly, fees, rf, ac_of)
    mu = apply_cash_forward_rate(mu, ac_of, rf, fees)
    policy = build_policy_portfolio(risk_score, mu, cov, ac_of)
    perf = get_portfolio_performance(policy["weights"], mu, cov, risk_free_rate=rf)

    return Decision(
        date=t,
        weights=policy["weights"],
        asset_class_of=ac_of,
        growth_target=policy["growth_target"],
        risk_free=rf,
        risk_free_source=rf_source,
        expected_return=perf["expected_return"],
        volatility_model=perf["volatility_model"],
        volatility=perf["volatility"],
        mu={k: float(v) for k, v in mu.items()},
        common_months=int(monthly[list(cov.columns)].dropna(how="any").shape[0]),
        fallbacks={ac: tks for ac, tks in skipped.items() if ac in ticker_map},
    )


def fixed_mix_decider(weights: dict[str, float], asset_class_of: dict[str, str]) -> DecideFn:
    """Benchmark: the same fixed weights at every decision (rf still point in time)."""
    growth = sum(w for tk, w in weights.items() if sleeve_of(asset_class_of.get(tk, "")) == "growth")

    def decide(history: pd.DataFrame, t: pd.Timestamp) -> Decision:
        rf, src = risk_free_at(history, t)
        return Decision(t, dict(weights), dict(asset_class_of), growth, rf, src)
    return decide


def memoised(decide: DecideFn) -> DecideFn:
    """Cache decisions by date so bands and calendar runs share identical targets."""
    cache: dict[pd.Timestamp, Decision] = {}

    def wrapped(history: pd.DataFrame, t: pd.Timestamp) -> Decision:
        if t not in cache:
            cache[t] = decide(history, t)
        return cache[t]
    return wrapped


# =============================================================================
# SIMULATION
# =============================================================================

def _mark(book: ledger.Book, prices: pd.Series) -> dict:
    return ledger.valuation(book, {tk: float(prices[tk]) for tk in book.units})


def _plan_order(book: ledger.Book, val: dict, decision: Decision, prices: pd.Series,
                day: pd.Timestamp, reason: str, cfg: SimConfig) -> Optional[Order]:
    names = set(val["values"]) | set(decision.weights)
    px = {tk: float(prices[tk]) for tk in names}
    bad = sorted(tk for tk, p in px.items() if not np.isfinite(p) or p <= 0)
    if bad:
        raise ValueError(f"{day:%Y-%m-%d}: no price to plan trades in {bad}")
    trades = plan_rebalance(val["values"], book.cash, decision.weights, px,
                            dict(book.avg_cost), cfg.cost_bps)
    if not trades:
        return None
    return Order(
        decided=day, reason=reason,
        sells={tr.ticker: tr.units for tr in trades if tr.action == "sell"},
        buys={tr.ticker: tr.value_gbp for tr in trades if tr.action == "buy"},
        target=dict(decision.weights), value_at_decision=val["total"],
    )


def _execute(book: ledger.Book, order: Order, day: pd.Timestamp, prices: pd.Series,
             cfg: SimConfig) -> tuple[dict, list[dict]]:
    """Fill an order at `day`'s prices: planned units sold, buys limited to cash on hand."""
    before = _mark(book, prices)["total"]
    fills: list[ledger.Fill] = []
    for tk, units in order.sells.items():
        units = min(units, book.units.get(tk, 0.0))
        if units > 0:
            p = float(prices[tk])
            fills.append(ledger.sell(book, tk, units * p, p, cfg.cost_bps))
            book.cash -= cfg.commission_gbp
    want = sum(order.buys.values())
    if want > 0:
        spendable = max(0.0, book.cash - cfg.commission_gbp * len(order.buys))
        scale = min(1.0, spendable / want)
        for tk, gbp in order.buys.items():
            if gbp * scale > 0.01:
                fills.append(ledger.buy(book, tk, gbp * scale, float(prices[tk]), cfg.cost_bps))
                book.cash -= cfg.commission_gbp

    buys = sum(f.value for f in fills if f.action == "buy")
    sells = sum(f.value for f in fills if f.action == "sell")
    commission = cfg.commission_gbp * len(fills)
    event = {
        "decided": order.decided, "executed": day, "reason": order.reason,
        "value_before": before, "buys_gbp": buys, "sells_gbp": sells,
        "cost_gbp": sum(f.cost for f in fills) + commission, "commission_gbp": commission,
        "n_fills": len(fills), "turnover": (buys + sells) / 2.0 / before if before > 0 else 0.0,
        "realised_gain_gbp": sum(f.realised_gain for f in fills),
        "value_after": _mark(book, prices)["total"],
    }
    rows = [{"executed": day, "decided": order.decided, "ticker": f.ticker, "action": f.action,
             "units": f.units, "price": f.price, "value_gbp": f.value, "cost_gbp": f.cost,
             "realised_gain_gbp": f.realised_gain} for f in fills]
    return event, rows


def _trigger(val: dict, decision: Decision, ac_seen: dict[str, str], cfg: SimConfig) -> tuple[Optional[str], dict]:
    """Why to trade at this check (None = hold), plus the drift diagnostics."""
    names = set(val["weights"]) | set(decision.weights)
    group_of = {tk: sleeve_of(ac_seen.get(tk, "")) for tk in names}
    report = check_drift(val["weights"], decision.weights, group_of,
                         {"growth": growth_tolerance_range(decision.growth_target)})
    diag = {
        "portfolio_drift": report.portfolio_drift,
        "max_abs_drift": max((abs(d) for d in report.drift.values()), default=0.0),
        "growth_weight": report.group_weights.get("growth", 0.0),
        "n_out_of_band": len(report.out_of_band),
        "drift_reasons": "; ".join(report.reasons),
    }
    if cfg.mode == "calendar":
        return "calendar", diag
    return ("; ".join(report.reasons) if report.needs_rebalance else None), diag


def run_backtest(
    prices: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    decide: DecideFn,
    cfg: SimConfig = SimConfig(),
) -> BacktestResult:
    """
    Simulate £`initial_cash` from `start` to `end` on the daily GBP panel
    `prices` (rows = trading days). See the module docstring for the timeline.
    """
    if cfg.mode not in ("bands", "calendar"):
        raise ValueError(f"Unknown mode {cfg.mode!r}")
    days = prices.loc[start:end].index
    if len(days) < 2:
        raise ValueError("Backtest needs at least two trading days")
    marks = prices.ffill()   # causal: the last print on or before each day
    book = ledger.Book(cash=float(cfg.initial_cash))
    decisions: list[Decision] = []
    orders: list[Order] = []
    equity, checks, events, fills = [], [], [], []
    ac_seen: dict[str, str] = {}
    pending: Optional[Order] = None
    n_due = 0
    rf = float("nan")

    for i, day in enumerate(days):
        mark = marks.loc[day]
        if pending is not None:
            event, rows = _execute(book, pending, day, mark, cfg)
            events.append(event)
            fills.extend(rows)
            pending = None
        val = _mark(book, mark)
        is_check = i % cfg.check_every == 0 and i < len(days) - 1
        if is_check:
            history = prices.loc[:day]
            rf = risk_free_at(history, day)[0]
            reason = None
            if day >= days[0] + pd.DateOffset(months=cfg.reopt_months * n_due):
                n_due += 1
                try:
                    decisions.append(decide(history, day))
                    ac_seen.update(decisions[-1].asset_class_of)
                    reason = "initial" if len(decisions) == 1 else "re-optimisation"
                except ValueError as e:        # OptimisationError is a ValueError
                    if not decisions:
                        raise
                    logger.warning(f"{day:%Y-%m-%d}: re-optimisation failed, keeping targets ({e})")
            drift_reason, diag = _trigger(val, decisions[-1], ac_seen, cfg)
            reason = reason or drift_reason
            order, note = None, ""
            if reason:
                try:
                    order = _plan_order(book, val, decisions[-1], mark, day, reason, cfg)
                except ValueError as e:        # like the app: refuse the rebalance, keep holdings
                    note = f"rebalance skipped: {e}"
                    logger.warning(note)
            checks.append({"date": day, "value": val["total"], "cash": book.cash, "rf": rf,
                           **diag, "triggered": reason is not None, "reason": reason or "",
                           "traded": order is not None, "note": note})
            if order is not None:
                orders.append(order)
                pending = order
        equity.append({"date": day, "value": val["total"], "cash": book.cash, "rf": rf})

    return BacktestResult(
        equity=pd.DataFrame(equity).set_index("date"),
        decisions=decisions,
        orders=orders,
        checks=pd.DataFrame(checks),
        events=pd.DataFrame(events),
        fills=pd.DataFrame(fills),
    )
