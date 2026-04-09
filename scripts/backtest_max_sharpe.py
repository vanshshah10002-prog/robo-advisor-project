"""
Walk-Forward Backtest: Max-Sharpe Portfolio @ 20% Vol Target
=============================================================
  Universe   : ETFs in uk_etf_registry with ≥3yr history
  Algorithm  : CAPM expected returns (VWRL.L proxy) + Ledoit-Wolf Σ + max_sharpe()
  Rebalancing: Quarterly (every 63 trading days), trailing 2yr window
  OOS period : 5 years (Apr 2021 → Apr 2026)
  Benchmark  : VWRL.L
"""

import sys, os, warnings, logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.basicConfig(level=logging.ERROR)
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from pypfopt import EfficientFrontier, expected_returns as er, risk_models

# ── Parameters ─────────────────────────────────────────────────────────────
RF          = 0.04
TARGET_VOL  = 0.20
TRAIN_YRS   = 2          # trailing window for each optimisation
OOS_YRS     = 5          # out-of-sample period
REBAL_DAYS  = 63         # ~quarterly rebalancing
INIT_CAP    = 100_000.0  # £100k initial capital
BENCHMARK   = "VWRL.L"
MAX_W       = 0.40
MIN_POS     = 0.005      # minimum weight to keep a position

# ── ETF universe ────────────────────────────────────────────────────────────
from backend.engine.asset_universe import get_all_etfs
ALL_ETFS   = get_all_etfs()
EXP_RATIOS = {e["ticker"]: e.get("expense_ratio", 0.002) for e in ALL_ETFS}
ALL_TKRS   = [e["ticker"] for e in ALL_ETFS]
AC_MAP     = {e["ticker"]: e.get("asset_class", "") for e in ALL_ETFS}

print("=" * 68)
print("  WALK-FORWARD BACKTEST  —  Max-Sharpe @ 20% Vol Target")
print(f"  Universe: {len(ALL_TKRS)} ETFs  |  OOS: {OOS_YRS}yr  |  "
      f"Rebal: ~quarterly  |  RF: {RF:.1%}")
print("=" * 68)

# ── Step 1: Download prices one ticker at a time (avoids MultiIndex issues) ──
print("\n[1] Downloading 7yr price history…")

close_dict = {}
fetch_tkrs = list(set(ALL_TKRS + [BENCHMARK]))

