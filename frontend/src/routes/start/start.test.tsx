import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { useIdentity, useOnboardingDraft } from '@/store/session'
import { renderApp, stubApi, warmPages } from '@/test/app'
import * as fx from '@/test/fixtures'

type User = ReturnType<typeof userEvent.setup>

const location = () => screen.getByTestId('location').textContent

async function answer(user: User, legend: RegExp, option: number) {
    const group = screen.getByRole('group', { name: legend })
    await user.click(within(group).getAllByRole('radio')[option - 1])
}

const journeyApi = () =>
    stubApi({
        '/api/quiz-questions': fx.quiz,
        'POST /api/risk-profile': fx.riskProfile,
        '/api/risk-profile/4': fx.riskProfile,
        'POST /api/portfolio/preview': fx.preview,
        '/api/strategy/track-record': fx.trackRecord,
    })

warmPages(
    () => import('./StartLayout'),
    () => import('./GoalsPage'),
    () => import('./LossesPage'),
    () => import('./FinancesPage'),
    () => import('./ResultPage'),
)

describe('onboarding', () => {
    it('walks the three steps and sends every answer once', async () => {
        const user = userEvent.setup()
        const calls = journeyApi()
        renderApp('/start')

        await screen.findByRole('heading', { level: 1, name: 'Your goal' })
        await user.type(screen.getByLabelText('What should we call you?'), 'Ada')
        await user.type(screen.getByLabelText(/When will you need most/), '15')
        await answer(user, /primary investment goal/, 4)
        await answer(user, /annual return do you expect/, 3)
        await user.click(screen.getByRole('button', { name: 'Continue' }))

        await screen.findByRole('heading', { level: 1, name: 'Ups and downs' })
        await answer(user, /dropped 20%/, 3)
        await answer(user, /short-term volatility/, 4)
        await answer(user, /investment knowledge/, 3)
        await answer(user, /invested in equities/, 3)
        await user.click(screen.getByRole('button', { name: 'Continue' }))

        await screen.findByRole('heading', { level: 1, name: 'Your finances' })
        await user.type(screen.getByLabelText('How much do you want to invest now?'), '50,000')
        await user.type(screen.getByLabelText('Your savings and investments in total'), '80000')
        await user.type(screen.getByLabelText('Monthly income after tax'), '3,200')
        await user.type(screen.getByLabelText('Monthly spending'), '2100')
        await user.click(screen.getByRole('radio', { name: 'Employed' }))
        await answer(user, /stable is your income/, 4)
        await answer(user, /emergency savings/, 4)
        await answer(user, /net worth/, 2)
        await user.click(screen.getByRole('radio', { name: 'Yes, an ISA' }))
        await user.click(screen.getByRole('button', { name: 'See my risk level' }))

        await screen.findByRole('heading', { level: 1, name: /Your risk level is/ })
        expect(location()).toBe('/start/result')
        expect(document.title).toBe('Your risk level · UK Robo Advisor')
        expect(screen.getByRole('main')).toHaveFocus()
        expect(useIdentity.getState().userId).toBe(4)

        const submitted = calls.filter((c) => c.method === 'POST' && c.path === '/api/risk-profile')
        expect(submitted).toHaveLength(1)
        expect(submitted[0].body).toEqual({
            name: 'Ada',
            quiz_answers: [3, 4, 5, 2, 3, 4, 4, 3, 3, 4].map((a, i) => ({ question_id: i + 1, answer: a })),
            objective_inputs: {
                monthly_income: 3_200,
                monthly_expenses: 2_100,
                total_investable_assets: 80_000,
                investment_amount: 50_000,
                employment_type: 'employed',
                time_horizon_years: 15,
                has_emergency_fund: 'yes',
            },
            uses_isa: true,
        })
    })

    it('lists every problem at the top, takes focus there, and links to each field', async () => {
        const user = userEvent.setup()
        journeyApi()
        renderApp('/start')
        await screen.findByRole('group', { name: /primary investment goal/ })
        await user.click(screen.getByRole('button', { name: 'Continue' }))

        const summary = await screen.findByRole('alert')
        expect(summary).toHaveFocus()
        const links = within(summary).getAllByRole('link')
        expect(links.map((l) => l.textContent)).toEqual([
            'Tell us what to call you.',
            'Enter how many years until you need the money, from 1 to 50.',
            'Choose an answer about your main goal.',
            'Choose an answer about the return you expect.',
        ])
        await user.click(links[1])
        expect(screen.getByLabelText(/When will you need most/)).toHaveFocus()
        expect(location()).toBe('/start')
    })

    it('updates the profile of the user this browser already has, rather than starting another', async () => {
        const user = userEvent.setup()
        const calls = journeyApi()
        useIdentity.getState().setUser(4)
        useOnboardingDraft.setState(fx.completeDraft)
        renderApp('/start/finances')

        await screen.findByRole('group', { name: /stable is your income/ })
        await user.click(screen.getByRole('button', { name: 'See my risk level' }))
        await screen.findByRole('heading', { level: 1, name: /Your risk level is/ })
        const submitted = calls.find((c) => c.method === 'POST' && c.path === '/api/risk-profile')
        expect(submitted?.body).toMatchObject({ user_id: 4, name: 'Ada' })
    })

    it('says so and keeps the answers when the risk level cannot be worked out', async () => {
        const user = userEvent.setup()
        stubApi({ '/api/quiz-questions': fx.quiz, 'POST /api/risk-profile': { status: 500, body: { detail: 'Profiler unavailable.' } } })
        useOnboardingDraft.setState(fx.completeDraft)
        renderApp('/start/finances')

        await screen.findByRole('group', { name: /stable is your income/ })
        await user.click(screen.getByRole('button', { name: 'See my risk level' }))

        expect(await screen.findByText('We could not work out your risk level')).toBeInTheDocument()
        expect(screen.getByText(/Profiler unavailable\. Your answers are kept/)).toBeInTheDocument()
        expect(useIdentity.getState().userId).toBeNull()
        expect(location()).toBe('/start/finances')
    })

    it('sends you back to finish an earlier step before submitting', async () => {
        const user = userEvent.setup()
        const calls = stubApi({ '/api/quiz-questions': fx.quiz })
        useOnboardingDraft.setState({ ...fx.completeDraft, answers: { ...fx.completeDraft.answers, 10: undefined as unknown as number } })
        renderApp('/start/finances')

        await screen.findByRole('group', { name: /stable is your income/ })
        await user.click(screen.getByRole('button', { name: 'See my risk level' }))

        await screen.findByRole('heading', { level: 1, name: 'Ups and downs' })
        expect(screen.getByText('A few answers are still needed here')).toBeInTheDocument()
        expect(screen.getByRole('alert')).toHaveFocus()
        expect(document.title).toBe('Ups and downs · UK Robo Advisor')
        expect(screen.getByRole('link', { name: 'Choose an answer about short-term ups and downs.' })).toBeInTheDocument()
        expect(calls.some((c) => c.method === 'POST')).toBe(false)
    })

    it('offers a retry when the questions do not load, and never invents them', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({ '/api/quiz-questions': () => (fail ? { status: 503, body: { detail: 'down' } } : fx.quiz) })
        renderApp('/start/losses')

        expect(await screen.findByText('The questions did not load')).toBeInTheDocument()
        expect(screen.queryByRole('radio')).not.toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('group', { name: /dropped 20%/ })).toBeInTheDocument()
    })

    it('marks progress: done steps link back, the current one is marked', async () => {
        stubApi({ '/api/quiz-questions': fx.quiz })
        useOnboardingDraft.setState(fx.completeDraft)
        renderApp('/start/finances')
        const progress = await screen.findByRole('navigation', { name: 'Progress' })
        await waitFor(() => expect(within(progress).getByRole('link', { name: /Your goal \(done\)/ })).toHaveAttribute('href', '/start'))
        expect(within(progress).getByText('Your finances').closest('li')).toHaveAttribute('aria-current', 'step')
        expect(within(progress).queryByRole('link', { name: /Your risk level/ })).not.toBeInTheDocument()
    })
})
