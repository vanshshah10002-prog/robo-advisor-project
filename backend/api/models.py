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
    user_id: Optional[int] = Field(default=None, ge=1, description="The id this browser was given before, to update that user")
    quiz_answers: list[QuizAnswer] = Field(..., min_length=10, max_length=10)
    objective_inputs: ObjectiveInputs
    uses_isa: bool = Field(default=False, description="Will invest via ISA?")


class QuickRiskRequest(BaseModel):
    """Minimal 3-question risk profile submission (fastest onboarding)."""
    name: str = Field(..., min_length=1, description="User's name")
    user_id: Optional[int] = Field(default=None, ge=1, description="The id this browser was given before, to update that user")
    loss_reaction: int = Field(..., ge=1, le=5, description="Reaction to a 20% drop (1–5)")
    time_horizon_choice: int = Field(..., ge=1, le=5, description="When money is needed (1–5)")
    financial_cushion: int = Field(..., ge=1, le=5, description="Savings buffer / share of wealth (1–5)")
    investment_amount: float = Field(..., gt=0, description="Amount to invest in GBP")
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
    selected_asset_classes: Optional[list[str]] = Field(default=None, description="Optional override — robo advisor auto-selects from risk score")
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
    # One-Fund Theorem outputs
    tangent_portfolio: Optional[dict[str, float]] = None
    risk_allocation_alpha: Optional[float] = None
    alpha: Optional[float] = None
    total_return_pct: Optional[float] = 0.0
    asset_classes_used: Optional[list[str]] = None


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
    # Portfolio-level inputs, for projecting a preview that is not saved yet.
    annual_return: Optional[float] = Field(default=None, ge=-0.5, le=0.5)
    annual_volatility: Optional[float] = Field(default=None, gt=0, le=1.0)
    goal_amount: Optional[float] = Field(default=None, gt=0, description="Target in today's money")
    real_terms: bool = Field(default=False, description="Report values in today's money")


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
    contributions: list[float] = []            # total paid in by each year end
    loss_probability_by_year: list[float] = []  # share of paths below what was paid in
    probability_of_loss: Optional[float] = None
    real_terms: bool = False
    inflation_rate: Optional[float] = None


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
    """One planned trade."""
    ticker: str
    etf_name: str
    action: str  # "buy" | "sell"
    current_weight: float
    target_weight: float
    trade_value_gbp: float
    quantity: float  # units
    price_gbp: float = 0.0
    est_cost_gbp: float = 0.0
    est_realised_gain_gbp: float = 0.0  # sells only, average-cost basis


class RebalanceResponse(BaseModel):
    """Drift check and, when triggered, the trade plan."""
    needs_rebalance: bool
    max_drift: float
    portfolio_drift: float = 0.0
    reasons: list[str] = []
    out_of_band: list[str] = []
    trades: list[RebalanceTrade]
    before_allocations: dict[str, float]
    after_allocations: dict[str, float]
    total_value_gbp: float = 0.0
    est_total_cost_gbp: float = 0.0
    est_realised_gain_gbp: float = 0.0
    cgt_applies: bool = True  # False inside an ISA
    stale_tickers: list[str] = []
    executed: bool = False


class ContributionRequest(BaseModel):
    """A cash deposit into an existing portfolio."""
    amount_gbp: float = Field(..., gt=0, description="Deposit in GBP")


# =============================================================
# MARKET DATA
# =============================================================

class ETFInfo(BaseModel):
    """ETF metadata from the registry (field names match uk_etf_registry.json)."""
    ticker: str
    name: str
    asset_class: str
    isin: Optional[str] = None
    expense_ratio: float
    currency: str
    benchmark: Optional[str] = None
    fund_size_gbp_mm: Optional[float] = None
    domicile: Optional[str] = None
    ucits: bool = False
    uk_retail_investable: bool = False
    tlh_substitute: Optional[str] = None
    factsheet_url: Optional[str] = None
    verification_note: Optional[str] = None


