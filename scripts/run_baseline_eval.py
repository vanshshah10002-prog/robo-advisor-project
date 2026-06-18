"""
Phase 0 Gate — Baseline Expected-Return Evaluation
===================================================
Proves the Phase 0 foundation end-to-end on clean monthly / GBP-unhedged data:

  1. Build month-end GBP log returns (outer-join, FX-converted) for a sample universe.
  2. Slice an untouched hold-out.
  3. Walk-forward each baseline model (hist_mean, EWMA, CAPM).
  4. Report forecast metrics (bias, MAE, RMSE, rank IC) + Student-t tail fit.
  5. Save a QQ plot of pooled standardized residuals for the best baseline.

Run:  python -m scripts.run_baseline_eval

This establishes the honest baseline that Phase 1 (Black-Litterman) must beat.
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

# Ensure project root on path when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BENCHMARK_TICKER, MVO_RISK_FREE_RATE
from backend.engine.asset_universe import get_ticker_map
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.models import get_baseline_models
from backend.eval.walkforward import run_walk_forward, split_holdout
from backend.eval.metrics import forecast_metrics, fit_student_t, qq_points

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("baseline_eval")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")

# A representative cross-asset universe for the baseline (one primary ETF per class)
SAMPLE_ASSET_CLASSES = [
    "uk_equity", "global_equity", "us_equity", "us_tech",
    "emerging_market_equity", "japan_equity", "europe_equity",
    "uk_gilts", "global_bonds", "corporate_bonds",
    "commodities_gold", "uk_reits",
    "indian_large_cap", "indian_mid_cap", "indian_bonds", "indian_gold",
]


def _build_universe() -> list[str]:
    ticker_map = get_ticker_map(SAMPLE_ASSET_CLASSES)
    tickers = sorted(set(ticker_map.values()) | {BENCHMARK_TICKER})
    logger.info(f"Sample universe: {len(tickers)} tickers -> {tickers}")
    return tickers


def _save_qq_plot(sample, fit, model_name: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib unavailable, skipping QQ plot: {e}")
        return ""

    os.makedirs(REPORTS_DIR, exist_ok=True)
    t_pts = qq_points(np.asarray(sample), dist="t", dist_args=(fit.nu, fit.loc, fit.scale))
    n_pts = qq_points(np.asarray(sample), dist="norm")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, pts, title in (
        (axes[0], t_pts, f"Student-t (ν={fit.nu:.1f})  KS p={fit.ks_p_t:.3f}"),
        (axes[1], n_pts, f"Normal  KS p={fit.ks_p_normal:.3f}"),
    ):
        theo = np.array(pts["theoretical"]); samp = np.array(pts["sample"])
        ax.scatter(theo, samp, s=8, alpha=0.5)
        lim = [min(theo.min(), samp.min()), max(theo.max(), samp.max())]
        ax.plot(lim, lim, "r--", lw=1)
        ax.set_title(title); ax.set_xlabel("Theoretical quantiles"); ax.set_ylabel("Sample quantiles")

    fig.suptitle(f"QQ of standardized residuals — {model_name}")
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, f"qq_residuals_{model_name}.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main() -> None:
    tickers = _build_universe()

    returns = build_monthly_gbp_log_returns(tickers, period_years=10, min_obs=24)
    if returns is None or returns.shape[1] < 3:
        logger.error("Insufficient data to run baseline evaluation. Check network/cache.")
        return

    logger.info(f"Returns panel: {returns.shape[0]} months x {returns.shape[1]} tickers")

    dev, holdout = split_holdout(returns, holdout_months=18)

    print("\n" + "=" * 78)
    print("PHASE 0 BASELINE — walk-forward on development set (hold-out reserved)")
    print("=" * 78)
    header = f"{'model':<12}{'bias':>9}{'mae':>9}{'rmse':>9}{'rankIC':>9}{'IC_t':>7}{'nu':>7}{'KSp_t':>8}{'KSp_N':>8}"
    print(header)
    print("-" * len(header))

    best = None
    for name, model in get_baseline_models().items():
        wf = run_walk_forward(dev, model, min_train_months=36, step_months=1, vol_lookback_months=36)
        if wf.predicted.empty:
            print(f"{name:<12}  (no predictions)")
            continue
        fm = forecast_metrics(wf.predicted, wf.realized, wf.sigma)
        resid = wf.pooled_residuals()
        fit = fit_student_t(resid) if resid.size >= 20 else None

        nu = fit.nu if fit else float("nan")
        ksp_t = fit.ks_p_t if fit else float("nan")
        ksp_n = fit.ks_p_normal if fit else float("nan")
        print(f"{name:<12}{fm.bias:>9.4f}{fm.mae:>9.4f}{fm.rmse:>9.4f}"
              f"{fm.rank_ic:>9.3f}{fm.rank_ic_t:>7.2f}{nu:>7.1f}{ksp_t:>8.3f}{ksp_n:>8.3f}")

        score = fm.rank_ic if np.isfinite(fm.rank_ic) else -np.inf
        if best is None or score > best[0]:
            best = (score, name, resid, fit)

    if best and best[3] is not None:
        _, name, resid, fit = best
        path = _save_qq_plot(resid, fit, name)
        print("\nBest baseline by rank IC:", name)
        print(f"  Student-t fit: nu={fit.nu:.2f}, KS p(t)={fit.ks_p_t:.3f}, "
              f"KS p(normal)={fit.ks_p_normal:.3f}, JB p={fit.jarque_bera_p:.3g}, QQ R²(t)={fit.qq_r2_t:.4f}")
        if path:
            print(f"  QQ plot saved: {path}")

    print("\nInterpretation guide:")
    print("  bias ~ 0          -> forecast level unbiased")
    print("  rank IC > 0       -> ranks assets correctly (what MVO needs)")
    print("  KSp_t >> KSp_N    -> residuals fat-tailed (Student-t fits better than Normal)")
    print("  nu in [3,10]      -> meaningful fat tails (justifies t-innovations in Monte Carlo)")
    print("\nHold-out reserved (not evaluated here):",
          f"{holdout.index.min():%Y-%m} .. {holdout.index.max():%Y-%m}" if not holdout.empty else "none")


if __name__ == "__main__":
    main()
