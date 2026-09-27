import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GLOSSARY } from '@/lib/glossary'
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

    it('lists its statistics beside the holdings, estimated and measured, each explained', async () => {
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/portfolio/19/construction': { ...fx.construction, portfolio_id: 19 },
            '/api/portfolio/19/history': {
                ...fx.history,
                points: [
                    { date: '2025-06-30', value: 100_000, net_contributions: 100_000, cumulative_return: 0 },
                    { date: '2026-09-25', value: 112_000, net_contributions: 100_000, cumulative_return: 0.12 },
                ],
                reason: null,
            },
        })
        renderApp('/portfolio/19')

        const stats = within(await screen.findByRole('complementary', { name: 'Portfolio statistics' }))
        const row = (label: string) => stats.getByText(label).closest('div') as HTMLElement
        expect(await stats.findByText('Expected return')).toHaveAccessibleDescription(GLOSSARY.expectedReturn)
        expect(stats.getByText(/^At the target weights, as a fund has no price today; from the estimates of 26 Sept 2026\./)).toBeInTheDocument()
        expect(row('Expected return')).toHaveTextContent('6.5% a year')
        expect(row('Volatility')).toHaveTextContent('8.9% a year')
        expect(row('Sharpe ratio')).toHaveTextContent('0.25Against 4.2% risk-free')
        expect(row('Value at risk (95%, 1 year)')).toHaveTextContent('8.2%About £10,236 today')
        expect(row('Diversification ratio')).toHaveTextContent('1.29')
        expect(row('Effective number of holdings')).toHaveTextContent('3.8Of 8 funds')
        expect(row('Ongoing charges')).toHaveTextContent('0.08% a yearAbout £104 a year')

        expect(await stats.findByText('+12.0%')).toBeInTheDocument()
        expect(row('Time-weighted return')).toHaveTextContent('+12.0%')
        expect(row('Annualised return')).toHaveTextContent('+9.6% a year')
        expect(row('Realised volatility')).toHaveTextContent('After 21 days of values')
        expect(row('Maximum drawdown')).toHaveTextContent('None yet')
    })

    it('measures volatility once there are enough daily values, and marks what the estimates lack', async () => {
        const snapshot = fx.construction.snapshot as NonNullable<typeof fx.construction.snapshot>
        const days = Array.from({ length: 22 }, (_, i) => {
            const cumulative = [0, 0.01, -0.005][i % 3] + i * 0.001
            return { date: new Date(Date.UTC(2026, 7, 1 + i)).toISOString().slice(0, 10), value: 100_000 * (1 + cumulative), net_contributions: 100_000, cumulative_return: cumulative }
        })
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/portfolio/19/construction': {
                ...fx.construction,
                portfolio_id: 19,
                snapshot: { ...snapshot, risk_free_rate: null, holdings: snapshot.holdings.map((h, i) => (i === 0 ? { ...h, expense_ratio: null } : h)) },
            },
            '/api/portfolio/19/history': { ...fx.history, points: days, reason: null },
        })
        renderApp('/portfolio/19')

        const stats = within(await screen.findByRole('complementary', { name: 'Portfolio statistics' }))
        const row = (label: string) => stats.getByText(label).closest('div') as HTMLElement
        expect(await stats.findByText('Realised volatility')).toBeInTheDocument()
        expect(row('Realised volatility')).toHaveTextContent(/\d+\.\d% a year$/)
        expect(row('Annualised return')).toHaveTextContent('After a year of history')
        expect(row('Maximum drawdown')).not.toHaveTextContent('None yet')
        await stats.findByText('Sharpe ratio')
        expect(row('Sharpe ratio')).toHaveTextContent(/—$/)
        expect(row('Ongoing charges')).toHaveTextContent(/—$/)
    })

    it('says when a fund has no estimate to combine', async () => {
        const snapshot = fx.construction.snapshot as NonNullable<typeof fx.construction.snapshot>
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/portfolio/19/construction': {
                ...fx.construction,
                portfolio_id: 19,
                snapshot: { ...snapshot, holdings: snapshot.holdings.map((h, i) => (i === 0 ? { ...h, volatility: null } : h)) },
            },
            '/api/portfolio/19/history': fx.history,
        })
        renderApp('/portfolio/19')

        const stats = within(await screen.findByRole('complementary', { name: 'Portfolio statistics' }))
        expect(await stats.findByText('A fund is missing an estimate, so these figures cannot be combined.')).toBeInTheDocument()
    })

    it('says why estimates are missing, and keeps the measured figures', async () => {
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/portfolio/19/construction': { portfolio_id: 19, recorded: false, snapshot: null },
            '/api/portfolio/19/history': { status: 500, body: { detail: 'Ledger busy.' } },
        })
        renderApp('/portfolio/19')

        const stats = within(await screen.findByRole('complementary', { name: 'Portfolio statistics' }))
        expect(await stats.findByText(/opened before its construction was recorded/)).toBeInTheDocument()
        expect(await stats.findByText('The history did not load: Ledger busy.')).toBeInTheDocument()
    })

    it('says so when the estimates do not load', async () => {
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': fx.portfolioDetail,
            '/api/portfolio/19/construction': { status: 500, body: { detail: 'Database busy.' } },
            '/api/portfolio/19/history': fx.history,
        })
        renderApp('/portfolio/19')

        const stats = within(await screen.findByRole('complementary', { name: 'Portfolio statistics' }))
        expect(await stats.findByText('The estimates did not load: Database busy.')).toBeInTheDocument()
        expect(await stats.findByText(fx.history.reason as string)).toBeInTheDocument()
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
