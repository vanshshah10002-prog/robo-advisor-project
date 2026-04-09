"""Quick test of the optimizer pipeline."""
import sys, time
sys.path.insert(0, ".")

from backend.engine.optimizer import build_optimised_portfolio

print("=" * 60)
print("Testing build_optimised_portfolio (risk_score=5)")
print("=" * 60)
start = time.time()
try:
    result = build_optimised_portfolio(
        risk_score=5.0,
        investment_amount=10000.0,
    )
    elapsed = time.time() - start
    print(f"Took {elapsed:.1f}s")
    print(f"Alpha (risk blend): {result.get('risk_allocation_alpha', 'N/A')}")
    print(f"Asset classes used: {len(result.get('asset_classes_used', []))}")

    perf = result["performance"]
    print(f"Expected return: {perf['expected_return']:.4f}")
    print(f"Volatility: {perf['volatility']:.4f}")
    print(f"Sharpe ratio: {perf['sharpe_ratio']:.4f}")

    weights = [a["weight"] for a in result["allocations"]]
    n = len(weights)
    equal_w = 1.0 / n if n > 0 else 0
    is_equal = all(abs(w - equal_w) < 0.01 for w in weights)
    print(f"\nAllocations ({n} positions):")
    for a in result["allocations"][:15]:
        print(f"  {a['asset_class']:30s}  {a['ticker']:10s}  {a['weight']*100:5.1f}%")
    print(f"\nWeights all equal? {is_equal} (SHOULD BE False)")

    print(f"\nTangent portfolio (max Sharpe):")
    for ac, w in result.get("tangent_portfolio", {}).items():
        if w > 0.01:
            print(f"  {ac:30s}  {w*100:5.1f}%")

except Exception as e:
    elapsed = time.time() - start
    print(f"Error after {elapsed:.1f}s: {e}")
    import traceback
    traceback.print_exc()
