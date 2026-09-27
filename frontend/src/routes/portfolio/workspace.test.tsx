import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GLOSSARY } from '@/lib/glossary'
import { renderApp, stubApi, warmPages, type Handler } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./PortfolioLayout'),
    () => import('./overview/OverviewPage'),
    () => import('./performance/PerformancePage'),
    () => import('./universe/UniversePage'),
)

const location = () => screen.getByTestId('location').textContent

/** The valuation, detail and names every section of portfolio 19 starts from. */
const workspace = (routes: Record<string, Handler> = {}) =>
    stubApi({
        '/api/performance/19': fx.performance,
        '/api/portfolio/19': fx.portfolioDetail,
        '/api/asset-classes': [fx.assetClass],
        '/api/etfs': [fx.etf],
        ...routes,
    })

const point = (date: string, value: number, cumulative: number) => ({ date, value, net_contributions: 100_000, cumulative_return: cumulative })

/** Fifteen months, with a dip at the turn of the year: every period is covered. */
const history = {
    portfolio_id: 19,
    points: [
        point('2025-06-30', 100_000, 0),
        point('2025-09-25', 104_000, 0.04),
        point('2025-12-31', 101_000, 0.01),
        point('2026-06-25', 108_000, 0.08),
        point('2026-08-25', 106_920, 0.0692),
        point('2026-09-25', 112_000, 0.12),
    ],
    start_date: '2025-06-30',
    end_date: '2026-09-25',
    time_weighted_return: 0.12,
    reason: null,
    unpriced_tickers: [],
}

describe('the workspace', () => {
    it('says which portfolio this is and moves between its sections', async () => {
        const user = userEvent.setup()
        workspace({ '/api/portfolio/19/history': history, '/api/strategy/track-record': fx.trackRecord })
        renderApp('/portfolio/19')

        expect(await screen.findByText('Portfolio 19 · risk level 5 · ISA · £250 a month')).toBeInTheDocument()
        const nav = screen.getByRole('navigation', { name: 'Portfolio sections' })
        const links = within(nav).getAllByRole('link')
        expect(links.map((l) => l.textContent)).toEqual(['Overview', 'Performance', 'Asset universe', 'Outlook', 'Activity'])
        expect(links[0]).toHaveAttribute('aria-current', 'page')

        await user.click(links[1])
        expect(await screen.findByRole('heading', { level: 1, name: /^Since it opened on 30 Jun 2025/ })).toBeInTheDocument()
        expect(location()).toBe('/portfolio/19/performance')
        expect(within(nav).getByRole('link', { name: 'Performance' })).toHaveAttribute('aria-current', 'page')
        expect(nav).toBeInTheDocument()
        expect(document.title).toBe('Performance · Portfolio 19 · UK Robo Advisor')
    })

    it('leaves out the monthly amount when there is none, and names a general account', async () => {
        workspace({ '/api/portfolio/19': { ...fx.portfolioDetail, monthly_contribution: 0, uses_isa: false } })
        renderApp('/portfolio/19')
        expect(await screen.findByText('Portfolio 19 · risk level 5 · General account')).toBeInTheDocument()
    })
})

describe('the overview', () => {
    it('updates the prices on request and says to which close', async () => {
        const user = userEvent.setup()
        const calls = workspace({ 'POST /api/portfolio/19/refresh': fx.refreshResult })
        renderApp('/portfolio/19')

        await user.click(await screen.findByRole('button', { name: 'Update prices' }))
        expect(await screen.findByText('Updated to the closes of 25 Sept 2026, 16:35.')).toBeInTheDocument()
        expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/api/portfolio/19/refresh'])
    })

    it('keeps the figures and says why when the prices cannot be updated', async () => {
        const user = userEvent.setup()
        workspace({ 'POST /api/portfolio/19/refresh': { status: 502, body: { detail: 'Price feed down.' } } })
        renderApp('/portfolio/19')

        await user.click(await screen.findByRole('button', { name: 'Update prices' }))
        expect(await screen.findByText('The prices were not updated')).toBeInTheDocument()
        expect(screen.getByText(/Price feed down\. The figures above are unchanged\./)).toBeInTheDocument()
    })

    it('points a due rebalance at the trades', async () => {
        workspace({ '/api/performance/19': { ...fx.performance, needs_rebalance: true } })
        renderApp('/portfolio/19')
        expect(await screen.findByRole('link', { name: 'Review the trades' })).toHaveAttribute('href', '/portfolio/19/activity')
    })
})

