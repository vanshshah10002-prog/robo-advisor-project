/**
 * Zustand Global State Store
 * ===========================
 * Central state for the robo advisor flow:
 * - Onboarding quiz answers + risk profile
 * - Selected asset classes
 * - Investment parameters
 * - Portfolio allocations
 * - User preferences
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// --- Types ---

export interface QuizAnswer {
    question_id: number
    answer: number
}

export interface ObjectiveInputs {
    monthly_income: number
    monthly_expenses: number
    total_investable_assets: number
    investment_amount: number
    employment_type: string
    time_horizon_years: number
    has_emergency_fund: string
}

export interface RiskProfile {
    user_id: number
    subjective_score: number
    objective_score: number
    composite_score: number
    risk_band: string
    risk_score_int: number
    time_horizon_years: number
    uses_isa: boolean
    description: string
}

export interface Allocation {
    asset_class: string
    weight: number
    ticker: string
    etf_name: string
    expense_ratio: number
    amount_gbp: number
}

export interface PortfolioResult {
    portfolio_id: number
    risk_score: number
    risk_band: string
    allocations: Allocation[]
    expected_annual_return: number
    expected_volatility: number
    sharpe_ratio: number
    total_expense_ratio: number
    investment_amount: number
}

// --- Store State ---

interface AdvisorState {
    // Flow
    currentStep: number
    userName: string

    // Onboarding
    quizAnswers: QuizAnswer[]
    objectiveInputs: ObjectiveInputs | null
    riskProfile: RiskProfile | null
    usesIsa: boolean

    // Asset selection
    selectedAssetClasses: string[]

    // Investment
    investmentAmount: number
    monthlyContribution: number

    // Portfolio
    adjustedRiskScore: number | null
    portfolioResult: PortfolioResult | null

    // Actions
    setCurrentStep: (step: number) => void
    setUserName: (name: string) => void
    setQuizAnswer: (questionId: number, answer: number) => void
    setObjectiveInputs: (inputs: ObjectiveInputs) => void
    setRiskProfile: (profile: RiskProfile) => void
    setUsesIsa: (uses: boolean) => void
    toggleAssetClass: (assetClass: string) => void
    setSelectedAssetClasses: (classes: string[]) => void
    setInvestmentAmount: (amount: number) => void
    setMonthlyContribution: (amount: number) => void
    setAdjustedRiskScore: (score: number) => void
    setPortfolioResult: (result: PortfolioResult) => void
    resetAll: () => void
}

const initialState = {
    currentStep: 0,
    userName: '',
    quizAnswers: [],
    objectiveInputs: null,
    riskProfile: null,
    usesIsa: false,
    selectedAssetClasses: [],
    investmentAmount: 10000,
    monthlyContribution: 0,
    adjustedRiskScore: null,
    portfolioResult: null,
}

export const useAdvisorStore = create<AdvisorState>()(
    persist(
        (set) => ({
            ...initialState,

            setCurrentStep: (step) => set({ currentStep: step }),

            setUserName: (name) => set({ userName: name }),

            setQuizAnswer: (questionId, answer) =>
                set((state) => {
                    const existing = state.quizAnswers.filter(
                        (a) => a.question_id !== questionId
                    )
                    return { quizAnswers: [...existing, { question_id: questionId, answer }] }
                }),

            setObjectiveInputs: (inputs) => set({ objectiveInputs: inputs }),

            setRiskProfile: (profile) =>
                set({
                    riskProfile: profile,
                    adjustedRiskScore: profile.risk_score_int,
                }),

            setUsesIsa: (uses) => set({ usesIsa: uses }),

            toggleAssetClass: (assetClass) =>
                set((state) => {
                    const current = state.selectedAssetClasses
                    if (current.includes(assetClass)) {
                        return { selectedAssetClasses: current.filter((c) => c !== assetClass) }
                    }
                    return { selectedAssetClasses: [...current, assetClass] }
                }),

            setSelectedAssetClasses: (classes) =>
                set({ selectedAssetClasses: classes }),

            setInvestmentAmount: (amount) => set({ investmentAmount: amount }),

            setMonthlyContribution: (amount) =>
                set({ monthlyContribution: amount }),

            setAdjustedRiskScore: (score) => set({ adjustedRiskScore: score }),

            setPortfolioResult: (result) => set({ portfolioResult: result }),

            resetAll: () => set(initialState),
        }),
        {
            name: 'uk-robo-advisor-store',
        }
    )
)
