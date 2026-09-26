/**
 * Contract: responses recorded from the running API (src/test/contract/*.json)
 * must parse with the schemas the app uses. Re-record after a backend change:
 * start the API and repeat the requests listed in docs/UI_OVERHAUL.md §9.
 */
import { describe, expect, it } from 'vitest'
import type { z } from 'zod'
import constructionLegacy from '@/test/contract/construction-legacy.json'
import construction from '@/test/contract/construction.json'
import historyLegacy from '@/test/contract/history-legacy.json'
import monteCarlo from '@/test/contract/monte-carlo.json'
import portfolios from '@/test/contract/portfolios.json'
import preview from '@/test/contract/preview.json'
import riskProfile from '@/test/contract/risk-profile.json'
import trackRecord from '@/test/contract/track-record.json'
import universe from '@/test/contract/universe.json'
import {
    constructionSchema,
    historySchema,
    monteCarloSchema,
    portfolioSummarySchema,
    previewSchema,
    riskProfileSchema,
    trackRecordSchema,
    universeSchema,
} from './schemas'

const cases: [string, z.ZodTypeAny, unknown][] = [
    ['POST /portfolio/preview', previewSchema, preview],
    ['GET /portfolio/{id}/construction (recorded)', constructionSchema, construction],
    ['GET /portfolio/{id}/construction (legacy)', constructionSchema, constructionLegacy],
    ['GET /portfolio/{id}/history (legacy)', historySchema, historyLegacy],
    ['GET /universe?portfolio_id', universeSchema, universe],
    ['GET /strategy/track-record', trackRecordSchema, trackRecord],
    ['POST /monte-carlo (preview, real terms)', monteCarloSchema, monteCarlo],
    ['GET /risk-profile/{id}', riskProfileSchema, riskProfile],
]

describe('recorded API responses parse with the app schemas', () => {
    it.each(cases)('%s', (_name, schema, sample) => {
        const result = schema.safeParse(sample)
        expect(result.success ? [] : result.error.issues).toEqual([])
    })

    it('GET /portfolios/user/{id}', () => {
        for (const row of portfolios) {
            expect(portfolioSummarySchema.safeParse(row).success).toBe(true)
        }
    })

    it('keeps the facts the UI relies on', () => {
        const p = previewSchema.parse(preview)
        expect(p.allocations.reduce((sum, a) => sum + a.weight, 0)).toBeCloseTo(1, 2)
        expect(p.capped).toBe(p.risk_score < p.requested_risk_score)

        const c = constructionSchema.parse(construction)
        const n = c.snapshot?.correlation.tickers.length ?? 0
        expect(c.snapshot?.correlation.matrix).toHaveLength(n)

        const mc = monteCarloSchema.parse(monteCarlo)
        expect(mc.contributions).toHaveLength(mc.years.length)
        expect(mc.loss_probability_by_year).toHaveLength(mc.years.length)

        const tr = trackRecordSchema.parse(trackRecord)
        expect(tr.series[0].strategy).toBe(tr.initial)
    })
})
