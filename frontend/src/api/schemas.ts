/**
 * API contract
 * ============
 * zod schemas mirroring backend/api/models.py and the dict-returning routes.
 * Nullability follows the database columns (backend/db/models.py): a field is
 * `.nullable()` only where the backend can actually send null.
 *
 * Request schemas carry the same bounds as the pydantic models so forms can
 * validate with them before a round trip.
 */

import { z } from 'zod'

const weights = z.record(z.string(), z.number())
const isoDate = z.string()

// ─── Onboarding ──────────────────────────────────────────────────────────────

export const quizQuestionSchema = z.object({
    id: z.number().int(),
    text: z.string(),
    options: z.array(z.string()),
    inverted: z.boolean().optional(),
})

export const minimalQuizQuestionSchema = z.object({
    id: z.number().int(),
    key: z.string(),
    text: z.string(),
    options: z.array(z.string()),
})

export const likert = z.number().int().min(1).max(5)

export const objectiveInputsSchema = z.object({
    monthly_income: z.number().positive(),
    monthly_expenses: z.number().nonnegative(),
    total_investable_assets: z.number().nonnegative(),
    investment_amount: z.number().positive(),
    employment_type: z.enum(['employed', 'self_employed', 'retired', 'student']),
    time_horizon_years: z.number().int().min(1).max(50),
    has_emergency_fund: z.enum(['no', 'partial', 'yes']),
})

export const riskProfileRequestSchema = z.object({
    name: z.string().trim().min(1),
    /** The id this browser was given before; without it the backend starts a new user. */
    user_id: z.number().int().positive().optional(),
    quiz_answers: z
        .array(z.object({ question_id: z.number().int().min(1).max(10), answer: likert }))
        .length(10),
    objective_inputs: objectiveInputsSchema,
    uses_isa: z.boolean(),
})

export const quickRiskRequestSchema = z.object({
    name: z.string().trim().min(1),
    user_id: z.number().int().positive().optional(),
    loss_reaction: likert,
    time_horizon_choice: likert,
    financial_cushion: likert,
    investment_amount: z.number().positive(),
    uses_isa: z.boolean(),
})

export const riskProfileSchema = z.object({
    user_id: z.number().int(),
    subjective_score: z.number(),
    objective_score: z.number(),
    composite_score: z.number(),
    risk_band: z.string(),
    risk_score_int: z.number().int(),
    time_horizon_years: z.number().int(),
    uses_isa: z.boolean(),
    description: z.string(),
})

// ─── Portfolio ───────────────────────────────────────────────────────────────

export const portfolioRequestSchema = z.object({
    user_id: z.number().int(),
    risk_score: z.number().min(1).max(10),
    selected_asset_classes: z.array(z.string()).optional(),
    investment_amount: z.number().positive(),
    monthly_contribution: z.number().nonnegative(),
    uses_isa: z.boolean(),
})

export const allocationSchema = z.object({
    asset_class: z.string(),
    weight: z.number(),
    ticker: z.string(),
    etf_name: z.string(),
    expense_ratio: z.number(),
    amount_gbp: z.number(),
})

export const createdPortfolioSchema = z.object({
    portfolio_id: z.number().int(),
    risk_score: z.number(),
    risk_band: z.string(),
    allocations: z.array(allocationSchema),
    expected_annual_return: z.number(),
    expected_volatility: z.number(),
    sharpe_ratio: z.number(),
    total_expense_ratio: z.number(),
    investment_amount: z.number(),
    tangent_portfolio: weights.nullish(),
    risk_allocation_alpha: z.number().nullish(),
    alpha: z.number().nullish(),
    total_return_pct: z.number().nullish(),
    asset_classes_used: z.array(z.string()).nullish(),
})

export const storedHoldingSchema = z.object({
    ticker: z.string(),
    asset_class: z.string(),
    units: z.number(),
    average_cost: z.number(),
    current_price: z.number().nullable(),
    price_as_of: isoDate.nullable(),
    target_weight: z.number(),
    current_weight: z.number().nullable(),
})

