"""
Risk-8 "Ideal" Portfolio Built at 2020 — No-Leakage Out-of-Sample Backtest
===========================================================================
Builds a risk-8 portfolio using the FULL revised logic (Phase 1-3 + caps)
with data ONLY up to 2019-12 (no forward-information leakage), then holds it
to today and compares:

    EXPECTED (2020 blended forecast)  vs  ACTUAL (realized buy-and-hold)  vs  MARKET (VWRL)

Assumptions (standardised):
    rf = 6% (mandate)         bonds ≤ 20%, gold ≤ 10% (mandate)
    txn cost = 10 bps one-way at entry        buy-and-hold (weights fixed at 2020)
    monthly GBP-unhedged returns; blend(trailing+BL) returns; EWMA+LW covariance

Also emits the per-asset EXPECTED vs ACTUAL table consumed by the
/variance-analysis step (actual vs blended-weighted returns).

Run:  python -m scripts.run_risk8_2020_backtest
"""

import json
import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety for ≤, −, etc.
except Exception:
    pass

from backend.config import (
    MVO_RISK_FREE_RATE, TRANSACTION_COST_BPS, BENCHMARK_TICKER,
    EXPECTED_RETURN_CLAMP,
)
from backend.data.rates import get_risk_free_rate
from backend.engine.asset_universe import get_ticker_map
from backend.engine.optimizer import (
    STRATEGIC_UNIVERSE, build_risk_targeted_portfolio, _get_weight_bounds,
)
from backend.data.returns import build_monthly_gbp_log_returns
from backend.engine.quant_models import blend_trailing_bl, ewma_lw_cov
from backend.eval.metrics import realized_sharpe

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("risk8_2020")
logger.setLevel(logging.INFO)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
RISK_SCORE = 8.0
BUILD_CUTOFF = "2019-12-31"   # use only data up to here (no leakage)
RF = get_risk_free_rate()     # LIVE GBP risk-free for Sharpe REPORTING (no hardcoded hurdle)
PRICING_RF = MVO_RISK_FREE_RATE  # fallback pricing rf inside CAPM/BL math


def _annualize_log(total_log: float, years: float) -> float:
    return float(np.exp(total_log / years) - 1.0) if years > 0 else float("nan")


