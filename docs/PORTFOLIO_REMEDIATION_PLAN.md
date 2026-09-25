# Portfolio Construction & Rebalancing — Remediation Plan

Status: plan of record, September 2026.
Scope: everything from `POST /api/portfolio` to rebalancing. It fixes the 35 findings in
the September 2026 code review (IDs A1–E3 below refer to that review).

---

## 1. Principles taken from industry practice

The design copies what established managers do, so every choice below has a reference.

| # | Principle | Source | What it means for this code |
|---|---|---|---|
| P1 | **Risk is expressed as the share in growth assets.** Each risk level maps to a fixed stock/bond mix. Clients and advisers understand this, and it stays stable over time. | Betterment offers 101 allocations from 0% to 100% stocks. Vanguard LifeStrategy uses 20/40/60/80/100. | Replace the data-driven volatility ladder (C2, C3) with a fixed growth-share policy per risk score. |
| P2 | **Start from the market portfolio. Use views, not history.** Reverse-optimise implied returns from market-cap weights (π = λΣw) and apply the same λ in the optimiser. The unconstrained optimum then *is* the market portfolio, which keeps the optimiser stable. | He & Litterman (1999). Idzorek, *A Step-by-Step Guide to Black-Litterman*. Wealthfront (CAPM prior on the global market portfolio). Doeswijk, Lam & Swinkels (2014), *The Global Multi-Asset Market Portfolio*. | Replace fund-AUM "market caps" with a reference market portfolio of asset classes (B1). Fix λ at 2.5 instead of fitting it to trailing data. |
| P3 | **Few asset classes, low correlation between them, no duplicates, sensible caps.** | Wealthfront: asset classes chosen for low correlation, "35% as the maximum allocation for most asset classes". | Curate about 13 building blocks. Drop the overlapping factor, ESG, thematic and duplicate-gilt classes from the core (A2, A3). |
| P4 | **Pick ETFs on cost, tracking and liquidity, with a fallback.** | Wealthfront ETF selection: expense ratio, tracking error, liquidity. | Score candidate ETFs and fall back to the next one when data is missing (A4). |
| P5 | **Home bias for UK investors should be moderate, and bonds should be hedged to GBP.** | Vanguard LifeStrategy (2026): 20% of equity in UK stocks. Global bonds are GBP-hedged so bonds "act as a stabiliser". | UK equity at 20% of equity (range 10–25%). Global bonds GBP-hedged only. Unhedged high yield and US Treasuries come out of the defensive sleeve (A6). |
| P6 | **Rebalance on bands, not a calendar. Check often, trade rarely.** | Vanguard (Jaconetti, Kinniry, Zilbering): about a 5% threshold, and frequency matters little. Daryanani (2008): relative bands of about 20–25%, checked frequently. | Band per sleeve = min(5 pp absolute, 25% relative), with a 1 pp floor (D6). |
| P7 | **Use cash flows to rebalance first, then sell only if still out of tolerance, with tax in mind.** Portfolio drift = ½·Σ\|drift\|, threshold 3%. | Betterment: reactive (cash-flow) then proactive rebalancing, default 3% drift threshold, tax-aware lot selection. | Wire up inflow allocation with fill-deficits-first logic (D8). Proactive trades net to zero and report estimated costs and realised gains (D7). |
| P8 | **Estimation hygiene.** Mean-variance needs **arithmetic** expected returns (μₐ ≈ μ_g + σ²/2). Errors in means dominate errors in variances, so trailing means should get little weight. | Kitces / Bogleheads on variance drain. Chopra & Ziemba (1993). | Correct the annualisation (B2). Cut the trailing-mean weight from 0.50 to 0.25. Deduct fees once (B3). Use a common estimation window (B4). |
| P9 | **Strategic, not tactical.** Mainstream robo-advisers hold the strategic allocation through volatility. | Betterment, Wealthfront and Vanguard all use strategic allocation. Vanguard found no benefit from more frequent rebalancing. | Crisis de-risking is off by default. If turned on, it is applied *inside* the optimiser as a tighter growth band, so no constraint can break (A8, C5, B7). |
| P10 | **Never show numbers that weren't measured.** | Basic reporting integrity (FCA COBS 4: fair, clear, not misleading). | Keep a real holdings ledger. Returns are marked to market or flagged stale, never made up (D1, D2). |

---

## 2. Target design

### 2.1 Holdings ledger (fixes D1, D2, E1)
- `Holding.quantity` stores **units**, `average_cost` is GBP per unit, `current_price` is the latest GBP price.
- Creating a portfolio prices each ETF from the cache-backed GBP price service, buys whole
  fractional units and writes a `Transaction("buy")` row per line.
- Refresh marks to market: value = units × latest GBP price, current_weight = value / total, and
  `total_return_pct` = (value − net contributions) / net contributions. If a price is missing,
  the holding keeps its last price and the response lists it under `stale_tickers`. Nothing is
  simulated.
