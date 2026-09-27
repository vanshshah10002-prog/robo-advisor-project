import { describe, expect, it } from 'vitest'
import * as fx from '@/test/fixtures'
import { accuracyNote, lossSentence, MAX_YEARS, OUTLOOK_PATHS, outlookRequest, outlookSentence, validYears, type OutlookInputs } from './model'

const inputs: OutlookInputs = { years: 15, monthly: 250, goal: null, realTerms: true }

describe('validYears', () => {
    it.each([
        [1, true],
        [MAX_YEARS, true],
        [0, false],
        [MAX_YEARS + 1, false],
        [2.5, false],
        [null, false],
    ])('%s is %s', (years, ok) => {
        expect(validYears(years)).toBe(ok)
    })
})

describe('outlookRequest', () => {
    it('projects this portfolio from what it is worth now', () => {
        expect(outlookRequest(19, 124_518, inputs)).toEqual({
            portfolio_id: 19,
            initial_investment: 124_518,
            monthly_contribution: 250,
            years: 15,
            n_simulations: OUTLOOK_PATHS,
            real_terms: true,
        })
    })

    it('adds a goal only when one is set', () => {
        expect(outlookRequest(19, 124_518, { ...inputs, goal: 200_000, realTerms: false })).toMatchObject({ goal_amount: 200_000, real_terms: false })
    })

    it.each([
        ['a horizon out of range', { ...inputs, years: 0 }],
        ['a missing monthly amount', { ...inputs, monthly: null }],
        ['a negative monthly amount', { ...inputs, monthly: -5 }],
        ['a goal of nothing', { ...inputs, goal: 0 }],
    ])('is null for %s', (_, bad) => {
        expect(outlookRequest(19, 124_518, bad)).toBeNull()
    })

    it('is null when there is nothing to project', () => {
        expect(outlookRequest(19, 0, inputs)).toBeNull()
    })
})

describe('outlookSentence', () => {
    it('reads the median and the 80% probability range at the horizon', () => {
        expect(outlookSentence(fx.monteCarloReal)).toBe(
            'In 15 years, adjusted for inflation, the median projection is £141,357, with an 80% probability of ending between £99,505 and £206,015.',
        )
    })

    it('says when amounts are not adjusted for inflation, and reads a single year', () => {
        expect(outlookSentence(fx.monteCarlo)).toBe(
            'In 1 year, not adjusted for inflation, the median projection is £108,000, with an 80% probability of ending between £98,000 and £119,000.',
        )
    })
})

describe('lossSentence', () => {
    it('reads the probability of a loss falling over the years', () => {
        expect(lossSentence(fx.monteCarloReal)).toBe(
            'The probability of ending below the amount paid in falls from 37% after 1 year to 6% after 15 years.',
        )
    })

    it('reads a rise, and a probability that stays the same', () => {
        const years = [0, 1, 2]
        expect(lossSentence({ ...fx.monteCarlo, years, loss_probability_by_year: [0, 0.1, 0.2] })).toBe(
            'The probability of ending below the amount paid in rises from 10% after 1 year to 20% after 2 years.',
        )
        expect(lossSentence({ ...fx.monteCarlo, years, loss_probability_by_year: [0, 0.1, 0.1] })).toBe(
            'The probability of ending below the amount paid in stays at 10% throughout.',
        )
    })

    it('is null without a year to read', () => {
        expect(lossSentence({ ...fx.monteCarlo, years: [0], loss_probability_by_year: [0] })).toBeNull()
    })
})

describe('accuracyNote', () => {
    it('compares the backtest with a well-judged forecast', () => {
        expect(accuracyNote(fx.trackRecord)).toBe(
            'In the walk-forward backtest at risk level 5, 60% of yearly returns landed within one standard deviation of the return forecast ' +
                'at the time; if the volatility estimates were accurate, about 68% would.',
        )
    })

    it('is null when the backtest has no forecasts to check', () => {
        expect(accuracyNote({ ...fx.trackRecord, within_one_sigma: null })).toBeNull()
    })
})