/** A headline figure by its label: the label's `<dt>` and value together, apart from a table header of the same name. */
const stat = (label: string) => screen.getAllByText(label).find((el) => el.closest('dt'))?.closest('div') as HTMLElement

describe('performance', () => {
    const open = () => {
        workspace({ '/api/portfolio/19/history': history, '/api/strategy/track-record': fx.trackRecord })
        renderApp('/portfolio/19/performance')
    }

    it('opens with the time-weighted return and the maximum drawdown, measured from the ledger', async () => {
        open()
        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
            'Since it opened on 30 Jun 2025, it has a time-weighted return of +12.0% and is worth £112,000 against £100,000 paid in. Its maximum drawdown was 2.9%.',
        )
        expect(stat('Time-weighted return')).toHaveTextContent('+12.0%')
        expect(within(stat('Time-weighted return')).getByText('Time-weighted return')).toHaveAccessibleDescription(GLOSSARY.timeWeightedReturn)
        expect(stat('Maximum drawdown')).toHaveTextContent('Low point on 31 Dec 2025')
        expect(stat('Expected return')).toHaveTextContent('4.4% a year')
        expect(stat('Expected return')).toHaveTextContent('Annualised return so far: +9.6% a year')
    })

    it('reads the return over every period it has been open, and a yearly average', async () => {
        open()
        const table = await screen.findByRole('table', { name: 'Returns by period' })
        const rows = within(table)
            .getAllByRole('row')
            .slice(1)
            .map((r) => r.textContent)
        expect(rows).toEqual([
            '1 month+4.8%',
            '3 months+3.7%',
            'This year+10.9%',
            '1 year+7.7%',
            'Since opening+12.0%',
            'Annualised+9.6%',
        ])
    })

    it('narrows the charts to a chosen period', async () => {
        const user = userEvent.setup()
        open()
        await user.click(await screen.findByRole('radio', { name: '1 month' }))
        expect(screen.getByRole('figure', { name: 'Value and money paid in' })).toHaveTextContent(
            'Over the last 1 month, the value went from £106,920 to £112,000.',
        )
        expect(screen.getByRole('figure', { name: 'Drawdown from the previous high' })).toBeInTheDocument()
    })

    it('shows the gain on each holding and the simulated record at its level', async () => {
        open()
        const gains = await screen.findByRole('table', { name: 'Gain or loss by holding' })
        expect(within(gains).getByRole('rowheader', { name: /VWRL\.L/ })).toBeInTheDocument()
        expect(within(gains).getAllByRole('row').at(-1)).toHaveTextContent(/All holdings.*£62,240.*£40,000.*\+£22,240/)
        expect(within(gains).getByRole('columnheader', { name: 'Return on cost' })).toBeInTheDocument()
        expect(within(gains).getByRole('columnheader', { name: 'Contribution to return' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'This strategy’s backtest at risk level 5' })).toBeInTheDocument()
        expect(screen.getByText(/, not this portfolio's history/)).toBeInTheDocument()
        expect(screen.getByText('backtest')).toHaveAccessibleDescription(GLOSSARY.backtest)
    })

    it('explains an empty history instead of drawing one', async () => {
        workspace({ '/api/portfolio/19/history': fx.history, '/api/strategy/track-record': fx.trackRecord })
        renderApp('/portfolio/19/performance')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(fx.history.reason as string)
        expect(screen.getByText('The charts start once two days of values are recorded.')).toBeInTheDocument()
        expect(stat('Maximum drawdown')).toHaveTextContent('None yet')
        expect(screen.queryByRole('radiogroup', { name: 'Period' })).not.toBeInTheDocument()
    })

    it('offers a retry when the history does not load', async () => {
        const user = userEvent.setup()
        let fail = true
        workspace({ '/api/portfolio/19/history': () => (fail ? { status: 500, body: { detail: 'Ledger busy.' } } : history) })
        renderApp('/portfolio/19/performance')

        expect(await screen.findByText('The history did not load')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: /^Since it opened/ })).toBeInTheDocument()
    })
})