- `alpha` is replaced by what it actually was: expected excess return over the **live**
  risk-free rate. The field name stays for frontend compatibility.

### 2.2 Rebalancer (fixes D3–D8)
- Current weights come from the ledger, keyed by the **ticker held** (D5). A 0% weight counts as 0% (D3).
- Trades are sized from **current market value** (D4).
- Triggers, where any one is enough:
  1. a sleeve outside its band `min(5pp, 25% × target)` (with a 1 pp floor),
  2. portfolio drift ½Σ|drift| > 3%,
  3. the growth share outside the policy band.
- Execution order:
  1. **Reactive:** new cash fills deficits first, and any remainder goes pro rata to target (D8).
  2. **Proactive:** trade to target. Trades below `max(£25, 0.25% of value)` are skipped, the
     remaining trades are re-netted so buys = sells, and the response includes estimated trading cost
     (`TRANSACTION_COST_BPS`) plus, for a general investment account, estimated realised gains at average cost (D7).
- If a price is missing, the rebalance stops with an explicit error instead of quietly skipping a trade (D7).
- New endpoints `POST /portfolio/{id}/contribute` and `POST /rebalance/{id}/execute` update the
  paper ledger and write `Transaction` rows.

### 2.3 Universe and data (fixes A3–A7, E3)
Core building blocks (`CORE_UNIVERSE` in config):

| Sleeve | Block | Candidates (in order) |
|---|---|---|
| Growth | UK equity | ISF.L, VUKE.L |
| Growth | US equity | VUAG.L, VUSA.L, CSP1.L |
| Growth | Europe ex-UK equity | VERX.L |
| Growth | Japan equity | VJPN.L, CJPE.L |
| Growth | Asia-Pacific ex-Japan equity | VAPX.L, CPXJ.L |
| Growth | Emerging-market equity | VFEM.L, IEEM.L, VFEG.L |
| Growth | Global property | IWDP.L |
| Growth | Gold | SGLN.L, PHAU.L |
| Defensive | UK gilts | IGLT.L, VGOV.L |
| Defensive | Index-linked gilts | INXG.L |
| Defensive | Global aggregate bonds (GBP-hedged) | AGBP.L, VAGP.L |
| Defensive | GBP investment-grade corporate bonds | VUKC.L, SLXX.L |
| Defensive | Cash (ultrashort / SONIA) | CSH2.L, ERNS.L |

- The factor, ESG, thematic, dividend, high-yield, small-cap, silver, broad-commodity,
  infrastructure and India classes stay in the registry but become **satellites**, off by default.
- **ETF selection** picks the first investable candidate that has usable data. Registry TER is only a tie-break (A4).
- **Registry corrections** (A5):
  - SGLP.L re-labelled to Invesco Physical Gold (`commodities_gold`).
  - ISPY.L re-labelled to L&G Cyber Security (`thematic`) and removed from small cap.
  - VEUR.L re-labelled to Europe incl. UK, and VERX.L added for ex-UK.
  - ERNS.L and CSH2.L names corrected.
  - These come from knowledge of the LSE listings and should be checked against issuer factsheets.
- **Quote currency** (A5): the Yahoo `currency` of each listing (GBp/GBP/USD/EUR) is detected when
  prices are fetched and cached, and it overrides the registry. GBp is scaled to GBP. FX conversion
  is only applied to listings that genuinely quote in a foreign currency.
- `ETFInfo` is aligned with the registry schema (E3).

### 2.4 Return model (fixes B1–B5)
- **Reference market portfolio** (`REFERENCE_MARKET_WEIGHTS`) is a global multi-asset proxy
  (Doeswijk et al.), used only for the prior:
  - equity 55%, split by FTSE All-World regional cap weights with UK at 20%;
  - bonds 40% (gilts 10, linkers 5, hedged global agg 18, IG credit 7);
  - property 3%;
  - gold 2%.
- π = λ·Σ·w_ref with **λ = 2.5** (He–Litterman). E[R]_BL = rf + π − TER.
- The trailing mean is computed **arithmetically** and over a **common window**. Its blend weight is
  `EXPECTED_RETURN_TRAILING_WEIGHT = 0.25`, and it is already net of fees, so there is no second fee deduction (B2, B3, B4).
- The cash sleeve's E[R] is the live rf minus TER (unchanged).
- The CMA clamp of −5%…12% stays.

### 2.5 Allocation policy and optimiser (fixes A1, A2, C2–C4, A8, C5)
- **Growth share by risk score:** G(r) = 10% × r, so risk 1 is 10% growth and risk 10 is 100%.
  The optimiser can move ±5 pp around it (clipped to [0, 1]).
