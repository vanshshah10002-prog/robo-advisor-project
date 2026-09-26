/**
 * API Client — Backend Communication Layer
 * ==========================================
 * All API calls to the FastAPI backend.
 * Uses fetch with the Vite proxy (/api → localhost:8000).
 */

import type { PortfolioSummary } from './schemas'

const API_BASE = '/api'

async function request<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE}${endpoint}`
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
}

// --- Onboarding ---

export interface QuizQuestion {
    id: number
    text: string
    options: string[]
    inverted?: boolean
}

export function fetchQuizQuestions(): Promise<QuizQuestion[]> {
    return request('/quiz-questions')
}

export function submitRiskProfile(data: {
    name: string
    quiz_answers: { question_id: number; answer: number }[]
    objective_inputs: {
        monthly_income: number
        monthly_expenses: number
        total_investable_assets: number
        investment_amount: number
        employment_type: string
        time_horizon_years: number
        has_emergency_fund: string
    }
    uses_isa: boolean
}) {
    return request('/risk-profile', {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

// --- Asset Classes ---

export interface AssetClassInfo {
    id: string
    name: string
    description: string
    risk_level: number
    primary_etf: string | null
    primary_etf_name: string | null
    expense_ratio: number | null
    factsheet_url: string | null
    etf_count: number
}

export function fetchAssetClasses(): Promise<AssetClassInfo[]> {
    return request('/asset-classes')
}

// --- Portfolio ---

export function createPortfolio(data: {
    user_id: number
    risk_score: number
    selected_asset_classes?: string[]
    investment_amount: number
    monthly_contribution: number
    uses_isa: boolean
}) {
    return request('/portfolio', {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

export function fetchPortfolio(portfolioId: number) {
    return request(`/portfolio/${portfolioId}`)
}

export function fetchUserPortfolios(userId: number): Promise<PortfolioSummary[]> {
    return request(`/portfolios/user/${userId}`)
}

export function refreshPortfolio(portfolioId: number): Promise<{ total_return_pct: number }> {
    return request(`/portfolio/${portfolioId}/refresh`, {
        method: 'POST',
    })
}

// --- Simulation ---

export interface FrontierPoint {
    expected_return: number
    volatility: number
    sharpe_ratio: number
    weights: Record<string, number>
}

export function fetchEfficientFrontier(
    assetClasses: string[],
    riskScore: number
): Promise<{ frontier_points: FrontierPoint[]; risk_free_rate: number }> {
    const params = new URLSearchParams({
        asset_classes: assetClasses.join(','),
        risk_score: String(riskScore),
    })
    return request(`/efficient-frontier?${params}`)
}

export function runMonteCarlo(data: {
    portfolio_id?: number
    weights?: Record<string, number>
    initial_investment: number
    monthly_contribution: number
    years: number
    n_simulations: number
}) {
    return request('/monte-carlo', {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

// --- Performance ---

export function fetchPerformance(portfolioId: number) {
    return request(`/performance/${portfolioId}`)
}

export function fetchRebalance(portfolioId: number) {
    return request(`/rebalance/${portfolioId}`)
}

// --- Market Data ---

export function fetchEtfList(assetClass?: string) {
    const params = assetClass ? `?asset_class=${assetClass}` : ''
    return request(`/etfs${params}`)
}

export function fetchPrices(ticker: string, years: number = 5) {
    return request(`/prices/${ticker}?period_years=${years}`)
}

export function fetchLatestPrice(ticker: string) {
    return request<{ ticker: string; price: number }>(`/price/${ticker}`)
}