export const portfolioDetailSchema = z.object({
    portfolio_id: z.number().int(),
    risk_score: z.number(),
    target_allocations: weights,
    selected_asset_classes: z.array(z.string()),
    investment_amount: z.number(),
    monthly_contribution: z.number(),
    uses_isa: z.boolean(),
    expected_return: z.number().nullable(),
    expected_volatility: z.number().nullable(),
    sharpe_ratio: z.number().nullable(),
    cash: z.number(),
    net_contributions: z.number(),
    total_return_pct: z.number(),
    last_valued_at: isoDate.nullable(),
    holdings: z.array(storedHoldingSchema),
})

/** A row of GET /portfolios/user/{id}: newest first, valued at last stored prices. */
export const portfolioSummarySchema = z.object({
    portfolio_id: z.number().int(),
    name: z.string().nullable(),
    risk_score: z.number(),
    investment_amount: z.number(),
    monthly_contribution: z.number(),
    uses_isa: z.boolean(),
    expected_return: z.number().nullable(),
    created_at: isoDate.nullable(),
    /** Null until the portfolio has been valued on the ledger. */
    total_value: z.number().nullable(),
    net_contributions: z.number().nullable(),
    total_return_pct: z.number().nullable(),
    last_valued_at: isoDate.nullable(),
    holdings_count: z.number().int(),
})

export const refreshResultSchema = z.object({
    portfolio_id: z.number().int(),
    total_value: z.number(),
    invested_value: z.number(),
    cash: z.number(),
    net_contributions: z.number(),
    total_return_pct: z.number(),
    stale_tickers: z.array(z.string()),
    unpriced_tickers: z.array(z.string()),
    valued_at: isoDate,
    status: z.string(),
})

// ─── Performance, rebalancing, cash flows ────────────────────────────────────

export const performanceHoldingSchema = z.object({
    ticker: z.string(),
    asset_class: z.string(),
    sleeve: z.enum(['growth', 'defensive']),
    units: z.number(),
    average_cost: z.number(),
    current_price: z.number().nullable(),
    current_value: z.number(),
    unrealised_pnl: z.number(),
    target_weight: z.number(),
    current_weight: z.number(),
    band: z.number(),
})

export const performanceSchema = z.object({
    portfolio_id: z.number().int(),
    investment_amount: z.number(),
    net_contributions: z.number(),
    total_value: z.number(),
    cash: z.number(),
    total_return_pct: z.number(),
    valued_at: isoDate.nullable(),
    expected_return: z.number().nullable(),
    expected_volatility: z.number().nullable(),
    sharpe_ratio: z.number().nullable(),
    holdings: z.array(performanceHoldingSchema),
    drift: weights,
    portfolio_drift: z.number(),
    needs_rebalance: z.boolean(),
    rebalance_reasons: z.array(z.string()),
    max_drift: z.number(),
    target_allocations: weights,
    unpriced_tickers: z.array(z.string()),
})

export const rebalanceTradeSchema = z.object({
    ticker: z.string(),
    etf_name: z.string(),
    action: z.enum(['buy', 'sell']),
    current_weight: z.number(),
    target_weight: z.number(),
    trade_value_gbp: z.number(),
    quantity: z.number(),
    price_gbp: z.number(),
    est_cost_gbp: z.number(),
    est_realised_gain_gbp: z.number(),
})

export const rebalancePlanSchema = z.object({
    needs_rebalance: z.boolean(),
    max_drift: z.number(),
    portfolio_drift: z.number(),
    reasons: z.array(z.string()),
    out_of_band: z.array(z.string()),
    trades: z.array(rebalanceTradeSchema),
    before_allocations: weights,
    after_allocations: weights,
    total_value_gbp: z.number(),
    est_total_cost_gbp: z.number(),
    est_realised_gain_gbp: z.number(),
    cgt_applies: z.boolean(),
    stale_tickers: z.array(z.string()),
    executed: z.boolean(),
})

export const contributionRequestSchema = z.object({
    amount_gbp: z.number().positive(),
})

