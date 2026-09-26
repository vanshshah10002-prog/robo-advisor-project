import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { useIdentity } from '@/store/session'
import { renderApp, stubApi, warmPages, type Call, type Handler } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./PortfolioLayout'),
    () => import('./outlook/OutlookPage'),
    () => import('./activity/ActivityPage'),
)

/** The valuation and detail every section of portfolio 19 starts from. */
const workspace = (routes: Record<string, Handler> = {}) =>
    stubApi({
        '/api/performance/19': fx.performance,
        '/api/portfolio/19': fx.portfolioDetail,
        '/api/etfs': [fx.etf],
        ...routes,
    })

const simulations = (calls: readonly Call[]) => calls.filter((c) => c.path === '/api/monte-carlo').map((c) => c.body)

describe('the outlook', () => {
    const outlook = (routes: Record<string, Handler> = {}) =>
        workspace({ '/api/monte-carlo': fx.monteCarloReal, '/api/strategy/track-record': fx.trackRecord, ...routes })

    it('projects what the portfolio is worth now, in today’s money, over ten years by default', async () => {
        const calls = outlook()
        renderApp('/portfolio/19/outlook')

        expect(await screen.findByRole('heading', { level: 1, name: /^In 15 years/ })).toHaveTextContent(
            "In 15 years, in today's money, the middle outcome is £141,357; 8 in 10 simulated outcomes land between £99,505 and £206,015.",
        )
        expect(simulations(calls)[0]).toEqual({
            portfolio_id: 19,
            initial_investment: 124_518,
            monthly_contribution: 250,
            years: 10,
            n_simulations: 2_000,
            real_terms: true,
        })
        expect(screen.getByText('Chance of ending below what was paid in').closest('div')).toHaveTextContent('6%')
        expect(screen.getByRole('figure', { name: 'What £124,518 could become' })).toHaveTextContent('4.4% a year')
        expect(document.title).toBe('Outlook · Portfolio 19 · UK Robo Advisor')
    })

    it('takes the horizon from the risk profile this browser gave', async () => {
        useIdentity.getState().setUser(4)
        const calls = outlook({ '/api/risk-profile/4': fx.riskProfile })
        renderApp('/portfolio/19/outlook')

        await waitFor(() => expect(simulations(calls).at(-1)).toMatchObject({ years: 15 }))
        expect(screen.getByRole('textbox', { name: 'Years ahead' })).toHaveValue('15')
    })

    it('reads a goal and the basis into the next simulation', async () => {
        const user = userEvent.setup()
        const calls = outlook()
        renderApp('/portfolio/19/outlook')
        await screen.findByRole('heading', { level: 1, name: /^In 15 years/ })

        await user.type(screen.getByRole('textbox', { name: /A goal/ }), '200000')
        await user.click(screen.getByRole('radio', { name: 'Pounds of the day' }))
        await waitFor(() => expect(simulations(calls).at(-1)).toMatchObject({ goal_amount: 200_000, real_terms: false }))
        expect(await screen.findByText('Chance of reaching £200,000')).toBeInTheDocument()
    })

    it('keeps the last figures, and says so, while the horizon is not a usable number', async () => {
        const user = userEvent.setup()
        const calls = outlook()
        renderApp('/portfolio/19/outlook')
        await screen.findByRole('heading', { level: 1, name: /^In 15 years/ })

        const years = screen.getByRole('textbox', { name: 'Years ahead' })
        await user.clear(years)
        await user.type(years, '0')
        expect(await screen.findByText('Enter a whole number of years from 1 to 50.')).toBeInTheDocument()
        expect(screen.getByText('These figures are for the last inputs that were valid. Correct the inputs to update them.')).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^In 15 years/)
        expect(simulations(calls).every((b) => (b as { years: number }).years >= 1)).toBe(true)
    })

    it('explains how to read the range, against the backtest at the same level', async () => {
        const calls = outlook()
        renderApp('/portfolio/19/outlook')

        expect(await screen.findByText('The chance of being worth less than was paid in falls from 37% after a year to 6% after 15 years.')).toBeInTheDocument()
        expect(await screen.findByText(/60% of yearly returns landed within one typical swing/)).toBeInTheDocument()
        expect(calls.find((c) => c.path === '/api/strategy/track-record')?.query.get('risk')).toBe('5')
    })

    it('waits for the details of the portfolio, and says so with a retry when they do not load', async () => {
        const user = userEvent.setup()
        let fail = true
        const calls = outlook({ '/api/portfolio/19': () => (fail ? { status: 500, body: { detail: 'Database busy.' } } : fx.portfolioDetail) })
        renderApp('/portfolio/19/outlook')

        expect(await screen.findByText('Part of this portfolio did not load')).toBeInTheDocument()
        expect(simulations(calls)).toEqual([])
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: /^In 15 years/ })).toBeInTheDocument()
        expect(simulations(calls)[0]).toMatchObject({ monthly_contribution: 250 })
        expect(screen.queryByText('Part of this portfolio did not load')).not.toBeInTheDocument()
    })

    it('says why when a portfolio cannot be projected', async () => {
        outlook({
            '/api/monte-carlo': { status: 422, body: { detail: 'This portfolio has no stored expected return and volatility to project from' } },
        })
        renderApp('/portfolio/19/outlook')

        expect(await screen.findByText('The outlook could not be simulated')).toBeInTheDocument()
        expect(screen.getByText(/no stored expected return and volatility/)).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Simulating the years ahead')
    })
})