class PriceData(BaseModel):
    """Historical price data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# =============================================================
# PREVIEW, CONSTRUCTION, UNIVERSE
# =============================================================

class PreviewRequest(BaseModel):
    """Build a portfolio without opening it."""
    user_id: Optional[int] = Field(default=None, description="Caps the risk at the stored profile when given")
    risk_score: float = Field(..., ge=1.0, le=10.0)
    investment_amount: float = Field(..., gt=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    uses_isa: bool = False


class PolicySummary(BaseModel):
    growth_target: float
    growth_range: list[float]
    growth_weight: float
    defensive_weight: float
    cash_weight: float


class PreviewAllocation(BaseModel):
    asset_class: str
    sleeve: str
    ticker: str
    etf_name: str
    weight: float
    amount_gbp: float
    expense_ratio: float


class PreviewResponse(BaseModel):
    requested_risk_score: float
    risk_score: float
    capped: bool                      # True when the stored profile lowered the request
    risk_band: str
    allocations: list[PreviewAllocation]
    expected_annual_return: float
    expected_volatility: float
    sharpe_ratio: float
    total_expense_ratio: float
    annual_fund_cost_gbp: float       # TER × amount, first year
    risk_free_rate: Optional[float] = None
    policy: Optional[PolicySummary] = None
    as_of: str


class SnapshotHolding(BaseModel):
    ticker: str
    asset_class: str
    sleeve: str
    weight: float
    expense_ratio: Optional[float] = None
    expected_return: Optional[float] = None
    volatility: Optional[float] = None


class CorrelationMatrix(BaseModel):
    tickers: list[str]
    matrix: list[list[float]]


class RiskReturnPoint(BaseModel):
    expected_return: float
    volatility: float


class ConstructionSnapshot(BaseModel):
    version: int
    as_of: str
    risk_score: float
    risk_free_rate: Optional[float] = None
    expected_return: Optional[float] = None
    expected_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    total_expense_ratio: Optional[float] = None
    policy: Optional[PolicySummary] = None
    holdings: list[SnapshotHolding]
    correlation: CorrelationMatrix
    frontier: list[RiskReturnPoint]
    etf_fallbacks: dict[str, list[str]] = {}
    crisis_regime: bool = False
    vol_calibration: float


class ConstructionResponse(BaseModel):
    portfolio_id: int
    recorded: bool                    # False for portfolios opened before snapshots existed
    snapshot: Optional[ConstructionSnapshot] = None


class UniverseFund(BaseModel):
    ticker: str
    name: str
    expense_ratio: float
    currency: str
    domicile: Optional[str] = None
    fund_size_gbp_mm: Optional[float] = None
    isin: Optional[str] = None
    benchmark: Optional[str] = None
    ucits: bool
    factsheet_url: Optional[str] = None
    preferred: bool


class UniverseBlock(BaseModel):
    asset_class: str
    name: str
    description: str
    sleeve: str
    rule: str
    max_weight: Optional[float] = None
    equity_share_range: Optional[list[float]] = None
    candidates: list[UniverseFund]
    held_ticker: Optional[str] = None
    held_weight: Optional[float] = None
    target_weight: Optional[float] = None


class UniverseResponse(BaseModel):
    portfolio_id: Optional[int] = None
    blocks: list[UniverseBlock]


# =============================================================
# HISTORY, LIST, TRACK RECORD
# =============================================================

class HistoryPoint(BaseModel):
    date: str
    value: float
    net_contributions: float
    cumulative_return: float          # time-weighted, fraction


class HistoryResponse(BaseModel):
    portfolio_id: int
    points: list[HistoryPoint]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_weighted_return: Optional[float] = None
    reason: Optional[str] = None      # why `points` is empty, in plain words
    unpriced_tickers: list[str] = []


class PortfolioListItem(BaseModel):
    portfolio_id: int
    name: Optional[str] = None
    risk_score: float
    investment_amount: float
    monthly_contribution: float
    uses_isa: bool
    expected_return: Optional[float] = None
    created_at: Optional[str] = None
    total_value: Optional[float] = None       # at last stored prices; None until first valued
    net_contributions: Optional[float] = None
    total_return_pct: Optional[float] = None
    last_valued_at: Optional[str] = None
    holdings_count: int
    archived_at: Optional[str] = None       # set only in the archived list


class ArchiveResponse(BaseModel):
    portfolio_id: int
    archived_at: Optional[str] = None       # None once restored


class TrackRecordSummary(BaseModel):
    end_value: float
    total_return: float
    cagr: float
    volatility: float
    max_drawdown: float
    sharpe: Optional[float] = None     # undefined when returns have no variance


class TrackRecordPoint(BaseModel):
    date: str
    strategy: float
    benchmark: float


class TrackRecordYear(BaseModel):
    year: int
    strategy: float
    benchmark: float
    partial: bool


class BenchmarkFund(BaseModel):
    ticker: str
    name: str
    weight: float


class TrackRecordResponse(BaseModel):
    risk: int
    start: str
    end: str
    initial: float
    benchmark_label: str
    benchmark_funds: list[BenchmarkFund]    # what the comparison holds, by name
    strategy: TrackRecordSummary
    benchmark: TrackRecordSummary
    costs_gbp: float
    rebalances: int
    turnover_per_year: float
    forecast_return: Optional[float] = None       # time-weighted E[R] of the decisions
    forecast_volatility: Optional[float] = None
    within_one_sigma: Optional[float] = None      # share of annual periods inside ±1σ
    series: list[TrackRecordPoint]
    calendar_years: list[TrackRecordYear]
    notes: list[str]
    generated_at: str
    prices_downloaded_at: Optional[str] = None
