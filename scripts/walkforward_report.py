"""
Charts and REPORT.md for scripts/run_walkforward_backtest.py.
Colours: the validated categorical slots 1–2 (blue, orange) in fixed order on a
light surface; every chart has a CSV table behind it in the same folder.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834"]   # slot 1 blue, slot 2 orange


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK_2, labelsize=8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def _matched_benchmark(summary: pd.DataFrame, risk: int) -> str:
    return summary[(summary["kind"] == "benchmark") & (summary["risk"] == risk)]["run"].iloc[0]


def equity_chart(tables: dict, risks: list[int], path: str) -> None:
    eq, summary = tables["equity"], tables["summary"]
    cols = 2
    rows = (len(risks) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(11, 3.6 * rows), sharex=True, facecolor=SURFACE, squeeze=False)
    for ax, risk in zip(axes.flat, risks):
        _style(ax)
        for colour, label in zip(SERIES, [f"Risk {risk} (bands)", _matched_benchmark(summary, risk)]):
            s = eq[label] / 1000.0
            ax.plot(s.index, s.values, color=colour, linewidth=2, label=label)
            ax.annotate(f"£{s.iloc[-1]:.0f}k", (s.index[-1], s.iloc[-1]), xytext=(4, 0),
                        textcoords="offset points", color=INK, fontsize=8, va="center")
        ax.set_title(f"Risk {risk}: policy portfolio vs two-fund at the same growth share",
                     fontsize=9, color=INK, loc="left")
        ax.set_ylabel("Value (£k)", color=INK_2, fontsize=8)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")
    for ax in list(axes.flat)[len(risks):]:
        ax.set_visible(False)
    fig.suptitle("£100k invested, walk-forward, trading costs included", color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def forecast_chart(tables: dict, risks: list[int], path: str) -> None:
    p = tables["accuracy_periods"]
    p = p[p["mode"] == "bands"]
    fig, axes = plt.subplots(1, len(risks), figsize=(3.2 * len(risks), 3.8), sharey=True, facecolor=SURFACE)
    axes = axes if len(risks) > 1 else [axes]
    for ax, risk in zip(axes, risks):
        _style(ax)
        d = p[p["risk"] == risk].reset_index(drop=True)
        x = range(len(d))
        sd = d["vol_calibrated"] / d["years"] ** 0.5
        ax.errorbar(x, d["expected_arith"] * 100, yerr=sd * 100, fmt="o", color=SERIES[0], markersize=6,
                    elinewidth=2, capsize=0, label="Forecast ±1σ")
        ax.plot(x, d["realised_ann"] * 100, "D", color=SERIES[1], markersize=6, label="Realised")
        ax.axhline(0, color=INK_2, linewidth=0.8)
        ax.set_xticks(list(x), [f"{s:%b %y}" for s in d["start"]], rotation=45, fontsize=7)
        ax.set_title(f"Risk {risk}", fontsize=9, color=INK, loc="left")
    axes[0].set_ylabel("Annualised return over the period (%)", color=INK_2, fontsize=8)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")
    fig.suptitle("Expected vs realised return per re-optimisation period (bands mode)",
                 color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def write_charts(tables: dict, risks: list[int], out: str) -> None:
    equity_chart(tables, risks, os.path.join(out, "equity_by_risk.png"))
    forecast_chart(tables, risks, os.path.join(out, "forecast_vs_realised.png"))


# =============================================================================
# REPORT.md
# =============================================================================

def _pct(x, d=1) -> str:
    return "" if pd.isna(x) else f"{x * 100:.{d}f}%"


def _gbp(x) -> str:
    return f"£{x:,.0f}"


def _md(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def _performance_table(summary: pd.DataFrame) -> str:
    t = pd.DataFrame({
        "Run": summary["run"], "End value": summary["end_value"].map(_gbp),
        "CAGR": summary["cagr"].map(_pct), "Volatility": summary["volatility"].map(_pct),
        "Sharpe": summary["sharpe"].map(lambda v: f"{v:.2f}"), "Max drawdown": summary["max_drawdown"].map(_pct),
        "Costs (all)": summary["total_costs_gbp"].map(lambda v: f"£{v:,.2f}"),
        "Rebalance costs": summary["rebalance_costs_gbp"].map(lambda v: f"£{v:,.2f}"),
        "Costs bp/yr": summary["costs_bp_per_year"].map(lambda v: f"{v:.1f}"),
        "Rebalances": summary["n_rebalances"], "Turnover/yr": summary["turnover_per_year"].map(_pct),
    })
    return _md(t)


def _accuracy_table(acc: pd.DataFrame) -> str:
    a = acc[acc["mode"] == "bands"]
    t = pd.DataFrame({
        "Risk": a["risk"], "Forecast E[R] (arith)": a["forecast_arith_time_weighted"].map(_pct),
        "Forecast (geo, E−σ²/2)": a["forecast_geo_time_weighted"].map(_pct),
        "Realised CAGR": a["realised_cagr_after_first_trade"].map(_pct),
        "Bias (mean actual − expected)": a["bias_mean_error"].map(_pct), "RMSE": a["rmse"].map(_pct),
        "Within ±1σ (calibrated)": a["coverage_1sd_calibrated"].map(lambda v: f"{v:.0%}"),
        "Within ±1σ (model)": a["coverage_1sd_model"].map(lambda v: f"{v:.0%}"),
        "Realised/predicted vol (model)": a["vol_ratio_realised_to_model"].map(lambda v: f"{v:.2f}"),
        "Realised/predicted vol (×1.15)": a["vol_ratio_realised_to_calibrated"].map(lambda v: f"{v:.2f}"),
    })
    return _md(t)


def _periods_table(periods: pd.DataFrame) -> str:
    p = periods[periods["mode"] == "bands"]
    t = pd.DataFrame({
        "Risk": p["risk"], "Period": [f"{s:%Y-%m-%d} → {e:%Y-%m-%d}" for s, e in zip(p["start"], p["end"])],
        "rf at decision": p["risk_free"].map(_pct), "Expected (arith)": p["expected_arith"].map(_pct),
        "Predicted vol (×1.15)": p["vol_calibrated"].map(_pct), "Realised (ann.)": p["realised_ann"].map(_pct),
        "Realised vol": p["realised_vol"].map(_pct), "Error": p["error"].map(_pct),
        "z": p["z_calibrated"].map(lambda v: f"{v:+.2f}"),
    })
    return _md(t)


def _targets_table(decisions: pd.DataFrame) -> str:
    w = decisions.pivot_table(index=["risk", "asset_class"], columns="decided", values="weight").fillna(0.0)
    w.columns = [f"{c:%Y-%m}" for c in pd.to_datetime(w.columns)]
    w = w.map(lambda v: f"{v:.1%}" if v > 0 else "–").reset_index()
    return _md(w)


def write_report(tables: dict, settings: dict, out: str) -> None:
    s = settings
    summary = tables["summary"]
    lines = [
        "# Walk-forward backtest — policy portfolio construction",
        "",
        f"Test window **{s['start']:%Y-%m-%d} → {s['end']:%Y-%m-%d}**, £{s['initial']:,.0f} per run, "
        f"risk scores {', '.join(map(str, s['risks']))}. Prices: Yahoo Finance daily closes rebuilt as "
        f"total-return indices, downloaded {s['downloaded_at']}. Generated by "
        "`scripts/run_walkforward_backtest.py`; every table below is also a CSV in this folder.",
        "",
        "## Settings",
        f"- Check every **{s['check_every']} trading days**; targets rebuilt every **{s['reopt_months']} months**, "
        f"estimated on up to **{s['estimation_years']} years** of month-end GBP returns available at the time.",
        f"- Trading cost **{s['cost_bps']:g} bp** of traded value per fill, plus £{s['commission']:g} per fill.",
        "- Modes: **bands** = the app's triggers (holding band min(5pp, 25%×target) with a 1pp floor, portfolio "
        "drift ½Σ|drift| > 3%, growth share outside ±5pp); **calendar** = trade to target at every check. "
        "Both skip trades below max(£25, 0.25% of value).",
        "- Benchmarks: VWRL.L and GBP-hedged AGBP.L two-fund mixes, run through the same ledger, costs and bands.",
        "",
        "## How look-ahead is excluded",
        "- Each decision receives only price rows dated on or before the decision date; the current month's "
        "partial return is dropped.",
        "- ETF choice per block: first candidate with ≥ 36 complete month-ends and a price within 10 days *at "
        "that date* (the registry's 2026 `delisted` flag is ignored).",
        "- rf = trailing 12-month return of the cash proxy up to the decision date (not today's live rate).",
        "- Orders are sized on day *i*'s close and filled at day *i+1*'s close (sells in units, buys limited "
        "to cash raised).",
        "- Data cleaning is causal: dividends reinvested from their ex-date; 100× pence glitches checked "
        "against a trailing median; FX (USD lines) uses the last FX print dated before each price.",
        "- `tests/test_walkforward_backtest.py` changes, then deletes, every price after a cut date and checks "
        "that every decision, order, fill and portfolio value up to that date is unchanged.",
        "",
        "## Performance",
        _performance_table(summary),
        "",
        "![Equity curves](equity_by_risk.png)",
        "",
        "## Forecast accuracy (bands mode)",
        "Forecasts are the portfolio's expected arithmetic return and volatility at each re-optimisation; "
        "*realised* is the portfolio's annualised return from the day those trades executed to the next "
        "re-optimisation. Coverage counts periods with |realised − expected| ≤ σ/√τ.",
        "",
        _accuracy_table(tables["accuracy_summary"]),
        "",
        "![Forecast vs realised](forecast_vs_realised.png)",
        "",
        "### Per period",
        _periods_table(tables["accuracy_periods"]),
        "",
        "## Target weights at each re-optimisation",
        _targets_table(tables["decisions"]),
        "",
        "## Remaining biases (disclosed)",
        "- **Survivorship:** CORE_UNIVERSE and its fallback order were chosen in 2026 from funds that exist "
        "today; TERs are today's registry values. The point-in-time fallback reduces, but cannot remove, this.",
        "- **Design-time (hyperparameter) leakage:** the covariance settings (EWMA half-life 12, 50/50 "
        "EWMA/Ledoit-Wolf) and the ×1.15 volatility calibration were chosen in 2026 on 2016–2026 data that "
        "overlaps this window (docs/OPTIMIZATION_WALKTHROUGH.md, risks R2/R5). The ×1.15 only rescales the "
        "*reported* volatility, so it affects the 'calibrated' coverage figures, not the weights; the "
        "covariance settings do shape the weights. Policy constants (λ = 2.5, reference weights, bands) come "
        "from the literature, not from fitting.",
        "- **Execution:** fills at the closing price plus a flat 10 bp; no market impact, bid-ask variation "
        "or partial fills. Uninvested cash earns nothing.",
        "- **Data:** Yahoo closes and dividends are not audited against issuer data; dividends are reinvested "
        "gross (no withholding or UK tax) on the ex-date.",
        "- **Sample:** five annual periods per risk level — coverage and bias are indicative, not significant.",
        "",
        "## Files",
        "`summary.csv`, `accuracy_summary.csv`, `accuracy_periods.csv`, `asset_accuracy.csv`, `decisions.csv`, "
        "`events.csv` (every rebalance: reason, buys/sells £, cost £), `fills.csv` (every trade), "
        "`checks.csv` (every 10-day check with drift diagnostics), `equity.csv` (daily values).",
    ]
    with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
