/**
 * Client session state
 * ====================
 * The server owns portfolios, holdings and valuations (fetched through
 * react-query). The client keeps only two small things:
 *
 * - `useIdentity`: which user and portfolio this browser is looking at.
 *   localStorage, so a returning visitor lands on their portfolio.
 * - `useOnboardingDraft`: answers typed during onboarding, so a reload does
 *   not lose them. sessionStorage, so they do not outlive the tab.
 *
 * Persisted state is validated on load; anything malformed or from an older
 * shape is discarded instead of crashing a page.
 */

import { z } from 'zod'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { objectiveInputsSchema } from '@/api/schemas'

const id = z.number().int().positive()

// ─── Identity ────────────────────────────────────────────────────────────────

const identitySchema = z.object({
    userId: id.nullable(),
    lastPortfolioId: id.nullable(),
})

type Identity = z.infer<typeof identitySchema>

interface IdentityActions {
    setUser: (userId: number) => void
    setLastPortfolio: (portfolioId: number | null) => void
    forget: () => void
}

const EMPTY_IDENTITY: Identity = { userId: null, lastPortfolioId: null }

export const useIdentity = create<Identity & IdentityActions>()(
    persist(
        (set) => ({
            ...EMPTY_IDENTITY,
            setUser: (userId) =>
                set((s) => (s.userId === userId ? s : { userId, lastPortfolioId: null })),
            setLastPortfolio: (lastPortfolioId) => set({ lastPortfolioId }),
            forget: () => set(EMPTY_IDENTITY),
        }),
        {
            name: 'ukra.identity',
            version: 1,
            storage: createJSONStorage(() => localStorage),
            partialize: ({ userId, lastPortfolioId }) => ({ userId, lastPortfolioId }),
            merge: (persisted, current) => {
                const parsed = identitySchema.safeParse(persisted)
                return parsed.success ? { ...current, ...parsed.data } : current
            },
        },
    ),
)

// ─── Onboarding draft ────────────────────────────────────────────────────────

const draftSchema = z.object({
    name: z.string(),
    /** Likert answers keyed by question id (full quiz) or key (minimal quiz). */
    answers: z.record(z.string(), z.number().int().min(1).max(5)),
    objective: objectiveInputsSchema.partial(),
    investmentAmount: z.number().positive().nullable(),
    monthlyContribution: z.number().nonnegative(),
    usesIsa: z.boolean().nullable(),
    /** The score the investor settled on, capped by their profile. */
    chosenRiskScore: z.number().min(1).max(10).nullable(),
})

export type OnboardingDraft = z.infer<typeof draftSchema>

interface DraftActions {
    update: (patch: Partial<OnboardingDraft>) => void
    answer: (question: string | number, value: number) => void
    reset: () => void
}

export const EMPTY_DRAFT: OnboardingDraft = {
    name: '',
    answers: {},
    objective: {},
    investmentAmount: null,
    monthlyContribution: 0,
    usesIsa: null,
    chosenRiskScore: null,
}

export const useOnboardingDraft = create<OnboardingDraft & DraftActions>()(
    persist(
        (set) => ({
            ...EMPTY_DRAFT,
            update: (patch) => set(patch),
            answer: (question, value) => set((s) => ({ answers: { ...s.answers, [String(question)]: value } })),
            reset: () => set(EMPTY_DRAFT),
        }),
        {
            name: 'ukra.onboarding',
            version: 1,
            storage: createJSONStorage(() => sessionStorage),
            partialize: ({ update: _u, answer: _a, reset: _r, ...draft }) => draft,
            merge: (persisted, current) => {
                const parsed = draftSchema.safeParse(persisted)
                return parsed.success ? { ...current, ...parsed.data } : current
            },
        },
    ),
)
