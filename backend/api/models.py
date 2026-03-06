"""
Pydantic Request/Response Models
=================================
Type-safe API schemas for all robo advisor endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


# =============================================================
# ONBOARDING / RISK PROFILE
# =============================================================

class QuizAnswer(BaseModel):
    """A single quiz question answer."""
    question_id: int = Field(..., ge=1, le=10, description="Question number (1–10)")
    answer: int = Field(..., ge=1, le=5, description="Likert scale answer (1–5)")


class ObjectiveInputs(BaseModel):
    """Financial capacity inputs for objective risk scoring."""
    monthly_income: float = Field(..., gt=0, description="Monthly income in GBP")
    monthly_expenses: float = Field(..., ge=0, description="Monthly expenses in GBP")
    total_investable_assets: float = Field(..., ge=0, description="Total investable assets in GBP")
    investment_amount: float = Field(..., gt=0, description="Amount to invest in GBP")
    employment_type: str = Field(..., description="employed | self_employed | retired | student")
    time_horizon_years: int = Field(..., ge=1, le=50, description="Investment horizon in years")
    has_emergency_fund: str = Field(..., description="no | partial | yes")


class RiskProfileRequest(BaseModel):
    """Full risk profile submission."""
    name: str = Field(..., min_length=1, description="User's name")
    quiz_answers: list[QuizAnswer] = Field(..., min_length=10, max_length=10)
    objective_inputs: ObjectiveInputs
    uses_isa: bool = Field(default=False, description="Will invest via ISA?")


class RiskProfileResponse(BaseModel):
    """Risk profile result returned to client."""
    user_id: int
    subjective_score: float
    objective_score: float
    composite_score: float
    risk_band: str
    risk_score_int: int
    time_horizon_years: int
    uses_isa: bool
    description: str


# =============================================================
# PORTFOLIO
# =============================================================

class PortfolioRequest(BaseModel):
    """Request to build an optimised portfolio."""
    user_id: int
    risk_score: float = Field(..., ge=1.0, le=10.0, description="Risk score 1–10")
    selected_asset_classes: list[str] = Field(..., min_length=3, description="Min 3 asset classes")
    investment_amount: float = Field(..., gt=0, description="Lump sum in GBP")
    monthly_contribution: float = Field(default=0.0, ge=0, description="Monthly recurring in GBP")
    uses_isa: bool = Field(default=False)


class AllocationItem(BaseModel):
    """A single asset class allocation in the portfolio."""
    asset_class: str
    weight: float
    ticker: str
    etf_name: str
    expense_ratio: float
    amount_gbp: float


class PortfolioResponse(BaseModel):
    """Optimised portfolio result."""
    portfolio_id: int
    risk_score: float
    risk_band: str
    allocations: list[AllocationItem]
    expected_annual_return: float
    expected_volatility: float
    sharpe_ratio: float
    total_expense_ratio: float
    investment_amount: float


# =============================================================
# SIMULATION
# =============================================================

class EfficientFrontierPoint(BaseModel):
    """A single point on the efficient frontier."""
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


class EfficientFrontierResponse(BaseModel):
    """Full efficient frontier data."""
    frontier_points: list[EfficientFrontierPoint]
    current_portfolio: Optional[EfficientFrontierPoint] = None
    risk_free_rate: float


class MonteCarloRequest(BaseModel):
    """Input for Monte Carlo simulation."""
    portfolio_id: Optional[int] = None
    weights: Optional[dict[str, float]] = None
    initial_investment: float = Field(..., gt=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    years: int = Field(default=30, ge=1, le=50)
    n_simulations: int = Field(default=1000, ge=100, le=10000)


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation results."""
    percentile_10: list[float]
    percentile_25: list[float]
    percentile_50: list[float]
    percentile_75: list[float]
    percentile_90: list[float]
    years: list[int]
    probability_of_goal: Optional[float] = None
    expected_final_value: float
    median_final_value: float


# =============================================================
# PERFORMANCE / DASHBOARD
# =============================================================

class HoldingInfo(BaseModel):
    """Current holding information for dashboard."""
    ticker: str
    etf_name: str
    asset_class: str
    quantity: float
    average_cost: float
    current_price: float
    current_value: float
    target_weight: float
    current_weight: float
    unrealised_pnl: float
    unrealised_pnl_pct: float
    day_change_pct: float


class PortfolioPerformance(BaseModel):
    """Portfolio performance metrics for the dashboard."""
    portfolio_id: int
    total_value: float
    total_invested: float
    total_return: float
    total_return_pct: float
    day_change: float
    day_change_pct: float
    annualised_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    beta: float
    holdings: list[HoldingInfo]
    needs_rebalance: bool
    drift_details: Optional[dict[str, float]] = None


class RebalanceTrade(BaseModel):
    """Suggested trade for rebalancing."""
    ticker: str
    etf_name: str
    action: str  # "buy" | "sell"
    current_weight: float
    target_weight: float
    trade_value_gbp: float
    quantity: float


class RebalanceResponse(BaseModel):
    """Rebalancing suggestion."""
    needs_rebalance: bool
    max_drift: float
    trades: list[RebalanceTrade]
    before_allocations: dict[str, float]
    after_allocations: dict[str, float]


# =============================================================
# MARKET DATA
# =============================================================

class ETFInfo(BaseModel):
    """ETF metadata from the registry."""
    ticker: str
    name: str
    asset_class: str
    isin: str
    expense_ratio: float
    currency: str
    benchmark_index: str
    fund_size_gbp: float
    domicile: str
    substitute_ticker: Optional[str] = None


class PriceData(BaseModel):
    """Historical price data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
