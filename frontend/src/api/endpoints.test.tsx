import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as fx from '@/test/fixtures'
import * as q from './queries'

type Call = { url: string; method: string; body: unknown }

/** Routes each request to a fixture by path, and records what was sent. */
function stubApi(routes: Record<string, unknown>) {
    const calls: Call[] = []
    vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init?: RequestInit) => {
            calls.push({ url, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined })
            const path = url.split('?')[0]
            if (!(path in routes)) return new Response(JSON.stringify({ detail: `no stub for ${path}` }), { status: 404 })
            return new Response(JSON.stringify(routes[path]), { status: 200 })
        }),
    )
    return calls
}

function wrapper() {
    const client = q.createQueryClient()
    const Wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    return Wrapper
}

afterEach(() => vi.unstubAllGlobals())

type IdleRow = [string, () => { fetchStatus: string }]
type MutationRow = [string, () => { mutate: (v: never) => void; isSuccess: boolean }, string, unknown]

const previewRequest = { risk_score: 7, investment_amount: 50_000, monthly_contribution: 250, uses_isa: true }

const mcRequest = { portfolio_id: 19, initial_investment: 100_000, monthly_contribution: 250, years: 15, n_simulations: 1000 }

const queryCases: [string, () => { isSuccess: boolean; isError: boolean; error: unknown }, string, unknown][] = [
    ['useQuizQuestions', () => q.useQuizQuestions(), '/api/quiz-questions', [fx.quizQuestion]],
    ['useMinimalQuizQuestions', () => q.useMinimalQuizQuestions(), '/api/quiz-questions/minimal', [fx.minimalQuizQuestion]],
    ['useRiskProfile', () => q.useRiskProfile(4), '/api/risk-profile/4', fx.riskProfile],
    ['useUserPortfolios', () => q.useUserPortfolios(4), '/api/portfolios/user/4', [fx.portfolioSummary]],
    ['usePortfolioDetail', () => q.usePortfolioDetail(19), '/api/portfolio/19', fx.portfolioDetail],
    ['usePerformance', () => q.usePerformance(19), '/api/performance/19', fx.performance],
    ['useRebalancePlan', () => q.useRebalancePlan(19), '/api/rebalance/19', fx.rebalancePlan],
    ['useTransactions', () => q.useTransactions(19), '/api/transactions/19', [fx.transaction]],
    ['useMonteCarlo', () => q.useMonteCarlo(mcRequest), '/api/monte-carlo', fx.monteCarlo],
    ['useEfficientFrontier', () => q.useEfficientFrontier(['global_bonds', 'global_equity'], 5), '/api/efficient-frontier', fx.efficientFrontier],
    ['useAssetClasses', () => q.useAssetClasses(), '/api/asset-classes', [fx.assetClass]],
    ['useEtfs', () => q.useEtfs('global_equity'), '/api/etfs', [fx.etf]],
    ['useEtf', () => q.useEtf('VWRL.L'), '/api/etf/VWRL.L', fx.etf],
    ['usePriceHistory', () => q.usePriceHistory('VWRL.L', 5), '/api/prices/VWRL.L', [fx.priceBar]],
    ['usePreview', () => q.usePreview(previewRequest), '/api/portfolio/preview', fx.preview],
    ['useConstruction', () => q.useConstruction(19), '/api/portfolio/19/construction', fx.construction],
    ['useHistory', () => q.useHistory(19), '/api/portfolio/19/history', fx.history],
    ['useUniverse', () => q.useUniverse(), '/api/universe', fx.universe],
    ['useUniverse (portfolio)', () => q.useUniverse(19), '/api/universe', fx.universe],
    ['useTrackRecord', () => q.useTrackRecord(5), '/api/strategy/track-record', fx.trackRecord],
]

