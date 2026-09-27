import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { TrackRecord } from '@/api/schemas'
import { useIdentity } from '@/store/session'
import { renderApp, stubApi, warmPages, type Call } from '@/test/app'
import * as fx from '@/test/fixtures'
import { benchmarkLabel, benchmarkNames, trackRecordSentence } from './evidence'

warmPages(() => import('./LandingPage'))

const record = fx.trackRecord as TrackRecord
const atLevel = (c: Call) => ({ ...fx.trackRecord, risk: Number(c.query.get('risk')) })

describe('trackRecordSentence', () => {
    it('says so when the benchmark did better, naming what it holds', () => {
        expect(trackRecordSentence(record)).toBe(
            'In the backtest at risk level 5, £100,000 invested from 27 Sept 2021 would have ended at £124,518, an annualised return of 4.5%. ' +
                'A benchmark of 50% VWRL.L and 50% AGBP.L did better, at 5.9% a year. ' +
                'The strategy’s maximum drawdown was 22.7%, against 13.0% for the benchmark.',
        )
    })

    it('says the strategy beat the benchmark only when it did', () => {
        const ahead = { ...record, strategy: { ...record.strategy, cagr: 0.07 } }
        expect(trackRecordSentence(ahead)).toContain('an annualised return of 7.0%. That beat a benchmark of 50% VWRL.L and 50% AGBP.L, which returned 5.9% a year.')
    })
})

describe('the benchmark', () => {
    it('is labelled by its funds and shares, and named in full', () => {
        expect(benchmarkLabel(record)).toBe('Benchmark: 50% VWRL.L + 50% AGBP.L')
        expect(benchmarkNames(record)).toBe(
            '50% in Vanguard FTSE All-World UCITS ETF (GBP) (VWRL.L) and 50% in iShares Core Global Aggregate Bond UCITS ETF (GBP Hedged) (AGBP.L)',
        )
    })

    it('reads a single fund at the top level', () => {
        const allShares = { ...record, benchmark_funds: [{ ticker: 'VWRL.L', name: 'Vanguard FTSE All-World UCITS ETF (GBP)', weight: 1 }] }
        expect(benchmarkLabel(allShares)).toBe('Benchmark: 100% VWRL.L')
        expect(benchmarkNames(allShares)).toBe('100% in Vanguard FTSE All-World UCITS ETF (GBP) (VWRL.L)')
    })
})

describe('the front page', () => {
    it('explains the steps and tells the track record in words', async () => {
        stubApi({ '/api/strategy/track-record': atLevel })
        renderApp('/')

        expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('A portfolio you can read.')
        const steps = screen.getByRole('region', { name: 'How it works' })
        expect(within(steps).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
            'Tell us about you',
            'See it before it is saved',
            'Follow it in plain figures',
        ])
        expect(await screen.findByText(/^In the backtest at risk level 5, £100,000 invested/)).toBeInTheDocument()
        const chart = screen.getByRole('figure', { name: '£100,000 at risk level 5, week by week' })
        expect(within(chart).getByText('This strategy (backtest)')).toBeInTheDocument()
        expect(within(chart).getByText('Benchmark: 50% VWRL.L + 50% AGBP.L')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Go to your portfolio' })).not.toBeInTheDocument()
    })

    it('shows the record for another risk level when you choose one', async () => {
        const user = userEvent.setup()
        const calls = stubApi({ '/api/strategy/track-record': atLevel })
        renderApp('/')

        await screen.findByText(/^In the backtest at risk level 5,/)
        await user.click(screen.getByRole('radio', { name: 'Level 7' }))
        expect(await screen.findByText(/^In the backtest at risk level 7,/)).toBeInTheDocument()
        expect(calls.map((c) => c.query.get('risk'))).toEqual(['5', '7'])
    })

    it('says so when the record does not load, rather than showing nothing', async () => {
        stubApi({ '/api/strategy/track-record': { status: 503, body: { detail: 'Backtest not run yet.' } } })
        renderApp('/')
        expect(await screen.findByText('The test results did not load: Backtest not run yet.')).toBeInTheDocument()
    })

    it('takes a returning investor straight to their portfolio', async () => {
        stubApi({ '/api/strategy/track-record': atLevel })
        useIdentity.getState().setLastPortfolio(19)
        renderApp('/')
        expect(await screen.findByRole('link', { name: 'Go to your portfolio' })).toHaveAttribute('href', '/portfolio/19')
    })
})
