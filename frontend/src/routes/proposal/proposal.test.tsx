import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GLOSSARY } from '@/lib/glossary'
import type { Call } from '@/test/app'
import { useIdentity, useOnboardingDraft } from '@/store/session'
import { renderApp, stubApi, warmPages } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./ProposalPage'),
    () => import('@/routes/portfolio/PortfolioLayout'),
    () => import('@/routes/portfolio/overview/OverviewPage'),
    () => import('@/routes/start/StartLayout'),
    () => import('@/routes/start/GoalsPage'),
)

const location = () => screen.getByTestId('location').textContent

/** A preview built at whatever level was asked for. */
const echoPreview = (c: Call) => {
    const risk = (c.body as { risk_score: number }).risk_score
    return { ...fx.preview, requested_risk_score: risk, risk_score: risk, capped: false }
}

function proposalApi(profile = fx.riskProfile, extra: Record<string, unknown> = {}) {
    return stubApi({
        '/api/risk-profile/4': profile,
        'POST /api/portfolio/preview': echoPreview,
        'POST /api/monte-carlo': fx.monteCarloReal,
        ...extra,
    })
}

function signIn() {
    useIdentity.getState().setUser(4)
    useOnboardingDraft.setState(fx.completeDraft)
}

const openButton = () => screen.getByRole('button', { name: 'Open portfolio' })
const previews = (calls: Call[]) => calls.filter((c) => c.path === '/api/portfolio/preview').map((c) => c.body)

