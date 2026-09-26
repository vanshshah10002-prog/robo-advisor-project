# Walk-Forward Backtest: Method and Findings (September 2026)

This is the backtest that `SESSION_HANDOFF_2026-09.md` §3 asked for. It replays the production
construction at risk 3, 5, 7 and 10. Each run starts with £100,000 and covers the five years
**2021-09-27 → 2026-09-25**. Portfolios are checked every 10 trading days and re-optimised every
12 months. Every decision uses only data available on its date.

- Generated tables and charts: [`reports/walkforward/REPORT.md`](../reports/walkforward/REPORT.md).
- Every rebalance, fill and check is logged as CSV in the same folder.
- To reproduce: `make walkforward`, or `python scripts/run_walkforward_backtest.py --refresh` to
  re-download prices.

- The app serves the same backtest at every risk level (1–10, bands mode, against a two-fund portfolio
  with the same growth share) from `backend/data/track_record.json`, via
  `GET /api/strategy/track-record?risk=N`. Rebuild it with `make track-record`.

## 1. Method

| Piece | Where | What it does |
|---|---|---|
| Price panel | `backend/eval/backtest_data.py` | Daily Yahoo closes rebuilt as total-return indices in GBP; every cleaning step is causal |
| Decisions and simulation | `backend/eval/walkforward_backtest.py` | Point-in-time universe, returns, rf, `estimate_mu_cov` → `build_policy_portfolio`; ledger simulation |
| Metrics | `backend/eval/backtest_metrics.py` | CAGR, Sharpe, drawdown, costs, turnover; forecast-vs-realised accuracy |
| CLI and report | `scripts/run_walkforward_backtest.py`, `scripts/walkforward_report.py` | Runs every risk level, mode and benchmark; writes CSVs, charts and REPORT.md |
| Tests | `tests/test_walkforward_backtest.py` (21 tests) | Point-in-time inputs, execution timing, accounting, look-ahead |

**Timeline.** A decision is made at day *i*'s close, using prices dated ≤ *i*. The trades are sized
at day *i*'s prices and filled at day *i+1*'s close. Sells are placed in units. Buys are limited to
the cash actually raised.

### How look-ahead is excluded

| Risk | Guard |
|---|---|
| Decision sees future rows | The decision function receives only `prices.loc[:t]`. |
| Incomplete current month | Month-end labels after *t* are dropped. |
| Live risk-free rate | rf is the cash proxy's trailing 12-month return up to *t*. `get_risk_free_rate()` is never called (a test enforces this). |
| Hindsight universe | The ETF for each block is the first candidate with ≥ 36 month-ends and a price within 10 days *at t*. The registry's 2026 `delisted` flag is ignored. |
| Same-bar execution | Orders are sized on day *i* and filled on day *i+1*. |
| Data cleaning | The pence-glitch fix uses a trailing median (`normalise_quote_units` uses the whole-series median, which is not causal). FX is the last print dated before each price date, forward-filled only and never back-filled. |

**Look-ahead test.** Every price after a cut date is shocked. Every decision, order, fill and
portfolio value on or before the cut stays bit-identical, while later decisions change. Deleting
every row after the cut gives the same result.

### Data defect found and fixed

Yahoo's adjusted close **omits dividends for pence-quoted LSE lines** (ISF.L, IEEM.L, IWDP.L). With
that data, ISF.L (FTSE 100) trailed VUKE.L (also FTSE 100) by about 4% a year. That would have
understated UK equity, the second-largest equity block, in both the forecasts and the realised
returns.

The backtest therefore rebuilds total return from raw closes and ex-date dividends:

TR_t = TR_{t-1} × (C_t + D_t) / C_{t-1}

After the fix, ISF.L and VUKE.L agree to within about 1% a year. GBP-quoted lines are unchanged,
which cross-checks the method.

**The live app still uses Yahoo's adjusted close** (`market_data.fetch_prices_yfinance`). Its UK
equity, EM (IEEM fallback) and property estimates carry the same understatement.

## 2. Results

### Performance (bands mode; costs 10 bp per fill)

| Risk | End value | CAGR | Vol | Sharpe | Max DD | Two-fund at same growth: CAGR / Max DD |
|---|---|---|---|---|---|---|
| 3 | £111,974 | 2.3% | 6.4% | −0.13 | −23.3% | 3.4% / −13.2% |
| 5 | £124,518 | 4.5% | 7.8% | 0.18 | −22.8% | 5.9% / −13.0% |
| 7 | £142,182 | 7.3% | 9.3% | 0.45 | −20.7% | 8.3% / −13.8% |
| 10 | £183,724 | 13.0% | 12.2% | 0.79 | −16.3% | 12.1% / −17.5% (100% VWRL) |

The two-fund benchmark is VWRL.L plus GBP-hedged AGBP.L, at the same growth share, run through
the same ledger, costs and bands.

### Costs and turnover (five years)

