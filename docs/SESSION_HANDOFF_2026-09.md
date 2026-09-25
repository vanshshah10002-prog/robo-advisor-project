# Session Handoff: Portfolio Remediation → Backtesting (September 2026)

Use this file to start the next session (local Claude Code) on the backtesting work.
Branch: `claude/brave-goldberg-igudnz`.

---

## 1. What this session did

1. **Reviewed the code.** It found 35 issues in portfolio construction, asset selection,
   diversification and rebalancing (IDs A1–E3).
2. **Wrote a plan backed by research.** See [`PORTFOLIO_REMEDIATION_PLAN.md`](PORTFOLIO_REMEDIATION_PLAN.md).
   Sources: Vanguard, Betterment, Wealthfront, Daryanani, Idzorek, He & Litterman, and
   Doeswijk et al. Each design choice in the plan is traced to one of them.
3. **Implemented all six steps of the plan**, one commit each:

| Commit | Step |
|---|---|
| `7ce3434` | Plan document |
| `695e8c1` | 1. Holdings ledger: units, cost basis, transactions, mark-to-market; no simulated returns |
| `37afced` | 2. Rebalancer: tolerance bands, portfolio drift, cash-flow first, netted trades; `/rebalance/{id}/execute` and `/portfolio/{id}/contribute` |
| `aa10dcc` | 3. Universe and data: 13 core building blocks with ETF fallback, registry corrections, pence/currency handling |
| `366d268` | 4. Return model: reference-portfolio equilibrium prior (λ = 2.5), arithmetic trailing means, fees deducted once |
| `24dad2f` | 5. Allocation policy: growth = 10% × risk score, cash ≤ ½ defensive, region bands, quadratic utility |
| `1fc3cab` | 6. Robustness: risk score capped at stored profile, GBP price route, docs |
| `0d8bbbf` | Refactor for backtesting: `estimate_mu_cov` and `apply_cash_forward_rate` shared with live code |

Tests: `pytest tests -q` gives **89 passed**. There were 29 at the start of the session.

## 2. How the system works now (short version)

```
risk score (capped at the stored profile)
  → universe: CORE_UNIVERSE (13 blocks), first ETF per block with ≥36 months of data
  → inputs: monthly GBP log returns → estimate_mu_cov()
        mu  = 25% trailing arithmetic mean (common window) + 75% equilibrium prior (λ = 2.5, less TER)
        cov = EWMA(halflife 12) + Ledoit-Wolf correlations, own-history volatilities
        cash mu = live rf − TER                          (apply_cash_forward_rate)
  → policy: growth share exactly 10% × risk; cash ≤ 50% of defensive; equity ≥ 75% of growth;
            region bands (UK 10–25% of equity); block caps (gilts 35, linkers 20, agg 35,
            IG credit 20, property 10, gold 5)
  → build_policy_portfolio(): max quadratic utility (λ = 2.5), positions < 0.5% re-solved to 0
  → ledger: buy units at GBP prices, 10 bp cost
  → rebalancer: trigger if any holding is outside min(5pp, 25%×target) (1pp floor),
                or ½Σ|drift| > 3%, or growth share is outside ±5pp;
                trades to target, netted, min trade max(£25, 0.25%)
```

Key files:
- `backend/engine/policy.py`
- `backend/engine/optimizer.py` (`build_policy_portfolio`, `build_optimised_portfolio`)
- `backend/engine/expected_returns.py` (`estimate_mu_cov`)
- `backend/engine/quant_models.py`
- `backend/engine/rebalancer.py`
- `backend/engine/ledger.py`
- `backend/engine/asset_universe.py` (`resolve_ticker_map`)
- `backend/config.py`

## 3. Next task: walk-forward backtest (not started)

### What the user asked for
- Backtest the new construction at **risk 3, 5, 7 and 10**.
- **£100,000** starting budget, **5-year** test window.
- **Rebalance every two weeks** (every 10 trading days).
- **Record the cost of buying and selling at every rebalance.**
- **No look-ahead bias.**
- **Accuracy:** compare actual returns against the expected returns the model produced.

### Why it wasn't done in the cloud session
The cloud environment's network policy blocks Yahoo Finance (`query1/query2.finance.yahoo.com`,
`guce.yahoo.com`, `fc.yahoo.com`), Stooq, Alpha Vantage and the issuer sites. Only PyPI and GitHub
can be reached. **Run it locally, where yfinance works.** The local price cache
`backend/data/price_cache.db` from the cloud session held **synthetic** prices. It is gitignored,
so a fresh local clone won't have it. If a local copy exists, delete it first so real prices are fetched.

