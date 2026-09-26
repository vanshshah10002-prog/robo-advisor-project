/**
 * react-query keys and hooks
 * ==========================
 * Keys are hierarchical so a mutation can invalidate everything it touches
 * for one portfolio with a single `invalidateQueries({ queryKey: keys.portfolio(id) })`.
 */

import {
    QueryClient,
    keepPreviousData,
    useMutation,
    useQuery,
    useQueryClient,
} from '@tanstack/react-query'
import * as api from './endpoints'
import { ApiError } from './http'
import type {
    ContributionRequest,
    MonteCarloRequest,
    PortfolioRequest,
    PreviewRequest,
    QuickRiskRequest,
    RiskProfileRequest,
} from './schemas'

const MINUTE = 60_000
const MAX_RETRIES = 2

export const keys = {
    quiz: ['quiz'] as const,
    quizMinimal: ['quiz', 'minimal'] as const,
    riskProfile: (userId: number) => ['risk-profile', userId] as const,
    userPortfolios: (userId: number) => ['portfolios', 'user', userId] as const,
    portfolio: (id: number) => ['portfolio', id] as const,
    portfolioDetail: (id: number) => ['portfolio', id, 'detail'] as const,
    performance: (id: number) => ['portfolio', id, 'performance'] as const,
    rebalancePlan: (id: number) => ['portfolio', id, 'rebalance'] as const,
    transactions: (id: number) => ['portfolio', id, 'transactions'] as const,
    construction: (id: number) => ['portfolio', id, 'construction'] as const,
    history: (id: number) => ['portfolio', id, 'history'] as const,
    portfolioUniverse: (id: number) => ['portfolio', id, 'universe'] as const,
    universe: ['universe'] as const,
    preview: (req: PreviewRequest) => ['preview', req] as const,
    trackRecord: (risk: number) => ['track-record', risk] as const,
    monteCarlo: (req: MonteCarloRequest) => ['monte-carlo', req] as const,
    frontier: (assetClasses: readonly string[], riskScore: number) =>
        ['efficient-frontier', [...assetClasses].sort(), riskScore] as const,
    assetClasses: ['asset-classes'] as const,
    etfs: (assetClass?: string) => ['etfs', assetClass ?? 'all'] as const,
    etf: (ticker: string) => ['etf', ticker] as const,
    priceHistory: (ticker: string, years: number) => ['prices', ticker, years] as const,
}

/** Retry only what a retry can fix: network drops and 5xx, never 4xx or a broken contract. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
    if (failureCount >= MAX_RETRIES) return false
    if (!(error instanceof ApiError)) return true
    return error.kind === 'network' || (error.kind === 'http' && error.status >= 500)
}

export function createQueryClient(): QueryClient {
    return new QueryClient({
        defaultOptions: {
            queries: { staleTime: MINUTE, retry: shouldRetry, refetchOnWindowFocus: false },
            mutations: { retry: false },
        },
    })
}

// ─── Queries ─────────────────────────────────────────────────────────────────

export const useQuizQuestions = () =>
    useQuery({ queryKey: keys.quiz, queryFn: ({ signal }) => api.getQuizQuestions({ signal }), staleTime: Infinity })

export const useMinimalQuizQuestions = () =>
    useQuery({
        queryKey: keys.quizMinimal,
        queryFn: ({ signal }) => api.getMinimalQuizQuestions({ signal }),
        staleTime: Infinity,
    })

export const useRiskProfile = (userId: number | null) =>
    useQuery({
        queryKey: keys.riskProfile(userId ?? -1),
        queryFn: ({ signal }) => api.getRiskProfile(userId as number, { signal }),
        enabled: userId !== null,
    })

export const useUserPortfolios = (userId: number | null) =>
    useQuery({
        queryKey: keys.userPortfolios(userId ?? -1),
        queryFn: ({ signal }) => api.listUserPortfolios(userId as number, { signal }),
        enabled: userId !== null,
    })

export const usePortfolioDetail = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.portfolioDetail(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getPortfolio(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
    })

export const usePerformance = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.performance(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getPerformance(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
    })

export const useRebalancePlan = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.rebalancePlan(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getRebalancePlan(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
    })

export const useTransactions = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.transactions(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getTransactions(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
    })

/** Previews change with the risk slider: keep the last one on screen while the next loads. */
export const usePreview = (req: PreviewRequest | null) =>
    useQuery({
        queryKey: req ? keys.preview(req) : ['preview', 'idle'],
        queryFn: ({ signal }) => api.previewPortfolio(req as PreviewRequest, { signal }),
        enabled: req !== null,
        placeholderData: keepPreviousData,
        staleTime: 10 * MINUTE,
    })

