"""
Phase 1 — Black-Litterman vs CAPM Bake-Off
===========================================
Runs the expected-return candidates (CAPM bar + Black-Litterman equilibrium
+ 50/50 blend) through the SAME walk-forward harness as Phase 0, then:

  1. Prints the comparison table (bias, rank IC, Student-t fit).
  2. Runs the one-sample t-test on pooled standardized residuals (unbiasedness).
  3. Plots CAPM vs BL QQ points overlaid on the same Student-t reference line.
  4. Prints an acceptance verdict for BL.

Run:  python -m scripts.run_phase1_bl
"""

import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import BENCHMARK_TICKER
from backend.engine.asset_universe import get_ticker_map
from backend.data.returns import build_monthly_gbp_log_returns
from backend.eval.models import get_phase1_models
from backend.eval.walkforward import run_walk_forward, split_holdout
from backend.eval.metrics import forecast_metrics, fit_student_t, residual_ttest, qq_points

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase1_bl")
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


def _overlay_qq(results: dict) -> str:
    """Overlay each model's QQ points vs its fitted Student-t on one axis."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib unavailable: {e}")
        return ""

    os.makedirs(REPORTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    colors = {"capm": "tab:blue", "black_litterman": "tab:red", "blend_50_50": "tab:green"}

    all_q = []
    for name, (resid, fit) in results.items():
        if fit is None:
            continue
        pts = qq_points(np.asarray(resid), dist="t", dist_args=(fit.nu, fit.loc, fit.scale))
        theo = np.array(pts["theoretical"]); samp = np.array(pts["sample"])
        all_q.extend([theo.min(), theo.max(), samp.min(), samp.max()])
        ax.scatter(theo, samp, s=10, alpha=0.45, color=colors.get(name, "gray"),
                   label=f"{name} (ν={fit.nu:.1f}, KSp={fit.ks_p_t:.2f})")

    if all_q:
        lim = [min(all_q), max(all_q)]
        ax.plot(lim, lim, "k--", lw=1.2, label="Student-t reference (y=x)")
    ax.set_title("CAPM vs Black-Litterman — QQ of standardized residuals vs Student-t")
    ax.set_xlabel("Theoretical Student-t quantiles")
    ax.set_ylabel("Sample residual quantiles")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    path = os.path.join(REPORTS_DIR, "qq_capm_vs_bl.png")
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

    print("\n" + "=" * 92)
    print("PHASE 1 — CAPM vs BLACK-LITTERMAN (walk-forward, dev set, 18m hold-out reserved)")
    print("=" * 92)
    header = (f"{'model':<16}{'bias':>9}{'rankIC':>9}{'IC_t':>7}{'nu':>6}"
              f"{'KSp_t':>8}{'KSp_N':>8}{'res_t':>8}{'res_p':>8}{'unbiased':>10}")
    print(header)
    print("-" * len(header))

    results = {}
    metrics_by_model = {}
    for name, model in get_phase1_models().items():
        wf = run_walk_forward(dev, model, min_train_months=36, step_months=1, vol_lookback_months=36)
        if wf.predicted.empty:
            print(f"{name:<16}  (no predictions)")
            continue
        fm = forecast_metrics(wf.predicted, wf.realized, wf.sigma)
        resid = wf.pooled_residuals()
        fit = fit_student_t(resid) if resid.size >= 20 else None
        tt = residual_ttest(resid)
        results[name] = (resid, fit)
        metrics_by_model[name] = (fm, fit, tt)

        nu = fit.nu if fit else float("nan")
        ksp_t = fit.ks_p_t if fit else float("nan")
        ksp_n = fit.ks_p_normal if fit else float("nan")
        print(f"{name:<16}{fm.bias:>9.4f}{fm.rank_ic:>9.3f}{fm.rank_ic_t:>7.2f}{nu:>6.1f}"
              f"{ksp_t:>8.3f}{ksp_n:>8.3f}{tt['t_stat']:>8.2f}{tt['p_value']:>8.3f}"
              f"{('YES' if tt['unbiased'] else 'no'):>10}")

    path = _overlay_qq(results)
    if path:
        print(f"\nOverlay QQ plot saved: {path}")

    # ── Acceptance verdict for Black-Litterman ──
    print("\n" + "-" * 92)
    print("BLACK-LITTERMAN ACCEPTANCE VERDICT")
    print("-" * 92)
    if "black_litterman" in metrics_by_model and "capm" in metrics_by_model:
        bl_fm, bl_fit, bl_tt = metrics_by_model["black_litterman"]
        cap_fm, cap_fit, cap_tt = metrics_by_model["capm"]

        c_unbiased = bl_tt["unbiased"]
        c_tailfit = bl_fit is not None and bl_fit.ks_p_t > 0.05
        c_rank = np.isfinite(bl_fm.rank_ic) and bl_fm.rank_ic >= cap_fm.rank_ic

        def mark(b): return "PASS" if b else "FAIL"
        print(f"  1) Unbiased (residual t-test p>0.05):  {mark(c_unbiased)}  "
              f"(t={bl_tt['t_stat']:.2f}, p={bl_tt['p_value']:.3f})")
        print(f"  2) Student-t tail fit (KS p>0.05):     {mark(c_tailfit)}  "
              f"(nu={bl_fit.nu:.1f}, KS p={bl_fit.ks_p_t:.3f})" if bl_fit else "  2) tail fit: n/a")
        print(f"  3) Rank IC >= CAPM:                    {mark(c_rank)}  "
              f"(BL={bl_fm.rank_ic:.3f} vs CAPM={cap_fm.rank_ic:.3f})")

        if c_unbiased and c_tailfit and c_rank:
            print("\n  ==> BL ACCEPTED: passes all three gates. Lock BL as the expected-returns model.")
        elif c_unbiased and c_tailfit and not c_rank:
            print("\n  ==> BL distribution OK but ranking weaker than CAPM.")
            print("      Inspect blend_50_50 above; tune w if it beats both -> proceed with blend.")
        else:
            print("\n  ==> BL NOT fully accepted. Fall back to blend / re-examine caps & λ.")
    print()


if __name__ == "__main__":
    main()
