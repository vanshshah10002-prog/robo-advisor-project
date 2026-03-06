"""
Backtest Runner — CLI Backtesting Tool
========================================
Run historical backtests from the command line.

Usage:
  python -m scripts.backtest_runner --risk 5 --amount 10000
  python -m scripts.backtest_runner --risk 7 --amount 50000 --years 10
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.engine.optimizer import build_optimised_portfolio
from backend.engine.backtester import backtest_portfolio
from backend.config import ASSET_CLASSES


def main():
    parser = argparse.ArgumentParser(description="UK Robo Advisor — Backtest Runner")
    parser.add_argument("--risk", type=float, default=5.0, help="Risk score (1–10)")
    parser.add_argument("--amount", type=float, default=10000.0, help="Investment amount (GBP)")
    parser.add_argument("--years", type=int, default=5, help="Backtest years")
    parser.add_argument("--rebalance", type=str, default="quarterly",
                        choices=["monthly", "quarterly", "annually", "none"],
                        help="Rebalancing frequency")
    args = parser.parse_args()

    print(f"Building portfolio: risk={args.risk}, amount=£{args.amount:,.2f}")
    print("=" * 60)

    # Build optimised portfolio
    result = build_optimised_portfolio(
        selected_asset_classes=ASSET_CLASSES,
        risk_score=args.risk,
        investment_amount=args.amount,
    )

    print(f"\nOptimal Allocation (Risk Level {args.risk}):")
    for alloc in result["allocations"]:
        print(f"  {alloc['asset_class']:30s} {alloc['ticker']:10s} {alloc['weight']:6.1%}  £{alloc['amount_gbp']:>10,.2f}")

    perf = result["performance"]
    print(f"\nExpected Performance:")
    print(f"  Annual Return: {perf['expected_return']:.2%}")
    print(f"  Volatility:    {perf['volatility']:.2%}")
    print(f"  Sharpe Ratio:  {perf['sharpe_ratio']:.2f}")

    # Run backtest
    print(f"\nRunning {args.years}-year backtest (rebalance: {args.rebalance})...")
    bt = backtest_portfolio(
        weights=result["ticker_weights"],
        initial_investment=args.amount,
        rebalance_frequency=args.rebalance,
    )

    m = bt["metrics"]
    print(f"\nBacktest Results:")
    print(f"  CAGR:          {m['cagr']:.2%}")
    print(f"  Volatility:    {m['volatility']:.2%}")
    print(f"  Sharpe Ratio:  {m['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:  {m['max_drawdown']:.2%}")
    print(f"  Final Value:   £{m['final_value']:,.2f}")

    if bt.get("benchmark_metrics"):
        bm = bt["benchmark_metrics"]
        print(f"\nBenchmark (VWRL.L):")
        print(f"  CAGR:          {bm['cagr']:.2%}")
        print(f"  Sharpe Ratio:  {bm['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:  {bm['max_drawdown']:.2%}")


if __name__ == "__main__":
    main()