export const useConstruction = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.construction(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getConstruction(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
        staleTime: Infinity,
    })

export const useHistory = (portfolioId: number | null) =>
    useQuery({
        queryKey: keys.history(portfolioId ?? -1),
        queryFn: ({ signal }) => api.getHistory(portfolioId as number, { signal }),
        enabled: portfolioId !== null,
        staleTime: 30 * MINUTE,
    })

/** Without a portfolio: the building blocks. With one: also what it holds. */
export const useUniverse = (portfolioId?: number) =>
    useQuery({
        queryKey: portfolioId === undefined ? keys.universe : keys.portfolioUniverse(portfolioId),
        queryFn: ({ signal }) => api.getUniverse(portfolioId, { signal }),
        staleTime: 60 * MINUTE,
    })

export const useTrackRecord = (risk: number | null) =>
    useQuery({
        queryKey: keys.trackRecord(risk ?? -1),
        queryFn: ({ signal }) => api.getTrackRecord(risk as number, { signal }),
        enabled: risk !== null,
        staleTime: Infinity,
    })

export const useMonteCarlo = (req: MonteCarloRequest | null) =>
    useQuery({
        queryKey: req ? keys.monteCarlo(req) : ['monte-carlo', 'idle'],
        queryFn: ({ signal }) => api.runMonteCarlo(req as MonteCarloRequest, { signal }),
        enabled: req !== null,
        placeholderData: keepPreviousData,
        staleTime: 10 * MINUTE,
    })

export const useEfficientFrontier = (assetClasses: readonly string[], riskScore: number) =>
    useQuery({
        queryKey: keys.frontier(assetClasses, riskScore),
        queryFn: ({ signal }) => api.getEfficientFrontier({ assetClasses, riskScore }, { signal }),
        enabled: assetClasses.length >= 2,
        staleTime: 30 * MINUTE,
    })

export const useAssetClasses = () =>
    useQuery({
        queryKey: keys.assetClasses,
        queryFn: ({ signal }) => api.listAssetClasses({ signal }),
        staleTime: 60 * MINUTE,
    })

export const useEtfs = (assetClass?: string) =>
    useQuery({
        queryKey: keys.etfs(assetClass),
        queryFn: ({ signal }) => api.listEtfs(assetClass, { signal }),
        staleTime: 60 * MINUTE,
    })

export const useEtf = (ticker: string | null) =>
    useQuery({
        queryKey: keys.etf(ticker ?? ''),
        queryFn: ({ signal }) => api.getEtf(ticker as string, { signal }),
        enabled: ticker !== null,
        staleTime: 60 * MINUTE,
    })

export const usePriceHistory = (ticker: string | null, years: number) =>
    useQuery({
        queryKey: keys.priceHistory(ticker ?? '', years),
        queryFn: ({ signal }) => api.getPriceHistory(ticker as string, years, { signal }),
        enabled: ticker !== null,
        staleTime: 60 * MINUTE,
    })

// ─── Mutations ───────────────────────────────────────────────────────────────

export const useSubmitRiskProfile = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: (body: RiskProfileRequest) => api.submitRiskProfile(body),
        onSuccess: (profile) => qc.setQueryData(keys.riskProfile(profile.user_id), profile),
    })
}

export const useSubmitQuickRiskProfile = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: (body: QuickRiskRequest) => api.submitQuickRiskProfile(body),
        onSuccess: (profile) => qc.setQueryData(keys.riskProfile(profile.user_id), profile),
    })
}

export const useCreatePortfolio = () => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: (body: PortfolioRequest) => api.createPortfolio(body),
        onSuccess: (_created, body) => qc.invalidateQueries({ queryKey: keys.userPortfolios(body.user_id) }),
    })
}

/** Every mutation below changes holdings, cash or prices, so all views of that portfolio refetch. */
function usePortfolioMutation<TArgs, TResult>(
    portfolioId: number,
    mutationFn: (args: TArgs) => Promise<TResult>,
) {
    const qc = useQueryClient()
    return useMutation({
        mutationFn,
        onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolio(portfolioId) }),
    })
}

export const useRefreshPortfolio = (portfolioId: number) =>
    usePortfolioMutation(portfolioId, () => api.refreshPortfolio(portfolioId))

export const useExecuteRebalance = (portfolioId: number) =>
    usePortfolioMutation(portfolioId, () => api.executeRebalance(portfolioId))

export const useContribute = (portfolioId: number) =>
    usePortfolioMutation(portfolioId, (body: ContributionRequest) => api.contribute(portfolioId, body))
