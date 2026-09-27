import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { useIdentity } from '@/store/session'
import { renderApp, stubApi, warmPages } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./PortfolioLayout'),
    () => import('./overview/OverviewPage'),
    () => import('./PortfoliosPage'),
    () => import('@/routes/NotFound'),
)

const location = () => screen.getByTestId('location').textContent

const rebalancing = {
    ...fx.performance,
    total_value: 98_760,
    total_return_pct: -0.0124,
    needs_rebalance: true,
    unpriced_tickers: ['SGLN.L'],
}

describe('a portfolio', () => {
    it('opens with a sentence from its valuation, then its figures and holdings', async () => {
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/asset-classes': [fx.assetClass],
            '/api/etfs': [fx.etf],
        })
        renderApp('/portfolio/19')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
            'Worth £124,518 on 25 Sept 2026: £24,518 more than the £100,000 paid in. Every holding is within its band.',
        )
        expect(await screen.findByText('Portfolio 19 · risk level 5 · ISA · £250 a month')).toBeInTheDocument()
        expect(screen.getByText('Gain or loss').closest('div')).toHaveTextContent('+£24,518')
        expect(screen.getByText('Within its bands')).toBeInTheDocument()
        expect(await screen.findAllByText('Global Equity')).not.toHaveLength(0)
        expect(await screen.findByText('Vanguard FTSE All-World UCITS ETF (GBP) · VWRL.L')).toBeInTheDocument()
        expect(useIdentity.getState().lastPortfolioId).toBe(19)
        expect(document.title).toBe('Portfolio 19 · UK Robo Advisor')
    })

    it('says when a rebalance is due and which funds have no price', async () => {
        stubApi({ '/api/performance/19': rebalancing, '/api/portfolio/19': fx.portfolioDetail })
        renderApp('/portfolio/19')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
            'Worth £98,760 on 25 Sept 2026: £1,240 less than the £100,000 paid in. It has drifted far enough from its targets to rebalance.',
        )
        expect(screen.getByText('Rebalance due')).toBeInTheDocument()
        expect(screen.getByText('No recent price for SGLN.L')).toBeInTheDocument()
        expect(screen.getByText('Gain or loss').closest('div')).toHaveTextContent('−£1,240')
    })

    it('never shows a portfolio without recorded purchases as a loss', async () => {
        stubApi({ '/api/performance/7': { ...fx.performance, portfolio_id: 7, total_value: 0, net_contributions: 0, total_return_pct: 0 } })
        renderApp('/portfolio/7')

        expect(await screen.findByRole('heading', { level: 1, name: 'Portfolio 7' })).toBeInTheDocument()
        expect(screen.getByText('This portfolio has no recorded purchases')).toBeInTheDocument()
        expect(screen.queryByText('Gain or loss')).not.toBeInTheDocument()
    })

    it('says plainly when there is no such portfolio', async () => {
        stubApi({ '/api/performance/404': { status: 404, body: { detail: 'Portfolio not found.' } } })
        renderApp('/portfolio/404')
        expect(await screen.findByRole('heading', { level: 1, name: 'There is no portfolio 404' })).toBeInTheDocument()
        expect(useIdentity.getState().lastPortfolioId).toBeNull()
    })

    it('treats an address that is not a number as unknown, without asking the API', async () => {
        const calls = stubApi({})
        renderApp('/portfolio/latest')
        expect(await screen.findByRole('heading', { level: 1, name: 'There is nothing at this address' })).toBeInTheDocument()
        expect(document.title).toBe('Page not found · UK Robo Advisor')
        expect(calls).toHaveLength(0)
    })

    it('offers a retry when it cannot be valued', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({ '/api/performance/19': () => (fail ? { status: 502, body: { detail: 'Price feed down.' } } : fx.performance) })
        renderApp('/portfolio/19')

        expect(await screen.findByText('The portfolio could not be valued')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: /^Worth £124,518/ })).toBeInTheDocument()
    })
})

