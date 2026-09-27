import { beforeEach, describe, expect, it } from 'vitest'
import { EMPTY_DRAFT, useIdentity, useOnboardingDraft } from './session'

beforeEach(() => {
    useIdentity.getState().forget()
    useOnboardingDraft.getState().reset()
})

describe('useIdentity', () => {
    it('remembers the user and portfolio in localStorage', () => {
        useIdentity.getState().setUser(4)
        useIdentity.getState().setLastPortfolio(19)

        const stored = JSON.parse(localStorage.getItem('ukra.identity') ?? '{}')
        expect(stored.state).toEqual({ userId: 4, lastPortfolioId: 19 })
    })

    it('clears the portfolio when a different user signs in', () => {
        useIdentity.getState().setUser(4)
        useIdentity.getState().setLastPortfolio(19)
        useIdentity.getState().setUser(5)

        expect(useIdentity.getState()).toMatchObject({ userId: 5, lastPortfolioId: null })
    })

    it('keeps the portfolio when the same user is set again', () => {
        useIdentity.getState().setUser(4)
        useIdentity.getState().setLastPortfolio(19)
        useIdentity.getState().setUser(4)

        expect(useIdentity.getState().lastPortfolioId).toBe(19)
    })

    it('restores valid stored state', async () => {
        localStorage.setItem('ukra.identity', JSON.stringify({ state: { userId: 2, lastPortfolioId: 8 }, version: 1 }))
        await useIdentity.persist.rehydrate()
        expect(useIdentity.getState()).toMatchObject({ userId: 2, lastPortfolioId: 8 })
    })

    it('discards malformed stored state instead of crashing', async () => {
        localStorage.setItem('ukra.identity', JSON.stringify({ state: { userId: 'two' }, version: 1 }))
        await useIdentity.persist.rehydrate()
        expect(useIdentity.getState()).toMatchObject({ userId: null, lastPortfolioId: null })
    })
})

describe('useOnboardingDraft', () => {
    it('keeps the draft in sessionStorage, not localStorage', () => {
        useOnboardingDraft.getState().update({ name: 'Sam', investmentAmount: 10_000 })

        expect(sessionStorage.getItem('ukra.onboarding')).toContain('"name":"Sam"')
        expect(localStorage.getItem('ukra.onboarding')).toBeNull()
    })

    it('records answers without dropping earlier ones', () => {
        const { answer } = useOnboardingDraft.getState()
        answer(1, 3)
        answer('loss_reaction', 5)
        answer(1, 4)

        expect(useOnboardingDraft.getState().answers).toEqual({ '1': 4, loss_reaction: 5 })
    })

    it('persists data only, not actions', () => {
        useOnboardingDraft.getState().update({ usesIsa: true })
        const stored = JSON.parse(sessionStorage.getItem('ukra.onboarding') ?? '{}')

        expect(Object.keys(stored.state).sort()).toEqual(Object.keys(EMPTY_DRAFT).sort())
    })

    it('resets to an empty draft', () => {
        useOnboardingDraft.getState().update({ name: 'Sam', chosenRiskScore: 6 })
        useOnboardingDraft.getState().reset()

        expect(useOnboardingDraft.getState()).toMatchObject(EMPTY_DRAFT)
    })

    it('discards a stored draft with out-of-range answers', async () => {
        const bad = { ...EMPTY_DRAFT, name: 'Old', answers: { '1': 9 } }
        sessionStorage.setItem('ukra.onboarding', JSON.stringify({ state: bad, version: 1 }))
        await useOnboardingDraft.persist.rehydrate()

        expect(useOnboardingDraft.getState().name).toBe('')
    })
})