| Risk | Bands: rebalances / costs / turnover a year | Calendar: rebalances / costs / turnover a year |
|---|---|---|
| 3 | 8 / £233 / 16% | 87 / £282 / 21% |
| 5 | 11 / £289 / 21% | 103 / £356 / 28% |
| 7 | 10 / £293 / 21% | 105 / £369 / 28% |
| 10 | 5 / £294 / 18% | 95 / £400 / 26% |

Costs include the £100 initial purchase. Every rebalance and fill is in `events.csv` and
`fills.csv`.

### Forecast accuracy (bands mode; five annual periods per risk level)

| Risk | Forecast E[R] (time-weighted) | Realised CAGR | Bias (actual − expected) | Within ±1σ | Realised/predicted vol (×1.15) |
|---|---|---|---|---|---|
| 3 | 3.9% | 2.3% | −0.7% | 60% | 0.94 |
| 5 | 4.4% | 4.5% | +1.0% | 60% | 0.99 |
| 7 | 4.8% | 7.3% | +3.3% | 60% | 1.01 |
| 10 | 5.6% | 13.0% | +7.8% | 80% | 1.00 |

## 3. Findings

1. **Low-risk portfolios carried too much UK duration into 2022.**
   - In September 2021 the point-in-time rf was 0.2%, so cash was forecast at 0.15% and received
     0%. The defensive sleeve went to capped index-linked gilts (20%), IG credit (20%) and hedged
     aggregate bonds (30%).
   - INXG fell 34% in 2022. Risk 3 drew down 23%, against 13% for a 30/70 VWRL/AGBP portfolio.
   - The bands and caps worked as designed. The exposure comes from the policy. The block caps
     (linkers 20%, gilts 35%) limit weight but not duration.
2. **At risk 3–7 the policy portfolios trailed a plain two-fund portfolio at the same growth share**
   by 1.0–1.4 pp a year, almost all of it in 2022.
   - At risk 10 the policy portfolio beat 100% VWRL by 0.9 pp a year. The UK tilt and the 5% gold
     position both helped; gold returned +53% in 2025.
   - Five years with a single bond crash is one regime. Treat this as evidence, not proof.
3. **Bands work: drift rebalancing is cheap; re-optimisation is what costs money.**
   - In bands mode, drift-triggered trades cost £3–38 over five years. Annual re-optimisation cost
     £110–190, which is 80–98% of rebalancing costs.
   - Calendar mode traded 9–19 times as often, for 21–36% more total cost, with no CAGR benefit
     (within ±0.2 pp). This agrees with Vanguard and Daryanani.
4. **The VUSA.L → VUAG.L swap is pure cost.**
   - In October 2022, VUAG.L passed 36 months of history and became the preferred US line. Every
     portfolio sold VUSA and bought VUAG, which track the same S&P 500 index.
   - At risk 10 that was £132 of the £190 re-optimisation cost.
   - The rebalancer should treat a held line tracking the same index as the target (keep VUSA),
     or `resolve_ticker_map` should prefer the held line.
5. **The risk-free rate lags policy rates.**
   - The trailing 12-month return of the cash ETF was 0.3% in October 2022, when Bank Rate was
     2.25%. It was 4.1% in October 2023, against a Bank Rate of 5.25%.
   - This depressed cash's forecast return (and every equilibrium return) just as rates rose.
   - A forward-looking proxy would fix this, for example the latest monthly return annualised, or
     SONIA itself.
6. **Forecasts are conservative, and the vol calibration held on average.**
   - The equilibrium prior forecast 2–8% for equities. Equities returned roughly 14–25% a year in 2023–25,
     so bias rises with risk (+7.8% at risk 10).
   - Coverage of ±1σ was 60–80%, against a nominal 68%.
   - The ×1.15-calibrated volatility matched realised volatility (ratio 0.94–1.01) over the five
     years. However, in 2022 realised volatility of bond-heavy portfolios was 1.65× the prediction
     (risk 3: 10.9% realised, 6.6% predicted). The calibration is also partly in-sample (see §4).

## 4. Remaining biases (disclosed)

- **Survivorship.**
  - `CORE_UNIVERSE`, its fallback order and the TERs were chosen in 2026 from funds that exist
    today.
  - Point-in-time fallback reduces this but cannot remove it.
  - Registry flags (UCITS / UK-retail eligibility) are also today's values; these are a fund's
    legal form and rarely change, but they are not point-in-time.
- **Hyperparameter leakage.**
  - The EWMA half-life, the EWMA/Ledoit-Wolf blend and the ×1.15 vol calibration were chosen on
    2016–2026 data (`OPTIMIZATION_WALKTHROUGH.md` R2/R5).
  - The ×1.15 affects only reported volatility; the covariance settings affect the weights.
  - The policy constants (λ = 2.5, reference weights, bands) come from the literature.
- **Execution.**
  - Trades fill at the close plus a flat 10 bp: no spread variation, market impact or partial fills.
  - Uninvested cash earns nothing.
  - Dividends are reinvested gross on their ex-date.
- **Sample.** There are only five annual forecast periods per risk level.
