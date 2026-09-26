import { describe, expect, it } from 'vitest'
import type { History } from '@/api/schemas'
import * as fx from '@/test/fixtures'
import {
    annualised,
    availablePeriods,
    drawdowns,
    holdingGains,
    monthsBefore,
    performanceSentence,
    periodReturn,
    periodStart,
    pointsFor,
    sumOf,
    worstFall,
} from './model'

const point = (date: string, cumulative: number, value = 100_000 * (1 + cumulative)) => ({
    date,
    value,
    net_contributions: 100_000,
    cumulative_return: cumulative,
})

/** Opened in January; the late-June close starts the 3 months, the late-August one the month. */
const points = [point('2026-01-02', 0), point('2026-06-26', 0.1), point('2026-08-26', -0.01), point('2026-09-25', 0.05), point('2026-09-26', 0.12)]

const history = (pts: History['points'], reason: string | null = null): History => ({
    portfolio_id: 19,
    points: pts,
    start_date: pts[0]?.date ?? null,
    end_date: pts[pts.length - 1]?.date ?? null,
    time_weighted_return: pts[pts.length - 1]?.cumulative_return ?? null,
    reason,
    unpriced_tickers: [],
})

describe('monthsBefore', () => {
    it.each([
        ['2026-09-26', 1, '2026-08-26'],
        ['2026-01-15', 1, '2025-12-15'],
        ['2026-09-26', 12, '2025-09-26'],
        ['2026-03-31', 1, '2026-02-28'],
        ['2024-03-31', 1, '2024-02-29'],
    ])('%s less %i month(s) is %s', (day, months, expected) => {
        expect(monthsBefore(day, months)).toBe(expected)
    })
})

describe('periodStart', () => {
    it('measures this year from the last close of the year before', () => {
        expect(periodStart('ytd', '2026-09-26')).toBe('2025-12-31')
    })

    it('counts back whole months, and has no start for "since opening"', () => {
        expect(periodStart('3m', '2026-09-26')).toBe('2026-06-26')
        expect(periodStart('1y', '2026-09-26')).toBe('2025-09-26')
        expect(periodStart('all', '2026-09-26')).toBeNull()
    })
})

describe('pointsFor', () => {
    it('starts a period from the last close on or before its start', () => {
        expect(pointsFor(points, '1m')?.map((p) => p.date)).toEqual(['2026-08-26', '2026-09-25', '2026-09-26'])
        expect(pointsFor(points, '3m')?.[0].date).toBe('2026-06-26')
    })

    it('is null when the history starts after the period does', () => {
        expect(pointsFor(points, '1y')).toBeNull()
        expect(pointsFor(points, 'ytd')).toBeNull()
        expect(pointsFor([], 'all')).toBeNull()
    })

    it('covers the whole history since opening', () => {
        expect(pointsFor(points, 'all')).toBe(points)
    })
})

describe('availablePeriods', () => {
    it('offers only the periods the history covers, always ending with since opening', () => {
        expect(availablePeriods(points)).toEqual(['1m', '3m', 'all'])
        expect(availablePeriods([])).toEqual(['all'])
    })
})

describe('periodReturn', () => {
    it('chains the time-weighted index across the period', () => {
        expect(periodReturn(points, '1m')).toBeCloseTo(1.12 / 0.99 - 1, 10)
        expect(periodReturn(points, '3m')).toBeCloseTo(1.12 / 1.1 - 1, 10)
    })

    it('reads "since opening" straight from the last cumulative return', () => {
        expect(periodReturn(points, 'all')).toBe(0.12)
        expect(periodReturn([], 'all')).toBeNull()
    })

    it('is null for a period the history does not cover', () => {
        expect(periodReturn(points, '1y')).toBeNull()
        expect(periodReturn([point('2026-09-26', 0)], '1m')).toBeNull()
    })
})

describe('drawdowns and worstFall', () => {
    it('measures each close against the highest before it', () => {
        const falls = drawdowns(points)
        expect(falls.map((v) => Number(v.toFixed(4)))).toEqual([0, 0, -0.1, -0.0455, 0])
    })

    it('finds the deepest fall and the day it bottomed', () => {
        const fall = worstFall(points)
        expect(fall?.value).toBeCloseTo(-0.1, 10)
        expect(fall?.date).toBe('2026-08-26')
    })

    it('is null when the portfolio has only risen, or has no history', () => {
        expect(worstFall([point('2026-01-02', 0), point('2026-01-05', 0.01)])).toBeNull()
        expect(worstFall([])).toBeNull()
    })
})

describe('annualised', () => {
    it('turns a return over two years into a yearly rate', () => {
        expect(annualised(0.21, '2024-01-01', '2026-01-01')).toBeCloseTo(0.1, 3)
    })

    it('refuses to annualise less than a year', () => {
        expect(annualised(0.05, '2026-01-01', '2026-12-30')).toBeNull()
    })
})

describe('performanceSentence', () => {
    it('gives the reason when there are no values yet', () => {
        expect(performanceSentence(history([], 'Opened before trades were recorded.'))).toBe('Opened before trades were recorded.')
        expect(performanceSentence(history([]))).toBe('No values have been recorded for this portfolio yet.')
    })

    it('explains a single day of history', () => {
        expect(performanceSentence(history([point('2026-09-26', -0.001, 99_900)]))).toBe(
            "Opened on 26 Sept 2026. Its value is recorded at each day's close, so there is one so far: £99,900 against £100,000 paid in.",
        )
    })

    it('reads the return and the worst fall', () => {
        expect(performanceSentence(history(points))).toBe(
            'Since it opened on 2 Jan 2026, it has returned +12.0% and is worth £112,000 against £100,000 paid in. Its worst fall from a high was 10.0%.',
        )
    })

    it('says so when it has never fallen', () => {
        expect(performanceSentence(history([point('2026-01-02', 0), point('2026-01-05', 0.01)]))).toMatch(/It has not yet fallen below a previous high\.$/)
    })
})

describe('holdingGains', () => {
    const holding = fx.performance.holdings[0]
    const performance = {
        ...fx.performance,
        holdings: [
            { ...holding, ticker: 'SMALL.L', units: 10, average_cost: 50, current_value: 600, unrealised_pnl: 100 },
            holding,
            { ...holding, ticker: 'GIFT.L', units: 0, average_cost: 0, current_value: 0, unrealised_pnl: 0 },
        ],
    }

    it('puts the largest holding first, with its gain on its own cost and on the money paid in', () => {
        const [first, second] = holdingGains(performance)
        expect(first).toMatchObject({ ticker: 'VWRL.L', value: 62_240, cost: 40_000, gain: 22_240, sleeve: 'growth' })
        expect(first.gainOnCost).toBeCloseTo(0.556, 3)
        expect(first.addedToReturn).toBeCloseTo(0.2224, 4)
        expect(second).toMatchObject({ ticker: 'SMALL.L', cost: 500, gainOnCost: 0.2 })
    })

    it('leaves the rates empty when there is nothing to divide by', () => {
        const gift = holdingGains({ ...performance, net_contributions: 0 }).find((g) => g.ticker === 'GIFT.L')
        expect(gift).toMatchObject({ gainOnCost: null, addedToReturn: null })
    })

    it('sums a column', () => {
        expect(sumOf(holdingGains(performance), (g) => g.gain)).toBe(22_340)
    })
})