export const contributionResultSchema = z.object({
    portfolio_id: z.number().int(),
    deposited_gbp: z.number(),
    buys: z.array(z.object({ ticker: z.string(), value_gbp: z.number(), units: z.number() })),
    total_value: z.number(),
    portfolio_drift: z.number(),
    needs_rebalance: z.boolean(),
})

export const transactionSchema = z.object({
    id: z.number().int(),
    ticker: z.string(),
    action: z.string(),
    quantity: z.number(),
    price: z.number(),
    value: z.number(),
    cost: z.number(),
    realised_gain: z.number(),
    timestamp: isoDate.nullable(),
    notes: z.string().nullable(),
})

// ─── Simulation ──────────────────────────────────────────────────────────────

export const monteCarloRequestSchema = z.object({
    portfolio_id: z.number().int().optional(),
    weights: weights.optional(),
    /** Portfolio-level figures, for projecting a preview that is not saved yet. */
    annual_return: z.number().min(-0.5).max(0.5).optional(),
    annual_volatility: z.number().positive().max(1).optional(),
    initial_investment: z.number().positive(),
    monthly_contribution: z.number().nonnegative(),
    years: z.number().int().min(1).max(50),
    n_simulations: z.number().int().min(100).max(10_000),
    /** In today's money. */
    goal_amount: z.number().positive().optional(),
    real_terms: z.boolean().optional(),
})

export const monteCarloSchema = z.object({
    percentile_10: z.array(z.number()),
    percentile_25: z.array(z.number()),
    percentile_50: z.array(z.number()),
    percentile_75: z.array(z.number()),
    percentile_90: z.array(z.number()),
    years: z.array(z.number().int()),
    probability_of_goal: z.number().nullish(),
    expected_final_value: z.number(),
    median_final_value: z.number(),
    /** Total paid in by each year end; in today's money when `real_terms`. */
    contributions: z.array(z.number()),
    /** Share of simulated paths worth less than was paid in, by year, on the same basis as the values. */
    loss_probability_by_year: z.array(z.number()),
    probability_of_loss: z.number().nullable(),
    real_terms: z.boolean(),
    inflation_rate: z.number().nullable(),
})

export const frontierPointSchema = z.object({
    expected_return: z.number(),
    volatility: z.number(),
    sharpe_ratio: z.number(),
    weights,
})

export const efficientFrontierSchema = z.object({
    frontier_points: z.array(frontierPointSchema),
    current_portfolio: frontierPointSchema.nullish(),
    risk_free_rate: z.number(),
})

// ─── Preview, construction, universe ─────────────────────────────────────────

export const sleeveSchema = z.enum(['growth', 'defensive'])

export const previewRequestSchema = z.object({
    user_id: z.number().int().optional(),
    risk_score: z.number().min(1).max(10),
    investment_amount: z.number().positive(),
    monthly_contribution: z.number().nonnegative(),
    uses_isa: z.boolean(),
})

export const policySummarySchema = z.object({
    growth_target: z.number(),
    growth_range: z.array(z.number()),
    growth_weight: z.number(),
    defensive_weight: z.number(),
    cash_weight: z.number(),
})

export const previewSchema = z.object({
    requested_risk_score: z.number(),
    risk_score: z.number(),
    /** True when the stored risk profile lowered the requested level. */
    capped: z.boolean(),
    risk_band: z.string(),
    allocations: z.array(
        z.object({
            asset_class: z.string(),
            sleeve: sleeveSchema,
            ticker: z.string(),
            etf_name: z.string(),
            weight: z.number(),
            amount_gbp: z.number(),
            expense_ratio: z.number(),
        }),
    ),
    expected_annual_return: z.number(),
    expected_volatility: z.number(),
    sharpe_ratio: z.number(),
    total_expense_ratio: z.number(),
    annual_fund_cost_gbp: z.number(),
    risk_free_rate: z.number().nullable(),
    policy: policySummarySchema.nullable(),
    as_of: isoDate,
})

export const riskReturnPointSchema = z.object({ expected_return: z.number(), volatility: z.number() })

