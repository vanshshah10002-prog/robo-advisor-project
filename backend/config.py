"""
ROBO ADVISOR ALGORITHM CONFIGURATION
=====================================
The Developer Control Panel — every magic number lives here.
Change any parameter and the whole engine adapts.

Reference: Wealthfront Investment Methodology (He & Litterman, 1999;
Markowitz, 1952; Ledoit & Wolf, 2004; Antonacci, 2014)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================
# API KEYS (loaded from .env)
# =============================================================
ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
OPEN_EXCHANGE_RATES_APP_ID: str = os.getenv("OPEN_EXCHANGE_RATES_APP_ID", "")
FMP_API_KEY: str = os.getenv("FMP_API_KEY", "")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

# =============================================================
# DATABASE
# =============================================================
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./backend/data/portfolios.db")
PRICE_CACHE_DB: str = "sqlite:///./backend/data/price_cache.db"

# =============================================================
# SERVER
# =============================================================
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
BENCHMARK_TICKER: str = "VWRL.L"  # FTSE All-World — used for beta & tracking error

# =============================================================
# RISK SCORING WEIGHTS
# =============================================================
RISK_SCORE_WEIGHTS: dict = {
    "subjective_quiz": 0.6,        # Weight of questionnaire answers
    "objective_capacity": 0.4,     # Weight of financial capacity assessment
    "conservative_bias": True,     # If True, blend toward more conservative score
}

# =============================================================
# RISK BANDS → PORTFOLIO PROFILES
# =============================================================
RISK_BANDS: dict[int, str] = {
    1:  "Capital Preservation",
    2:  "Very Conservative",
    3:  "Conservative",
    4:  "Moderately Conservative",
    5:  "Balanced",
    6:  "Moderately Aggressive",
    7:  "Growth",
    8:  "Aggressive Growth",
    9:  "High Risk",
    10: "Maximum Growth",
}

# =============================================================
# RISK SCORE DECAY — life-stage adjustment
# If time_horizon < DECAY_HORIZON_YEARS, cap max risk at DECAY_MAX_RISK
# =============================================================
RISK_DECAY_ENABLED: bool = True
RISK_DECAY_HORIZON_YEARS: int = 5
RISK_DECAY_MAX_RISK: int = 6

# =============================================================
# ASSET CLASS UNIVERSE (UK-LISTED)
# =============================================================
ASSET_CLASSES: list[str] = [
    "cash_equivalent",
    "uk_equity", "uk_mid_cap", "global_equity", "us_equity", "us_tech",
    "emerging_market_equity", "japan_equity", "europe_equity", "europe_ex_uk_equity",
    "asia_pacific_equity",
    "uk_bonds", "uk_gilts", "uk_inflation_linked", "global_bonds", "corporate_bonds",
    "high_yield_bonds", "us_treasury",
    "commodities_gold", "commodities_silver", "commodities_broad",
    "uk_reits", "global_reits", "infrastructure",
    "global_dividend", "uk_dividend", "esg_global", "esg_uk",
    "global_small_cap", "global_value", "global_momentum", "global_quality",
    
    # --- Indian ETF Specific Classes ---
    "indian_large_cap", 
    "indian_mid_cap", 
    "indian_small_cap", 
    "indian_broad_equity",
    "indian_factor_value", 
    "indian_factor_momentum", 
    "indian_factor_low_vol", 
    "indian_factor_dividend",
    "indian_sector_financials", 
    "indian_sector_it", 
    "indian_sector_healthcare", 
    "indian_sector_fmcg",
    "indian_sector_auto", 
    "indian_sector_infra", 
    "indian_sector_manufacturing", 
    "indian_sector_psu",
    "indian_gold", 
    "indian_silver", 
    "indian_bonds",
    "indian_arbitrage_us_tech", 
    "indian_arbitrage_us_equity"
]

# =============================================================
# CORE UNIVERSE — the building blocks the optimiser uses
# =============================================================
# A small set of low-overlap asset classes (Wealthfront: few, low-correlation
# classes; Vanguard LifeStrategy: regional equity + GBP-hedged bonds). Each
# lists its ETFs in order of preference; the first one that is UK-investable,
# not delisted and has usable price history is used (fallback, not silent drop).
# Order rationale: lowest cost among large, liquid, long-history GBP lines;
# cash prefers a SONIA tracker (CSH2) over ultrashort credit (ERNS).
# See docs/PORTFOLIO_REMEDIATION_PLAN.md §2.3.
CORE_UNIVERSE: dict[str, list[str]] = {
    # Growth
    "uk_equity":              ["ISF.L", "VUKE.L"],
    "us_equity":              ["VUAG.L", "VUSA.L", "CSP1.L"],
    "europe_ex_uk_equity":    ["VERX.L"],
    "japan_equity":           ["VJPN.L", "CJPE.L"],
    "asia_pacific_equity":    ["VAPX.L", "CPXJ.L"],
    "emerging_market_equity": ["VFEM.L", "IEEM.L", "VFEG.L"],
    "global_reits":           ["IWDP.L"],
    "commodities_gold":       ["SGLN.L", "PHAU.L", "SGLP.L"],
    # Defensive
    "uk_gilts":               ["IGLT.L", "VGOV.L"],
    "uk_inflation_linked":    ["INXG.L"],
    "global_bonds":           ["AGBP.L", "VAGP.L"],   # GBP-hedged only
    "corporate_bonds":        ["SLXX.L", "VUKC.L"],
    "cash_equivalent":        ["CSH2.L", "ERNS.L"],
}
# Overlapping or specialist classes (factor, ESG, thematic, dividend, high
# yield, unhedged Treasuries, small cap, silver, broad commodities,
# infrastructure, India, Europe incl. UK). Kept in the registry; the optimiser
# only sees them when this is True.
USE_SATELLITE_CLASSES: bool = False
# Minimum monthly history for an ETF to be used (≥3 years keeps the
# complete-case correlation window meaningful).
MIN_HISTORY_MONTHS: int = 36

# =============================================================
# MIN / MAX ALLOCATION CONSTRAINTS PER ASSET CLASS
# =============================================================
ALLOCATION_CONSTRAINTS: dict[str, dict[str, float]] = {
    "cash_equivalent":         {"min": 0.00, "max": 0.80},
    "uk_equity":               {"min": 0.00, "max": 0.40},
    "uk_mid_cap":              {"min": 0.00, "max": 0.20},
    "global_equity":           {"min": 0.00, "max": 0.50},
    "us_equity":               {"min": 0.00, "max": 0.40},
    "us_tech":                 {"min": 0.00, "max": 0.25},
    "emerging_market_equity":  {"min": 0.00, "max": 0.20},
    "japan_equity":            {"min": 0.00, "max": 0.15},
    "europe_equity":           {"min": 0.00, "max": 0.25},
    "europe_ex_uk_equity":     {"min": 0.00, "max": 0.25},
    "asia_pacific_equity":     {"min": 0.00, "max": 0.15},
    "uk_bonds":                {"min": 0.00, "max": 0.50},
    "uk_gilts":                {"min": 0.00, "max": 0.40},
    "uk_inflation_linked":     {"min": 0.00, "max": 0.20},
    "global_bonds":            {"min": 0.00, "max": 0.30},
    "corporate_bonds":         {"min": 0.00, "max": 0.25},
    "high_yield_bonds":        {"min": 0.00, "max": 0.15},
    "us_treasury":             {"min": 0.00, "max": 0.20},
    "commodities_gold":        {"min": 0.00, "max": 0.15},
    "commodities_silver":      {"min": 0.00, "max": 0.05},
    "commodities_broad":       {"min": 0.00, "max": 0.10},
    "uk_reits":                {"min": 0.00, "max": 0.15},
    "global_reits":            {"min": 0.00, "max": 0.15},
    "infrastructure":          {"min": 0.00, "max": 0.10},
    "global_dividend":         {"min": 0.00, "max": 0.20},
    "uk_dividend":             {"min": 0.00, "max": 0.15},
    "esg_global":              {"min": 0.00, "max": 0.40},
    "esg_uk":                  {"min": 0.00, "max": 0.25},
    "global_small_cap":        {"min": 0.00, "max": 0.15},
    "global_value":            {"min": 0.00, "max": 0.20},
    "global_momentum":         {"min": 0.00, "max": 0.15},
    "global_quality":          {"min": 0.00, "max": 0.20},

    # --- Indian ETF CONSTRAINTS ---
    "indian_large_cap":              {"min": 0.00, "max": 0.40},
    "indian_mid_cap":                {"min": 0.00, "max": 0.20},
    "indian_small_cap":              {"min": 0.00, "max": 0.15},
    "indian_broad_equity":           {"min": 0.00, "max": 0.30},
    "indian_factor_value":           {"min": 0.00, "max": 0.15},
    "indian_factor_momentum":        {"min": 0.00, "max": 0.15},
    "indian_factor_low_vol":         {"min": 0.00, "max": 0.20},
    "indian_factor_dividend":        {"min": 0.00, "max": 0.10},
    "indian_sector_financials":      {"min": 0.00, "max": 0.20},
    "indian_sector_it":              {"min": 0.00, "max": 0.15},
    "indian_sector_healthcare":      {"min": 0.00, "max": 0.10},
    "indian_sector_fmcg":            {"min": 0.00, "max": 0.10},
    "indian_sector_auto":            {"min": 0.00, "max": 0.05},
    "indian_sector_infra":           {"min": 0.00, "max": 0.05},
    "indian_sector_manufacturing":   {"min": 0.00, "max": 0.05},
    "indian_sector_psu":             {"min": 0.00, "max": 0.10},
    "indian_gold":                   {"min": 0.00, "max": 0.15},
    "indian_silver":                 {"min": 0.00, "max": 0.05},
    "indian_bonds":                  {"min": 0.00, "max": 0.50},
    "indian_arbitrage_us_tech":      {"min": 0.00, "max": 0.25},
    "indian_arbitrage_us_equity":    {"min": 0.00, "max": 0.30},
}

# =============================================================
# ALLOCATION POLICY — how a risk score becomes a portfolio
# =============================================================
# See docs/PORTFOLIO_REMEDIATION_PLAN.md §2.5.
# Risk is the share in growth assets (Betterment 0–100% stocks; Vanguard
# LifeStrategy 20/40/60/80/100): portfolios are built at exactly
# growth = 10% × risk score and may drift ±5pp before a rebalance. The rest
# is the defensive sleeve, where bonds — not cash — do the de-risking.
GROWTH_ASSET_CLASSES: list[str] = [
    "us_equity", "uk_equity", "europe_ex_uk_equity", "emerging_market_equity",
    "japan_equity", "asia_pacific_equity", "global_reits", "commodities_gold",
]
DEFENSIVE_ASSET_CLASSES: list[str] = [
    "uk_gilts", "uk_inflation_linked", "global_bonds", "corporate_bonds", "cash_equivalent",
]
POLICY_GROWTH_PER_RISK_POINT: float = 0.10
POLICY_GROWTH_TOLERANCE: float = 0.05
# Cash may be at most half the defensive sleeve (liquidity buffer, not the de-risker).
POLICY_CASH_MAX_SHARE_OF_DEFENSIVE: float = 0.50
# Regional equity (the EQUITY_REGION_REFERENCE blocks) must be at least this
# share of the growth sleeve; property and gold are diversifiers, not the core.
POLICY_EQUITY_MIN_SHARE_OF_GROWTH: float = 0.75
# Per-block maximum weight in the whole portfolio (Wealthfront: 35% for most
# classes). Regional equity is governed by the region bands below instead.
POLICY_BLOCK_MAX: dict[str, float] = {
    "uk_gilts": 0.35,
    "uk_inflation_linked": 0.20,
    "global_bonds": 0.35,
    "corporate_bonds": 0.20,
    "global_reits": 0.10,
    "commodities_gold": 0.05,
    "cash_equivalent": 1.00,   # limited by POLICY_CASH_MAX_SHARE_OF_DEFENSIVE
}
# Each equity region's share of total equity stays within
# reference ± max(ABS, REL × reference) (look-through at region level).
REGION_BAND_ABS: float = 0.05
REGION_BAND_REL: float = 0.30
UK_EQUITY_SHARE_RANGE: tuple[float, float] = (0.10, 0.25)
# Positions below this are removed by re-solving with them fixed at zero.
POLICY_MIN_POSITION: float = 0.005

# =============================================================
# GROUP (SECTOR) ALLOCATION CAPS — LEGACY (backend/eval/legacy_construction.py only)
# Production uses the allocation policy above. The flat 20% bond cap forced
# low- and mid-risk portfolios into cash + equity barbells (finding A1).
# =============================================================
ASSET_GROUP_CAPS: dict[str, float] = {
    "bonds": 0.20,   # total TERM fixed income ≤ 20% (mandate)
    "gold": 0.10,    # total gold/precious metals ≤ 10% (mandate)
}
BOND_ASSET_CLASSES: list[str] = [
    "uk_bonds", "uk_gilts", "uk_inflation_linked", "global_bonds",
    "corporate_bonds", "high_yield_bonds", "us_treasury", "indian_bonds",
]
GOLD_ASSET_CLASSES: list[str] = [
    "commodities_gold", "commodities_silver", "indian_gold", "indian_silver",
]
# The cash sleeve (cash_equivalent: ultrashort/money-market ETFs, ~0.5% vol) is
# the de-risking instrument and is EXEMPT from the 20% bond cap — mirroring
# Betterment, whose most conservative portfolio is 60% short-term treasuries.
# Without this exemption the bond cap makes low-risk portfolios impossible
# (risk-1 was forced to ~72% equity). Disclosed in docs/OPTIMIZATION_WALKTHROUGH.md.
CASH_ASSET_CLASSES: list[str] = ["cash_equivalent"]

# Universe filter: UK retail investors cannot hold non-UCITS funds (PRIIPs);
# NSE-listed (.NS) lines are excluded from the investable map when True.
UK_RETAIL_UCITS_ONLY: bool = True

# Client-facing volatility calibration: Phase 2 measured realized/predicted
# vol ≈ 1.1–1.2 for the EWMA+LW model; reported vol is scaled accordingly.
VOL_CALIBRATION_MULTIPLIER: float = 1.15

# =============================================================
# REBALANCING THRESHOLDS
# =============================================================
# Tolerance band per holding = max(MIN, min(ABS, REL × target)): ±5pp for large
# sleeves, ±25% of target for small ones, never tighter than ±1pp.
# Sources: Vanguard (Jaconetti, Kinniry & Zilbering) ~5% thresholds;
# Daryanani (2008) 20–25% relative bands. See docs/PORTFOLIO_REMEDIATION_PLAN.md.
REBALANCE_ABS_BAND: float = 0.05
REBALANCE_REL_BAND: float = 0.25
REBALANCE_MIN_BAND: float = 0.01
REBALANCE_DRIFT_THRESHOLD: float = REBALANCE_ABS_BAND  # legacy name
# Portfolio drift = ½·Σ|current − target| (Betterment's definition and default 3%).
REBALANCE_PORTFOLIO_DRIFT: float = 0.03
# Trades smaller than max(£25, 0.25% of portfolio value) are not worth their cost.
REBALANCE_MIN_TRADE_GBP: float = 25.0
REBALANCE_MIN_TRADE_PCT: float = 0.0025
REBALANCE_CHECK_FREQUENCY: str = "daily"     # check often, trade rarely (Daryanani); bands limit turnover

# Round-trip transaction cost assumption (one-way, basis points of traded notional).
# ~0.10% covers typical UK ETF bid-ask half-spread + commission. UK ETFs are exempt
# from the 0.5% stamp duty that applies to individual LSE shares.
TRANSACTION_COST_BPS: float = 10.0
# A previewed construction is reused when the investor confirms within this
# window, so the portfolio they open is exactly the one they were shown.
CONSTRUCTION_CACHE_TTL_SECONDS: float = 6 * 3600

# =============================================================
# OPTIMIZATION PARAMETERS
# =============================================================
# Risk-free rate FALLBACK — used only when the live fetch fails.
# The LIVE GBP risk-free rate is fetched from yfinance via
# backend/data/rates.py (trailing return of a GBP money-market ETF ≈ realized
# SONIA). It drives BOTH the pricing math (CAPM/BL/tangency) and all Sharpe
# reporting — the previous hardcoded 6% HURDLE_RATE has been removed.
MVO_RISK_FREE_RATE: float = 0.040
# Live risk-free proxy: GBP ultrashort/money-market ETFs, tried in order.
RISK_FREE_PROXY_TICKERS: list[str] = ["CSH2.L", "ERNS.L"]  # SONIA tracker first; ERNS carries credit spread
RISK_FREE_LOOKBACK_MONTHS: int = 12
# Sanity clamp on the fetched rate (annual). Outside this band = data error.
RISK_FREE_CLAMP: tuple[float, float] = (0.0, 0.08)
# Sanity clamp on production expected returns (annual, arithmetic). Informed by
# professional CMAs (Vanguard 2026: ~4% bonds, muted equities) — trailing-heavy
# estimates outside this band are treated as estimation error, not signal.
EXPECTED_RETURN_CLAMP: tuple[float, float] = (-0.05, 0.12)
BLACK_LITTERMAN_TAU: float = 0.05            # Scaling factor for BL prior uncertainty

# Reference (neutral) portfolio for the equilibrium prior: π = λ·Σ·w_ref.
# A global multi-asset market proxy (Doeswijk, Lam & Swinkels 2014) with the
# equity split by FTSE All-World regional weights and a 20% UK home bias
# (Vanguard LifeStrategy 2026). Cash is excluded: its E[R] is the live rate.
# Using asset-class weights, not ETF fund sizes, is what makes the prior an
# equilibrium (Idzorek; Wealthfront uses the global market portfolio).
EQUITY_REGION_REFERENCE: dict[str, float] = {   # share of total equity
    "us_equity": 0.53,
    "uk_equity": 0.20,
    "europe_ex_uk_equity": 0.10,
    "emerging_market_equity": 0.09,
    "japan_equity": 0.05,
    "asia_pacific_equity": 0.03,
}
REFERENCE_EQUITY_SHARE: float = 0.55
REFERENCE_MARKET_WEIGHTS: dict[str, float] = {
    **{ac: REFERENCE_EQUITY_SHARE * w for ac, w in EQUITY_REGION_REFERENCE.items()},
    "uk_gilts": 0.10,
    "uk_inflation_linked": 0.05,
    "global_bonds": 0.18,
    "corporate_bonds": 0.07,
    "global_reits": 0.03,
    "commodities_gold": 0.02,
}
# Market price of risk λ, fixed (He & Litterman 1999 use 2.5). Fitting it to a
# trailing window made the prior swing with recent returns.
BL_RISK_AVERSION: float = 2.5
# Weight on the trailing (historical) mean in the expected-return blend; the
# rest is the equilibrium prior. Errors in means dominate MVO error (Chopra &
# Ziemba 1993), so history gets a minority weight — and less when the common
# estimation window is shorter than TRAILING_FULL_WEIGHT_MONTHS.
EXPECTED_RETURN_TRAILING_WEIGHT: float = 0.25
TRAILING_FULL_WEIGHT_MONTHS: int = 120
MVO_EFFICIENT_FRONTIER_POINTS: int = 50      # Number of portfolios on frontier curve

# =============================================================
# MONTE CARLO
# =============================================================
MONTE_CARLO_SIMULATIONS: int = 1000
MONTE_CARLO_YEARS: int = 30
MONTE_CARLO_T_DOF: float = 6.0       # Student-t dof (fitted dev residuals ν≈6.3; stress-conservative)
MONTE_CARLO_INFLATION: float = 0.025 # annual inflation for contribution & goal growth
MONTE_CARLO_SEED: int = 42           # reproducibility; vary for sensitivity runs

# =============================================================
# EXPECTED RETURNS MODEL
# =============================================================
USE_BLACK_LITTERMAN: bool = True             # False = use pure historical/CAPM means
FACTOR_MODEL_LOOKBACK_YEARS: int = 5         # Historical window for factor estimation
SHRINKAGE_METHOD: str = "ledoit_wolf"        # "ledoit_wolf" | "oracle_approx" | "identity"

# =============================================================
# DUAL MOMENTUM OVERLAY (Optional — Antonacci, 2014)
# =============================================================
USE_DUAL_MOMENTUM: bool = False              # Toggle dual momentum tactical overlay
DUAL_MOMENTUM_LOOKBACK_MONTHS: int = 12      # Lookback period for momentum signal
DUAL_MOMENTUM_REDUCTION: float = 0.50        # Reduce allocation by 50% if negative momentum

# =============================================================
# CORRELATION REGIME DETECTION
# =============================================================
REGIME_DETECTION_ENABLED: bool = False     # strategic by default (Betterment/Wealthfront/Vanguard); see plan P9
REGIME_HIGH_CORR_THRESHOLD: float = 0.75     # (legacy correlation detector)
REGIME_VOL_ENTER_Z: float = 1.0              # enter crisis when vol z-score > this
REGIME_VOL_EXIT_Z: float = 0.5               # remain in crisis until z falls below this (hysteresis)
REGIME_DRAWDOWN_TRIGGER: float = -0.10       # or drawdown below this
CRISIS_CASH_BUFFER: float = 0.05             # Extra defensive allocation in crisis regime

# =============================================================
# UK TAX ASSUMPTIONS
# =============================================================
UK_CGT_BASIC_RATE: float = 0.10
UK_CGT_HIGHER_RATE: float = 0.20
UK_DIVIDEND_ALLOWANCE_GBP: float = 500.0
ISA_ANNUAL_ALLOWANCE_GBP: float = 20000.0

# =============================================================
# ISA OPTIMISATION
# Prioritise high-tax-drag assets inside the ISA wrapper
# =============================================================
ISA_PRIORITY_ASSET_CLASSES: list[str] = [
    "uk_reits",          # highest income tax drag → shelter first
    "global_reits",
    "high_yield_bonds",
    "corporate_bonds",
    "uk_bonds",
    "global_bonds",
]

# =============================================================
# BENCHMARK
# =============================================================
BENCHMARK_TICKER: str = "VWRL.L"             # Vanguard FTSE All-World ETF (LSE)
BENCHMARK_NAME: str = "FTSE All-World"

# =============================================================
# DATA FETCHING
# =============================================================
PRICE_HISTORY_YEARS: int = 5                 # Default historical price window
# LIVE-FIRST data policy: prices are always fetched from yfinance; the local
# SQLite cache is a resilience/rate-limit layer, not an offline store. Data
# older than this is re-fetched (default 1h; set PRICE_STALE_HOURS=0 to force
# a live fetch on every call — cache then serves only as a network-failure
# fallback).
PRICE_STALE_HOURS: float = float(os.getenv("PRICE_STALE_HOURS", "1"))
UK_MARKET_CLOSE_HOUR: int = 16               # 4pm UK time (market close ~4:35pm)
UK_MARKET_CLOSE_MINUTE: int = 35
YFINANCE_TICKER_SUFFIX: str = ".L"           # LSE ticker suffix
