/**
 * One typed function per backend route. Components never call `fetch`
 * directly; they go through `queries.ts`, which wraps these in react-query.
 */

import { z } from 'zod'
import { request } from './http'
import {
    assetClassSchema,
    constructionSchema,
    contributionResultSchema,
    createdPortfolioSchema,
    efficientFrontierSchema,
    etfSchema,
    historySchema,
    latestPriceSchema,
    minimalQuizQuestionSchema,
    monteCarloSchema,
    performanceSchema,
    portfolioDetailSchema,
    portfolioSummarySchema,
    previewSchema,
    priceBarSchema,
    quizQuestionSchema,
    rebalancePlanSchema,
    refreshResultSchema,
    riskProfileSchema,
    trackRecordSchema,
    transactionSchema,
    universeSchema,
    type ContributionRequest,
    type MonteCarloRequest,
    type PortfolioRequest,
    type PreviewRequest,
    type QuickRiskRequest,
    type RiskProfileRequest,
} from './schemas'

type Signal = { signal?: AbortSignal }

// Onboarding
export const getQuizQuestions = ({ signal }: Signal = {}) =>
    request('/quiz-questions', z.array(quizQuestionSchema), { signal })

export const getMinimalQuizQuestions = ({ signal }: Signal = {}) =>
    request('/quiz-questions/minimal', z.array(minimalQuizQuestionSchema), { signal })

export const submitRiskProfile = (body: RiskProfileRequest) =>
    request('/risk-profile', riskProfileSchema, { method: 'POST', body })

export const submitQuickRiskProfile = (body: QuickRiskRequest) =>
    request('/risk-profile/quick', riskProfileSchema, { method: 'POST', body })

export const getRiskProfile = (userId: number, { signal }: Signal = {}) =>
    request(`/risk-profile/${userId}`, riskProfileSchema, { signal })

// Portfolio
export const createPortfolio = (body: PortfolioRequest) =>
    request('/portfolio', createdPortfolioSchema, { method: 'POST', body })

export const getPortfolio = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/portfolio/${portfolioId}`, portfolioDetailSchema, { signal })

export const listUserPortfolios = (userId: number, { signal }: Signal = {}) =>
    request(`/portfolios/user/${userId}`, z.array(portfolioSummarySchema), { signal })

export const refreshPortfolio = (portfolioId: number) =>
    request(`/portfolio/${portfolioId}/refresh`, refreshResultSchema, { method: 'POST' })

/** Builds without opening: nothing is stored or bought. */
export const previewPortfolio = (body: PreviewRequest, { signal }: Signal = {}) =>
    request('/portfolio/preview', previewSchema, { method: 'POST', body, signal })

export const getConstruction = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/portfolio/${portfolioId}/construction`, constructionSchema, { signal })

export const getHistory = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/portfolio/${portfolioId}/history`, historySchema, { signal })

export const getUniverse = (portfolioId?: number, { signal }: Signal = {}) =>
    request('/universe', universeSchema, { query: { portfolio_id: portfolioId }, signal })

export const getTrackRecord = (risk: number, { signal }: Signal = {}) =>
    request('/strategy/track-record', trackRecordSchema, { query: { risk }, signal })

// Performance, rebalancing, cash flows
export const getPerformance = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/performance/${portfolioId}`, performanceSchema, { signal })

export const getRebalancePlan = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/rebalance/${portfolioId}`, rebalancePlanSchema, { signal })

export const executeRebalance = (portfolioId: number) =>
    request(`/rebalance/${portfolioId}/execute`, rebalancePlanSchema, { method: 'POST' })

export const contribute = (portfolioId: number, body: ContributionRequest) =>
    request(`/portfolio/${portfolioId}/contribute`, contributionResultSchema, { method: 'POST', body })

export const getTransactions = (portfolioId: number, { signal }: Signal = {}) =>
    request(`/transactions/${portfolioId}`, z.array(transactionSchema), { signal })

// Simulation
export const runMonteCarlo = (body: MonteCarloRequest, { signal }: Signal = {}) =>
    request('/monte-carlo', monteCarloSchema, { method: 'POST', body, signal })

export const getEfficientFrontier = (
    { assetClasses, riskScore }: { assetClasses: readonly string[]; riskScore: number },
    { signal }: Signal = {},
) =>
    request('/efficient-frontier', efficientFrontierSchema, {
        query: { asset_classes: assetClasses.join(','), risk_score: riskScore },
        signal,
    })

// Market data
export const listEtfs = (assetClass?: string, { signal }: Signal = {}) =>
    request('/etfs', z.array(etfSchema), { query: { asset_class: assetClass }, signal })

export const getEtf = (ticker: string, { signal }: Signal = {}) =>
    request(`/etf/${encodeURIComponent(ticker)}`, etfSchema, { signal })

export const listAssetClasses = ({ signal }: Signal = {}) =>
    request('/asset-classes', z.array(assetClassSchema), { signal })

export const getPriceHistory = (ticker: string, periodYears: number, { signal }: Signal = {}) =>
    request(`/prices/${encodeURIComponent(ticker)}`, z.array(priceBarSchema), {
        query: { period_years: periodYears },
        signal,
    })

export const getLatestPrice = (ticker: string, { signal }: Signal = {}) =>
    request(`/price/${encodeURIComponent(ticker)}`, latestPriceSchema, { signal })