describe('the proposal', () => {
    it('sends you to the start without an identity', async () => {
        stubApi({ '/api/quiz-questions': fx.quiz })
        renderApp('/proposal')
        await screen.findByRole('heading', { level: 1, name: 'Your goal' })
        expect(location()).toBe('/start')
    })

    it('describes the portfolio in one sentence built from the preview, then its figures and projection', async () => {
        const calls = proposalApi({ ...fx.riskProfile, composite_score: 7, risk_score_int: 7 })
        signIn()
        renderApp('/proposal')

        const title = await screen.findByRole('heading', {
            level: 1,
            name: '£50,000 now and £250 a month, at risk level 7: 70% in growth and 30% in defensive holdings, spread across 8 funds costing about £42 a year.',
        })
        expect(title).toBeInTheDocument()
        expect(screen.getByText('Your proposal · not saved')).toBeInTheDocument()
        expect(screen.getByText('Expected return').closest('div')).toHaveTextContent('6.5%')
        expect(screen.getByText('Volatility').closest('div')).toHaveTextContent('8.9%')
        expect(screen.getByText('Volatility')).toHaveAccessibleDescription(GLOSSARY.volatility)
        expect(screen.getByText('Sharpe ratio').closest('div')).toHaveTextContent('0.25Against a 4.2% risk-free rate')
        expect(screen.getByText('Ongoing charges').closest('div')).toHaveTextContent('£42')
        expect(screen.getByRole('table', { name: 'The funds in this proposal' })).toBeInTheDocument()

        expect(await screen.findByText('What £50,000 could become')).toBeInTheDocument()
        expect(screen.getByText('Probability of a loss').closest('div')).toHaveTextContent(/6%Below the amount paid in after 15 years, adjusted for inflation$/)
        const projection = calls.find((c) => c.path === '/api/monte-carlo')
        expect(projection?.body).toEqual({
            annual_return: fx.preview.expected_annual_return,
            annual_volatility: fx.preview.expected_volatility,
            initial_investment: 50_000,
            monthly_contribution: 250,
            years: 15,
            n_simulations: 2_000,
            real_terms: true,
        })
    })

    it('lets you lower the risk level, never raise it, and rebuilds for the new level', async () => {
        const calls = proposalApi({ ...fx.riskProfile, composite_score: 5.5, risk_score_int: 6 })
        signIn()
        renderApp('/proposal')

        const slider = await screen.findByRole('slider', { name: 'Risk level' })
        expect(slider).toHaveAttribute('aria-valuetext', 'Level 5.5 of 10, your assessed level')
        expect(screen.getByText(/Your answers put you at 5\.5\. You can take less risk than that, not more\./)).toBeInTheDocument()
        await screen.findByRole('heading', { level: 1, name: /at risk level 5\.5:/ })

        fireEvent.change(slider, { target: { value: String(Number(slider.getAttribute('max'))) } })
        expect(slider).toHaveAttribute('aria-valuetext', 'Level 5.5 of 10, your assessed level')

        fireEvent.change(slider, { target: { value: '3' } })
        expect(slider).toHaveAttribute('aria-valuetext', 'Level 4 of 10')
        await screen.findByRole('heading', { level: 1, name: /at risk level 4:/ })
        expect(previews(calls).map((b) => (b as { risk_score: number }).risk_score)).toEqual([5.5, 4])
        expect(useOnboardingDraft.getState().chosenRiskScore).toBe(4)
    })

    it('opens exactly the portfolio on screen and goes to it', async () => {
        const user = userEvent.setup()
        const calls = proposalApi(fx.riskProfile, {
            'POST /api/portfolio': { ...fx.createdPortfolio, portfolio_id: 21 },
            '/api/performance/21': { ...fx.performance, portfolio_id: 21 },
        })
        signIn()
        renderApp('/proposal')

        await screen.findByText('What £50,000 could become')
        await waitFor(() => expect(openButton()).toBeEnabled())
        await user.click(openButton())

        await screen.findByRole('heading', { level: 1, name: /Worth £124,518/ })
        expect(location()).toBe('/portfolio/21')
        expect(useIdentity.getState().lastPortfolioId).toBe(21)
        const opened = calls.filter((c) => c.method === 'POST' && c.path === '/api/portfolio')
        expect(opened.map((c) => c.body)).toEqual([
            { user_id: 4, risk_score: 5, investment_amount: 50_000, monthly_contribution: 250, uses_isa: true },
        ])
    })

    it('will not open while the amount is invalid', async () => {
        const user = userEvent.setup()
        proposalApi()
        signIn()
        renderApp('/proposal')

        await screen.findByText('What £50,000 could become')
        await user.clear(screen.getByLabelText('Amount to invest now'))
        expect(screen.getByText('Enter an amount above £0.')).toBeInTheDocument()
        expect(openButton()).toBeDisabled()
        expect(screen.getByText(/These figures are for the last amounts that were valid/)).toBeInTheDocument()
        // Still disabled, and still the last valid proposal, once the empty amount has settled.
        await new Promise((resolve) => setTimeout(resolve, 600))
        expect(openButton()).toBeDisabled()
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^£50,000 now and £250 a month/)
        expect(useOnboardingDraft.getState().investmentAmount).toBe(50_000)

        await user.type(screen.getByLabelText('Amount to invest now'), '20000')
        await screen.findByRole('heading', { level: 1, name: /^£20,000 now and £250 a month/ })
        expect(screen.queryByText(/These figures are for the last amounts/)).not.toBeInTheDocument()
        await waitFor(() => expect(openButton()).toBeEnabled())
    })

    it('asks for an amount when the session has none, rather than building nothing', async () => {
        const user = userEvent.setup()
        const calls = proposalApi()
        useIdentity.getState().setUser(4)
        renderApp('/proposal')

        expect(await screen.findByRole('heading', { level: 1, name: 'Enter an amount to see your proposal' })).toBeInTheDocument()
        expect(openButton()).toBeDisabled()
        expect(calls.some((c) => c.path === '/api/portfolio/preview')).toBe(false)

        await user.type(screen.getByLabelText('Amount to invest now'), '10,000')
        expect(await screen.findByRole('heading', { level: 1, name: /^£10,000 now, at risk level 5:/ })).toBeInTheDocument()
    })

    it('keeps you on the proposal and says so when opening fails', async () => {
        const user = userEvent.setup()
        proposalApi(fx.riskProfile, { 'POST /api/portfolio': { status: 503, body: { detail: 'Prices are updating.' } } })
        signIn()
        renderApp('/proposal')

        await screen.findByText('What £50,000 could become')
        await waitFor(() => expect(openButton()).toBeEnabled())
        await user.click(openButton())

        const notice = await screen.findByText('The portfolio was not opened')
        expect(notice.closest('[role="alert"]')).toHaveTextContent('Prices are updating. Nothing was saved; try again.')
        expect(location()).toBe('/proposal')
        expect(useIdentity.getState().lastPortfolioId).toBeNull()
    })

    it('offers a retry when the proposal cannot be built', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({
            '/api/risk-profile/4': fx.riskProfile,
            'POST /api/portfolio/preview': (c: Call) => (fail ? { status: 503, body: { detail: 'Optimiser busy.' } } : echoPreview(c)),
            'POST /api/monte-carlo': fx.monteCarloReal,
        })
        signIn()
        renderApp('/proposal')

        const failed = await screen.findByText('The proposal could not be built')
        expect(within(failed.closest('[role="alert"]') as HTMLElement).getByText(/Optimiser busy\./)).toBeInTheDocument()
        expect(openButton()).toBeDisabled()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: /at risk level 5:/ })).toBeInTheDocument()
    })
})
