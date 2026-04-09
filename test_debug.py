"""Debug the covariance and BL prior scaling."""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd

from backend.engine.optimizer import select_asset_classes_for_risk
from backend.engine.asset_universe import get_ticker_map, get_expense_ratios
from backend.data.market_data import build_close_price_matrix
from backend.engine.covariance import compute_covariance
from backend.engine.expected_returns import _get_market_caps_from_registry, MVO_RISK_AVERSION

# Get tickers for balanced profile
classes = select_asset_classes_for_risk(5.0)
ticker_map = get_ticker_map(classes)
tickers = list(ticker_map.values())
print(f"Tickers: {tickers}")

# Fetch prices
prices = build_close_price_matrix(tickers)
valid = [c for c in prices.columns if prices[c].dropna().shape[0] >= 60]
prices = prices[valid]
print(f"Valid tickers: {len(valid)}")
print(f"Price matrix shape: {prices.shape}")

# Covariance
cov = compute_covariance(prices)
print(f"\nCovariance matrix diagonal (should be ~0.01-0.1 if annualised):")
for t in valid[:5]:
    print(f"  {t:10s}: {cov.loc[t, t]:.6f}  (vol = {np.sqrt(cov.loc[t, t]):.4f})")

# Market caps
caps = _get_market_caps_from_registry(valid)
total_aum = sum(caps.values())
w_mkt = np.array([caps[t] / total_aum for t in valid])
print(f"\nMarket weights (sum={w_mkt.sum():.4f}):")
for i, t in enumerate(valid[:5]):
    print(f"  {t:10s}: {w_mkt[i]:.4f}")

# BL prior π = λΣwₘ
pi = MVO_RISK_AVERSION * cov.loc[valid, valid].values @ w_mkt
print(f"\nπ = λΣwₘ (should be ~0.03-0.12 for equities):")
for i, t in enumerate(valid[:5]):
    print(f"  {t:10s}: {pi[i]:.6f}")
print(f"  Range: [{pi.min():.6f}, {pi.max():.6f}]")
print(f"  Mean: {pi.mean():.6f}")

# Try max_sharpe directly
print("\n--- Efficient Frontier Check ---")
from pypfopt import EfficientFrontier
from backend.engine.optimizer import _get_weight_bounds
ac_by_ticker = {v: k for k, v in ticker_map.items()}
bounds = _get_weight_bounds(valid, ac_by_ticker)
ef = EfficientFrontier(pd.Series(pi, index=valid), cov.loc[valid, valid], weight_bounds=bounds)
try:
    ef.max_sharpe(risk_free_rate=0.02)
    print("max_sharpe SUCCESS")
    print(ef.clean_weights())
except Exception as e:
    print(f"max_sharpe FAILED: {e}")

try:
    ef2 = EfficientFrontier(pd.Series(pi, index=valid), cov.loc[valid, valid], weight_bounds=bounds)
    ef2.min_volatility()
    print("min_volatility SUCCESS")
    print(ef2.clean_weights())
except Exception as e:
    print(f"min_volatility FAILED: {e}")

