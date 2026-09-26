import { describe, expect, it } from 'vitest'
import type { ConstructionSnapshot, Universe } from '@/api/schemas'
import * as fx from '@/test/fixtures'
import { blockRows, heldCorrelations, regionShares, riskSentence, riskShares, universeSentence, type BlockRow } from './model'

const snapshot = fx.construction.snapshot as ConstructionSnapshot
const universe = fx.heldUniverse as Universe
const rows = blockRows(universe, snapshot)
const row = (assetClass: string) => rows.find((r) => r.assetClass === assetClass) as BlockRow

/** Two holdings, half each, with 20% and 10% volatility and the given correlation. */
function pair(correlation: number, volatility: number | null = 0.1): ConstructionSnapshot {
    return {
        ...snapshot,
        holdings: [
            { ticker: 'A', asset_class: 'a', sleeve: 'growth', weight: 0.5, expense_ratio: null, expected_return: null, volatility: 0.2 },
            { ticker: 'B', asset_class: 'b', sleeve: 'defensive', weight: 0.5, expense_ratio: null, expected_return: null, volatility },
        ],
        correlation: { tickers: ['A', 'B'], matrix: [[1, correlation], [correlation, 1]] },
    }
}

describe('riskShares', () => {
    it('splits the variance of two unrelated holdings by their own variance', () => {
        const shares = riskShares(pair(0))
        expect(shares.get('A')).toBeCloseTo(0.8, 10)
        expect(shares.get('B')).toBeCloseTo(0.2, 10)
    })

    it('shares the covariance between related holdings', () => {
        const shares = riskShares(pair(0.5))
        expect(shares.get('A')).toBeCloseTo(0.0125 / 0.0175, 10)
        expect(shares.get('B')).toBeCloseTo(0.005 / 0.0175, 10)
    })

    it('adds up to the whole risk of the recorded portfolio, most of it from US shares', () => {
        const shares = riskShares(snapshot)
        expect([...shares.values()].reduce((a, b) => a + b, 0)).toBeCloseTo(1, 10)
        expect(shares.get('VUAG.L')).toBeCloseTo(0.7094, 4)
        expect(shares.get('ERNS.L')).toBeLessThan(0.005)
    })

    it('is empty when a volatility or a correlation is missing', () => {
        expect(riskShares(pair(0, null)).size).toBe(0)
        expect(riskShares({ ...pair(0), correlation: { tickers: ['A'], matrix: [[1]] } }).size).toBe(0)
        expect(riskShares({ ...snapshot, holdings: [] }).size).toBe(0)
    })
})

describe('blockRows', () => {
    it('lists all thirteen blocks, growth first and largest first', () => {
        expect(rows).toHaveLength(13)
        expect(rows.slice(0, 3).map((r) => r.assetClass)).toEqual(['us_equity', 'europe_ex_uk_equity', 'uk_equity'])
        expect(rows.findIndex((r) => r.sleeve === 'defensive')).toBe(rows.filter((r) => r.sleeve === 'growth').length)
    })

    it('carries the estimates the portfolio was built with', () => {
        expect(row('us_equity')).toMatchObject({ weight: 0.4479, expectedReturn: 0.080697, volatility: 0.149793 })
        expect(row('us_equity').held?.ticker).toBe('VUAG.L')
        expect(row('us_equity').riskShare).toBeCloseTo(0.7094, 4)
        expect(row('us_equity').note).toBeNull()
    })

    it('says why the first-choice fund was passed over', () => {
        expect(row('cash_equivalent').note).toBe(
            'CSH2.L, the first choice, had too little usable price history when the portfolio was built, so ERNS.L is held instead.',
        )
        expect(row('cash_equivalent').alternatives.map((f) => f.ticker)).toEqual(['CSH2.L'])
    })

    it('says a block is not held because the optimiser gave it no weight', () => {
        expect(row('japan_equity')).toMatchObject({ held: null, weight: null, riskShare: null, expectedReturn: null })
        expect(row('japan_equity').note).toBe('Not held: the optimiser gave it no weight at this risk level.')
    })

    it('says a block is not held because none of its funds had the history', () => {
        const noHistory = { ...snapshot, etf_fallbacks: { japan_equity: ['VJPN.L'] } }
        expect(blockRows(universe, noHistory).find((r) => r.assetClass === 'japan_equity')?.note).toBe(
            'Not held: none of its funds had enough usable price history when the portfolio was built.',
        )
    })

    it('without a snapshot, names the fund held instead of the first choice but gives no estimates', () => {
        const cash = blockRows(universe, null).find((r) => r.assetClass === 'cash_equivalent')
        expect(cash).toMatchObject({ expectedReturn: null, volatility: null, riskShare: null })
        expect(cash?.note).toBe('ERNS.L is held rather than the first choice, CSH2.L.')
    })
})

