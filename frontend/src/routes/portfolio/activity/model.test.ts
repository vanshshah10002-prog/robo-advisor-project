import { describe, expect, it } from 'vitest'
import * as fx from '@/test/fixtures'
import { actionLabel, activitySentence, ledgerSummary, newestFirst, pounds, rebalanceSentence } from './model'

const deposit = { ...fx.transaction, id: 1, ticker: 'CASH', action: 'deposit', quantity: 50_000, price: 1, value: 50_000, cost: 0 }
const buy = { ...fx.transaction, id: 2, value: 40_000, cost: 40, timestamp: '2026-09-26T09:00:00' }
const sell = { ...fx.transaction, id: 3, action: 'sell', value: 5_000, cost: 5, realised_gain: 420, timestamp: '2026-09-27T09:00:00' }
const ledger = [{ ...deposit, timestamp: '2026-09-26T09:00:00' }, buy, sell]

describe('actionLabel', () => {
    it('names each kind of entry in plain words', () => {
        expect(['deposit', 'buy', 'sell', 'dividend'].map(actionLabel)).toEqual(['Paid in', 'Bought', 'Sold', 'Dividend'])
    })
})

describe('pounds', () => {
    it('keeps the pence on small sums only', () => {
        expect(pounds(0.42)).toBe('£0.42')
        expect(pounds(7.6)).toBe('£7.60')
        expect(pounds(15.2)).toBe('£15')
        expect(pounds(0)).toBe('£0')
    })
})

describe('newestFirst', () => {
    it('sorts by time, then by the order entries were written', () => {
        expect(newestFirst(ledger).map((t) => t.id)).toEqual([3, 2, 1])
    })

    it('puts undated entries last, without changing the list it was given', () => {
        const rows = [{ ...buy, timestamp: null }, sell]
        expect(newestFirst(rows).map((t) => t.id)).toEqual([3, 2])
        expect(rows.map((t) => t.id)).toEqual([2, 3])
    })
})

describe('ledgerSummary and activitySentence', () => {
    it('totals money paid in, costs and gains realised since the first entry', () => {
        const summary = ledgerSummary(ledger)
        expect(summary).toEqual({ count: 3, since: '2026-09-26T09:00:00', paidIn: 50_000, costs: 45, realised: 420 })
        expect(activitySentence(summary, false)).toBe(
            '3 transactions since 26 Sept 2026: £50,000 paid in and £45 in trading costs. Sales have realised +£420. No rebalance is due.',
        )
    })

    it('reads a single entry and a rebalance that is due', () => {
        expect(activitySentence(ledgerSummary([{ ...deposit, timestamp: null }]), true)).toBe(
            '1 transaction: £50,000 paid in and £0 in trading costs. A rebalance is due.',
        )
    })

    it('says so when nothing is recorded', () => {
        expect(activitySentence(ledgerSummary([]), false)).toBe('Nothing has been recorded for this portfolio yet.')
    })
})

describe('rebalanceSentence', () => {
    const buyBack = { ...fx.rebalancePlan.trades[0], ticker: 'VAGP.L', action: 'buy' as const, trade_value_gbp: 7_590 }
    const plan = { ...fx.rebalancePlan, trades: [...fx.rebalancePlan.trades, buyBack] }

    it('sizes the trades and their costs, with no tax inside an ISA', () => {
        expect(rebalanceSentence(plan)).toBe(
            'Selling £7,600 and buying £7,590 brings every holding back to its target, for about £15 in trading costs. ' +
                'Inside an ISA there is no capital gains tax on the sales.',
        )
    })

    it('leaves out a side with nothing to trade', () => {
        expect(rebalanceSentence(fx.rebalancePlan)).toMatch(/^Selling £7,600 brings every holding back to its target,/)
        expect(rebalanceSentence({ ...plan, trades: [buyBack] })).toMatch(/^Buying £7,590 brings every holding back to its target,/)
    })

    it('warns of gains that count towards capital gains tax outside an ISA', () => {
        expect(rebalanceSentence({ ...plan, cgt_applies: true })).toMatch(
            /The sales would realise about £2,720 of gains, which can count towards capital gains tax outside an ISA\.$/,
        )
        expect(rebalanceSentence({ ...plan, cgt_applies: true, est_realised_gain_gbp: -80 })).toMatch(/The sales would realise no gains\.$/)
    })

    it('says when there is nothing to trade, or the trades could not be priced', () => {
        expect(rebalanceSentence({ ...plan, needs_rebalance: false })).toBe('Every holding is within its band, so there is nothing to trade.')
        expect(rebalanceSentence({ ...plan, trades: [] })).toBe(
            'A rebalance is due, but the trades could not be priced. Update the prices and check again.',
        )
    })
})
