import { describe, expect, it } from 'vitest'
import { EMPTY_DRAFT, type OnboardingDraft } from '@/store/session'
import * as fx from '@/test/fixtures'
import {
    buildProfileRequest,
    emergencyFund,
    fieldId,
    firstIncomplete,
    horizonAnswer,
    validateSection,
} from './model'

const completeDraft: OnboardingDraft = { ...fx.completeDraft, name: ' Ada ' }

const ids = (draft: OnboardingDraft, key: Parameters<typeof validateSection>[0]) =>
    validateSection(key, draft).map((p) => p.id)

describe('horizonAnswer', () => {
    it.each([
        [0, 1],
        [1, 2],
        [2, 2],
        [3, 3],
        [4, 3],
        [5, 4],
        [9, 4],
        [10, 5],
        [40, 5],
    ])('%i years answers the horizon question with %i', (years, answer) => {
        expect(horizonAnswer(years)).toBe(answer)
    })
})

describe('emergencyFund', () => {
    it('maps the savings answer onto the capacity check', () => {
        expect(emergencyFund(1)).toBe('no')
        expect(emergencyFund(2)).toBe('partial')
        expect(emergencyFund(3)).toBe('yes')
        expect(emergencyFund(5)).toBe('yes')
    })
})

describe('validateSection', () => {
    it('passes a complete draft in every section', () => {
        expect(firstIncomplete(completeDraft)).toBeNull()
    })

    it('lists every missing goal answer in field order', () => {
        expect(ids(EMPTY_DRAFT, 'goals')).toEqual([fieldId.name, fieldId.horizon, 'q-2', 'q-9'])
    })

    it('rejects a horizon outside 1–50 years or not whole', () => {
        for (const years of [0, 51, 2.5]) {
            const draft = { ...completeDraft, objective: { ...completeDraft.objective, time_horizon_years: years } }
            expect(ids(draft, 'goals')).toEqual([fieldId.horizon])
        }
    })

    it('treats a name of spaces as missing', () => {
        expect(ids({ ...completeDraft, name: '   ' }, 'goals')).toEqual([fieldId.name])
    })

    it('asks for each of the four questions about losses', () => {
        expect(ids(EMPTY_DRAFT, 'losses')).toEqual(['q-1', 'q-10', 'q-5', 'q-8'])
    })

    it('lists every missing finance field', () => {
        expect(ids(EMPTY_DRAFT, 'finances')).toEqual([
            fieldId.amount,
            fieldId.savings,
            fieldId.income,
            fieldId.spending,
            fieldId.employment,
            fieldId.isa,
            'q-7',
            'q-6',
            'q-4',
        ])
    })

    it('says total savings must include the amount invested', () => {
        const draft = { ...completeDraft, objective: { ...completeDraft.objective, total_investable_assets: 20_000 } }
        expect(validateSection('finances', draft)).toEqual([
            { id: fieldId.savings, message: 'Your savings in total should include the £50,000 you plan to invest.' },
        ])
    })

    it('accepts zero spending and zero savings beyond the amount, but not zero income', () => {
        const draft = {
            ...completeDraft,
            investmentAmount: 1_000,
            objective: { ...completeDraft.objective, monthly_expenses: 0, total_investable_assets: 1_000, monthly_income: 0 },
        }
        expect(ids(draft, 'finances')).toEqual([fieldId.income])
    })

    it('finds the first incomplete section', () => {
        const noLosses = { ...completeDraft, answers: { ...completeDraft.answers, 10: 0 } }
        expect(firstIncomplete(noLosses)?.key).toBe('losses')
        expect(firstIncomplete(EMPTY_DRAFT)?.key).toBe('goals')
    })
})

describe('buildProfileRequest', () => {
    it('builds all ten answers, deriving the horizon and the emergency fund', () => {
        const request = buildProfileRequest(completeDraft)
        expect(request).not.toBeNull()
        expect(request?.name).toBe('Ada')
        expect(request?.quiz_answers.map((a) => a.answer)).toEqual([3, 4, 5, 2, 3, 4, 4, 3, 3, 4])
        expect(request?.objective_inputs).toEqual({
            monthly_income: 3_200,
            monthly_expenses: 2_100,
            total_investable_assets: 80_000,
            investment_amount: 50_000,
            employment_type: 'employed',
            time_horizon_years: 15,
            has_emergency_fund: 'yes',
        })
        expect(request?.uses_isa).toBe(true)
    })

    it('builds nothing while a section is incomplete', () => {
        expect(buildProfileRequest(EMPTY_DRAFT)).toBeNull()
        expect(buildProfileRequest({ ...completeDraft, usesIsa: null })).toBeNull()
    })
})