describe('the list of portfolios', () => {
    it('invites you to build one when this browser has none', async () => {
        const calls = stubApi({})
        renderApp('/portfolios')
        expect(await screen.findByText(/No portfolios have been opened in this browser yet/)).toBeInTheDocument()
        expect(within(screen.getByRole('main')).getByRole('link', { name: 'Build a portfolio' })).toHaveAttribute('href', '/start')
        expect(calls).toHaveLength(0)
    })

    it('shows the same empty state when your list is empty', async () => {
        stubApi({ '/api/portfolios/user/4': [], '/api/portfolios/user/4/archived': [] })
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')
        expect(await screen.findByText(/No portfolios have been opened in this browser yet/)).toBeInTheDocument()
    })

    it('lists each one with its value, and totals the valued ones', async () => {
        stubApi({
            '/api/portfolios/user/4/archived': [],
            '/api/portfolios/user/4': [
                { ...fx.portfolioSummary, portfolio_id: 21, name: 'House deposit' },
                { ...fx.portfolioSummary, portfolio_id: 19, name: 'My Portfolio', total_value: null, total_return_pct: null },
            ],
            '/api/portfolio/21/history': {
                ...fx.history,
                portfolio_id: 21,
                reason: null,
                points: [
                    { date: '2026-09-01', value: 100_000, net_contributions: 100_000, cumulative_return: 0 },
                    { date: '2026-09-25', value: 124_518, net_contributions: 100_000, cumulative_return: 0.245 },
                ],
            },
            '/api/portfolio/19/history': fx.history,
        })
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        expect(await screen.findByRole('heading', { level: 1, name: '2 portfolios, worth £124,518 together (1 not valued).' })).toBeInTheDocument()
        const table = screen.getByRole('table', { name: 'Your portfolios' })
        expect(within(table).getByRole('link', { name: 'House deposit' })).toHaveAttribute('href', '/portfolio/21')
        expect(within(table).getByRole('link', { name: 'Portfolio 19' })).toHaveAttribute('href', '/portfolio/19')
        expect(within(table).getByText('Not valued')).toBeInTheDocument()
        expect(within(table).getAllByText('Opened 1 Sept 2026')).toHaveLength(2)
        expect(await within(table).findByRole('img', { name: 'Value from £100,000 on 1 Sept 2026 to £124,518 on 25 Sept 2026' })).toBeInTheDocument()
        expect(await within(table).findByText('Not enough days yet')).toBeInTheDocument()
    })

    it('offers a retry when the list does not load', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({
            '/api/portfolios/user/4': () => (fail ? { status: 500, body: { detail: 'Database busy.' } } : [fx.portfolioSummary]),
            '/api/portfolios/user/4/archived': [],
        })
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        expect(await screen.findByText('Your portfolios did not load')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: '1 portfolio, worth £124,518 together.' })).toBeInTheDocument()
    })
})

describe('old addresses', () => {
    it('sends the dashboard to your last portfolio, or to the list', async () => {
        stubApi({ '/api/performance/19': fx.performance })
        useIdentity.getState().setLastPortfolio(19)
        const first = renderApp('/dashboard')
        await screen.findByRole('heading', { level: 1, name: /^Worth £124,518/ })
        expect(location()).toBe('/portfolio/19')
        first.unmount()

        useIdentity.getState().forget()
        renderApp('/dashboard')
        await screen.findByText(/No portfolios have been opened/)
        expect(location()).toBe('/portfolios')
    })

    it.each([
        ['/history', '/portfolios'],
        ['/onboarding', '/start'],
        ['/builder', '/start'],
    ])('sends %s on to %s', async (from, to) => {
        stubApi({ '/api/quiz-questions': fx.quiz })
        renderApp(from)
        await screen.findByRole('heading', { level: 1 })
        expect(location()).toBe(to)
    })

    it('says so for an address it does not know', async () => {
        stubApi({})
        renderApp('/somewhere/else')
        expect(await screen.findByRole('heading', { level: 1, name: 'There is nothing at this address' })).toBeInTheDocument()
    })
})
