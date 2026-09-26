/**
 * The building blocks, what the portfolio holds of each and why. Share of
 * risk and correlations come from the construction snapshot: the estimates
 * the portfolio was actually built with, not today's.
 */
import type { ConstructionSnapshot, Sleeve, Universe, UniverseBlock, UniverseFund } from '@/api/schemas'
import { percent } from '@/lib/format'

type SnapshotHolding = ConstructionSnapshot['holdings'][number]

export interface BlockRow {
    assetClass: string
    name: string
    description: string
    sleeve: Sleeve
    rule: string
    held: UniverseFund | null
    weight: number | null
    target: number | null
    expectedReturn: number | null
    volatility: number | null
    riskShare: number | null
    /** Why it is not held, or why its fund is not the first choice. Null when neither applies. */
    note: string | null
    alternatives: readonly UniverseFund[]
}

/**
 * Each holding's share of the portfolio's variance: w·(Σw) / w'Σw, with Σ
 * built from the snapshot's volatilities and correlations. The shares sum to 1.
 * Empty when the snapshot lacks a volatility or a correlation it needs.
 */
export function riskShares(snapshot: ConstructionSnapshot): Map<string, number> {
    const { holdings, correlation } = snapshot
    const at = new Map(correlation.tickers.map((t, i) => [t, i]))
    const usable = holdings.every((h) => h.volatility !== null && at.has(h.ticker))
    if (!usable || holdings.length === 0) return new Map()
    const corr = (a: SnapshotHolding, b: SnapshotHolding) => correlation.matrix[at.get(a.ticker) as number][at.get(b.ticker) as number]
    const marginal = holdings.map((a) =>
        holdings.reduce((sum, b) => sum + (a.volatility as number) * (b.volatility as number) * corr(a, b) * b.weight, 0),
    )
    const variance = holdings.reduce((sum, h, i) => sum + h.weight * marginal[i], 0)
    if (variance <= 0) return new Map()
    return new Map(holdings.map((h, i) => [h.ticker, (h.weight * marginal[i]) / variance]))
}

function blockNote(block: UniverseBlock, passedOver: readonly string[]): string | null {
    const first = block.candidates.find((c) => c.preferred) ?? block.candidates[0]
    if (block.held_ticker === null) {
        const allPassed = block.candidates.length > 0 && block.candidates.every((c) => passedOver.includes(c.ticker))
        return allPassed
            ? 'Not held: none of its funds had enough usable price history when the portfolio was built.'
            : 'Not held: the optimiser gave it no weight at this risk level.'
    }
    if (!first || first.ticker === block.held_ticker) return null
    return passedOver.includes(first.ticker)
        ? `${first.ticker}, the first choice, had too little usable price history when the portfolio was built, so ${block.held_ticker} is held instead.`
        : `${block.held_ticker} is held rather than the first choice, ${first.ticker}.`
}

/** One row per building block, growth first, then by weight held. */
export function blockRows(universe: Universe, snapshot: ConstructionSnapshot | null): BlockRow[] {
    const estimates = new Map((snapshot?.holdings ?? []).map((h) => [h.ticker, h]))
    const shares = snapshot ? riskShares(snapshot) : new Map<string, number>()
    const rows = universe.blocks.map((b) => {
        const held = b.candidates.find((c) => c.ticker === b.held_ticker) ?? null
        const estimate = b.held_ticker ? estimates.get(b.held_ticker) : undefined
        return {
            assetClass: b.asset_class,
            name: b.name,
            description: b.description,
            sleeve: b.sleeve,
            rule: b.rule,
            held,
            weight: b.held_weight,
            target: b.target_weight,
            expectedReturn: estimate?.expected_return ?? null,
            volatility: estimate?.volatility ?? null,
            riskShare: b.held_ticker ? (shares.get(b.held_ticker) ?? null) : null,
            note: blockNote(b, snapshot?.etf_fallbacks[b.asset_class] ?? []),
            alternatives: b.candidates.filter((c) => c.ticker !== b.held_ticker),
        }
    })
    const rank = (s: Sleeve) => (s === 'growth' ? 0 : 1)
    return rows.sort((a, b) => rank(a.sleeve) - rank(b.sleeve) || (b.weight ?? 0) - (a.weight ?? 0))
}

