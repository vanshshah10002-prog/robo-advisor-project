"""
Walk-forward backtest of the production construction on real LSE prices
=======================================================================
Risk scores 3/5/7/10, £100,000, a 5-year test window, a check every 10
trading days, targets rebuilt every 12 months — all from data available at
each decision date (see backend/eval/walkforward_backtest.py).

    python scripts/run_walkforward_backtest.py              # uses the saved price snapshot
    python scripts/run_walkforward_backtest.py --refresh    # re-download from Yahoo first

Outputs (CSV logs, charts, REPORT.md) go to reports/walkforward/.
"""

import argparse
import json
import logging
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config import BENCHMARK_TICKER, CORE_UNIVERSE, RISK_FREE_PROXY_TICKERS, TRANSACTION_COST_BPS  # noqa: E402
from backend.eval.backtest_data import download_panel, gbp_prices, load_panel, save_panel, trading_calendar  # noqa: E402
from backend.eval.backtest_metrics import (  # noqa: E402
    accuracy_summary, asset_forecast_periods, forecast_periods, performance_summary,
)
from backend.eval.walkforward_backtest import (  # noqa: E402
    SimConfig, decide_policy_portfolio, fixed_mix_decider, memoised, run_backtest,
)

logger = logging.getLogger("walkforward")
BOND_BENCHMARK = "AGBP.L"
SNAPSHOT_DIR = os.path.join(ROOT, "backend", "data", "backtest_snapshot")
OUT_DIR = os.path.join(ROOT, "reports", "walkforward")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--risks", type=int, nargs="+", default=[3, 5, 7, 10])
    p.add_argument("--initial", type=float, default=100_000.0)
    p.add_argument("--years", type=float, default=5.0, help="test window length")
    p.add_argument("--end", type=str, default=None, help="last test date (default: last date in the data)")
    p.add_argument("--check-every", type=int, default=10, help="trading days between checks")
    p.add_argument("--reopt-months", type=int, default=12)
    p.add_argument("--estimation-years", type=int, default=10)
    p.add_argument("--cost-bps", type=float, default=TRANSACTION_COST_BPS)
    p.add_argument("--commission", type=float, default=0.0, help="fixed GBP fee per fill")
    p.add_argument("--modes", nargs="+", default=["bands", "calendar"], choices=["bands", "calendar"])
    p.add_argument("--refresh", action="store_true", help="re-download prices from Yahoo")
    p.add_argument("--snapshot-dir", default=SNAPSHOT_DIR)
    p.add_argument("--out", default=OUT_DIR)
    return p.parse_args()


def load_prices(args) -> tuple[pd.DataFrame, str]:
    panel = None if args.refresh else load_panel(args.snapshot_dir)
    if panel is None:
        tickers = [t for c in CORE_UNIVERSE.values() for t in c] + RISK_FREE_PROXY_TICKERS
        tickers = list(dict.fromkeys(tickers + [BENCHMARK_TICKER, BOND_BENCHMARK]))
        logger.info(f"Downloading {len(tickers)} tickers from Yahoo Finance")
        panel = download_panel(tickers)
        save_panel(panel, args.snapshot_dir)
    gbp = gbp_prices(panel)
    return gbp.loc[trading_calendar(gbp)], panel.downloaded_at


def benchmark_deciders(risks: list[int]) -> dict[str, tuple]:
    """label -> (decider, matched risk or None). Two-fund mixes of VWRL (equity) and AGBP (hedged bonds)."""
    ac = {BENCHMARK_TICKER: "global_equity", BOND_BENCHMARK: "global_bonds"}

    def mix(g: float):
        w = {BENCHMARK_TICKER: round(g, 4), BOND_BENCHMARK: round(1 - g, 4)}
        return fixed_mix_decider({k: v for k, v in w.items() if v > 0}, ac)

    out = {"VWRL 100%": (mix(1.0), None), "VWRL/AGBP 60/40": (mix(0.6), None)}
    for r in risks:
        g = min(1.0, 0.1 * r)
        out[f"Two-fund {g:.0%}/{1 - g:.0%} (risk {r})"] = (mix(g), r)
    return out


