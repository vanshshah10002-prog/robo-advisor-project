import { describe, expect, it } from 'vitest'
import * as fx from '@/test/fixtures'
import { isUnrecorded, listSentence, overviewSentence, portfolioName } from './model'

describe('isUnrecorded', () => {
    it('is true only when nothing was paid in and nothing is valued', () => {
        expect(isUnrecorded({ net_contributions: 0, total_value: 0 })).toBe(true)
        expect(isUnrecorded({ net_contributions: 0, total_value: 12 })).toBe(false)
        expect(isUnrecorded({ net_contributions: 100, total_value: 0 })).toBe(false)
    })
})

describe('overviewSentence', () => {
    it('reads a gain', () => {
        expect(overviewSentence(fx.performance)).toBe(
            'Worth £124,518 on 25 Sept 2026: £24,518 more than the £100,000 paid in. Every holding is within its band.',
        )
    })

    it('reads a loss and a rebalance', () => {
        const p = { ...fx.performance, total_value: 99_500, needs_rebalance: true }
        expect(overviewSentence(p)).toBe(
            'Worth £99,500 on 25 Sept 2026: £500 less than the £100,000 paid in. It has drifted far enough from its targets to rebalance.',
        )
    })

    it('says "the same" when the change rounds to nothing, and leaves out a missing date', () => {
        const p = { ...fx.performance, total_value: 100_000.4, valued_at: null }
        expect(overviewSentence(p)).toBe('Worth £100,000: the same as the £100,000 paid in. Every holding is within its band.')
    })
})

describe('listSentence', () => {
    const row = fx.portfolioSummary

    it('counts one portfolio in the singular', () => {
        expect(listSentence([row])).toBe('1 portfolio, worth £124,518 together.')
    })

    it('adds only the valued ones, and says how many are not', () => {
        expect(listSentence([row, { ...row, total_value: 1_000 }, { ...row, total_value: null }])).toBe(
            '3 portfolios, worth £125,518 together (1 not valued).',
        )
    })

    it('says when none is valued yet', () => {
        expect(listSentence([{ ...row, total_value: null }, { ...row, total_value: null }])).toBe('2 portfolios, none valued yet.')
    })
})

describe('portfolioName', () => {
    it('uses a name of its own, and numbers the unnamed and the default', () => {
        expect(portfolioName({ portfolio_id: 3, name: ' House ' })).toBe('House')
        expect(portfolioName({ portfolio_id: 3, name: null })).toBe('Portfolio 3')
        expect(portfolioName({ portfolio_id: 3, name: '  ' })).toBe('Portfolio 3')
        expect(portfolioName({ portfolio_id: 3, name: 'My Portfolio' })).toBe('Portfolio 3')
    })
})