describe('query hooks', () => {
    it.each(queryCases)('%s requests %s and parses the response', async (_name, hook, path, payload) => {
        const calls = stubApi({ [path]: payload })
        const { result } = renderHook(hook, { wrapper: wrapper() })

        await waitFor(() => expect(result.current.isSuccess || result.current.isError).toBe(true))
        expect(result.current.error).toBeNull()
        expect(calls).toHaveLength(1)
        expect(calls[0].url.split('?')[0]).toBe(path)
    })

    it('sends frontier and ETF filters as query parameters', async () => {
        const calls = stubApi({ '/api/efficient-frontier': fx.efficientFrontier, '/api/etfs': [fx.etf] })
        const w = wrapper()
        const frontier = renderHook(() => q.useEfficientFrontier(['uk_equity', 'uk_gilts'], 6.5), { wrapper: w })
        const etfs = renderHook(() => q.useEtfs('uk_gilts'), { wrapper: w })

        await waitFor(() => expect(frontier.result.current.isSuccess && etfs.result.current.isSuccess).toBe(true))
        const urls = calls.map((c) => c.url)
        expect(urls).toContain('/api/efficient-frontier?asset_classes=uk_equity%2Cuk_gilts&risk_score=6.5')
        expect(urls).toContain('/api/etfs?asset_class=uk_gilts')
    })

    it('posts the Monte Carlo request body', async () => {
        const calls = stubApi({ '/api/monte-carlo': fx.monteCarlo })
        const { result } = renderHook(() => q.useMonteCarlo(mcRequest), { wrapper: wrapper() })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(calls[0]).toMatchObject({ method: 'POST', body: mcRequest })
    })

    it.each<IdleRow>([
        ['useRiskProfile', () => q.useRiskProfile(null)],
        ['useUserPortfolios', () => q.useUserPortfolios(null)],
        ['usePortfolioDetail', () => q.usePortfolioDetail(null)],
        ['useRebalancePlan', () => q.useRebalancePlan(null)],
        ['useTransactions', () => q.useTransactions(null)],
        ['useMonteCarlo', () => q.useMonteCarlo(null)],
        ['useEfficientFrontier', () => q.useEfficientFrontier(['only_one'], 5)],
        ['useEtf', () => q.useEtf(null)],
        ['usePriceHistory', () => q.usePriceHistory(null, 5)],
        ['usePreview', () => q.usePreview(null)],
        ['useConstruction', () => q.useConstruction(null)],
        ['useHistory', () => q.useHistory(null)],
        ['useTrackRecord', () => q.useTrackRecord(null)],
    ])('%s waits until it has what it needs', (_name, hook) => {
        const calls = stubApi({})
        const { result } = renderHook(hook, { wrapper: wrapper() })
        expect(result.current.fetchStatus).toBe('idle')
        expect(calls).toHaveLength(0)
    })
})

describe('mutation hooks', () => {
    it.each<MutationRow>([
        ['useSubmitRiskProfile', () => q.useSubmitRiskProfile(), '/api/risk-profile', fx.riskProfile],
        ['useSubmitQuickRiskProfile', () => q.useSubmitQuickRiskProfile(), '/api/risk-profile/quick', fx.riskProfile],
        ['useCreatePortfolio', () => q.useCreatePortfolio(), '/api/portfolio', fx.createdPortfolio],
        ['useRefreshPortfolio', () => q.useRefreshPortfolio(19), '/api/portfolio/19/refresh', fx.refreshResult],
        ['useExecuteRebalance', () => q.useExecuteRebalance(19), '/api/rebalance/19/execute', fx.rebalancePlan],
        ['useContribute', () => q.useContribute(19), '/api/portfolio/19/contribute', fx.contributionResult],
    ])('%s posts to %s', async (_name, hook, path, payload) => {
        const calls = stubApi({ [path]: payload })
        const { result } = renderHook(hook, { wrapper: wrapper() })

        // Each mutation's variables are validated by its own schema at the call site;
        // here only the transport matters.
        ;(result.current.mutate as (v: unknown) => void)({ user_id: 4, amount_gbp: 500 })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(calls[0]).toMatchObject({ url: path, method: 'POST' })
    })

    it('caches the submitted risk profile under its user', async () => {
        stubApi({ '/api/risk-profile/quick': fx.riskProfile })
        const client = q.createQueryClient()
        const Wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={client}>{children}</QueryClientProvider>
        )
        const { result } = renderHook(() => q.useSubmitQuickRiskProfile(), { wrapper: Wrapper })

        result.current.mutate({
            name: 'Sam',
            loss_reaction: 3,
            time_horizon_choice: 4,
            financial_cushion: 3,
            investment_amount: 100_000,
            uses_isa: true,
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(client.getQueryData(q.keys.riskProfile(4))).toEqual(fx.riskProfile)
    })

    it('refreshes the user’s portfolio list after creating one', async () => {
        stubApi({ '/api/portfolio': fx.createdPortfolio })
        const client = q.createQueryClient()
        const invalidate = vi.spyOn(client, 'invalidateQueries')
        const Wrapper = ({ children }: { children: ReactNode }) => (
            <QueryClientProvider client={client}>{children}</QueryClientProvider>
        )
        const { result } = renderHook(() => q.useCreatePortfolio(), { wrapper: Wrapper })

        result.current.mutate({ user_id: 4, risk_score: 5, investment_amount: 100_000, monthly_contribution: 0, uses_isa: true })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(invalidate).toHaveBeenCalledWith({ queryKey: q.keys.userPortfolios(4) })
    })
})
