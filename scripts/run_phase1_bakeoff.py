"""
Phase 1 — Wide Expected-Return Bake-Off
========================================
Runs the full candidate set through the SAME walk-forward harness:
CAPM, hist mean, EWMA, James-Stein, cross-sectional momentum, Black-Litterman,
BL+momentum, and a trailing/BL blend sweep (25/50/75).

For each method reports:
  - distribution diagnostics (bias, rank IC, Student-t ν, KS p, residual t-test)
  - REALIZED out-of-sample Sharpe (max-Sharpe portfolio held forward)

No winner is selected — this is for exploring methods. Also plots a QQ overlay
of every method's standardized residuals vs Student-t.

Run:  python -m scripts.run_phase1_bakeoff
"""

import logging
import os
import sys
from functools import partial

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BENCHMARK_TICKER
from backend.engine.asset_universe import get_ticker_map
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.models import get_phase1_full_models, build_factor_returns, factor_model
from backend.eval.walkforward import run_walk_forward, run_walk_forward_portfolio, split_holdout
from backend.eval.metrics import forecast_metrics, fit_student_t, residual_ttest, realized_sharpe, qq_points

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase1_bakeoff")
logger.setLevel(logging.INFO)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")

SAMPLE_ASSET_CLASSES = [
    "uk_equity", "global_equity", "us_equity", "us_tech",
    "emerging_market_equity", "japan_equity", "europe_equity",
    "uk_gilts", "global_bonds", "corporate_bonds",
    "commodities_gold", "uk_reits",
    "indian_large_cap", "indian_mid_cap", "indian_bonds", "indian_gold",
]


def _build_universe() -> list[str]:
    ticker_map = get_ticker_map(SAMPLE_ASSET_CLASSES)
    return sorted(set(ticker_map.values()) | {BENCHMARK_TICKER})


def _overlay_qq(results: dict, path_name: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import itertools
    except Exception as e:
        logger.warning(f"matplotlib unavailable: {e}")
        return ""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 9))
    cmap = plt.get_cmap("tab10")
    colors = itertools.cycle([cmap(i) for i in range(10)])
    all_q = []
    for name, (resid, fit) in results.items():
        if fit is None:
            continue
        pts = qq_points(np.asarray(resid), dist="t", dist_args=(fit.nu, fit.loc, fit.scale))
        theo = np.array(pts["theoretical"]); samp = np.array(pts["sample"])
        all_q.extend([theo.min(), theo.max(), samp.min(), samp.max()])
        ax.scatter(theo, samp, s=7, alpha=0.4, color=next(colors), label=f"{name} (KSp={fit.ks_p_t:.2f})")
    if all_q:
        lim = [min(all_q), max(all_q)]
        ax.plot(lim, lim, "k--", lw=1.2, label="Student-t reference")
    ax.set_title("Phase 1 bake-off — QQ of standardized residuals vs Student-t")
    ax.set_xlabel("Theoretical Student-t quantiles"); ax.set_ylabel("Sample residual quantiles")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, path_name)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main() -> None:
    tickers = _build_universe()
    returns = build_monthly_gbp_log_returns(tickers, period_years=10, min_obs=24)
    if returns is None or returns.shape[1] < 3:
        logger.error("Insufficient data. Check network/cache.")
        return
    dev, holdout = split_holdout(returns, holdout_months=18)
    logger.info(f"Dev set: {dev.shape[0]} months x {dev.shape[1]} tickers")

    print("\n" + "=" * 104)
    print("PHASE 1 WIDE BAKE-OFF — distribution diagnostics + realized OOS Sharpe (dev set, hold-out reserved)")
    print("=" * 104)
    header = (f"{'model':<16}{'bias':>9}{'rankIC':>9}{'IC_t':>7}{'nu':>6}{'KSp_t':>8}"
              f"{'res_p':>8}{'unbias':>8}{'OOS_CAGR':>10}{'OOS_vol':>9}{'OOS_Shrp':>9}")
    print(header)
    print("-" * len(header))

    # Build self-contained factor returns and append the factor model
    models = get_phase1_full_models()
    factors = build_factor_returns(period_years=10)
    if factors is not None and not factors.empty:
        models["factor_model"] = partial(factor_model, factor_returns=factors)
        logger.info(f"Factor model added with factors: {list(factors.columns)}")
    else:
        logger.warning("Factor model skipped (no factor returns)")

    results = {}
    for name, model in models.items():
        wf = run_walk_forward(dev, model, min_train_months=36, step_months=1, vol_lookback_months=36)
        if wf.predicted.empty:
            print(f"{name:<16}  (no predictions)")
            continue
        fm = forecast_metrics(wf.predicted, wf.realized, wf.sigma)
        resid = wf.pooled_residuals()
        fit = fit_student_t(resid) if resid.size >= 20 else None
        tt = residual_ttest(resid)
        results[name] = (resid, fit)

        port = run_walk_forward_portfolio(dev, model, min_train_months=36, vol_lookback_months=36)
        sh = realized_sharpe(port)

        nu = fit.nu if fit else float("nan")
        ksp = fit.ks_p_t if fit else float("nan")
        print(f"{name:<16}{fm.bias:>9.4f}{fm.rank_ic:>9.3f}{fm.rank_ic_t:>7.2f}{nu:>6.1f}{ksp:>8.3f}"
              f"{tt['p_value']:>8.3f}{('YES' if tt['unbiased'] else 'no'):>8}"
              f"{sh['cagr']:>10.3f}{sh['vol']:>9.3f}{sh['sharpe']:>9.3f}")

    path = _overlay_qq(results, "qq_phase1_bakeoff.png")
    if path:
        print(f"\nOverlay QQ plot saved: {path}")
    print("\nNotes:")
    print("  - res_p>0.05 (unbias=YES) -> forecast level unbiased (t-test accepted)")
    print("  - KSp_t>0.05             -> Student-t tail fit accepted")
    print("  - OOS_Shrp                -> realized max-Sharpe portfolio, walk-forward (the real test)")
    print("  - rankIC / OOS_Shrp are what differ between methods; tails are ~shared.")
    if not holdout.empty:
        print(f"\nHold-out reserved (untouched): {holdout.index.min():%Y-%m} .. {holdout.index.max():%Y-%m}")


if __name__ == "__main__":
    main()
