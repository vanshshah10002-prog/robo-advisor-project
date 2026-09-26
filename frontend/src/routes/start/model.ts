/**
 * Onboarding: what is asked where, how answers are checked, and how they
 * become the risk-profile request. Pure, so every rule is unit-tested.
 *
 * Each question is asked once. The questionnaire's horizon question (3) is
 * answered by the number of years given in the goal section, and the
 * emergency-savings question (6) also answers the capacity check's
 * "emergency fund" field.
 */
import { riskProfileRequestSchema, type ObjectiveInputs, type RiskProfileRequest } from '@/api/schemas'
import { money } from '@/lib/format'
import type { OnboardingDraft } from '@/store/session'

export type SectionKey = 'goals' | 'losses' | 'finances'

export interface Section {
    key: SectionKey
    path: string
    title: string
    intro: string
    /** Questionnaire items shown in this section, by id, in order. */
    questionIds: readonly number[]
}

export const SECTIONS: readonly Section[] = [
    {
        key: 'goals',
        path: '/start',
        title: 'Your goal',
        intro: 'What the money is for and when you will need it. This sets how long it can stay invested.',
        questionIds: [2, 9],
    },
    {
        key: 'losses',
        path: '/start/losses',
        title: 'Ups and downs',
        intro: 'How you feel when prices fall. There are no right answers; honest ones give a portfolio you can stick with.',
        questionIds: [1, 10, 5, 8],
    },
    {
        key: 'finances',
        path: '/start/finances',
        title: 'Your finances',
        intro: 'What you could afford to lose. Rough figures are fine; nothing here is checked or shared.',
        questionIds: [7, 6, 4],
    },
]

export const RESULT_PATH = '/start/result'

/** Question id → what it is about, for "Choose an answer about …". */
const TOPIC: Record<number, string> = {
    1: 'a 20% fall',
    2: 'your main goal',
    4: 'how much of your wealth this is',
    5: 'your investment knowledge',
    6: 'your emergency savings',
    7: 'how steady your income is',
    8: 'your experience with shares',
    9: 'the return you expect',
    10: 'short-term ups and downs',
}

export const EMPLOYMENT = [
    { value: 'employed', label: 'Employed' },
    { value: 'self_employed', label: 'Self-employed' },
    { value: 'retired', label: 'Retired' },
    { value: 'student', label: 'Student' },
] as const

export const MAX_HORIZON_YEARS = 50
const QUESTION_COUNT = 10
const HORIZON_QUESTION = 3
const EMERGENCY_QUESTION = 6

export const fieldId = {
    name: 'name',
    horizon: 'horizon',
    amount: 'amount',
    savings: 'savings',
    income: 'income',
    spending: 'spending',
    employment: 'employment',
    isa: 'isa',
    question: (id: number) => `q-${id}`,
} as const

/** Years until the money is needed → the questionnaire's horizon answer (1–5). */
export function horizonAnswer(years: number): number {
    if (years < 1) return 1
    if (years < 3) return 2
    if (years < 5) return 3
    if (years < 10) return 4
    return 5
}

/** The emergency-savings answer (1–5) → the capacity check's three levels. */
export function emergencyFund(answer: number): ObjectiveInputs['has_emergency_fund'] {
    if (answer <= 1) return 'no'
    if (answer === 2) return 'partial'
    return 'yes'
}

export interface Problem {
    id: string
    message: string
}

const isPositive = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0
const isNonNegative = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0

function unanswered(ids: readonly number[], draft: OnboardingDraft): Problem[] {
    return ids
        .filter((id) => !draft.answers[String(id)])
        .map((id) => ({ id: fieldId.question(id), message: `Choose an answer about ${TOPIC[id]}.` }))
}

function goalProblems(draft: OnboardingDraft): Problem[] {
    const years = draft.objective.time_horizon_years
    const problems: Problem[] = []
    if (!draft.name.trim()) problems.push({ id: fieldId.name, message: 'Tell us what to call you.' })
    if (!Number.isInteger(years) || (years as number) < 1 || (years as number) > MAX_HORIZON_YEARS) {
        problems.push({ id: fieldId.horizon, message: `Enter how many years until you need the money, from 1 to ${MAX_HORIZON_YEARS}.` })
    }
    return [...problems, ...unanswered(SECTIONS[0].questionIds, draft)]
}

function financeProblems(draft: OnboardingDraft): Problem[] {
    const { objective: o, investmentAmount: amount } = draft
    const problems: Problem[] = []
    if (!isPositive(amount)) problems.push({ id: fieldId.amount, message: 'Enter the amount you want to invest, like 10,000.' })
    if (!isNonNegative(o.total_investable_assets)) {
        problems.push({ id: fieldId.savings, message: 'Enter your savings and investments in total, including this amount.' })
    } else if (isPositive(amount) && o.total_investable_assets < amount) {
        problems.push({ id: fieldId.savings, message: `Your savings in total should include the ${money(amount)} you plan to invest.` })
    }
    if (!isPositive(o.monthly_income)) problems.push({ id: fieldId.income, message: 'Enter your monthly income after tax.' })
    if (!isNonNegative(o.monthly_expenses)) problems.push({ id: fieldId.spending, message: 'Enter what you spend in a month, or 0.' })
    if (!o.employment_type) problems.push({ id: fieldId.employment, message: 'Choose how you earn your living.' })
    if (draft.usesIsa === null) problems.push({ id: fieldId.isa, message: 'Choose whether you will invest through an ISA.' })
    return [...problems, ...unanswered(SECTIONS[2].questionIds, draft)]
}

/** Everything wrong with one section, in the order the fields appear. */
export function validateSection(key: SectionKey, draft: OnboardingDraft): Problem[] {
    if (key === 'goals') return goalProblems(draft)
    if (key === 'losses') return unanswered(SECTIONS[1].questionIds, draft)
    return financeProblems(draft)
}

/** The first section that still has a problem, or null when all are complete. */
export function firstIncomplete(draft: OnboardingDraft): Section | null {
    return SECTIONS.find((s) => validateSection(s.key, draft).length > 0) ?? null
}

/** The request for POST /risk-profile, or null while any section is incomplete. */
export function buildProfileRequest(draft: OnboardingDraft): RiskProfileRequest | null {
    if (firstIncomplete(draft)) return null
    const o = draft.objective
    const years = o.time_horizon_years as number
    const answer = (id: number) => (id === HORIZON_QUESTION ? horizonAnswer(years) : draft.answers[String(id)])
    const parsed = riskProfileRequestSchema.safeParse({
        name: draft.name.trim(),
        quiz_answers: Array.from({ length: QUESTION_COUNT }, (_, i) => ({ question_id: i + 1, answer: answer(i + 1) })),
        objective_inputs: {
            monthly_income: o.monthly_income,
            monthly_expenses: o.monthly_expenses,
            total_investable_assets: o.total_investable_assets,
            investment_amount: draft.investmentAmount,
            employment_type: o.employment_type,
            time_horizon_years: years,
            has_emergency_fund: emergencyFund(draft.answers[String(EMERGENCY_QUESTION)]),
        },
        uses_isa: draft.usesIsa,
    })
    return parsed.success ? parsed.data : null
}