def main() -> None:
    ticker_map = get_ticker_map(STRATEGIC_UNIVERSE)
    ac_by_ticker = {v: k for k, v in ticker_map.items()}
    tickers = sorted(set(ticker_map.values()) | {BENCHMARK_TICKER})

    returns = build_monthly_gbp_log_returns(tickers, period_years=11, min_obs=24)
    if returns is None or returns.empty:
        logger.error("No data."); return

    # ── Split at 2020 (no leakage) ──
    train = returns[returns.index <= BUILD_CUTOFF]
    evalr = returns[returns.index > BUILD_CUTOFF]
    if train.shape[0] < 24 or evalr.empty:
        logger.error(f"Train={train.shape}, eval={evalr.shape} insufficient."); return
    eval_start, eval_end = evalr.index.min(), evalr.index.max()
    years = (eval_end - eval_start).days / 365.25
    logger.info(f"Train ≤ {train.index.max():%Y-%m} ({train.shape[0]}m); "
                f"eval {eval_start:%Y-%m}..{eval_end:%Y-%m} ({evalr.shape[0]}m, {years:.2f}y)")

    # ── Build risk-8 portfolio AS OF 2020 (no forward info) ──
    valid = train.columns[train.count() >= 24]
    valid = [t for t in valid if t != BENCHMARK_TICKER]  # benchmark not an investable sleeve here
    lo, hi = EXPECTED_RETURN_CLAMP
    mu = blend_trailing_bl(train[valid], w_trailing=0.5,
                           risk_free_annual=PRICING_RF).clip(lo, hi)
    cov = ewma_lw_cov(train[valid])
    common = [c for c in mu.index if c in cov.columns]
    mu, cov = mu.reindex(common), cov.loc[common, common]
    bounds = _get_weight_bounds(common, ac_by_ticker)
    tf = build_risk_targeted_portfolio(RISK_SCORE, mu, cov, bounds,
                                       risk_free_rate=PRICING_RF,
                                       asset_class_map=ac_by_ticker)
    weights = {t: w for t, w in tf["weights"].items() if w > 1e-4}
    # Renormalise (safety)
    sw = sum(weights.values()); weights = {t: w / sw for t, w in weights.items()}

    # 2020 model forecast (annual): blended expected return & expected vol
    w_vec = pd.Series(weights)
    exp_return = float((w_vec * mu.reindex(w_vec.index)).sum())
    exp_vol = float(np.sqrt(w_vec.values @ cov.loc[w_vec.index, w_vec.index].values @ w_vec.values))

    # ── Buy-and-hold realized 2020 → now (weights fixed at 2020) ──
    cols = [t for t in weights if t in evalr.columns]
    w0 = pd.Series({t: weights[t] for t in cols}); w0 = w0 / w0.sum()
    entry_cost = TRANSACTION_COST_BPS / 10000.0           # one-way, full deployment from cash
    simple = np.expm1(evalr[cols])                         # monthly simple returns
    asset_val = pd.DataFrame(index=evalr.index, columns=cols, dtype=float)
    prev = (w0 * (1.0 - entry_cost))
    for dt in evalr.index:
        prev = prev * (1.0 + simple.loc[dt])
        asset_val.loc[dt] = prev
    port_value = asset_val.sum(axis=1)
    port_total_log = float(np.log(port_value.iloc[-1] / 1.0))
    port_cagr = _annualize_log(port_total_log, years)
    port_metrics = realized_sharpe(np.log(port_value / port_value.shift(1)).dropna(),
                                   risk_free_annual=RF)

    # ── Market (VWRL) buy-and-hold over same window ──
    mkt = evalr[BENCHMARK_TICKER].dropna() if BENCHMARK_TICKER in evalr else None
    if mkt is not None:
        mkt_total_log = float(mkt.sum())
        mkt_cagr = _annualize_log(mkt_total_log, years)
        mkt_metrics = realized_sharpe(mkt, risk_free_annual=RF)
    else:
        mkt_cagr, mkt_metrics, mkt_total_log = float("nan"), {}, float("nan")

    # ── Per-asset EXPECTED vs ACTUAL (for variance analysis) ──
    rows = []
    for t in cols:
        actual_total_log = float(evalr[t].sum())
        actual_ann = _annualize_log(actual_total_log, years)
        expected_ann = float(mu.get(t, np.nan))
        w = float(w0[t])
        rows.append({
            "ticker": t,
            "asset_class": ac_by_ticker.get(t, t),
            "weight": round(w, 4),
            "expected_return": round(expected_ann, 4),
            "actual_return": round(actual_ann, 4),
            "contribution_expected": round(w * expected_ann, 4),
            "contribution_actual": round(w * actual_ann, 4),
            "variance_contribution": round(w * (actual_ann - expected_ann), 4),
        })
    attribution = sorted(rows, key=lambda r: r["variance_contribution"])

    blended_expected = sum(r["contribution_expected"] for r in attribution)
    blended_actual = sum(r["contribution_actual"] for r in attribution)

    # ── Report ──
    print("\n" + "=" * 84)
    print(f"RISK-8 PORTFOLIO BUILT AT 2020 (≤{BUILD_CUTOFF}) — NO-LEAKAGE BACKTEST TO {eval_end:%Y-%m}")
    print("=" * 84)
    print(f"  Horizon: {years:.2f} years | rf={RF:.0%} | entry cost={TRANSACTION_COST_BPS:.0f}bps | buy-and-hold")
    print(f"  Positions ({len(weights)}):")
    for t, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"    {t:<14}{ac_by_ticker.get(t,''):<22}{w:>7.1%}")

    print("\n  HEADLINE — annualised:")
    print(f"    {'':<26}{'CAGR':>9}{'Vol':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print(f"    {'EXPECTED (2020 forecast)':<26}{exp_return:>9.2%}{exp_vol:>9.2%}"
          f"{(exp_return-RF)/exp_vol:>9.2f}{'—':>9}")
    print(f"    {'ACTUAL (realized)':<26}{port_cagr:>9.2%}{port_metrics['vol']:>9.2%}"
          f"{port_metrics['sharpe']:>9.2f}{port_metrics['max_drawdown']:>9.1%}")
    print(f"    {'MARKET (VWRL)':<26}{mkt_cagr:>9.2%}{mkt_metrics.get('vol',float('nan')):>9.2%}"
          f"{mkt_metrics.get('sharpe',float('nan')):>9.2f}{mkt_metrics.get('max_drawdown',float('nan')):>9.1%}")

    tr_port = float(port_value.iloc[-1] - 1.0)
    tr_mkt = float(np.expm1(mkt_total_log)) if mkt is not None else float("nan")
    print(f"\n  Total return over horizon:  portfolio={tr_port:+.1%}   market={tr_mkt:+.1%}")
    print(f"  Blended EXPECTED annual return (2020): {blended_expected:+.2%}")
    print(f"  Blended ACTUAL   annual return:        {blended_actual:+.2%}")
    print(f"  Expectation gap (actual − expected):   {blended_actual-blended_expected:+.2%}")

    # Persist attribution for the variance-analysis step
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out = {
        "build_cutoff": BUILD_CUTOFF, "eval_start": str(eval_start.date()),
        "eval_end": str(eval_end.date()), "years": round(years, 2), "rf": RF,
        "risk_score": RISK_SCORE,
        "expected_return": round(exp_return, 4), "expected_vol": round(exp_vol, 4),
        "actual_cagr": round(port_cagr, 4), "actual_vol": round(port_metrics["vol"], 4),
        "actual_sharpe": port_metrics["sharpe"], "actual_maxdd": port_metrics["max_drawdown"],
        "market_cagr": round(mkt_cagr, 4), "market_sharpe": mkt_metrics.get("sharpe"),
        "blended_expected_annual": round(blended_expected, 4),
        "blended_actual_annual": round(blended_actual, 4),
        "attribution": attribution,
    }
    path = os.path.join(REPORTS_DIR, "risk8_2020_attribution.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Attribution + metrics saved: {path}")
    print("\n  DISCLAIMERS:")
    print("   - Survivorship bias: universe = funds alive today; delisted funds absent.")
    print("   - Universe & hyperparameters (blend w, halflife, clamp) selected with")
    print("     post-2020 information; a true 2020 deployment may have differed.")
    print("   - Sharpe reported vs the 6% client hurdle (pricing rf inside models is 4%).")

    # Cumulative growth chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(port_value.index, port_value.values, label="Risk-8 portfolio (2020, buy & hold)", lw=2)
        if mkt is not None:
            mkt_curve = np.exp(mkt.cumsum())
            ax.plot(mkt_curve.index, mkt_curve.values, label="Market (VWRL)", lw=2, ls="--")
        ax.axhline(1.0, color="gray", lw=0.8)
        ax.set_title("Risk-8 (built 2020, no leakage) vs Market — growth of £1")
        ax.set_ylabel("Growth of £1"); ax.legend(loc="upper left")
        fig.tight_layout()
        cpath = os.path.join(REPORTS_DIR, "risk8_2020_vs_market.png")
        fig.savefig(cpath, dpi=120); plt.close(fig)
        print(f"  Growth chart saved: {cpath}")
    except Exception as e:
        logger.warning(f"chart skipped: {e}")


if __name__ == "__main__":
    main()
