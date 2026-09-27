"""
Build the track-record artefact the app serves
===============================================
Runs the walk-forward backtest (bands mode) at every risk level 1–10 and a
two-fund benchmark with the same growth share, over the last five years, and
writes backend/data/track_record.json for GET /api/strategy/track-record.

    python scripts/build_track_record.py              # uses the saved price snapshot
    python scripts/build_track_record.py --refresh    # re-download prices first

Same method, costs and no-look-ahead guarantees as
scripts/run_walkforward_backtest.py (docs/WALKFORWARD_BACKTEST.md).
"""

import argparse
import datetime
import json
import logging
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config import TRANSACTION_COST_BPS  # noqa: E402
from backend.eval.track_record import build_artefact, track_record_entry  # noqa: E402
from backend.eval.walkforward_backtest import (  # noqa: E402
    SimConfig, decide_policy_portfolio, memoised, run_backtest,
)
from scripts.run_walkforward_backtest import SNAPSHOT_DIR, benchmark_deciders, load_prices  # noqa: E402

logger = logging.getLogger("track_record")
OUT_PATH = os.path.join(ROOT, "backend", "data", "track_record.json")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--risks", type=int, nargs="+", default=list(range(1, 11)))
    p.add_argument("--initial", type=float, default=100_000.0)
    p.add_argument("--years", type=float, default=5.0)
    p.add_argument("--check-every", type=int, default=10)
    p.add_argument("--reopt-months", type=int, default=12)
    p.add_argument("--estimation-years", type=int, default=10)
    p.add_argument("--cost-bps", type=float, default=TRANSACTION_COST_BPS)
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--snapshot-dir", default=SNAPSHOT_DIR)
    p.add_argument("--out", default=OUT_PATH)
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for noisy in ("yfinance", "peewee", "urllib3", "cvxpy", "backend"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    args = parse_args()
    args.end = None
    gbp, downloaded_at = load_prices(args)
    end = gbp.index[-1]
    start = gbp.index[gbp.index.searchsorted(end - pd.DateOffset(months=round(args.years * 12)))]
    logger.info(f"Window {start:%Y-%m-%d} → {end:%Y-%m-%d}; risks {args.risks}")

    cfg = SimConfig(args.initial, args.check_every, args.reopt_months, "bands", args.cost_bps, 0.0)
    benchmarks = {risk: (label, decide) for label, (decide, risk) in benchmark_deciders(args.risks).items()
                  if risk is not None}
    entries = {}
    for risk in args.risks:
        decide = memoised(lambda h, t, r=risk: decide_policy_portfolio(h, t, r, args.estimation_years))
        logger.info(f"Risk {risk}: strategy")
        strategy = run_backtest(gbp, start, end, decide, cfg)
        label, bench_decide = benchmarks[risk]
        logger.info(f"Risk {risk}: {label}")
        benchmark = run_backtest(gbp, start, end, bench_decide, cfg)
        entries[risk] = track_record_entry(strategy, benchmark, label.split(" (")[0])

    artefact = build_artefact(
        entries, start.date().isoformat(), end.date().isoformat(), args.initial,
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), downloaded_at,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(artefact, f, indent=1)
    logger.info(f"Wrote {args.out} ({os.path.getsize(args.out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
