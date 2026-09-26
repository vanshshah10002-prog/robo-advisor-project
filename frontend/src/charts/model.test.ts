import { describe, expect, it } from 'vitest'
import {
    cumulativeStarts,
    describeRows,
    driftOf,
    driftScale,
    isOutside,
    orderAllocation,
    sleeveTotals,
    type AllocationItem,
    type DriftItem,
} from './model'

const holdings: AllocationItem[] = [
    { key: 'IGLT.L', label: 'UK gilts', sleeve: 'defensive', weight: 0.2 },
    { key: 'VUAG.L', label: 'US equity', sleeve: 'growth', weight: 0.1 },
    { key: 'VAGP.L', label: 'Global bonds', sleeve: 'defensive', weight: 0.3 },
    { key: 'VWRL.L', label: 'Global equity', sleeve: 'growth', weight: 0.4 },
]

describe('orderAllocation', () => {
    it('puts growth first, largest first within each sleeve, without touching the input', () => {
        const before = holdings.map((h) => h.key)
        expect(orderAllocation(holdings).map((h) => h.key)).toEqual(['VWRL.L', 'VUAG.L', 'VAGP.L', 'IGLT.L'])
        expect(holdings.map((h) => h.key)).toEqual(before)
    })
})

describe('sleeveTotals', () => {
    it('adds weights by sleeve', () => {
        const totals = sleeveTotals(holdings)
        expect(totals.growth).toBeCloseTo(0.5)
        expect(totals.defensive).toBeCloseTo(0.5)
    })

    it('reports an empty sleeve as zero', () => {
        expect(sleeveTotals([holdings[1]])).toEqual({ growth: 0.1, defensive: 0 })
    })
})

describe('cumulativeStarts', () => {
    it('gives where each segment begins along the strip', () => {
        const starts = cumulativeStarts([{ weight: 0.4 }, { weight: 0.1 }, { weight: 0.5 }])
        expect(starts[0]).toBe(0)
        expect(starts[1]).toBeCloseTo(0.4)
        expect(starts[2]).toBeCloseTo(0.5)
    })
})

const drift = (current: number | null, target = 0.25, band = 0.025): DriftItem => ({
    key: 'X',
    label: 'X',
    target,
    current,
    band,
})

describe('drift', () => {
    it('is current minus target, or null without a price', () => {
        expect(driftOf(drift(0.28))).toBeCloseTo(0.03)
        expect(driftOf(drift(null))).toBeNull()
    })

    it('flags only holdings strictly outside their band', () => {
        expect(isOutside(drift(0.28))).toBe(true)
        expect(isOutside(drift(0.22))).toBe(true)
        expect(isOutside(drift(0.26))).toBe(false)
        expect(isOutside(drift(null))).toBe(false)
    })

    it('scales the axis to the widest drift or band, with headroom', () => {
        expect(driftScale([drift(0.29), drift(0.25)])).toBeCloseTo(0.05)
        expect(driftScale([drift(0.25, 0.25, 0.04)])).toBeCloseTo(0.05)
    })

    it('never collapses the axis to nothing', () => {
        expect(driftScale([drift(0.25, 0.25, 0)])).toBeCloseTo(0.0125)
        expect(driftScale([])).toBeCloseTo(0.0125)
    })
})

describe('describeRows', () => {
    it('reads a title then each label and value', () => {
        expect(describeRows('2030', [{ label: 'Middle', value: '£80,000' }])).toBe('2030. Middle £80,000')
    })
})
