import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { PortfolioSummary } from '@/api/schemas'
import { useIdentity } from '@/store/session'
import { renderApp, stubApi, warmPages, type Handler } from '@/test/app'
import * as fx from '@/test/fixtures'

warmPages(
    () => import('./PortfoliosPage'),
    () => import('./PortfolioLayout'),
    () => import('./overview/OverviewPage'),
)

const ARCHIVED_AT = '2026-09-27T10:00:00'
const house: PortfolioSummary = { ...fx.portfolioSummary, portfolio_id: 21, name: 'House deposit' }
const nineteen: PortfolioSummary = { ...fx.portfolioSummary }

/**
 * A server that moves portfolios between the two lists as they are archived
 * and restored, as the real one does, and can be told to refuse.
 */
function stubLists(active: readonly PortfolioSummary[], archived: readonly PortfolioSummary[] = [], refuse = false) {
    let lists = { active, archived }
    const all = [...active, ...archived]
    const move = (id: number, toArchive: boolean): Handler => () => {
        if (refuse) return { status: 500, body: { detail: 'Database busy.' } }
        const row = all.find((r) => r.portfolio_id === id) as PortfolioSummary
        const moved = { ...row, archived_at: toArchive ? ARCHIVED_AT : null }
        const without = (rows: readonly PortfolioSummary[]) => rows.filter((r) => r.portfolio_id !== id)
        lists = toArchive ? { active: without(lists.active), archived: [moved, ...without(lists.archived)] } : { active: [moved, ...without(lists.active)], archived: without(lists.archived) }
        return { portfolio_id: id, archived_at: moved.archived_at }
    }
    return stubApi({
        '/api/portfolios/user/4': () => lists.active,
        '/api/portfolios/user/4/archived': () => lists.archived,
        ...Object.fromEntries(all.flatMap((r) => [
            [`POST /api/portfolio/${r.portfolio_id}/archive`, move(r.portfolio_id, true)],
            [`POST /api/portfolio/${r.portfolio_id}/restore`, move(r.portfolio_id, false)],
            [`/api/portfolio/${r.portfolio_id}/history`, fx.history],
        ])),
    })
}

const posts = (calls: ReturnType<typeof stubApi>) => calls.filter((c) => c.method === 'POST').map((c) => c.path)