export const constructionSnapshotSchema = z.object({
    version: z.number().int(),
    as_of: isoDate,
    risk_score: z.number(),
    risk_free_rate: z.number().nullable(),
    expected_return: z.number().nullable(),
    expected_volatility: z.number().nullable(),
    sharpe_ratio: z.number().nullable(),
    total_expense_ratio: z.number().nullable(),
    policy: policySummarySchema.nullable(),
    holdings: z.array(
        z.object({
            ticker: z.string(),
            asset_class: z.string(),
            sleeve: sleeveSchema,
            weight: z.number(),
            expense_ratio: z.number().nullable(),
            expected_return: z.number().nullable(),
            volatility: z.number().nullable(),
        }),
    ),
    correlation: z.object({ tickers: z.array(z.string()), matrix: z.array(z.array(z.number())) }),
    frontier: z.array(riskReturnPointSchema),
    etf_fallbacks: z.record(z.string(), z.array(z.string())),
    crisis_regime: z.boolean(),
    vol_calibration: z.number(),
})

export const constructionSchema = z.object({
    portfolio_id: z.number().int(),
    /** False for portfolios opened before construction was recorded. */
    recorded: z.boolean(),
    snapshot: constructionSnapshotSchema.nullable(),
})

export const universeFundSchema = z.object({
    ticker: z.string(),
    name: z.string(),
    expense_ratio: z.number(),
    currency: z.string(),
    domicile: z.string().nullable(),
    fund_size_gbp_mm: z.number().nullable(),
    isin: z.string().nullable(),
    benchmark: z.string().nullable(),
    ucits: z.boolean(),
    factsheet_url: z.string().nullable(),
    preferred: z.boolean(),
})

export const universeBlockSchema = z.object({
    asset_class: z.string(),
    name: z.string(),
    description: z.string(),
    sleeve: sleeveSchema,
    rule: z.string(),
    max_weight: z.number().nullable(),
    equity_share_range: z.array(z.number()).nullable(),
    candidates: z.array(universeFundSchema),
    held_ticker: z.string().nullable(),
    held_weight: z.number().nullable(),
    target_weight: z.number().nullable(),
})

export const universeSchema = z.object({
    portfolio_id: z.number().int().nullable(),
    blocks: z.array(universeBlockSchema),
})

// ─── History and track record ────────────────────────────────────────────────

export const historySchema = z.object({
    portfolio_id: z.number().int(),
    points: z.array(
        z.object({
            date: isoDate,
            value: z.number(),
            net_contributions: z.number(),
            /** Time-weighted, as a fraction: deposits are not counted as growth. */
            cumulative_return: z.number(),
        }),
    ),
    start_date: isoDate.nullable(),
    end_date: isoDate.nullable(),
    time_weighted_return: z.number().nullable(),
    /** Why `points` is empty, in plain words. */
    reason: z.string().nullable(),
    unpriced_tickers: z.array(z.string()),
})

const trackRecordSummarySchema = z.object({
    end_value: z.number(),
    total_return: z.number(),
    cagr: z.number(),
    volatility: z.number(),
    max_drawdown: z.number(),
    sharpe: z.number().nullable(),
})

export const trackRecordSchema = z.object({
    risk: z.number().int(),
    start: isoDate,
    end: isoDate,
    initial: z.number(),
    benchmark_label: z.string(),
    strategy: trackRecordSummarySchema,
    benchmark: trackRecordSummarySchema,
    costs_gbp: z.number(),
    rebalances: z.number().int(),
    turnover_per_year: z.number(),
    forecast_return: z.number().nullable(),
    forecast_volatility: z.number().nullable(),
    within_one_sigma: z.number().nullable(),
    series: z.array(z.object({ date: isoDate, strategy: z.number(), benchmark: z.number() })),
    calendar_years: z.array(
        z.object({ year: z.number().int(), strategy: z.number(), benchmark: z.number(), partial: z.boolean() }),
    ),
    notes: z.array(z.string()),
    generated_at: z.string(),
    prices_downloaded_at: z.string().nullable(),
})

// ─── Market data ─────────────────────────────────────────────────────────────