def run_all(gbp: pd.DataFrame, start, end, args) -> dict:
    runs: dict[str, dict] = {}
    for risk in args.risks:
        decide = memoised(lambda h, t, r=risk: decide_policy_portfolio(h, t, r, args.estimation_years))
        for mode in args.modes:
            cfg = SimConfig(args.initial, args.check_every, args.reopt_months, mode, args.cost_bps, args.commission)
            logger.info(f"Risk {risk}, {mode}")
            runs[f"Risk {risk} ({mode})"] = {"kind": "strategy", "risk": risk, "mode": mode,
                                             "result": run_backtest(gbp, start, end, decide, cfg)}
    for label, (decide, risk) in benchmark_deciders(args.risks).items():
        cfg = SimConfig(args.initial, args.check_every, args.reopt_months, "bands", args.cost_bps, args.commission)
        runs[label] = {"kind": "benchmark", "risk": risk, "mode": "bands",
                       "result": run_backtest(gbp, start, end, decide, cfg)}
    return runs


def _tagged(frames: list[tuple[dict, pd.DataFrame]]) -> pd.DataFrame:
    parts = [df.assign(run=tag["run"], risk=tag["risk"], mode=tag["mode"]) for tag, df in frames if not df.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def decision_rows(risk: int, decisions) -> list[dict]:
    rows = []
    for d in decisions:
        for tk, w in sorted(d.weights.items(), key=lambda kv: -kv[1]):
            rows.append({"risk": risk, "decided": d.date.date(), "ticker": tk,
                         "asset_class": d.asset_class_of.get(tk, ""), "weight": w, "mu": d.mu.get(tk),
                         "portfolio_expected_return": d.expected_return, "vol_model": d.volatility_model,
                         "vol_calibrated": d.volatility, "risk_free": d.risk_free,
                         "risk_free_source": d.risk_free_source, "common_months": d.common_months,
                         "fallbacks": json.dumps(d.fallbacks)})
    return rows


def collect(runs: dict, gbp: pd.DataFrame) -> dict[str, pd.DataFrame]:
    summary, acc_sum, periods, assets, decisions = [], [], [], [], []
    events, fills, checks = [], [], []
    for label, run in runs.items():
        res, tag = run["result"], {"run": label, "risk": run["risk"], "mode": run["mode"]}
        summary.append({"run": label, "kind": run["kind"], "risk": run["risk"], "mode": run["mode"],
                        **performance_summary(res)})
        events.append((tag, res.events))
        fills.append((tag, res.fills))
        checks.append((tag, res.checks))
        if run["kind"] != "strategy":
            continue
        p = forecast_periods(res)
        periods.append((tag, p))
        acc_sum.append({"run": label, "risk": run["risk"], "mode": run["mode"], **accuracy_summary(p, res)})
        if run["mode"] == "bands":
            assets.append((tag, asset_forecast_periods(res, gbp)))
            decisions.extend(decision_rows(run["risk"], res.decisions))
    equity = pd.DataFrame({label: run["result"].equity["value"] for label, run in runs.items()})
    return {
        "summary": pd.DataFrame(summary), "accuracy_summary": pd.DataFrame(acc_sum),
        "accuracy_periods": _tagged(periods), "asset_accuracy": _tagged(assets),
        "decisions": pd.DataFrame(decisions), "events": _tagged(events), "fills": _tagged(fills),
        "checks": _tagged(checks), "equity": equity,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for noisy in ("yfinance", "peewee", "urllib3", "cvxpy", "backend"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    args = parse_args()
    gbp, downloaded_at = load_prices(args)
    end = pd.Timestamp(args.end) if args.end else gbp.index[-1]
    end = gbp.index[gbp.index.searchsorted(end, side="right") - 1]
    start = gbp.index[gbp.index.searchsorted(end - pd.DateOffset(months=round(args.years * 12)))]
    logger.info(f"Test window {start:%Y-%m-%d} → {end:%Y-%m-%d}; prices downloaded {downloaded_at}")

    runs = run_all(gbp, start, end, args)
    tables = collect(runs, gbp)
    os.makedirs(args.out, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(os.path.join(args.out, f"{name}.csv"), index=(name == "equity"))

    from scripts.walkforward_report import write_charts, write_report   # matplotlib only when reporting
    write_charts(tables, args.risks, args.out)
    write_report(tables, vars(args) | {"start": start, "end": end, "downloaded_at": downloaded_at}, args.out)
    logger.info(f"Wrote {len(tables)} tables, charts and REPORT.md to {args.out}")


if __name__ == "__main__":
    main()