- **Defensive sleeve** = 1 − G, split by the optimiser. Cash ≤ 50% of the defensive sleeve, so
  bonds do the de-risking (A1). The per-block caps follow Wealthfront's 35% guidance: gilts ≤ 35%,
  linkers ≤ 20%, hedged global agg ≤ 35%, IG credit ≤ 20%.
- **Equity regions** are expressed as a share of total equity, with look-through at the regional block level (A2):
  - each region lies within ±max(5 pp, 30% of reference) of its reference weight;
  - UK lies in [10%, 25%].
  - Property ≤ 10% and gold ≤ 5% of the portfolio.
- **Objective:** `max_quadratic_utility(λ = 2.5)`. This uses the same λ as the prior, so an unconstrained
  optimisation with no views returns the reference mix (P2). Constraints then shape it to the risk policy.
  The L2 penalty is removed (C4).
- **Crisis overlay** (off by default, P9): when it is on, it narrows the growth band by 5 pp and re-solves,
  so the result is feasible by construction (A8, C5).
- Tiny weights (< 0.5%) are removed by re-solving with those assets fixed at zero, not by renormalising (C4).

### 2.6 Robustness (fixes C1, C6, C7, E2, B6)
- The tangency (max-Sharpe) check compares rf with the **highest return the constraints allow**, not just the
  best single asset. Optimiser failures return a clear 422 error instead of an empty 200 (C1).
- `/portfolio` uses the stored risk profile's score. The request may only lower it (C7).
- Allocation names come from the actual ticker (E2).
- Dual momentum uses the live rf (C5).
- The regime detector, when enabled, uses the equity sleeves only (B7).

### 2.7 Deferred (documented, not in this change)
- Backtester alignment (D10): walk-forward weights, band rebalancing, GBP prices.
- Scheduler (D9): daily drift checks.
- ISA/GIA asset location.
- Lot-level tax-loss harvesting.

---

## 3. Order of work and why

| Step | Work | Why this order |
|---|---|---|
| 1 | Holdings ledger | Everything after purchase (drift, returns, rebalancing) needs real units and prices. Until then no fix in section D can be checked. |
| 2 | Rebalancer | Depends only on the ledger. It fixes the most serious runtime defect (rebalancing never fires). |
| 3 | Universe and data | The allocation policy refers to specific building blocks, and bad data (mislabelled funds, fake FX) corrupts every estimate built on it. |
| 4 | Return model | The optimiser is only as good as its inputs. The prior has to exist before the policy optimiser that uses the same λ. |
| 5 | Allocation policy and optimiser | Uses steps 3 and 4. It changes client-facing weights, so it comes after the inputs are right. |
| 6 | Robustness and API | Cleans up the edges once the core is correct. |

This order differs slightly from the review's first suggestion (policy before universe). The universe
and return model come first so the policy optimiser is built on correct inputs.

## 4. Validation (each step ships with tests)
- **Ledger:**
  - units × price equals the invested amount at creation;
  - marking to market changes value exactly as prices change;
  - a missing price is flagged, never made up.
- **Rebalancer:**
  - band maths (absolute, relative, floor), and the ½Σ|drift| definition;
  - trades net to zero within £0.01, and none is below the minimum size;
  - held tickers are used even when the registry's primary ETF changes;
  - inflow fills deficits first.
- **Universe:**
  - no duplicate indices in the core;
  - falls back when the first candidate has no data;
  - GBp scaling and currency override.
- **Returns:**
  - arithmetic ≥ geometric by about σ²/2;
  - the prior reproduces the reference mix under unconstrained utility maximisation;
  - fees are deducted once.
- **Policy:**
  - for every risk score from 1 to 10: weights sum to 1, all constraints hold, growth share lies in its band;
  - volatility rises monotonically with risk;
  - bonds exceed cash at every risk level below 10.
- **End to end:** the full API flow on synthetic prices, with a table of risk score → growth, bonds, cash,
  positions, E[R] and volatility.

## 5. Sources
- Vanguard, *Best practices for portfolio rebalancing* (Jaconetti, Kinniry, Zilbering).
- Vanguard UK, *LifeStrategy is evolving* (2026): 20% UK home bias, hedged global bonds.
- Betterment: portfolio construction methodology; rebalancing methods (3% drift threshold, cash-flow rebalancing).
- Wealthfront: *Investment Methodology White Paper* (CAPM/BL, per-class caps of 35%, ETF selection).
- Daryanani, G. (2008), *Opportunistic Rebalancing*, Journal of Financial Planning.
- Idzorek, T., *A Step-by-Step Guide to the Black-Litterman Model*.
- He, G. & Litterman, R. (1999), *The Intuition Behind Black-Litterman Model Portfolios*.
- Doeswijk, Lam & Swinkels (2014), *The Global Multi-Asset Market Portfolio*, FAJ.
- Kitces, *Volatility Drag: arithmetic vs geometric returns*.