const deposit = { ...fx.transaction, id: 1, ticker: 'CASH', action: 'deposit', quantity: 100_000, price: 1, value: 100_000, cost: 0 }
const ledger = [deposit, { ...fx.transaction, id: 2 }]

describe('activity', () => {
    const activity = (routes: Record<string, Handler> = {}) =>
        workspace({ '/api/transactions/19': ledger, '/api/rebalance/19': fx.rebalancePlan, ...routes })

    it('sums up the ledger and lists it newest first', async () => {
        activity()
        renderApp('/portfolio/19/activity')

        expect(await screen.findByRole('heading', { level: 1, name: /^2 transactions/ })).toHaveTextContent(
            '2 transactions since 27 Sept 2021: £100,000 paid in and £40 in trading costs. No rebalance is due.',
        )
        const rows = within(screen.getByRole('table', { name: 'Every transaction, newest first' })).getAllByRole('row').slice(1)
        expect(rows[0]).toHaveTextContent(/Bought.*VWRL\.L.*400\.00.*£100\.00.*£40,000.*£40/)
        expect(rows[1]).toHaveTextContent(/Paid in.*Cash.*£100,000/)
    })

    it('adds money, then says where it went', async () => {
        const user = userEvent.setup()
        const calls = activity({ 'POST /api/portfolio/19/contribute': fx.contributionResult })
        renderApp('/portfolio/19/activity')

        const add = await screen.findByRole('button', { name: 'Add money' })
        await user.click(add)
        expect(screen.getByText('Enter an amount above £0.')).toBeInTheDocument()

        await user.type(screen.getByRole('textbox', { name: /Amount to add/ }), '500')
        await user.click(screen.getByRole('button', { name: 'Add £500' }))
        expect(await screen.findByText('£500 added and invested in 1 fund. The portfolio is now worth £125,018.')).toBeInTheDocument()
        expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ amount_gbp: 500 })
        expect(screen.getByRole('textbox', { name: /Amount to add/ })).toHaveValue('')
    })

    it('records nothing, and says so, when the money cannot be added', async () => {
        const user = userEvent.setup()
        activity({ 'POST /api/portfolio/19/contribute': { status: 409, body: { detail: 'Prices are out of date.' } } })
        renderApp('/portfolio/19/activity')

        await user.type(await screen.findByRole('textbox', { name: /Amount to add/ }), '500')
        await user.click(screen.getByRole('button', { name: 'Add £500' }))
        expect(await screen.findByText('The money was not added')).toBeInTheDocument()
        expect(screen.getByText(/Prices are out of date\. Nothing was recorded\./)).toBeInTheDocument()
    })

    it('shows each trade a rebalance would make before running it', async () => {
        const user = userEvent.setup()
        const calls = activity({ 'POST /api/rebalance/19/execute': { ...fx.rebalancePlan, executed: true } })
        renderApp('/portfolio/19/activity')

        expect(await screen.findByText(/^Selling £7,600 brings every holding back to its target/)).toBeInTheDocument()
        const trades = screen.getByRole('table', { name: 'The trades a rebalance would make' })
        expect(within(trades).getAllByRole('row')[1]).toHaveTextContent(/Vanguard FTSE All-World.*Sell.*56\.1% → 50\.0%.*£7,600.*£7\.60.*\+£2,720/)

        await user.click(screen.getByRole('button', { name: 'Rebalance now' }))
        expect(await screen.findByText('Rebalanced: 1 trade, for about £15 in costs.')).toBeInTheDocument()
        expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/api/rebalance/19/execute'])
    })

    it('offers nothing to run when every holding is within its band, and warns of old prices', async () => {
        activity({ '/api/rebalance/19': { ...fx.rebalancePlan, needs_rebalance: false, trades: [], stale_tickers: ['SGLN.L'] } })
        renderApp('/portfolio/19/activity')

        expect(await screen.findByText('Every holding is within its band, so there is nothing to trade.')).toBeInTheDocument()
        expect(screen.getByText('Old prices for SGLN.L')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Rebalance now' })).not.toBeInTheDocument()
    })

    it('says nothing was traded when a rebalance fails', async () => {
        const user = userEvent.setup()
        activity({ 'POST /api/rebalance/19/execute': { status: 409, body: { detail: 'Prices are out of date.' } } })
        renderApp('/portfolio/19/activity')

        await user.click(await screen.findByRole('button', { name: 'Rebalance now' }))
        expect(await screen.findByText('The rebalance did not run')).toBeInTheDocument()
        expect(screen.getByText(/Prices are out of date\. Nothing was traded\./)).toBeInTheDocument()
    })

    it('offers a retry when the ledger or the check does not load', async () => {
        const user = userEvent.setup()
        let fail = true
        activity({
            '/api/transactions/19': () => (fail ? { status: 500, body: { detail: 'Ledger busy.' } } : ledger),
            '/api/rebalance/19': () => (fail ? { status: 500, body: { detail: 'Prices busy.' } } : fx.rebalancePlan),
        })
        renderApp('/portfolio/19/activity')

        expect(await screen.findByText('The ledger did not load')).toBeInTheDocument()
        expect(await screen.findByText('The check did not run')).toBeInTheDocument()
        fail = false
        for (const button of screen.getAllByRole('button', { name: 'Try again' })) await user.click(button)
        expect(await screen.findByRole('heading', { level: 1, name: /^2 transactions/ })).toBeInTheDocument()
        expect(await screen.findByRole('button', { name: 'Rebalance now' })).toBeInTheDocument()
    })
})
