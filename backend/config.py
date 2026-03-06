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
    "uk_equity",
    "uk_mid_cap",
    "global_equity",
    "us_equity",
    "us_tech",
    "emerging_market_equity",
    "japan_equity",
    "europe_equity",
    "asia_pacific_equity",
    "uk_bonds",
    "uk_gilts",
    "uk_inflation_linked",
    "global_bonds",
    "corporate_bonds",
    "high_yield_bonds",
    "us_treasury",
    "commodities_gold",
    "commodities_silver",
    "commodities_broad",
    "uk_reits",
    "global_reits",
    "infrastructure",
    "cash_equivalent",
    "global_dividend",
    "uk_dividend",
    "esg_global",
    "esg_uk",
    "global_small_cap",
    "global_value",
    "global_momentum",
    "global_quality",
]

# =============================================================
# MIN / MAX ALLOCATION CONSTRAINTS PER ASSET CLASS
# =============================================================
ALLOCATION_CONSTRAINTS: dict[str, dict[str, float]] = {
    "uk_equity":               {"min": 0.00, "max": 0.40},
    "uk_mid_cap":              {"min": 0.00, "max": 0.20},
    "global_equity":           {"min": 0.00, "max": 0.50},
    "us_equity":               {"min": 0.00, "max": 0.40},
    "us_tech":                 {"min": 0.00, "max": 0.25},
    "emerging_market_equity":  {"min": 0.00, "max": 0.20},
    "japan_equity":            {"min": 0.00, "max": 0.15},
    "europe_equity":           {"min": 0.00, "max": 0.25},
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
    "cash_equivalent":         {"min": 0.02, "max": 0.15},
    "global_dividend":         {"min": 0.00, "max": 0.20},
    "uk_dividend":             {"min": 0.00, "max": 0.15},
    "esg_global":              {"min": 0.00, "max": 0.40},
    "esg_uk":                  {"min": 0.00, "max": 0.25},
    "global_small_cap":        {"min": 0.00, "max": 0.15},
    "global_value":            {"min": 0.00, "max": 0.20},
    "global_momentum":         {"min": 0.00, "max": 0.15},
    "global_quality":          {"min": 0.00, "max": 0.20},
}

# =============================================================
# REBALANCING THRESHOLDS
# =============================================================
REBALANCE_DRIFT_THRESHOLD: float = 0.05     # Trigger if any asset drifts >5%
REBALANCE_CHECK_FREQUENCY: str = "daily"     # "daily" | "weekly" | "monthly"

# =============================================================
# OPTIMIZATION PARAMETERS
# =============================================================
MVO_RISK_FREE_RATE: float = 0.0525           # UK base rate (update periodically)
BLACK_LITTERMAN_TAU: float = 0.05            # Scaling factor for BL prior uncertainty
MVO_EFFICIENT_FRONTIER_POINTS: int = 50      # Number of portfolios on frontier curve
TRACKING_ERROR_WEIGHT: float = 0.10          # Weight for tracking error minimisation (secondary objective)

# =============================================================
# MONTE CARLO
# =============================================================
MONTE_CARLO_SIMULATIONS: int = 1000
MONTE_CARLO_YEARS: int = 30

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
REGIME_DETECTION_ENABLED: bool = True
REGIME_HIGH_CORR_THRESHOLD: float = 0.75     # Average pairwise corr threshold for "crisis"
CRISIS_CASH_BUFFER: float = 0.05             # Extra cash allocation in high-corr regime

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
    "real_estate_reits",
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
PRICE_STALE_HOURS: int = 24                  # Re-fetch if cache older than this
UK_MARKET_CLOSE_HOUR: int = 16               # 4pm UK time (market close ~4:35pm)
UK_MARKET_CLOSE_MINUTE: int = 35
YFINANCE_TICKER_SUFFIX: str = ".L"           # LSE ticker suffix
