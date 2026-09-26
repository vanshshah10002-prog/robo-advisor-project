import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { TrackRecord } from '@/api/schemas'
import { useIdentity } from '@/store/session'
import { renderApp, stubApi, warmPages, type Call } from '@/test/app'
import * as fx from '@/test/fixtures'
import { trackRecordSentence } from './evidence'

warmPages(() => import('./LandingPage'))

const record = fx.trackRecord as TrackRecord
const atLevel = (c: Call) => ({ ...fx.trackRecord, risk: Number(c.query.get('risk')) })

describe('trackRecordSentence', () => {
    it('says so when the simple benchmark did better', () => {
        expect(trackRecordSentence(record)).toBe(
            'At level 5, £100,000 run through these rules from 27 Sept 2021 would have ended at £124,518, or 4.5% a year. ' +
                'A simple two-fund portfolio with the same share in shares did better, at 5.9% a year. ' +
                'At its worst it was 22.7% below its previous high, against 13.0% for the two-fund portfolio.',
        )
    })

    it('says the rules beat the benchmark only when they did', () => {
        const ahead = { ...record, strategy: { ...record.strategy, cagr: 0.07 } }
        expect(trackRecordSentence(ahead)).toContain('or 7.0% a year. That beat a simple two-fund portfolio with the same share in shares, which made 5.9% a year.')
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
        expect(await screen.findByText(/^At level 5, £100,000 run through these rules/)).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Go to your portfolio' })).not.toBeInTheDocument()
    })

    it('shows the record for another risk level when you choose one', async () => {
        const user = userEvent.setup()
        const calls = stubApi({ '/api/strategy/track-record': atLevel })
        renderApp('/')

        await screen.findByText(/^At level 5,/)
        await user.click(screen.getByRole('radio', { name: 'Level 7' }))
        expect(await screen.findByText(/^At level 7,/)).toBeInTheDocument()
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
