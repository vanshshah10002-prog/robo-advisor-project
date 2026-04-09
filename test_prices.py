"""Check if close price columns are actually distinct."""
import sys; sys.path.insert(0, ".")
from backend.data.market_data import build_close_price_matrix

tickers = ['ISF.L','VMID.L','HMWO.L','VUAG.L','IGLT.L','SGLN.L','ERNS.L']
p = build_close_price_matrix(tickers)

print(f"Shape: {p.shape}")
print(f"\nLast row:")
print(p.iloc[-1])
print(f"\nFirst row:")
print(p.iloc[0])
print(f"\nAll columns identical? {(p.nunique() == 1).all()}")
print(f"\nUnique values per column:")
for col in p.columns:
    print(f"  {col:10s}: {p[col].nunique()} unique values, "
          f"range=[{p[col].min():.2f}, {p[col].max():.2f}]")

# Check daily returns are distinct
returns = p.pct_change().dropna()
print(f"\nReturn correlations (should NOT all be 1.0):")
print(returns.corr().round(3))