describe('archiving from the list', () => {
    it('moves a portfolio to the archived list, says so, and can undo it', async () => {
        const user = userEvent.setup()
        const calls = stubLists([house, nineteen])
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        expect(await screen.findByRole('heading', { level: 1, name: '2 portfolios, worth £249,036 together.' })).toBeInTheDocument()
        expect(screen.queryByRole('heading', { name: 'Archived' })).not.toBeInTheDocument()

        await user.click(screen.getByRole('button', { name: 'Archive House deposit' }))

        const status = await within(screen.getByRole('main')).findByRole('status')
        await waitFor(() => expect(status).toHaveTextContent('House deposit is archived'))
        expect(status).toHaveTextContent('It is off your list; nothing was deleted, and it still opens.')
        expect(status).toHaveFocus()
        expect(await screen.findByRole('heading', { level: 1, name: '1 portfolio, worth £124,518 together.' })).toBeInTheDocument()
        const archived = await screen.findByRole('table', { name: 'Archived portfolios' })
        expect(within(archived).getByRole('link', { name: 'House deposit' })).toHaveAttribute('href', '/portfolio/21')
        expect(within(archived).getByText('Archived 27 Sept 2026')).toBeInTheDocument()

        await user.click(within(status).getByRole('button', { name: 'Undo' }))

        await waitFor(() => expect(status).toHaveTextContent('House deposit is back on your list'))
        expect(await screen.findByRole('heading', { level: 1, name: '2 portfolios, worth £249,036 together.' })).toBeInTheDocument()
        await waitFor(() => expect(screen.queryByRole('table', { name: 'Archived portfolios' })).not.toBeInTheDocument())
        expect(posts(calls)).toEqual(['/api/portfolio/21/archive', '/api/portfolio/21/restore'])
    })

    it('shows the row being archived as busy, and holds the other rows until it is done', async () => {
        const user = userEvent.setup()
        stubLists([house, nineteen])
        const answer = globalThis.fetch
        let release = () => {}
        const gate = new Promise<void>((resolve) => {
            release = resolve
        })
        vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
            if (url.endsWith('/archive')) await gate
            return answer(url, init)
        })
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        await user.click(await screen.findByRole('button', { name: 'Archive House deposit' }))
        expect(screen.getByRole('button', { name: 'Archive House deposit' })).toHaveAttribute('aria-busy', 'true')
        expect(screen.getByRole('button', { name: 'Archive Portfolio 19' })).toBeDisabled()

        release()
        await waitFor(() => expect(within(screen.getByRole('main')).getByRole('status')).toHaveTextContent('House deposit is archived'))
        expect(screen.getByRole('button', { name: 'Archive Portfolio 19' })).toBeEnabled()
    })

    it('restores from the archived list', async () => {
        const user = userEvent.setup()
        const calls = stubLists([nineteen], [fx.archivedSummary])
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        const archived = await screen.findByRole('table', { name: 'Archived portfolios' })
        expect(within(archived).getByText('Archived 20 Sept 2026')).toBeInTheDocument()
        await user.click(within(archived).getByRole('button', { name: 'Restore Old plan' }))

        await waitFor(() => expect(within(screen.getByRole('main')).getByRole('status')).toHaveTextContent('Old plan is back on your list'))
        expect(await screen.findByRole('link', { name: 'Old plan' })).toHaveAttribute('href', '/portfolio/17')
        expect(posts(calls)).toEqual(['/api/portfolio/17/restore'])
    })

    it('says so when every portfolio is archived, rather than that none were opened', async () => {
        stubLists([], [fx.archivedSummary])
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        expect(await screen.findByText(/Every portfolio opened in this browser is archived/)).toBeInTheDocument()
        expect(screen.queryByText(/No portfolios have been opened/)).not.toBeInTheDocument()
        expect(await screen.findByRole('table', { name: 'Archived portfolios' })).toBeInTheDocument()
    })

    it('points "your portfolio" at the newest one left when the last one opened is archived', async () => {
        const user = userEvent.setup()
        stubLists([house, nineteen])
        useIdentity.getState().setUser(4)
        useIdentity.getState().setLastPortfolio(21)
        renderApp('/portfolios')

        await user.click(await screen.findByRole('button', { name: 'Archive House deposit' }))
        await waitFor(() => expect(useIdentity.getState().lastPortfolioId).toBe(19))
        await user.click(await screen.findByRole('button', { name: 'Archive Portfolio 19' }))
        await waitFor(() => expect(useIdentity.getState().lastPortfolioId).toBeNull())
    })

    it('says when archiving fails, and leaves the list as it was', async () => {
        const user = userEvent.setup()
        stubLists([house, nineteen], [], true)
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        await user.click(await screen.findByRole('button', { name: 'Archive House deposit' }))

        const alert = await screen.findByRole('alert')
        expect(alert).toHaveTextContent('House deposit could not be archived')
        expect(alert).toHaveTextContent('Database busy.')
        expect(screen.getByRole('heading', { level: 1, name: '2 portfolios, worth £249,036 together.' })).toBeInTheDocument()
    })

    it('says when the archived list does not load, with a retry', async () => {
        const user = userEvent.setup()
        let fail = true
        stubApi({
            '/api/portfolios/user/4': [nineteen],
            '/api/portfolios/user/4/archived': () => (fail ? { status: 500, body: { detail: 'Database busy.' } } : [fx.archivedSummary]),
            '/api/portfolio/19/history': fx.history,
        })
        useIdentity.getState().setUser(4)
        renderApp('/portfolios')

        expect(await screen.findByText('Archived portfolios did not load')).toBeInTheDocument()
        fail = false
        await user.click(screen.getByRole('button', { name: 'Try again' }))
        expect(await screen.findByRole('table', { name: 'Archived portfolios' })).toBeInTheDocument()
    })
})

describe('an archived portfolio', () => {
    it('opens as usual, says it is archived, and can be restored', async () => {
        const user = userEvent.setup()
        let archived = true
        const calls = stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': () => ({ ...fx.portfolioDetail, archived, archived_at: archived ? '2026-09-20T09:00:00' : null }),
            'POST /api/portfolio/19/restore': () => {
                archived = false
                return { portfolio_id: 19, archived_at: null }
            },
            '/api/asset-classes': [fx.assetClass],
            '/api/etfs': [fx.etf],
        })
        renderApp('/portfolio/19')

        expect(await screen.findByRole('heading', { level: 1, name: /^Worth £124,518/ })).toBeInTheDocument()
        expect(await screen.findByText('This portfolio is archived')).toBeInTheDocument()
        expect(screen.getByText(/Archived on 20 Sept 2026/)).toBeInTheDocument()

        await user.click(screen.getByRole('button', { name: 'Restore' }))

        await waitFor(() => expect(screen.queryByText('This portfolio is archived')).not.toBeInTheDocument())
        expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/api/portfolio/19/restore'])
    })

    it('says when it could not be restored', async () => {
        const user = userEvent.setup()
        stubApi({
            '/api/performance/19': fx.performance,
            '/api/portfolio/19': { ...fx.portfolioDetail, archived: true, archived_at: '2026-09-20T09:00:00' },
            'POST /api/portfolio/19/restore': { status: 500, body: { detail: 'Database busy.' } },
            '/api/asset-classes': [fx.assetClass],
            '/api/etfs': [fx.etf],
        })
        renderApp('/portfolio/19')

        await user.click(await screen.findByRole('button', { name: 'Restore' }))

        expect(await screen.findByText(/It could not be restored: Database busy\./)).toBeInTheDocument()
        expect(screen.getByText('This portfolio is archived')).toBeInTheDocument()
    })
})
