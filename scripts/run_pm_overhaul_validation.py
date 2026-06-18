"""
PM Overhaul — Walk-Forward Validation of the Risk-Targeted Ladder
==================================================================
Validates the rebuilt construction (cash sleeve + UCITS universe + efficient_risk
SD ladder + caps) the same way Phase 3 validated the old glide:

  For each month t (expanding window ≥36m): estimate blend E[R] (clamped) and
  EWMA+LW covariance from data ≤ t; build the risk-targeted portfolio for each
  risk level; hold one month; record realized returns.

  Gate: realized volatility strictly increasing in risk; caps respected.

DISCLAIMERS (printed with results):
  - Survivorship: universe = funds alive today fetched from yfinance; delisted
    funds are absent, flattering absolute results.
  - Hyperparameters (blend w=0.5, EWMA halflife, clamp) were selected on data
    through 2024; treat pre-2024 walk-forward as in-sample for those choices.

Run:  python -m scripts.run_pm_overhaul_validation [--eval-start YYYY-MM] [--eval-end YYYY-MM]

Era testing: --eval-start/--eval-end restrict the months EVALUATED; training
always uses only data strictly BEFORE each evaluated month (expanding window
from the start of available history), so there is no lookahead by construction.
"""

import argparse
import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from backend.config import (
    MVO_RISK_FREE_RATE, BOND_ASSET_CLASSES, GOLD_ASSET_CLASSES,
    CASH_ASSET_CLASSES, ASSET_GROUP_CAPS, EXPECTED_RETURN_CLAMP, RISK_FREE_CLAMP,
)
from backend.data.rates import get_risk_free_rate
from backend.engine.asset_universe import get_ticker_map
from backend.engine.optimizer import (
    STRATEGIC_UNIVERSE, build_risk_targeted_portfolio, _get_weight_bounds,
)
from backend.data.returns import build_monthly_gbp_log_returns
from backend.engine.quant_models import blend_trailing_bl, ewma_lw_cov
from backend.eval.metrics import realized_sharpe

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("pm_validation")

RISK_SCORES = [1, 3, 5, 8, 10]
MIN_TRAIN = 36


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-start", default=None, help="YYYY-MM first evaluated month")
    ap.add_argument("--eval-end", default=None, help="YYYY-MM last evaluated month")
    ap.add_argument("--min-train", type=int, default=MIN_TRAIN)
    args = ap.parse_args()

    tmap = get_ticker_map(STRATEGIC_UNIVERSE)
    ac = {v: k for k, v in tmap.items()}
    R = build_monthly_gbp_log_returns(sorted(tmap.values()), period_years=10, min_obs=24)
    if R is None or R.shape[1] < 3:
        print("Insufficient data"); return
    R = R.sort_index()
    dates = R.index
    lo, hi = EXPECTED_RETURN_CLAMP

    eval_start = pd.Period(args.eval_start, "M").to_timestamp("M") if args.eval_start else None
    eval_end = pd.Period(args.eval_end, "M").to_timestamp("M") if args.eval_end else None
    min_train = args.min_train

    realized = {rs: {} for rs in RISK_SCORES}
    cap_violations = 0
    t = min_train
    while t + 1 <= len(dates):
        eval_date = dates[t]
        if (eval_start is not None and eval_date < eval_start) or \
           (eval_end is not None and eval_date > eval_end):
            t += 1; continue
        train = R.iloc[:t]
        valid = train.columns[train.count() >= min_train]
        if len(valid) < 3:
            t += 1; continue
        train_v = train[valid]
        # Pricing rf at month t: trailing 12m cash-ETF return computed from the
        # TRAINING window only (no lookahead). Config constant is the fallback.
        rf_t = MVO_RISK_FREE_RATE
        cash_tk = next((tk for tk in train_v.columns
                        if ac.get(tk, "") in CASH_ASSET_CLASSES), None)
        if cash_tk is not None:
            tail = train_v[cash_tk].dropna().iloc[-12:]
            if len(tail) == 12:
                rf_t = float(np.clip(np.expm1(tail.mean() * 12.0), *RISK_FREE_CLAMP))
        mu = blend_trailing_bl(train_v, w_trailing=0.5,
                               risk_free_annual=rf_t).clip(lo, hi)
        cov = ewma_lw_cov(train_v)
        common = [c for c in mu.index if c in cov.columns]
        if len(common) < 3:
            t += 1; continue
        mu_c, cov_c = mu.reindex(common), cov.loc[common, common]
        bounds = _get_weight_bounds(common, ac)
        nxt = np.expm1(R.iloc[t][common])

        for rs in RISK_SCORES:
            try:
                res = build_risk_targeted_portfolio(
                    float(rs), mu_c, cov_c, bounds, asset_class_map=ac)
            except Exception:
                continue
            w = pd.Series(res["weights"]).reindex(common).fillna(0.0)
            if w.sum() <= 0:
                continue
            w = w / w.sum()
            bonds = sum(w[tk] for tk in common if ac.get(tk, "") in BOND_ASSET_CLASSES)
            gold = sum(w[tk] for tk in common if ac.get(tk, "") in GOLD_ASSET_CLASSES)
            if bonds > ASSET_GROUP_CAPS["bonds"] + 1e-3 or gold > ASSET_GROUP_CAPS["gold"] + 1e-3:
                cap_violations += 1
            realized[rs][dates[t]] = float(np.log1p(float((w * nxt).sum())))
        t += 1

    any_dates = [d for rs in RISK_SCORES for d in realized[rs].keys()]
    era = (f"{min(any_dates):%Y-%m} .. {max(any_dates):%Y-%m}" if any_dates else "none")
    rf_report = get_risk_free_rate()
    print("=" * 74)
    print("PM OVERHAUL — WALK-FORWARD VALIDATION (risk-targeted ladder, caps, cash)")
    print(f"EVALUATED ERA: {era}  (training: expanding, strictly before each month)")
    print(f"Sharpe reported vs LIVE GBP risk-free rate: {rf_report:.2%}")
    print("=" * 74)
    sharpe_hdr = f"Sharpe({rf_report:.1%})"
    print(f"{'risk':>5}{'realVol':>10}{'CAGR':>9}{sharpe_hdr:>14}{'maxDD':>9}{'n':>5}")
    prev = None; monotone = True
    for rs in RISK_SCORES:
        s = pd.Series(realized[rs]).sort_index()
        if s.empty:
            continue
        vol = float(s.std(ddof=1) * np.sqrt(12))
        m = realized_sharpe(s, risk_free_annual=rf_report)
        if prev is not None and vol < prev - 1e-4:
            monotone = False
        prev = vol
        print(f"{rs:>5}{vol:>10.4f}{m['cagr']:>9.3f}{m['sharpe']:>14.3f}"
              f"{m['max_drawdown']:>9.1%}{m['n_periods']:>5}")
    print("-" * 50)
    print(f"Realized vol monotone in risk: {'YES' if monotone else 'NO'}")
    print(f"Group-cap violations across all months/levels: {cap_violations}")
    print()
    print("DISCLAIMERS: survivorship-biased universe (today's live funds);")
    print("hyperparameters selected on data through 2024 (pre-2024 = in-sample for them).")


if __name__ == "__main__":
    main()
