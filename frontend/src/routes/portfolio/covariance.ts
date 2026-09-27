/**
 * Covariance from the construction snapshot: the volatilities and
 * correlations the portfolio was built with, shared by the risk shares on
 * the Universe page and the statistics on the Overview.
 */
import type { ConstructionSnapshot } from '@/api/schemas'

/**
 * Σ in the order of the snapshot's holdings: σᵢσⱼρᵢⱼ. Null when there are no
 * holdings, or one lacks a volatility or a place in the correlations.
 */
export function covarianceMatrix(snapshot: ConstructionSnapshot): number[][] | null {
    const { holdings, correlation } = snapshot
    const at = new Map(correlation.tickers.map((t, i) => [t, i]))
    if (holdings.length === 0 || !holdings.every((h) => h.volatility !== null && at.has(h.ticker))) return null
    const index = holdings.map((h) => at.get(h.ticker) as number)
    const vol = holdings.map((h) => h.volatility as number)
    return vol.map((a, i) => vol.map((b, j) => a * b * correlation.matrix[index[i]][index[j]]))
}

/** Σw: each holding's covariance with the whole portfolio. */
export const marginal = (cov: readonly (readonly number[])[], weights: readonly number[]): number[] =>
    cov.map((row) => row.reduce((sum, c, j) => sum + c * weights[j], 0))

/** w'Σw: the portfolio's variance. */
export const variance = (cov: readonly (readonly number[])[], weights: readonly number[]): number =>
    marginal(cov, weights).reduce((sum, m, i) => sum + weights[i] * m, 0)