for t in fetch_tkrs:
    try:
        df = yf.download(t, period="7y", interval="1d",
                         auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            s = df["Close"].dropna()
            if len(s) >= 60:
                s.index = pd.to_datetime(s.index)
                if s.index.tz is not None:
                    s.index = s.index.tz_localize(None)
                close_dict[t] = s
    except Exception:
        pass

prices_raw = pd.DataFrame(close_dict).sort_index()
# Forward-fill up to 5 trading days to handle exchange calendar gaps
prices_raw = prices_raw.ffill(limit=5)

# Keep ETFs with ≥ 3yr of non-NaN data
MIN_ROWS = 756
etf_valid = [c for c in prices_raw.columns
             if c != BENCHMARK and prices_raw[c].dropna().shape[0] >= MIN_ROWS]
# Always keep benchmark
bm_ok = BENCHMARK in prices_raw.columns and prices_raw[BENCHMARK].dropna().shape[0] >= MIN_ROWS

prices = prices_raw[etf_valid + ([BENCHMARK] if bm_ok else [])].copy()
prices.index = pd.to_datetime(prices.index)

print(f"   → {len(etf_valid)} ETFs with ≥3yr history + "
      f"benchmark={'yes' if bm_ok else 'NO'}")
print(f"   → Date range: {prices.index[0].date()} → {prices.index[-1].date()}")

# ── Step 2: Timeline ────────────────────────────────────────────────────────
idx         = prices.index
oos_start   = idx[idx >= (idx[-1] - pd.DateOffset(years=OOS_YRS))][0]
oos_idx     = idx[idx >= oos_start]
rebal_dates = [oos_idx[i] for i in range(0, len(oos_idx), REBAL_DAYS)]

print(f"\n[2] Timeline")
print(f"   OOS start      : {oos_start.date()}")
print(f"   OOS end        : {idx[-1].date()}")
print(f"   Rebal events   : {len(rebal_dates)}")

# ── Step 3: Optimise function ────────────────────────────────────────────────
def optimise_window(price_win: pd.DataFrame):
    """CAPM mu + Ledoit-Wolf Σ → max_sharpe.  Returns (weights, pred_r, pred_vol)."""
    etf_c = [c for c in price_win.columns if c != BENCHMARK]
    # Use only ETFs with complete data in this window
    complete = [c for c in etf_c if price_win[c].isna().sum() == 0]
    if len(complete) < 4:
        return {}, 0.0, 0.0

    sub = price_win[complete].copy()
    bm_ser = price_win[BENCHMARK].dropna() if BENCHMARK in price_win.columns else None

    # CAPM expected returns
    if bm_ser is not None and len(bm_ser) > 100:
        mkt = pd.DataFrame({"market": bm_ser}).reindex(sub.index).ffill()
        mu  = er.capm_return(sub, market_prices=mkt, risk_free_rate=RF,
                             compounding=True, frequency=252)
    else:
        mu = er.capm_return(sub, risk_free_rate=RF, compounding=True, frequency=252)

    # Cost-adjust
    mu = mu - pd.Series({t: EXP_RATIOS.get(t, 0.002) for t in mu.index})

    # Ledoit-Wolf covariance on daily returns
    rets = sub.pct_change().dropna()
    if len(rets) < 60:
        return {}, 0.0, 0.0
    cov = risk_models.CovarianceShrinkage(rets, returns_data=True).ledoit_wolf()

    # Max-Sharpe: try progressively looser bounds
    for bnd in [(0.0, MAX_W), (0.0, 1.0)]:
        try:
            ef  = EfficientFrontier(mu, cov, weight_bounds=bnd)
            ef.max_sharpe(risk_free_rate=RF)
            raw = ef.clean_weights()
            w   = {t: v for t, v in raw.items() if v > MIN_POS}
            if w:
                w_arr    = np.array([w.get(t, 0.0) for t in mu.index])
                pred_r   = float(mu.values @ w_arr)
                pred_vol = float(np.sqrt(w_arr @ cov.values @ w_arr))
                return w, pred_r, pred_vol
        except Exception:
            continue

    # Fallback: inverse-vol weights
    vols = np.sqrt(np.diag(cov.values))
    inv  = 1.0 / np.where(vols > 1e-8, vols, 1e-8)
    w    = {t: float(inv[i] / inv.sum()) for i, t in enumerate(complete)}
    w    = {t: v for t, v in w.items() if v > MIN_POS}
    w_arr    = np.array([w.get(t, 0.0) for t in mu.index])
    pred_r   = float(mu.values @ w_arr)
    pred_vol = float(np.sqrt(w_arr @ cov.values @ w_arr))
    return w, pred_r, pred_vol

# ── Step 4: Walk-forward optimisation ───────────────────────────────────────
print("\n[3] Walk-forward optimisations (per rebalance date):")
print(f"   {'Date':<12} {'Assets':>7} {'Pred E[R]':>10} {'Pred σ':>8}")
print("   " + "-" * 42)

rebal_log = []
for rd in rebal_dates:
    win_end   = rd
    win_start = rd - pd.DateOffset(years=TRAIN_YRS)
    win = prices[(prices.index >= win_start) & (prices.index <= win_end)]
    if len(win) < 150:
        continue
    w, pr, pv = optimise_window(win)
    if w:
        rebal_log.append({"date": rd, "weights": w, "pred_r": pr, "pred_vol": pv})
        print(f"   {str(rd.date()):<12} {len(w):>7}  {pr:>9.2%}  {pv:>7.2%}")

if not rebal_log:
    print("FATAL: No successful optimisations.")
    sys.exit(1)

# ── Step 5: Simulate NAV between rebalance periods ───────────────────────────
print(f"\n[4] Simulating NAV for {OOS_YRS}-year OOS period…")

oos_prices = prices[prices.index >= oos_start].copy()
daily_rets = oos_prices.pct_change()

nav_records   = [{"date": oos_start, "portfolio": INIT_CAP, "benchmark": INIT_CAP}]
port_nav      = INIT_CAP
bm_nav        = INIT_CAP

for seg_i, log in enumerate(rebal_log):
    seg_start = log["date"]
    seg_end   = rebal_log[seg_i + 1]["date"] if seg_i + 1 < len(rebal_log) else oos_prices.index[-1]
    w         = log["weights"]
    active    = [t for t in w if t in daily_rets.columns]
    if not active:
        continue
    w_arr     = np.array([w[t] for t in active])
    w_arr    /= w_arr.sum()          # normalise to 1

    seg_days  = oos_prices.index[(oos_prices.index > seg_start) &
                                  (oos_prices.index <= seg_end)]
    for day in seg_days:
        # Portfolio
        dr   = daily_rets.loc[day, active].fillna(0).values
        port_nav *= (1 + float(w_arr @ dr))
        # Benchmark
        bm_r = daily_rets.loc[day, BENCHMARK] if BENCHMARK in daily_rets.columns else 0.0
        bm_nav *= (1 + float(bm_r if not pd.isna(bm_r) else 0.0))
        nav_records.append({"date": day, "portfolio": port_nav, "benchmark": bm_nav})

nav_df = (pd.DataFrame(nav_records)
            .drop_duplicates("date")
            .set_index("date")
            .sort_index())
print(f"   → {len(nav_df)} daily NAV observations")

# ── Step 6: Metrics ──────────────────────────────────────────────────────────
def calc_metrics(ret_s, bm_s=None, label=""):
    n     = len(ret_s)
    yrs   = n / 252
    tot   = (1 + ret_s).prod() - 1
    cagr  = (1 + tot) ** (1 / max(yrs, 0.01)) - 1
    vol   = ret_s.std() * np.sqrt(252)
    sh    = (cagr - RF) / vol if vol > 0 else 0
    ds    = ret_s[ret_s < RF / 252]
    dv    = ds.std() * np.sqrt(252) if len(ds) > 1 else vol
    so    = (cagr - RF) / dv if dv > 0 else 0
    cum   = (1 + ret_s).cumprod()
    mdd   = (cum / cum.cummax() - 1).min()
    beta  = 1.0; alpha = 0.0; te = 0.0
    if bm_s is not None:
        al  = pd.concat([ret_s, bm_s], axis=1).dropna()
        al.columns = ["p", "b"]
        bm_cagr = (1 + al["b"]).prod() ** (252 / max(len(al), 1)) - 1
        vb = al["b"].var()
        beta  = al["p"].cov(al["b"]) / vb if vb > 0 else 1.0
        alpha = cagr - RF - beta * (bm_cagr - RF)
        te    = (al["p"] - al["b"]).std() * np.sqrt(252)
    return dict(label=label, CAGR=cagr, Vol=vol, Sharpe=sh, Sortino=so,
                MaxDD=mdd, Beta=beta, Alpha=alpha, TE=te,
                Calmar=cagr / abs(mdd) if mdd != 0 else 0, Total=tot)

p_ret  = nav_df["portfolio"].pct_change().dropna()
bm_ret = nav_df["benchmark"].pct_change().dropna()
pm  = calc_metrics(p_ret, bm_ret, "Max-Sharpe (CAPM+MVO)")
bmm = calc_metrics(bm_ret, label=f"Benchmark ({BENCHMARK})")

# ── Step 7: Expected vs. Actual per rebalance ────────────────────────────────
print("\n[5] Expected vs. Actual return (per rebalance period):")
print(f"   {'Date':<12} {'Pred E[R]':>10} {'Pred σ':>8} "
      f"{'Act. ret':>9} {'Act. σ':>7} {'Gap':>8}")
print("   " + "-" * 60)

ev_rows = []
for log in rebal_log:
    rd = log["date"]
    fwd = rd + pd.DateOffset(days=365)
    seg = p_ret[(p_ret.index > rd) & (p_ret.index <= fwd)]
    if len(seg) >= 40:
        ar = (1 + seg).prod() ** (252 / len(seg)) - 1
        av = seg.std() * np.sqrt(252)
    else:
        ar = av = float("nan")
    gap = ar - log["pred_r"] if not pd.isna(ar) else float("nan")
    ev_rows.append(dict(date=rd, pred_r=log["pred_r"], pred_v=log["pred_vol"],
                        act_r=ar, act_v=av, gap=gap))
    print(f"   {str(rd.date()):<12} {log['pred_r']:>9.2%} {log['pred_vol']:>7.2%} "
          f"  {ar:>7.2%}   {av:>5.2%}  {gap:>+7.2%}")

evdf = pd.DataFrame(ev_rows).dropna(subset=["act_r"])
mp   = evdf["pred_r"].mean() if not evdf.empty else 0
ma   = evdf["act_r"].mean()  if not evdf.empty else 0
mg   = evdf["gap"].mean()    if not evdf.empty else 0
print(f"\n   {'MEAN':12} {mp:>9.2%} {'':>7}   {ma:>7.2%}           {mg:>+7.2%}")

# ── Step 8: Year-by-year ─────────────────────────────────────────────────────
print("\n[6] Year-by-year breakdown:")
print(f"   {'Year':<6} {'Port':>9} {'BM':>8} {'Excess':>8} {'Vol':>7} {'Sharpe':>8}")
print("   " + "-" * 50)
for yr in sorted(set(p_ret.index.year)):
    yp = p_ret[p_ret.index.year == yr]
    yb = bm_ret[bm_ret.index.year == yr]
    if len(yp) < 20:
        continue
    pr  = (1 + yp).prod() ** (252 / len(yp)) - 1
    br  = (1 + yb).prod() ** (252 / len(yb)) - 1 if len(yb) > 10 else float("nan")
    ex  = pr - br
    vol = yp.std() * np.sqrt(252)
    sh  = (pr - RF) / vol if vol > 0 else 0
    print(f"   {yr:<6} {pr:>8.2%} {br:>7.2%} {ex:>+7.2%} {vol:>6.2%} {sh:>7.3f}")

# ── Step 9: Most recent portfolio ─────────────────────────────────────────────
last = rebal_log[-1]
print(f"\n[7] Most recent portfolio weights ({last['date'].date()}):")
print(f"   {'Ticker':<18} {'Weight':>8}  Asset Class")
print("   " + "-" * 48)
for t, w in sorted(last["weights"].items(), key=lambda x: x[1], reverse=True):
    print(f"   {t:<18} {w:>7.2%}  {AC_MAP.get(t, '')}")
print(f"   {'TOTAL':<18} {sum(last['weights'].values()):>7.2%}")

# ── Step 10: Summary table ───────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  FULL PERFORMANCE SUMMARY  (5-Year OOS)")
print("=" * 68)
fmt_row = "  {:<26} {:>14}  {:>14}".format
print(fmt_row("Metric",             "Portfolio",        f"BM ({BENCHMARK})"))
print("  " + "-" * 58)
for k, pv, bv in [
    ("CAGR",              f"{pm['CAGR']:.2%}",    f"{bmm['CAGR']:.2%}"),
    ("Annualised Vol",    f"{pm['Vol']:.2%}",     f"{bmm['Vol']:.2%}"),
    ("Sharpe Ratio",      f"{pm['Sharpe']:.3f}",  f"{bmm['Sharpe']:.3f}"),
    ("Sortino Ratio",     f"{pm['Sortino']:.3f}", f"{bmm['Sortino']:.3f}"),
    ("Max Drawdown",      f"{pm['MaxDD']:.2%}",   f"{bmm['MaxDD']:.2%}"),
    ("Beta vs BM",        f"{pm['Beta']:.3f}",    "1.000"),
    ("Jensen's Alpha",    f"{pm['Alpha']:.2%}",   "0.00%"),
    ("Tracking Error",    f"{pm['TE']:.2%}",      "0.00%"),
    ("Calmar Ratio",      f"{pm['Calmar']:.3f}",  f"{bmm['Calmar']:.3f}"),
    ("Total Return",      f"{pm['Total']:.2%}",   f"{bmm['Total']:.2%}"),
    ("Final Value (£100k)",f"£{INIT_CAP*(1+pm['Total']):,.0f}", "—"),
]:
    print(fmt_row(k, pv, bv))

# ── Step 11: Algorithm Verdict ───────────────────────────────────────────────
print("\n" + "=" * 68)
print("  ALGORITHM VERDICT")
print("=" * 68)
checks = [
    (pm['Sharpe'] > 0.5,                    "Sharpe > 0.5 (good RA return)"),
    (abs(pm['Vol'] - TARGET_VOL) < 0.06,    f"Volatility within 6% of {TARGET_VOL:.0%} target"),
    (pm['Alpha'] > 0,                        "Positive Jensen's Alpha vs benchmark"),
    (abs(mg) < 0.05,                         "CAPM predictions within 5% of actual"),
    (pm['CAGR'] > bmm['CAGR'],              "Portfolio CAGR beats benchmark"),
    (pm['MaxDD'] > bmm['MaxDD'],             "Smaller max drawdown than benchmark"),
]
score = sum(passed for passed, _ in checks)
for passed, desc in checks:
    print(f"  {'✅' if passed else '❌'}  {desc}")
print(f"\n  Score: {score}/{len(checks)}")
verdicts = {6:"FULLY VALIDATED",5:"MOSTLY VALIDATED",4:"MOSTLY VALIDATED",
            3:"PARTIALLY VALIDATED",2:"PARTIALLY VALIDATED",1:"NEEDS REVISION",0:"FAILED"}
print(f"  → {verdicts.get(score,'?')}")
print("\n  Model Calibration:")
print(f"    Mean Predicted Return : {mp:.2%}")
print(f"    Mean Actual Return    : {ma:.2%}")
print(f"    Average Gap           : {mg:+.2%}")
print("=" * 68)
