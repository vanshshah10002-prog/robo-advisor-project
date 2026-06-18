"""
Phase 2 — Covariance Estimator Bake-Off + Time-Varying Regime Detector
=======================================================================
1. Bakes off covariance estimators via the global minimum-variance (GMV)
   out-of-sample volatility test (Ledoit-Wolf 2004): lower realized vol = better.
   Also reports calibration (realized/predicted vol ratio ~ 1 is good) and the
   GMV realized Sharpe.
2. Builds the time-varying rolling-correlation regime signal and plots it over
   time (vs the static production threshold), to confirm it lights up on
   2020-COVID / 2022 stress.

Run:  python -m scripts.run_phase2_cov
"""

import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BENCHMARK_TICKER, REGIME_HIGH_CORR_THRESHOLD
from backend.engine.asset_universe import get_ticker_map
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.cov_models import get_cov_models, rolling_avg_correlation, volatility_regime
from backend.eval.walkforward import run_walk_forward_gmv
from backend.eval.metrics import realized_sharpe

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase2_cov")
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
    tmap = get_ticker_map(SAMPLE_ASSET_CLASSES)
    return sorted(set(tmap.values()) | {BENCHMARK_TICKER})


def _plot_regime(sig, threshold: float) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib unavailable: {e}")
        return ""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(sig.index, sig.values, color="tab:blue", lw=1.5, label="Rolling avg pairwise |corr| (6m)")
    ax.axhline(threshold, color="tab:red", ls="--", lw=1.2, label=f"Crisis threshold ({threshold})")
    ax.fill_between(sig.index, threshold, sig.values, where=(sig.values > threshold),
                    color="tab:red", alpha=0.25, label="Regime: HIGH correlation")
    ax.set_title("Time-varying regime detector — rolling average pairwise correlation")
    ax.set_ylabel("avg |correlation|"); ax.set_xlabel("date")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, "regime_rolling_correlation.png")
    fig.savefig(path, dpi=120); plt.close(fig)
    return path


def _plot_vol_regime(vr) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib unavailable: {e}")
        return ""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax1.plot(vr.index, vr["vol_z"], color="tab:purple", lw=1.5, label="Vol z-score")
    ax1.axhline(1.0, color="tab:red", ls="--", lw=1.2, label="Crisis threshold (z=1.0)")
    ax1.fill_between(vr.index, 1.0, vr["vol_z"], where=(vr["vol_z"] > 1.0),
                     color="tab:red", alpha=0.25)
    ax1.set_ylabel("vol z-score"); ax1.legend(loc="upper left", fontsize=9)
    ax1.set_title("Volatility-based regime detector")
    ax2.fill_between(vr.index, vr["drawdown"], 0, color="tab:blue", alpha=0.4)
    ax2.set_ylabel("drawdown"); ax2.set_xlabel("date")
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, "regime_volatility.png")
    fig.savefig(path, dpi=120); plt.close(fig)
    return path


def main() -> None:
    tickers = _build_universe()
    returns = build_monthly_gbp_log_returns(tickers, period_years=10, min_obs=24)
    if returns is None or returns.shape[1] < 3:
        logger.error("Insufficient data. Check network/cache.")
        return
    logger.info(f"Returns: {returns.shape[0]} months x {returns.shape[1]} tickers")

    # ── 1. Covariance estimator bake-off (GMV out-of-sample volatility) ──
    print("\n" + "=" * 86)
    print("PHASE 2 — COVARIANCE BAKE-OFF (global min-variance, out-of-sample)")
    print("=" * 86)
    header = (f"{'estimator':<14}{'GMV_realVol':>13}{'GMV_predVol':>13}"
              f"{'calib(r/p)':>12}{'GMV_Sharpe':>12}{'n':>6}")
    print(header)
    print("-" * len(header))

    rows = []
    for name, cov_fn in get_cov_models().items():
        res = run_walk_forward_gmv(returns, cov_fn, min_train_months=36, max_weight=0.30)
        r = res["realized"]
        if r.empty:
            print(f"{name:<14}  (no result)")
            continue
        real_vol = float(r.std(ddof=1) * np.sqrt(12))
        pred_vol = float(res["pred_vol_annual"].mean())
        calib = real_vol / pred_vol if pred_vol > 0 else float("nan")
        sh = realized_sharpe(r)["sharpe"]
        rows.append((name, real_vol))
        print(f"{name:<14}{real_vol:>13.4f}{pred_vol:>13.4f}{calib:>12.3f}{sh:>12.3f}{res['n']:>6}")

    if rows:
        best = min(rows, key=lambda x: x[1])
        print("-" * len(header))
        print(f"Lowest realized GMV volatility (best estimator): {best[0]} ({best[1]:.4f})")

    # ── 2. Time-varying regime detector ──
    sig = rolling_avg_correlation(returns, window=6, min_assets=3)
    print("\n" + "=" * 86)
    print("TIME-VARYING REGIME DETECTOR (rolling 6m avg pairwise |corr|)")
    print("=" * 86)
    if not sig.empty:
        print(f"  range: [{sig.min():.3f}, {sig.max():.3f}], mean={sig.mean():.3f}, "
              f"static threshold={REGIME_HIGH_CORR_THRESHOLD}")
        hi = sig[sig > REGIME_HIGH_CORR_THRESHOLD]
        print(f"  months above threshold: {len(hi)} / {len(sig)}")
        if not hi.empty:
            print("  peak stress months:")
            for dt, v in sig.sort_values(ascending=False).head(5).items():
                print(f"    {dt:%Y-%m}: {v:.3f}")
        path = _plot_regime(sig, REGIME_HIGH_CORR_THRESHOLD)
        if path:
            print(f"  regime plot saved: {path}")
    # ── 3. Volatility-based regime detector ──
    vr = volatility_regime(returns, market=returns.get(BENCHMARK_TICKER),
                           short_window=3, long_window=36, z_threshold=1.0)
    print("\n" + "=" * 86)
    print("VOLATILITY-BASED REGIME DETECTOR (vol z-score; crisis = z>1.0)")
    print("=" * 86)
    if not vr.empty:
        crises = vr[vr["crisis"]]
        print(f"  crisis months flagged: {len(crises)} / {len(vr)}")
        print("  peak stress months (by vol z-score):")
        for dt, row in vr.sort_values("vol_z", ascending=False).head(6).iterrows():
            print(f"    {dt:%Y-%m}: vol_z={row['vol_z']:+.2f}, "
                  f"ann_vol={row['short_vol']:.2f}, drawdown={row['drawdown']:.1%}")
        path = _plot_vol_regime(vr)
        if path:
            print(f"  regime plot saved: {path}")

    print("\nNotes:")
    print("  - GMV_realVol is the headline: lowest = best covariance estimator (Ledoit-Wolf 2004).")
    print("  - calib(r/p) ~ 1.0 means the estimator's vol forecast is well-calibrated.")
    print("  - The static production detector uses ONE full-sample number; this rolling signal")
    print("    is time-varying and should spike around 2020-03 (COVID) and 2022.")


if __name__ == "__main__":
    main()