describe('the asset universe', () => {
    const construction = { ...fx.construction, portfolio_id: 19 }

    it('lists every block, held or not, and asks for this portfolio', async () => {
        const calls = workspace({ '/api/universe': fx.heldUniverse, '/api/portfolio/19/construction': construction })
        renderApp('/portfolio/19/universe')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
            '8 of the 13 building blocks are held: 70% in growth and 30% in defensive holdings.',
        )
        expect(calls.find((c) => c.path === '/api/universe')?.query.get('portfolio_id')).toBe('19')
        expect(screen.getByRole('heading', { level: 2, name: 'Growth 6 of 8 held' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'Defensive 2 of 5 held' })).toBeInTheDocument()
        expect(document.title).toBe('Asset universe · Portfolio 19 · UK Robo Advisor')
    })

    it('gives each held block its estimates, fund facts and why its fund was chosen', async () => {
        workspace({ '/api/universe': fx.heldUniverse, '/api/portfolio/19/construction': construction })
        renderApp('/portfolio/19/universe')

        const cash = (await screen.findByRole('heading', { level: 3, name: 'Cash-like fund' })).closest('li') as HTMLElement
        expect(cash).toHaveTextContent('15.0%')
        expect(within(cash).getByText('Volatility').closest('div')).toHaveTextContent(/0\.6% a year$/)
        expect(within(cash).getByText('Risk contribution')).toHaveAccessibleDescription(GLOSSARY.riskContribution)
        expect(cash).toHaveTextContent('ERNS.L · IE00BCRY6557 · 0.06% a year')
        expect(cash).toHaveTextContent('CSH2.L, the first choice, had too little usable price history when the portfolio was built, so ERNS.L is held instead.')
        const factsheet = within(cash).getAllByRole('link', { name: /Factsheet/ })[0]
        expect(factsheet).toHaveAttribute('target', '_blank')
        expect(factsheet).toHaveAttribute('rel', 'noreferrer')

        const japan = screen.getByRole('heading', { level: 3, name: 'Japanese shares' }).closest('li') as HTMLElement
        expect(japan).toHaveTextContent('Not held')
        expect(japan).toHaveTextContent('Not held: the optimiser gave it no weight at this risk level.')
    })

    it('never links a factsheet that is not a plain https address', async () => {
        const unsafe = {
            ...fx.heldUniverse,
            blocks: fx.heldUniverse.blocks.map((b) =>
                b.asset_class === 'us_equity' ? { ...b, candidates: b.candidates.map((c) => ({ ...c, factsheet_url: 'javascript:alert(1)' })) } : b,
            ),
        }
        workspace({ '/api/universe': unsafe, '/api/portfolio/19/construction': construction })
        renderApp('/portfolio/19/universe')

        const us = (await screen.findByRole('heading', { level: 3, name: 'US shares' })).closest('li') as HTMLElement
        expect(within(us).queryByRole('link')).not.toBeInTheDocument()
    })

    it('shows where the risk comes from and how the funds move together', async () => {
        workspace({ '/api/universe': fx.heldUniverse, '/api/portfolio/19/construction': construction })
        renderApp('/portfolio/19/universe')

        const risk = await screen.findByRole('figure', { name: 'Where the risk comes from' })
        expect(risk).toHaveTextContent('The biggest source of risk: US shares, 45% of the value but 71% of the risk.')
        expect(risk).toHaveTextContent('Volatilities include a 1.15× allowance')
        expect(
            screen.getByRole('img', {
                name: 'Correlations between 8 funds. Closest: European shares and UK shares, 0.78. Most independent: Gold and Cash-like fund, 0.02.',
            }),
        ).toBeInTheDocument()
        expect(screen.getByRole('figure', { name: 'Where the shares are' })).toBeInTheDocument()
    })

    it('says so when the estimates behind an older portfolio were not kept', async () => {
        workspace({ '/api/universe': fx.heldUniverse, '/api/portfolio/19/construction': { portfolio_id: 19, recorded: false, snapshot: null } })
        renderApp('/portfolio/19/universe')

        expect(await screen.findByText('The estimates behind this portfolio were not recorded')).toBeInTheDocument()
        expect(screen.queryByRole('figure', { name: 'How the funds move together' })).not.toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^8 of the 13 building blocks are held/)
    })

    it('offers a retry when the blocks do not load', async () => {
        const user = userEvent.setup()
        let fail = true
        workspace({
            '/api/universe': () => (fail ? { status: 500, body: { detail: 'Registry busy.' } } : fx.heldUniverse),
            '/api/portfolio/19/construction': construction,
        })
        renderApp('/portfolio/19/universe')

        expect(await screen.findByText('The building blocks did not load')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('heading', { level: 1, name: /^8 of the 13/ })).toBeInTheDocument()
    })
})
