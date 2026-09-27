/**
 * A portfolio in words. Pure, so the sentence at the top of each page is
 * tested against the figures it is built from.
 */
import type { Performance, PortfolioSummary } from '@/api/schemas'
import { date, money } from '@/lib/format'

/**
 * Portfolios opened before the ledger existed have holdings but no recorded
 * purchases, so the API values them at £0. They must not be shown as a loss.
 */
export function isUnrecorded(p: Pick<Performance, 'net_contributions' | 'total_value'>): boolean {
    return p.net_contributions === 0 && p.total_value === 0
}

/** "Worth £50,012 on 26 Sept 2026: £12 more than the £50,000 paid in. Every holding is within its band." */
export function overviewSentence(p: Performance): string {
    const gain = p.total_value - p.net_contributions
    const when = p.valued_at ? ` on ${date(p.valued_at)}` : ''
    const change =
        Math.round(gain) === 0
            ? `the same as the ${money(p.net_contributions)} paid in`
            : `${money(Math.abs(gain))} ${gain > 0 ? 'more' : 'less'} than the ${money(p.net_contributions)} paid in`
    const bands = p.needs_rebalance ? 'It has drifted far enough from its targets to rebalance.' : 'Every holding is within its band.'
    return `Worth ${money(p.total_value)}${when}: ${change}. ${bands}`
}

/** "3 portfolios, worth £152,400 together." Unvalued ones are counted but not added. */
export function listSentence(rows: readonly PortfolioSummary[]): string {
    const valued = rows.filter((r) => r.total_value !== null)
    const total = valued.reduce((sum, r) => sum + (r.total_value ?? 0), 0)
    const count = `${rows.length} portfolio${rows.length === 1 ? '' : 's'}`
    if (valued.length === 0) return `${count}, none valued yet.`
    const unvalued = rows.length - valued.length
    return `${count}, worth ${money(total)} together${unvalued ? ` (${unvalued} not valued)` : ''}.`
}

/** "Portfolio 19" when it has no name of its own, or a generic default name. */
export function portfolioName(row: Pick<PortfolioSummary, 'portfolio_id' | 'name'>): string {
    const name = row.name?.trim()
    return name && name !== 'My Portfolio' ? name : `Portfolio ${row.portfolio_id}`
}
