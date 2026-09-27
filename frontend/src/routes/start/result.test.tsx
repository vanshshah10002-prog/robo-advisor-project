import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { useIdentity, useOnboardingDraft } from '@/store/session'
import { renderApp, stubApi, warmPages } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./StartLayout'),
    () => import('./ResultPage'),
    () => import('./GoalsPage'),
)

const location = () => screen.getByTestId('location').textContent
const between = { ...fx.riskProfile, composite_score: 5.5, risk_score_int: 6 }

function signIn(draft = fx.completeDraft) {
    useIdentity.getState().setUser(4)
    useOnboardingDraft.setState(draft)
}

describe('the risk level result', () => {
    it('sends you to the start without an identity', async () => {
        stubApi({ '/api/quiz-questions': fx.quiz })
        renderApp('/start/result')
        await screen.findByRole('heading', { level: 1, name: 'Your goal' })
        expect(location()).toBe('/start')
    })

    it('sends you to the start when your profile no longer exists', async () => {
        stubApi({ '/api/quiz-questions': fx.quiz, '/api/risk-profile/4': { status: 404, body: { detail: 'No profile.' } } })
        signIn()
        renderApp('/start/result')
        await screen.findByRole('heading', { level: 1, name: 'Your goal' })
        expect(location()).toBe('/start')
    })

    it('explains the level, its split, and how far the nearest tested level has fallen', async () => {
        const calls = stubApi({
            '/api/risk-profile/4': between,
            'POST /api/portfolio/preview': { ...fx.preview, requested_risk_score: 5.5, risk_score: 5.5, capped: false },
            '/api/strategy/track-record': { ...fx.trackRecord, risk: 6 },
        })
        signIn()
        renderApp('/start/result')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Your risk level is 5.5 out of 10')
        expect(screen.getByText('Willingness to take risk').closest('div')).toHaveTextContent('5.2')
        expect(screen.getByText('Capacity for loss').closest('div')).toHaveTextContent('4.8')
        expect(screen.queryByText(/cannot go above 6/)).not.toBeInTheDocument()

        expect(await screen.findByText('What level 5.5 holds')).toBeInTheDocument()
        const fall = await screen.findByRole('region', { name: /How far level 6 has fallen before/ })
        expect(within(fall).getByText('−22.7%')).toBeInTheDocument()
        expect(within(fall).getByText('About −£11,374 on £50,000')).toBeInTheDocument()
        expect(within(fall).getByText('Worst calendar year, 2022')).toBeInTheDocument()
        expect(fall).toHaveTextContent('(the nearest tested level to your 5.5)')

        const preview = calls.find((c) => c.path === '/api/portfolio/preview')
        expect(preview?.body).toMatchObject({ user_id: 4, risk_score: 5.5, investment_amount: 50_000, monthly_contribution: 0 })
        expect(calls.find((c) => c.path === '/api/strategy/track-record')?.query.get('risk')).toBe('6')
        expect(screen.getByRole('link', { name: 'See your proposal' })).toHaveAttribute('href', '/proposal')
    })

    it('says a short horizon caps the level', async () => {
        stubApi({
            '/api/risk-profile/4': { ...fx.riskProfile, time_horizon_years: 3 },
            'POST /api/portfolio/preview': fx.preview,
            '/api/strategy/track-record': fx.trackRecord,
        })
        signIn()
        renderApp('/start/result')
        expect(await screen.findByText(/within 5 years, the level cannot go above 6/)).toBeInTheDocument()
        const fall = await screen.findByRole('region', { name: /How far level 5 has fallen before/ })
        expect(fall).not.toHaveTextContent('nearest tested level')
    })

    it('offers a retry when the profile does not load', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({
            '/api/risk-profile/4': () => (fail ? { status: 500, body: { detail: 'Database busy.' } } : fx.riskProfile),
            'POST /api/portfolio/preview': fx.preview,
            '/api/strategy/track-record': fx.trackRecord,
        })
        signIn()
        renderApp('/start/result')
        expect(await screen.findByText('Your risk level did not load')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Your risk level is 5 out of 10')
    })

    it('says so when the mix does not load, and still shows the level', async () => {
        stubApi({
            '/api/risk-profile/4': fx.riskProfile,
            'POST /api/portfolio/preview': { status: 503, body: { detail: 'Prices are updating.' } },
            '/api/strategy/track-record': fx.trackRecord,
        })
        signIn()
        renderApp('/start/result')
        expect(await screen.findByText('The mix for your level did not load')).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Your risk level is 5 out of 10')
    })
})