### Suggested design
New module `backend/eval/walkforward_backtest.py` (pure, testable) and a CLI in `scripts/`.

**Data**
- Download daily closes for every `CORE_UNIVERSE` candidate plus `RISK_FREE_PROXY_TICKERS`
  (about 15 years: 10 years of estimation history before the 5-year test).
- Convert to GBP per ticker. Use the detected quote currency (`df.attrs["currency"]`) and FX series.
  **Forward-fill FX only. Never `bfill`** (`convert_to_gbp` bfills leading gaps, which is a small look-ahead;
  do the conversion in the backtest instead).

**Decision at date t**, using data dated ≤ t only:
1. **Universe:** the first candidate per block with ≥ 36 complete month-ends before t and a price within
   about 10 days of t. Pass this as the `usable` callable to `resolve_ticker_map`. **Ignore the
   registry's `delisted` flag.** It records today's knowledge, so using it is look-ahead.
2. **Monthly returns:** `resample("ME").last()`, then **drop any month-end label > t**
   (that drops the partial current month), then log returns.
3. **Risk-free rate:** `trailing_annualized_return(cash_series[:t])` from `backend/data/rates.py`,
   clamped to `RISK_FREE_CLAMP`. **Do not call `get_risk_free_rate()`.** It fetches today's live rate.
4. **Estimates:** `estimate_mu_cov(monthly, fees, rf, asset_class_of)`, then `apply_cash_forward_rate(...)`.
5. **Weights:** `build_policy_portfolio(risk, mu, cov, asset_class_of)`. Regime overlay stays off (the default).
6. **Record the forecast:** `get_portfolio_performance(...)` gives the expected return and volatility.

**Execution**
- Decide on day i's close and **trade at day i+1's close**.

**Simulation**
- Use `engine/ledger.Book`: `buy`/`sell` with `TRANSACTION_COST_BPS`, plus an optional fixed
  commission per trade (a CLI flag).
- **Every 10 trading days:** mark to market and run `check_drift` (bands, portfolio drift and the growth
  trigger via `growth_tolerance_range`). If triggered, run `plan_rebalance` and execute sells, then buys.
- Report two modes:
  - `bands`: the app's real behaviour.
  - `calendar`: always trade to target every two weeks (subject to the minimum trade size).
- **Re-optimise targets every 12 months** (configurable) using only data ≤ t. Log it as a rebalance event.
- **Log every event:** date, trigger reasons, turnover, buys/sells in £, cost in £, portfolio value.
  Write the log to CSV.

**Accuracy metrics**, per risk level and per re-optimisation period:
- Expected arithmetic return vs realised annualised return. Also compare the geometric equivalent
  (E_a − σ²/2) with the realised CAGR.
- Predicted volatility (model and ×1.15 calibrated) vs realised volatility.
- Bias (mean actual − expected), and coverage (share of periods where the actual return fell within
  the expected return ± 1σ).
- Five-year CAGR, maximum drawdown, Sharpe (against the point-in-time rf), total costs in £ and as
  bp a year, number of rebalances, and turnover.
- Benchmark: VWRL.L (or a 60/40 split of VWRL and AGBP), converted to GBP the same way.

**Look-ahead test** (must pass):
- Build a synthetic price panel and run the backtest.
- Then change every price after date D and run it again.
- All targets and trades decided before D−1 must be identical in both runs.

### Remaining known bias (disclose it, don't hide it)
Survivorship bias. `CORE_UNIVERSE` and its fallback order were chosen in 2026 from funds that exist
today, and TERs are today's. The fallback logic reduces this, but it can't remove it.

## 4. Other open items
- Check every registry entry that has a `verification_note` against the issuer factsheet (ERNS.L, CSH2.L,
  SGLP.L, ISPY.L, VEUR.L, INXG.L, and the new VERX.L, SSLN.L and WLDS.L).
- Deferred items from plan §2.7:
  - scheduler for daily drift checks;
  - ISA/GIA asset location;
  - lot-level tax-loss harvesting;
  - retiring `backend/engine/backtester.py`, which is superseded by the walk-forward backtest.
- `REBALANCE_CHECK_FREQUENCY` is still unused: nothing schedules the checks yet.
- The frontend still has an AssetSelection page. The backend ignores `selected_asset_classes`.

## 5. Running locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt pytest arch
pytest tests -q                                   # expect 89 passed
uvicorn backend.main:app --reload --port 8000     # API docs at /docs
```
