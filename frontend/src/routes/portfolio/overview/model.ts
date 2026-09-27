/**
 * Portfolio statistics
 * ====================
 * The technical figures beside the holdings. Estimated ones combine each
 * fund's expected return, volatility and correlations from the construction
 * snapshot (volatilities already include its calibration allowance) at the
 * weights held today; measured ones come from the portfolio's own daily
 * values, replayed from its ledger.
 */
import type { ConstructionSnapshot, History, PerformanceHolding } from '@/api/schemas'
import { annualised, drawdowns } from '../performance/model'
import { covarianceMatrix, variance } from '../covariance'

type Point = History['points'][number]

/** One-sided 95% point of the normal distribution. */
const Z_95 = 1.645
const TRADING_DAYS = 252
/** Fewer daily returns than this say too little about how much the value moves. */
const MIN_RETURNS = 20

export interface EstimatedStatistics {
    /** Whether the weights are those held today, or the targets when a price is missing. */
    weightsFrom: 'today' | 'target'
    expectedReturn: number
    volatility: number
    sharpe: number | null
    riskFree: number | null
    /** The one-year loss, as a fraction, exceeded with 5% probability under a normal distribution. */
    valueAtRisk: number
    diversificationRatio: number
    effectiveHoldings: number
    ongoingCharges: number | null
}

export interface MeasuredStatistics {
    timeWeightedReturn: number | null
    annualisedReturn: number | null
    realisedVolatility: number | null
    /** The deepest fall from a high, as a negative fraction; 0 before any fall. */
    maxDrawdown: number | null
}

const sum = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0)

/**
 * The weight of each snapshot holding: what it is worth today when every
 * fund has a price, otherwise the targets, scaled to add up to exactly 1.
 */
export function portfolioWeights(snapshot: ConstructionSnapshot, holdings: readonly PerformanceHolding[]): { from: 'today' | 'target'; weights: number[] } {
    const byTicker = new Map(holdings.map((h) => [h.ticker, h]))
    const today = snapshot.holdings.map((h) => byTicker.get(h.ticker))
    const priced = today.every((h) => h !== undefined && h.current_price !== null) && holdings.length === snapshot.holdings.length
    const values = today.map((h) => h?.current_value ?? 0)
    const scaled = (xs: readonly number[]) => xs.map((x) => x / sum(xs))
    return priced && sum(values) > 0
        ? { from: 'today', weights: scaled(values) }
        : { from: 'target', weights: scaled(snapshot.holdings.map((h) => h.weight)) }
}

/** The snapshot's estimates combined at today's weights; null when an estimate the figures need is missing. */
export function estimatedStatistics(snapshot: ConstructionSnapshot, holdings: readonly PerformanceHolding[]): EstimatedStatistics | null {
    const cov = covarianceMatrix(snapshot)
    if (!cov || snapshot.holdings.some((h) => h.expected_return === null)) return null
    const { from, weights } = portfolioWeights(snapshot, holdings)
    const volatility = Math.sqrt(variance(cov, weights))
    if (!(volatility > 0)) return null
    const funds = snapshot.holdings
    const expectedReturn = sum(funds.map((h, i) => weights[i] * (h.expected_return as number)))
    const rf = snapshot.risk_free_rate
    const charges = funds.every((h) => h.expense_ratio !== null) ? sum(funds.map((h, i) => weights[i] * (h.expense_ratio as number))) : null
    return {
        weightsFrom: from,
        expectedReturn,
        volatility,
        sharpe: rf === null ? null : (expectedReturn - rf) / volatility,
        riskFree: rf,
        valueAtRisk: Math.max(0, Z_95 * volatility - expectedReturn),
        diversificationRatio: sum(funds.map((h, i) => weights[i] * (h.volatility as number))) / volatility,
        effectiveHoldings: 1 / sum(weights.map((w) => w * w)),
        ongoingCharges: charges,
    }
}

/** Sample standard deviation of the daily returns of the time-weighted index, scaled to a year. */
function realisedVolatility(points: readonly Point[]): number | null {
    const returns = points.slice(1).map((p, i) => (1 + p.cumulative_return) / (1 + points[i].cumulative_return) - 1)
    if (returns.length < MIN_RETURNS) return null
    const mean = sum(returns) / returns.length
    const spread = sum(returns.map((r) => (r - mean) ** 2)) / (returns.length - 1)
    return Math.sqrt(spread * TRADING_DAYS)
}

/** What the portfolio's own values show so far. */
export function measuredStatistics(points: readonly Point[]): MeasuredStatistics {
    if (points.length === 0) return { timeWeightedReturn: null, annualisedReturn: null, realisedVolatility: null, maxDrawdown: null }
    const [first, last] = [points[0], points[points.length - 1]]
    return {
        timeWeightedReturn: last.cumulative_return,
        annualisedReturn: annualised(last.cumulative_return, first.date, last.date),
        realisedVolatility: realisedVolatility(points),
        maxDrawdown: Math.min(0, ...drawdowns(points)),
    }
}
