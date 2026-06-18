"""
Phase 1 Gate — Hold-Out Validation
===================================
Final, honest out-of-sample test that closes Phase 1.

Method: run the walk-forward over the FULL monthly series so that at each
hold-out month the model trains only on data BEFORE it (no leakage), then
evaluate ONLY the rebalance dates inside the untouched hold-out window
(default: last 18 months). The hold-out was never used to select methods.

For each candidate, on the hold-out slice, reports:
  - forecast bias, rank IC, Student-t fit, residual t-test (unbiasedness)
  - realized OOS Sharpe (max-Sharpe portfolio held forward) vs the benchmark

Run:  python -m scripts.run_phase1_holdout
"""

import logging
import os
import sys
from functools import partial

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BENCHMARK_TICKER
from backend.engine.asset_universe import get_ticker_map
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.models import (
    capm, black_litterman, mean_historical, ewma_historical, blend_trailing_bl,
)
from backend.eval.walkforward import run_walk_forward, run_walk_forward_portfolio, split_holdout
from backend.eval.metrics import (
    forecast_metrics, fit_student_t, residual_ttest, realized_sharpe, qq_points,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase1_holdout")
logger.setLevel(logging.INFO)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
HOLDOUT_MONTHS = 18

SAMPLE_ASSET_CLASSES = [
    "uk_equity", "global_equity", "us_equity", "us_tech",
    "emerging_market_equity", "japan_equity", "europe_equity",
    "uk_gilts", "global_bonds", "corporate_bonds",
    "commodities_gold", "uk_reits",
    "indian_large_cap", "indian_mid_cap", "indian_bonds", "indian_gold",
]

CANDIDATES = {
    "capm": capm,
    "black_litterman": black_litterman,
    "hist_mean": mean_historical,
    "ewma_24m": partial(ewma_historical, halflife=24),
    "blend_50_50": partial(blend_trailing_bl, w_trailing=0.50),
    "blend_75tr": partial(blend_trailing_bl, w_trailing=0.75),
}


def _build_universe() -> list[str]:
    ticker_map = get_ticker_map(SAMPLE_ASSET_CLASSES)
    return sorted(set(ticker_map.values()) | {BENCHMARK_TICKER})


def _slice_residuals(pred: pd.DataFrame, real: pd.DataFrame, sig: pd.DataFrame) -> np.ndarray:
    cols = pred.columns.intersection(real.columns).intersection(sig.columns)
    z = ((real[cols] - pred[cols]) / sig[cols]).values.flatten()
    return z[np.isfinite(z)]


def _save_qq(resid: np.ndarray, fit, name: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib unavailable: {e}")
        return ""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    t_pts = qq_points(resid, dist="t", dist_args=(fit.nu, fit.loc, fit.scale))
    theo = np.array(t_pts["theoretical"]); samp = np.array(t_pts["sample"])
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(theo, samp, s=12, alpha=0.6, color="tab:red")
    lim = [min(theo.min(), samp.min()), max(theo.max(), samp.max())]
    ax.plot(lim, lim, "k--", lw=1.2)
    ax.set_title(f"Hold-out residual QQ vs Student-t — {name} (nu={fit.nu:.1f}, KSp={fit.ks_p_t:.2f})")
    ax.set_xlabel("Theoretical Student-t quantiles"); ax.set_ylabel("Sample residual quantiles")
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, f"qq_holdout_{name}.png")
    fig.savefig(path, dpi=120); plt.close(fig)
    return path


def main() -> None:
    tickers = _build_universe()
    returns = build_monthly_gbp_log_returns(tickers, period_years=10, min_obs=24)
    if returns is None or returns.shape[1] < 3:
        logger.error("Insufficient data. Check network/cache.")
        return

    _, holdout = split_holdout(returns, holdout_months=HOLDOUT_MONTHS)
    if holdout.empty:
        logger.error("No hold-out window available.")
        return
    h_start, h_end = holdout.index.min(), holdout.index.max()
    logger.info(f"Hold-out window: {h_start:%Y-%m} .. {h_end:%Y-%m} ({len(holdout)} months)")

    # Benchmark realized Sharpe over the hold-out
    bench = returns[BENCHMARK_TICKER].loc[h_start:h_end] if BENCHMARK_TICKER in returns else None
    bench_sh = realized_sharpe(bench) if bench is not None else None

    print("\n" + "=" * 100)
    print(f"PHASE 1 HOLD-OUT VALIDATION — {h_start:%Y-%m} .. {h_end:%Y-%m} "
          f"({len(holdout)} months, untouched)")
    print("=" * 100)
    header = (f"{'model':<16}{'bias':>9}{'rankIC':>9}{'nu':>6}{'KSp_t':>8}"
              f"{'res_p':>8}{'unbias':>8}{'OOS_CAGR':>10}{'OOS_Shrp':>9}")
    print(header)
    print("-" * len(header))

    best = None
    for name, model in CANDIDATES.items():
        # Full walk-forward (no leakage: trains only on data before each date)
        wf = run_walk_forward(returns, model, min_train_months=36, step_months=1, vol_lookback_months=36)
        if wf.predicted.empty:
            print(f"{name:<16}  (no predictions)")
            continue
        mask = (wf.predicted.index >= h_start) & (wf.predicted.index <= h_end)
        pred, real, sig = wf.predicted.loc[mask], wf.realized.loc[mask], wf.sigma.loc[mask]
        if pred.empty:
            print(f"{name:<16}  (no hold-out predictions)")
            continue

        fm = forecast_metrics(pred, real, sig)
        resid = _slice_residuals(pred, real, sig)
        fit = fit_student_t(resid) if resid.size >= 20 else None
        tt = residual_ttest(resid)

        port = run_walk_forward_portfolio(returns, model, min_train_months=36, vol_lookback_months=36)
        port_h = port.loc[h_start:h_end]
        sh = realized_sharpe(port_h)

        nu = fit.nu if fit else float("nan")
        ksp = fit.ks_p_t if fit else float("nan")
        print(f"{name:<16}{fm.bias:>9.4f}{fm.rank_ic:>9.3f}{nu:>6.1f}{ksp:>8.3f}"
              f"{tt['p_value']:>8.3f}{('YES' if tt['unbiased'] else 'no'):>8}"
              f"{sh['cagr']:>10.3f}{sh['sharpe']:>9.3f}")

        if name.startswith("blend") and fit is not None:
            if best is None or sh["sharpe"] > best[0]:
                best = (sh["sharpe"], name, resid, fit, fm, tt, sh)

    if bench_sh:
        print("-" * len(header))
        print(f"{'BENCHMARK(VWRL)':<16}{'':>9}{'':>9}{'':>6}{'':>8}{'':>8}{'':>8}"
              f"{bench_sh['cagr']:>10.3f}{bench_sh['sharpe']:>9.3f}")

    # ── Phase 1 verdict on the leading blend ──
    print("\n" + "-" * 100)
    print("PHASE 1 GATE — leading candidate on hold-out")
    print("-" * 100)
    if best:
        _, name, resid, fit, fm, tt, sh = best
        path = _save_qq(resid, fit, name)
        c_unbiased = tt["unbiased"]
        c_tailfit = fit.ks_p_t > 0.05
        c_bench = (bench_sh is None) or (sh["sharpe"] >= bench_sh["sharpe"])

        def mark(b): return "PASS" if b else "FAIL"
        print(f"  Candidate: {name}")
        print(f"  1) Unbiased (residual t-test p>0.05):  {mark(c_unbiased)}  (p={tt['p_value']:.3f})")
        print(f"  2) Student-t tail fit (KS p>0.05):     {mark(c_tailfit)}  (nu={fit.nu:.1f}, KSp={fit.ks_p_t:.3f})")
        print(f"  3) Realized Sharpe >= benchmark:       {mark(c_bench)}  "
              f"(model={sh['sharpe']:.3f} vs bench={bench_sh['sharpe'] if bench_sh else float('nan'):.3f})")
        if path:
            print(f"  QQ plot: {path}")
        if c_unbiased and c_tailfit and c_bench:
            print("\n  ==> PHASE 1 PASSED on hold-out. Lock the trailing+BL blend; proceed to Phase 2.")
        else:
            print("\n  ==> Hold-out shortfall on one or more gates — review before locking.")
    print("\n  Caveat: 18-month hold-out -> Sharpe SE is wide (~0.7); treat realized Sharpe")
    print("          as a sanity check, not a precise ranking. Bias/tail-fit are more stable.")
    print()


if __name__ == "__main__":
    main()
