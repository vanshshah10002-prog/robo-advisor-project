import { describe, expect, it } from 'vitest'
import type { ConstructionSnapshot, History, PerformanceHolding } from '@/api/schemas'
import * as fx from '@/test/fixtures'
import { estimatedStatistics, measuredStatistics, portfolioWeights } from './model'

const stored = fx.construction.snapshot as ConstructionSnapshot

/** 60% in a share fund (8% expected, 15% volatility), 40% in a bond fund (3%, 5%), correlated 0.2, against 4% cash. */
const pair: ConstructionSnapshot = {
    ...stored,
    risk_free_rate: 0.04,
    holdings: [
        { ticker: 'A', asset_class: 'a', sleeve: 'growth', weight: 0.6, expense_ratio: 0.002, expected_return: 0.08, volatility: 0.15 },
        { ticker: 'B', asset_class: 'b', sleeve: 'defensive', weight: 0.4, expense_ratio: 0.001, expected_return: 0.03, volatility: 0.05 },
    ],
    correlation: { tickers: ['A', 'B'], matrix: [[1, 0.2], [0.2, 1]] },
}

const holding = (ticker: string, value: number, priced = true): PerformanceHolding => ({
    ...fx.performance.holdings[0],
    ticker,
    current_value: value,
    current_price: priced ? 1 : null,
})

describe('portfolioWeights', () => {
    it('uses what each fund is worth today when every fund has a price', () => {
        expect(portfolioWeights(pair, [holding('A', 70), holding('B', 30)])).toEqual({ from: 'today', weights: [0.7, 0.3] })
    })

    it('falls back to the targets when a fund has no price, or is missing', () => {
        expect(portfolioWeights(pair, [holding('A', 70), holding('B', 30, false)])).toEqual({ from: 'target', weights: [0.6, 0.4] })
        expect(portfolioWeights(pair, [holding('A', 70)])).toEqual({ from: 'target', weights: [0.6, 0.4] })
        expect(portfolioWeights(pair, [])).toEqual({ from: 'target', weights: [0.6, 0.4] })
        expect(portfolioWeights(pair, [holding('A', 0), holding('B', 0)])).toEqual({ from: 'target', weights: [0.6, 0.4] })
    })

    it('scales targets that round to slightly more than 1 back to a whole', () => {
        const { weights } = portfolioWeights(stored, [])
        expect(weights.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12)
    })
})