/** "9 of the 13 building blocks are held: 40% in growth and 60% in defensive holdings." */
export function universeSentence(rows: readonly BlockRow[]): string {
    const held = rows.filter((r) => r.held !== null)
    const inSleeve = (s: Sleeve) => held.filter((r) => r.sleeve === s).reduce((sum, r) => sum + (r.weight ?? 0), 0)
    return (
        `${held.length} of the ${rows.length} building blocks are held: ` +
        `${percent(inSleeve('growth'), 0)} in growth and ${percent(inSleeve('defensive'), 0)} in defensive holdings.`
    )
}

/** A share for a sentence: "51%", or "under 1%" rather than a misleading "0%". */
const shareWords = (v: number) => (v > 0 && v < 0.005 ? 'under 1%' : percent(v, 0))

/**
 * "24% of the money but 51% of the risk", or "and" when the two round alike.
 * A hedge can have a share below zero: it lowers the risk, and says so.
 */
function moneyAndRisk(r: { weight: number; riskShare: number }): string {
    const money = shareWords(r.weight)
    if (r.riskShare < 0) return `${money} of the money, and it lowers the risk overall`
    const risk = shareWords(r.riskShare)
    return `${money} of the money ${money === risk ? 'and' : 'but'} ${risk} of the risk`
}

/**
 * The holding that carries the most risk, then the one that carries least for
 * its size: "The biggest source of risk: US shares, 24% of the money but 51%
 * of the risk. Least for its size: Cash-like fund, 30% of the money but under
 * 1% of the risk."
 */
export function riskSentence(rows: readonly BlockRow[]): string | null {
    const held = rows.filter((r): r is BlockRow & { weight: number; riskShare: number } => (r.weight ?? 0) > 0 && r.riskShare !== null)
    if (held.length < 2) return null
    const ratio = (r: { weight: number; riskShare: number }) => r.riskShare / r.weight
    const biggest = held.reduce((a, b) => (b.riskShare > a.riskShare ? b : a))
    const least = held.reduce((a, b) => (ratio(b) < ratio(a) ? b : a))
    const lead = `The biggest source of risk: ${biggest.name}, ${moneyAndRisk(biggest)}.`
    return least === biggest ? lead : `${lead} Least for its size: ${least.name}, ${moneyAndRisk(least)}.`
}

/** Where the shares are: each equity block's part of all the shares held. */
export function regionShares(rows: readonly BlockRow[], universe: Universe): { key: string; label: string; detail?: string; weight: number }[] {
    const equity = new Set(universe.blocks.filter((b) => b.equity_share_range !== null).map((b) => b.asset_class))
    const held = rows.filter((r) => equity.has(r.assetClass) && (r.weight ?? 0) > 0)
    const total = held.reduce((sum, r) => sum + (r.weight ?? 0), 0)
    if (total <= 0) return []
    return held.map((r) => ({ key: r.assetClass, label: r.name, detail: r.held?.ticker, weight: (r.weight ?? 0) / total }))
}

/** The correlations between the funds held, largest holding first. */
export function heldCorrelations(snapshot: ConstructionSnapshot, rows: readonly BlockRow[]) {
    const at = new Map(snapshot.correlation.tickers.map((t, i) => [t, i]))
    const held = rows.filter((r): r is BlockRow & { held: UniverseFund } => r.held !== null && at.has(r.held.ticker))
    const index = held.map((r) => at.get(r.held.ticker) as number)
    return {
        labels: held.map((r) => ({ key: r.held.ticker, label: r.name, short: r.held.ticker })),
        matrix: index.map((i) => index.map((j) => snapshot.correlation.matrix[i][j])),
    }
}