describe('universeSentence', () => {
    it('counts the blocks held and splits them into growth and defensive', () => {
        expect(universeSentence(rows)).toBe('8 of the 13 building blocks are held: 70% in growth and 30% in defensive holdings.')
    })
})

describe('riskSentence', () => {
    it('leads with the biggest source of risk, then the least risk for its size', () => {
        expect(riskSentence(rows)).toBe(
            'The biggest source of risk: US shares, 45% of the money but 71% of the risk. ' +
                'Least for its size: Cash-like fund, 15% of the money but under 1% of the risk.',
        )
    })

    it('says "and" when the two shares round alike, and names one holding once', () => {
        const even = [
            { ...row('us_equity'), weight: 0.601, riskShare: 0.604 },
            { ...row('uk_equity'), weight: 0.399, riskShare: 0.396 },
        ]
        expect(riskSentence(even)).toBe(
            'The biggest source of risk: US shares, 60% of the money and 60% of the risk. Least for its size: UK shares, 40% of the money and 40% of the risk.',
        )
        const lopsided = [
            { ...row('us_equity'), weight: 0.9, riskShare: 0.85 },
            { ...row('uk_equity'), weight: 0.1, riskShare: 0.15 },
        ]
        expect(riskSentence(lopsided)).toBe('The biggest source of risk: US shares, 90% of the money but 85% of the risk.')
    })

    it('says a holding lowers the risk when its share is below zero', () => {
        const hedged = [
            { ...row('us_equity'), weight: 0.95, riskShare: 1.02 },
            { ...row('commodities_gold'), weight: 0.05, riskShare: -0.02 },
        ]
        expect(riskSentence(hedged)).toBe(
            'The biggest source of risk: US shares, 95% of the money but 102% of the risk. Least for its size: Gold, 5% of the money, and it lowers the risk overall.',
        )
    })

    it('is null with fewer than two holdings to compare', () => {
        expect(riskSentence([row('us_equity')])).toBeNull()
        expect(riskSentence(blockRows(universe, null))).toBeNull()
    })
})

describe('regionShares', () => {
    it('divides the shares held between regions, leaving out gold and property', () => {
        const regions = regionShares(rows, universe)
        expect(regions.map((r) => r.key)).toEqual(['us_equity', 'europe_ex_uk_equity', 'uk_equity', 'emerging_market_equity', 'asia_pacific_equity'])
        expect(regions.reduce((sum, r) => sum + r.weight, 0)).toBeCloseTo(1, 10)
        expect(regions[0]).toMatchObject({ label: 'US shares', detail: 'VUAG.L' })
        expect(regions[0].weight).toBeCloseTo(0.4479 / 0.6501, 10)
    })

    it('is empty when no shares are held', () => {
        expect(regionShares(rows.filter((r) => r.sleeve === 'defensive'), universe)).toEqual([])
    })
})

describe('heldCorrelations', () => {
    it('keeps only the funds held, in the order of the list', () => {
        const { labels, matrix } = heldCorrelations(snapshot, rows)
        expect(labels.map((l) => l.short)).toEqual(['VUAG.L', 'VERX.L', 'ISF.L', 'SGLN.L', 'VFEM.L', 'VAPX.L', 'AGBP.L', 'ERNS.L'])
        expect(labels[0].label).toBe('US shares')
        expect(matrix.map((r, i) => r[i])).toEqual(Array(8).fill(1))
        expect(matrix[1][2]).toBeCloseTo(0.7815, 4)
        expect(matrix[2][1]).toBe(matrix[1][2])
    })
})