describe('estimatedStatistics', () => {
    it('combines the funds’ estimates at the target weights', () => {
        const s = estimatedStatistics(pair, [])
        expect(s?.weightsFrom).toBe('target')
        expect(s?.expectedReturn).toBeCloseTo(0.06, 10)
        expect(s?.volatility).toBeCloseTo(Math.sqrt(0.00922), 10)
        expect(s?.sharpe).toBeCloseTo(0.02 / Math.sqrt(0.00922), 10)
        expect(s?.riskFree).toBe(0.04)
        expect(s?.valueAtRisk).toBeCloseTo(1.645 * Math.sqrt(0.00922) - 0.06, 10)
        expect(s?.diversificationRatio).toBeCloseTo(0.11 / Math.sqrt(0.00922), 10)
        expect(s?.effectiveHoldings).toBeCloseTo(1 / 0.52, 10)
        expect(s?.ongoingCharges).toBeCloseTo(0.0016, 10)
    })

    it('moves with the weights held today', () => {
        const s = estimatedStatistics(pair, [holding('A', 70), holding('B', 30)])
        expect(s?.weightsFrom).toBe('today')
        expect(s?.expectedReturn).toBeCloseTo(0.7 * 0.08 + 0.3 * 0.03, 10)
    })

    it('agrees with the figures stored when the portfolio was built', () => {
        const s = estimatedStatistics(stored, [])
        expect(s?.expectedReturn).toBeCloseTo(stored.expected_return as number, 3)
        expect(s?.volatility).toBeCloseTo(stored.expected_volatility as number, 3)
        expect(s?.sharpe).toBeCloseTo(stored.sharpe_ratio as number, 2)
        expect(s?.ongoingCharges).toBeCloseTo(stored.total_expense_ratio as number, 5)
    })

    it('has no value at risk when the expected return covers the fall, and no Sharpe ratio without a risk-free rate', () => {
        const calm = { ...pair, risk_free_rate: null, holdings: pair.holdings.map((h) => ({ ...h, expected_return: 0.5 })) }
        const s = estimatedStatistics(calm, [])
        expect(s?.valueAtRisk).toBe(0)
        expect(s?.sharpe).toBeNull()
        expect(s?.riskFree).toBeNull()
    })

    it('leaves out the charges when a fund’s charge is unknown', () => {
        const unknown = { ...pair, holdings: [pair.holdings[0], { ...pair.holdings[1], expense_ratio: null }] }
        expect(estimatedStatistics(unknown, [])?.ongoingCharges).toBeNull()
    })

    it('is null without an estimate or a correlation for every fund, or without any risk', () => {
        expect(estimatedStatistics({ ...pair, holdings: [pair.holdings[0], { ...pair.holdings[1], volatility: null }] }, [])).toBeNull()
        expect(estimatedStatistics({ ...pair, holdings: [pair.holdings[0], { ...pair.holdings[1], expected_return: null }] }, [])).toBeNull()
        expect(estimatedStatistics({ ...pair, correlation: { tickers: ['A'], matrix: [[1]] } }, [])).toBeNull()
        expect(estimatedStatistics({ ...pair, holdings: [] }, [])).toBeNull()
        expect(estimatedStatistics({ ...pair, holdings: pair.holdings.map((h) => ({ ...h, volatility: 0 })) }, [])).toBeNull()
    })
})

const point = (date: string, cumulative: number) => ({ date, value: 100_000 * (1 + cumulative), net_contributions: 100_000, cumulative_return: cumulative })

/** Consecutive market days from 1 June 2026, the index moving by each return in turn. */
function path(returns: readonly number[]): History['points'] {
    const levels = returns.reduce<number[]>((acc, r) => [...acc, acc[acc.length - 1] * (1 + r)], [1])
    return levels.map((level, i) => point(new Date(Date.UTC(2026, 5, 1 + i)).toISOString().slice(0, 10), level - 1))
}

describe('measuredStatistics', () => {
    it('measures volatility from daily returns, scaled to a year', () => {
        const s = measuredStatistics(path(Array.from({ length: 20 }, (_, i) => (i % 2 === 0 ? 0.01 : -0.01))))
        expect(s.realisedVolatility).toBeCloseTo(0.01 * Math.sqrt(20 / 19) * Math.sqrt(252), 10)
        expect(s.timeWeightedReturn).toBeCloseTo(0.9999 ** 10 - 1, 10)
        // Each up-and-down pair loses a little, so the deepest point is the last, against the first high.
        expect(s.maxDrawdown).toBeCloseTo(0.9999 ** 10 / 1.01 - 1, 10)
        expect(s.annualisedReturn).toBeNull()
    })

    it('waits for 20 daily returns before measuring volatility', () => {
        expect(measuredStatistics(path(Array.from({ length: 19 }, () => 0.001))).realisedVolatility).toBeNull()
    })

    it('annualises the return after a year, and reads no drawdown before any fall', () => {
        const s = measuredStatistics([point('2025-01-02', 0), point('2026-01-02', 0.1)])
        expect(s.annualisedReturn).toBeCloseTo(0.1, 2)
        expect(s.maxDrawdown).toBe(0)
    })

    it('is empty without any values', () => {
        expect(measuredStatistics([])).toEqual({ timeWeightedReturn: null, annualisedReturn: null, realisedVolatility: null, maxDrawdown: null })
    })
})
