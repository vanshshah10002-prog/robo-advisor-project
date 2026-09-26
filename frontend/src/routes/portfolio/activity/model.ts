/**
 * The ledger and the two things that change it, adding money and
 * rebalancing, in words. Pure, so each sentence is tested against its figures.
 */
import type { RebalancePlan, Transaction } from '@/api/schemas'
import { date, money, signedMoney } from '@/lib/format'

const ACTIONS: Readonly<Record<string, string>> = { deposit: 'Paid in', buy: 'Bought', sell: 'Sold' }

export const actionLabel = (action: string) => ACTIONS[action] ?? action.charAt(0).toUpperCase() + action.slice(1)

/** Small sums keep their pence, so £0.42 of costs never reads as "£0". */
export const pounds = (v: number) => money(v, { pence: Math.abs(v) < 10 && v !== 0 })

/** Newest first; entries made in the same moment keep the order they were written in, reversed. */
export const newestFirst = (rows: readonly Transaction[]): Transaction[] =>
    [...rows].sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? '') || b.id - a.id)

export interface LedgerSummary {
    count: number
    since: string | null
    paidIn: number
    costs: number
    realised: number
}

export function ledgerSummary(rows: readonly Transaction[]): LedgerSummary {
    const dated = rows.map((r) => r.timestamp).filter((t): t is string => t !== null).sort()
    return {
        count: rows.length,
        since: dated[0] ?? null,
        paidIn: rows.filter((r) => r.action === 'deposit').reduce((sum, r) => sum + r.value, 0),
        costs: rows.reduce((sum, r) => sum + r.cost, 0),
        realised: rows.reduce((sum, r) => sum + r.realised_gain, 0),
    }
}

/** "10 transactions since 26 Sept 2026: £50,000 paid in and £50 in trading costs. No rebalance is due." */
export function activitySentence(s: LedgerSummary, needsRebalance: boolean): string {
    if (s.count === 0) return 'Nothing has been recorded for this portfolio yet.'
    const since = s.since ? ` since ${date(s.since)}` : ''
    const realised = s.realised === 0 ? '' : ` Sales have realised ${signedMoney(s.realised)}.`
    const rebalance = needsRebalance ? ' A rebalance is due.' : ' No rebalance is due.'
    return `${s.count} transaction${s.count === 1 ? '' : 's'}${since}: ${money(s.paidIn)} paid in and ${pounds(s.costs)} in trading costs.${realised}${rebalance}`
}

/** What a rebalance would do, and what it would cost, before it is run. */
export function rebalanceSentence(plan: RebalancePlan): string {
    if (!plan.needs_rebalance) return 'Every holding is within its band, so there is nothing to trade.'
    if (plan.trades.length === 0) return 'A rebalance is due, but the trades could not be priced. Update the prices and check again.'
    const total = (action: 'buy' | 'sell') => plan.trades.filter((t) => t.action === action).reduce((sum, t) => sum + t.trade_value_gbp, 0)
    const tax = !plan.cgt_applies
        ? ' Inside an ISA there is no capital gains tax on the sales.'
        : plan.est_realised_gain_gbp > 0
          ? ` The sales would realise about ${money(plan.est_realised_gain_gbp)} of gains, which can count towards capital gains tax outside an ISA.`
          : ' The sales would realise no gains.'
    const [sold, bought] = [total('sell'), total('buy')]
    const sides = [sold > 0 && `selling ${money(sold)}`, bought > 0 && `buying ${money(bought)}`].filter(Boolean).join(' and ')
    return (
        `${sides.charAt(0).toUpperCase()}${sides.slice(1)} brings every holding back to its target, ` +
        `for about ${pounds(plan.est_total_cost_gbp)} in trading costs.${tax}`
    )
}

