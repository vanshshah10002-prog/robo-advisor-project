"""
Phase 3 — Risk Mapping Validation (Two-Fund Glide)
===================================================
Validates that the new two-fund glide produces a COHERENT, MONOTONIC risk dial
on a single strategic universe (fixing the old universe-swap that gave bond-free
"balanced" portfolios).

1. Walk-forward: for each risk score 1..10, build the two-fund portfolio each
   month (min-variance ↔ tangency blend) and record realized returns. Reports
   realized volatility (must INCREASE with risk) and Sharpe.
2. Allocation snapshots (risk 1/3/5/7/10) on the latest data: shows the
   equity / bond / gold / other split — bonds MUST appear at low risk.

Run:  python -m scripts.run_phase3_riskmap
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import MVO_RISK_FREE_RATE
from backend.engine.asset_universe import get_ticker_map
from backend.engine.optimizer import STRATEGIC_UNIVERSE, _get_weight_bounds
from backend.eval.legacy_construction import (
    build_two_fund_portfolio, compute_tangent_portfolio, build_sector_caps, _apply_sector_caps,
)
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.models import blend_trailing_bl
from backend.eval.cov_models import ewma_lw_cov
from backend.eval.metrics import realized_sharpe

from pypfopt import EfficientFrontier

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase3")
logger.setLevel(logging.INFO)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
RISK_SCORES = list(range(1, 11))

# Asset-class buckets for the allocation snapshot
BOND_CLASSES = {"uk_gilts", "global_bonds", "corporate_bonds", "uk_bonds", "indian_bonds",
                "us_treasury", "uk_inflation_linked", "high_yield_bonds"}
GOLD_CLASSES = {"commodities_gold", "indian_gold", "commodities_silver", "indian_silver",
                "commodities_broad"}


def _setup():
    ticker_map = get_ticker_map(STRATEGIC_UNIVERSE)
    tickers = sorted(set(ticker_map.values()))
    ac_by_ticker = {v: k for k, v in ticker_map.items()}
    returns = build_monthly_gbp_log_returns(tickers, period_years=10, min_obs=24)
    return returns, ac_by_ticker


def _bucket(ac: str) -> str:
    if ac in BOND_CLASSES:
        return "bonds"
    if ac in GOLD_CLASSES:
        return "gold/commod"
    return "equity/other"


def main() -> None:
    returns, ac_by_ticker = _setup()
    if returns is None or returns.shape[1] < 3:
        logger.error("Insufficient data. Check network/cache.")
        return
    logger.info(f"Universe: {returns.shape[1]} tickers, {returns.shape[0]} months")

    # ── 1. Walk-forward realized vol/Sharpe across the risk dial ──
    R = returns.sort_index()
    dates = R.index
    n = len(dates)
    min_train = 36
    realized = {rs: {} for rs in RISK_SCORES}

    t = min_train
    while t + 1 <= n:
        train = R.iloc[:t]
        valid = train.columns[train.count() >= min_train]
        if len(valid) < 2:
            t += 1
            continue
        train_v = train[valid]
        mu = blend_trailing_bl(train_v, w_trailing=0.5, risk_free_annual=MVO_RISK_FREE_RATE)
        cov = ewma_lw_cov(train_v)
        common = [c for c in mu.index if c in cov.columns]
        if len(common) < 2:
            t += 1
            continue
        mu = mu.reindex(common); cov = cov.loc[common, common]
        bounds = _get_weight_bounds(common, ac_by_ticker)
        sm, sl, su = build_sector_caps(common, ac_by_ticker)

        # Compute the two anchor funds ONCE; blend per risk score (with group caps)
        try:
            ef = EfficientFrontier(mu, cov, weight_bounds=bounds)
            _apply_sector_caps(ef, sm, sl, su); ef.min_volatility()
            w_def = pd.Series(ef.clean_weights()).reindex(common).fillna(0.0)
        except Exception:
            iv = 1.0 / np.diag(cov.values); w_def = pd.Series(iv / iv.sum(), index=common)
        w_growth = pd.Series(
            compute_tangent_portfolio(mu, cov, bounds, sector_mapper=sm,
                                      sector_lower=sl, sector_upper=su)
        ).reindex(common).fillna(0.0)

        nxt = np.expm1(R.iloc[t][common])
        for rs in RISK_SCORES:
            a = rs / 10.0
            w = a * w_growth + (1 - a) * w_def
            s = w.sum()
            if s <= 0:
                continue
            w = w / s
            realized[rs][dates[t]] = float(np.log1p(float((w * nxt).sum())))
        t += 1

    print("\n" + "=" * 70)
    print("PHASE 3 — RISK DIAL WALK-FORWARD (two-fund glide, single universe)")
    print("=" * 70)
    print(f"{'risk':>5}{'alpha':>7}{'realVol':>10}{'CAGR':>9}{'Sharpe':>9}")
    print("-" * 40)
    prev_vol = None
    monotonic = True
    for rs in RISK_SCORES:
        s = pd.Series(realized[rs]).sort_index()
        if s.empty:
            continue
        vol = float(s.std(ddof=1) * np.sqrt(12))
        sh = realized_sharpe(s)
        if prev_vol is not None and vol < prev_vol - 1e-4:
            monotonic = False
        prev_vol = vol
        print(f"{rs:>5}{rs/10:>7.1f}{vol:>10.4f}{sh['cagr']:>9.3f}{sh['sharpe']:>9.3f}")
    print("-" * 40)
    print(f"Realized volatility monotonically increasing with risk: {'YES' if monotonic else 'NO'}")

    # ── 2. Allocation snapshots on latest data ──
    valid = R.columns[R.count() >= min_train]
    mu = blend_trailing_bl(R[valid], w_trailing=0.5, risk_free_annual=MVO_RISK_FREE_RATE)
    cov = ewma_lw_cov(R[valid])
    common = [c for c in mu.index if c in cov.columns]
    mu = mu.reindex(common); cov = cov.loc[common, common]
    bounds = _get_weight_bounds(common, ac_by_ticker)

    print("\n" + "=" * 70)
    print("ALLOCATION SNAPSHOTS (latest data) — bucket split by risk score")
    print("=" * 70)
    print(f"{'risk':>5}{'equity/other':>15}{'bonds':>9}{'gold/commod':>14}{'#pos':>6}")
    print("-" * 49)
    for rs in [1, 3, 5, 7, 10]:
        tf = build_two_fund_portfolio(rs, mu, cov, bounds, asset_class_map=ac_by_ticker)
        buckets = {"equity/other": 0.0, "bonds": 0.0, "gold/commod": 0.0}
        for tk, w in tf["weights"].items():
            buckets[_bucket(ac_by_ticker.get(tk, ""))] += w
        npos = sum(1 for w in tf["weights"].values() if w > 0.001)
        print(f"{rs:>5}{buckets['equity/other']:>15.1%}{buckets['bonds']:>9.1%}"
              f"{buckets['gold/commod']:>14.1%}{npos:>6}")

    print("\nGate: vol monotonic in risk AND bonds present at low risk (risk 1-3).")


if __name__ == "__main__":
    main()