/** Registry rows can omit optional keys entirely, so optional fields are `nullish`. */
export const etfSchema = z.object({
    ticker: z.string(),
    name: z.string(),
    asset_class: z.string(),
    isin: z.string().nullish(),
    expense_ratio: z.number(),
    currency: z.string(),
    benchmark: z.string().nullish(),
    fund_size_gbp_mm: z.number().nullish(),
    domicile: z.string().nullish(),
    ucits: z.boolean().default(false),
    uk_retail_investable: z.boolean().default(false),
    tlh_substitute: z.string().nullish(),
    factsheet_url: z.string().nullish(),
    verification_note: z.string().nullish(),
})

export const assetClassSchema = z.object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    risk_level: z.number(),
    primary_etf: z.string().nullable(),
    primary_etf_name: z.string().nullable(),
    expense_ratio: z.number().nullable(),
    factsheet_url: z.string().nullable(),
    etf_count: z.number().int(),
})

export const priceBarSchema = z.object({
    date: isoDate,
    open: z.number(),
    high: z.number(),
    low: z.number(),
    close: z.number(),
    volume: z.number(),
})

export const latestPriceSchema = z.object({
    ticker: z.string(),
    price_gbp: z.number(),
    as_of: isoDate,
})

// ─── Types ───────────────────────────────────────────────────────────────────

export type QuizQuestion = z.infer<typeof quizQuestionSchema>
export type MinimalQuizQuestion = z.infer<typeof minimalQuizQuestionSchema>
export type ObjectiveInputs = z.infer<typeof objectiveInputsSchema>
export type RiskProfileRequest = z.infer<typeof riskProfileRequestSchema>
export type QuickRiskRequest = z.infer<typeof quickRiskRequestSchema>
export type RiskProfile = z.infer<typeof riskProfileSchema>
export type PortfolioRequest = z.infer<typeof portfolioRequestSchema>
export type Allocation = z.infer<typeof allocationSchema>
export type CreatedPortfolio = z.infer<typeof createdPortfolioSchema>
export type PortfolioDetail = z.infer<typeof portfolioDetailSchema>
export type PortfolioSummary = z.infer<typeof portfolioSummarySchema>
export type RefreshResult = z.infer<typeof refreshResultSchema>
export type Performance = z.infer<typeof performanceSchema>
export type PerformanceHolding = z.infer<typeof performanceHoldingSchema>
export type RebalanceTrade = z.infer<typeof rebalanceTradeSchema>
export type RebalancePlan = z.infer<typeof rebalancePlanSchema>
export type ContributionRequest = z.infer<typeof contributionRequestSchema>
export type ContributionResult = z.infer<typeof contributionResultSchema>
export type Transaction = z.infer<typeof transactionSchema>
export type MonteCarloRequest = z.infer<typeof monteCarloRequestSchema>
export type MonteCarlo = z.infer<typeof monteCarloSchema>
export type FrontierPoint = z.infer<typeof frontierPointSchema>
export type EfficientFrontier = z.infer<typeof efficientFrontierSchema>
export type Sleeve = z.infer<typeof sleeveSchema>
export type PreviewRequest = z.infer<typeof previewRequestSchema>
export type PolicySummary = z.infer<typeof policySummarySchema>
export type Preview = z.infer<typeof previewSchema>
export type RiskReturnPoint = z.infer<typeof riskReturnPointSchema>
export type ConstructionSnapshot = z.infer<typeof constructionSnapshotSchema>
export type Construction = z.infer<typeof constructionSchema>
export type UniverseFund = z.infer<typeof universeFundSchema>
export type UniverseBlock = z.infer<typeof universeBlockSchema>
export type Universe = z.infer<typeof universeSchema>
export type History = z.infer<typeof historySchema>
export type TrackRecord = z.infer<typeof trackRecordSchema>
export type Etf = z.infer<typeof etfSchema>
export type AssetClass = z.infer<typeof assetClassSchema>
export type PriceBar = z.infer<typeof priceBarSchema>
export type LatestPrice = z.infer<typeof latestPriceSchema>
