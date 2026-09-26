import { describe, expect, it } from 'vitest'
import type { Preview, PreviewRequest } from '@/api/schemas'
import * as fx from '@/test/fixtures'
import { PROJECTION_PATHS, projectionRequest, proposalSentence } from './model'

const preview = fx.preview as Preview
const built: PreviewRequest = { user_id: 4, risk_score: 7, investment_amount: 50_000, monthly_contribution: 250, uses_isa: true }

describe('proposalSentence', () => {
    it('reads the amounts, the level, the split, the fund count and the cost', () => {
        expect(proposalSentence(preview, 50_000, 250)).toBe(
            '£50,000 now and £250 a month, at risk level 7: 70% in growth and 30% in defensive holdings, spread across 8 funds costing about £42 a year.',
        )
    })

    it('leaves out a monthly amount of nothing, and counts one fund in the singular', () => {
        const one = { ...preview, risk_score: 5.5, allocations: preview.allocations.slice(0, 1).map((a) => ({ ...a, weight: 1 })) }
        expect(proposalSentence(one, 10_000, 0)).toBe(
            '£10,000 now, at risk level 5.5: 100% in growth and 0% in defensive holdings, spread across 1 fund costing about £42 a year.',
        )
    })
})

describe('projectionRequest', () => {
    it('simulates the built amounts from the preview, in today’s money', () => {
        expect(projectionRequest(preview, built, 15)).toEqual({
            annual_return: preview.expected_annual_return,
            annual_volatility: preview.expected_volatility,
            initial_investment: 50_000,
            monthly_contribution: 250,
            years: 15,
            n_simulations: PROJECTION_PATHS,
            real_terms: true,
        })
    })

    it('keeps the horizon to whole years from 1 to 50', () => {
        expect(projectionRequest(preview, built, 0).years).toBe(1)
        expect(projectionRequest(preview, built, 7.6).years).toBe(8)
        expect(projectionRequest(preview, built, 80).years).toBe(50)
    })
})
