# 🤖 UK Robo Advisor

A sophisticated, UK-focused robo-advisory platform inspired by Wealthfront's methodology. Built for UK retail investors using UK-listed ETFs, bonds, and funds on the London Stock Exchange.

> ⚠️ **Disclaimer**: This application is for educational/personal use only. It is not registered with the FCA, does not constitute financial advice, and should not be used to make real investment decisions without consulting a qualified financial advisor.

---

## ✨ Features

- **Risk Profiling** — 10-question subjective quiz + objective financial capacity scoring with conservative bias
- **Portfolio Optimisation** — Policy-constrained mean-variance: the risk score sets the growth share (10% per point), the optimiser picks the mix using a Black-Litterman equilibrium prior on a reference market portfolio
- **13 Core Building Blocks** — Regional equity, property, gold, gilts, index-linked gilts, GBP-hedged global bonds, IG credit and SONIA cash, with ordered ETF fallbacks; 100+ further UK-listed ETFs as optional satellites
- **Efficient Frontier** — Interactive visualization of optimal portfolios
- **Monte Carlo Projections** — 30-year probabilistic forecasting with percentile fan charts
- **Holdings Ledger** — Units, cost basis and transactions; values marked to market at GBP prices
- **Band-Based Rebalancing** — Per-holding tolerance bands, portfolio drift and growth-share triggers; deposits invested where underweight; netted trade plans with cost and CGT estimates
- **Historical Backtesting** — Benchmark comparison, CAGR, Sharpe, max drawdown
- **Regime Detection** — Optional (off by default) volatility/drawdown overlay that lowers the growth target inside the optimiser
- **Dual Momentum Overlay** — Optional tactical allocation (Antonacci, 2014)
- **ISA Optimisation** — Tax-drag-aware asset placement
- **Zero Recurring Costs** — Runs entirely locally on free APIs

---

## 🏗️ Architecture

```
uk-robo-advisor/
├── backend/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # ALL algorithm parameters (developer control panel)
│   ├── engine/                    # Core algorithms
│   │   ├── risk_profiler.py       # Subjective + objective risk scoring
│   │   ├── optimizer.py           # MVO + efficient frontier + dual momentum
│   │   ├── expected_returns.py    # Equilibrium prior + trailing blend, cost adjustment
│   │   ├── policy.py              # Risk score → growth share, sleeve and region limits
│   │   ├── ledger.py              # Units, cost basis, mark-to-market
│   │   ├── covariance.py          # Ledoit-Wolf shrinkage + regime detection
│   │   ├── monte_carlo.py         # GBM simulation for projections
│   │   ├── rebalancer.py          # Tolerance bands, cash-flow and netted trade plans
│   │   ├── backtester.py          # Historical simulation engine
│   │   └── asset_universe.py      # ETF registry manager
│   ├── data/
│   │   ├── market_data.py         # yfinance + Alpha Vantage fallback
│   │   ├── cache.py               # SQLite price cache
│   │   └── uk_etf_registry.json   # 20+ UK-listed ETF metadata
│   ├── api/routes/                # FastAPI endpoint handlers
│   └── db/                        # SQLAlchemy ORM + SQLite
├── frontend/                      # React + Vite + TypeScript
│   └── src/
│       ├── pages/                 # Onboarding, Portfolio Builder, Dashboard
│       ├── components/            # Charts, sliders, data display
│       └── design-system/         # Tokens, base components
├── scripts/                       # CLI tools (seed, backtest, update)
└── Makefile                       # install, dev, seed, backtest
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm 9+

### 1. Clone & Configure
```bash
git clone (https://github.com/vanshshah10002-prog/robo-advisor-project)
cd uk-robo-advisor
cp .env.example .env
# Edit .env with your API keys (see API Keys section below)
```

### 2. Install Dependencies
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 3. Seed Price Data
```bash
# From project root
python scripts/seed_etf_registry.py
```

### 4. Run
```bash
# Terminal 1 — Backend (from project root)
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- **Backend API**: http://127.0.0.1:8000/docs (Swagger UI)
- **Frontend**: http://127.0.0.1:5173

---

## 🔑 API Keys (Free Tier)

| Service | Purpose | Free Tier | Sign Up |
|---------|---------|-----------|---------|
| **yfinance** | UK ETF prices | Free, no key | `pip install yfinance` |
| **Alpha Vantage** | Market data fallback | 25 req/day | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| **Open Exchange Rates** | FX rates | 1000 req/month | [openexchangerates.org](https://openexchangerates.org/signup/free) |
| **Financial Modeling Prep** | ETF fundamentals | 250 req/day | [financialmodelingprep.com](https://site.financialmodelingprep.com/developer/docs) |
| **NewsAPI** | Financial news | 100 req/day | [newsapi.org](https://newsapi.org/register) |

> **Note**: Only yfinance is required. All other APIs are optional enhancements.

---

## ⚙️ Algorithm Configuration

**Every** algorithm parameter is exposed in [`backend/config.py`](backend/config.py). Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MVO_RISK_FREE_RATE` | 0.040 | Fallback only; the live rate comes from a SONIA tracker (CSH2.L) |
| `CORE_UNIVERSE` | 13 blocks | Building blocks and their ETF candidates, in order of preference |
| `POLICY_GROWTH_PER_RISK_POINT` | 0.10 | Growth share per risk point (risk 6 → 60%) |
| `POLICY_CASH_MAX_SHARE_OF_DEFENSIVE` | 0.50 | Cash may be at most half the defensive sleeve |
| `REFERENCE_MARKET_WEIGHTS` | 55/40/3/2 | Neutral portfolio for the equilibrium prior |
| `BL_RISK_AVERSION` | 2.5 | λ for the prior and the optimiser |
| `EXPECTED_RETURN_TRAILING_WEIGHT` | 0.25 | Weight on trailing means (rest is the prior) |
| `REBALANCE_ABS_BAND` / `REBALANCE_REL_BAND` | 0.05 / 0.25 | Holding band = min(5pp, 25% of target), floor 1pp |
| `REBALANCE_PORTFOLIO_DRIFT` | 0.03 | Portfolio drift (½Σ\|drift\|) that triggers a rebalance |
| `REGIME_DETECTION_ENABLED` | False | Tactical crisis overlay |

Methodology and rationale: [`docs/PORTFOLIO_REMEDIATION_PLAN.md`](docs/PORTFOLIO_REMEDIATION_PLAN.md).
| `USE_DUAL_MOMENTUM` | False | Antonacci dual momentum overlay |
| `MONTE_CARLO_SIMULATIONS` | 1000 | Number of MC paths |
| `RISK_DECAY_MAX_RISK` | 6 | Max risk for short horizons |

---

## 📚 References

- **Markowitz (1952)** — Portfolio Selection (Mean-Variance Optimization)
- **He & Litterman (1999)** — Black-Litterman Model
- **Ledoit & Wolf (2004)** — Shrinkage Covariance Estimation
- **Antonacci (2014)** — Dual Momentum Investing
- **Wealthfront Investment Methodology** — Case study from WBS Algorithmic Trading module
- **PyPortfolioOpt** — [github.com/robertmartin8/PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
