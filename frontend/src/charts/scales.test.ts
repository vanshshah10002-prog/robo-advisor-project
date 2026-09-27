import { describe, expect, it } from 'vitest'
import {
    anchorOf,
    extent,
    nearestIndex,
    paddedDomain,
    parseDay,
    plotBox,
    sampleIndices,
    spacedLabels,
    spreadLabels,
    tickCount,
    timeTickFormat,
} from './scales'

describe('tickCount', () => {
    it('gives about one tick per spacing, never fewer than two', () => {
        expect(tickCount(880, 88)).toBe(10)
        expect(tickCount(100, 88)).toBe(2)
        expect(tickCount(0, 88)).toBe(2)
    })
})

describe('extent', () => {
    it('spans every finite value across series and skips gaps', () => {
        expect(extent([[3, null, 9], [Number.NaN, -2, undefined]])).toEqual([-2, 9])
    })

    it('falls back to [0, 1] with nothing to measure', () => {
        expect(extent([[], [null]])).toEqual([0, 1])
    })
})

describe('paddedDomain', () => {
    it('pads both ends by 6% of the range', () => {
        const [lo, hi] = paddedDomain([100, 200])
        expect(lo).toBeCloseTo(94)
        expect(hi).toBeCloseTo(206)
    })

    it('pads a flat series so it does not sit on the frame', () => {
        const [lo, hi] = paddedDomain([50, 50])
        expect(lo).toBeLessThan(50)
        expect(hi).toBeGreaterThan(50)
    })

    it('anchors filled charts at zero', () => {
        expect(paddedDomain([120, 300], { zero: true })).toEqual([0, 300])
        expect(paddedDomain([-40, 300], { zero: true })).toEqual([-40, 300])
        expect(paddedDomain([0, 0], { zero: true })).toEqual([0, 1])
    })

    it('keeps zero in view when every value is below it', () => {
        expect(paddedDomain([-40, -10], { zero: true })).toEqual([-40, 0])
    })
})

describe('parseDay', () => {
    it('reads a calendar day as UTC midnight', () => {
        expect(parseDay('2024-03-18').toISOString()).toBe('2024-03-18T00:00:00.000Z')
    })

    it('reads a full timestamp as given', () => {
        expect(parseDay('2024-03-18T16:35:00Z').getUTCHours()).toBe(16)
    })
})

describe('timeTickFormat', () => {
    it('labels January-first ticks by year alone', () => {
        const ticks = [parseDay('2022-01-01'), parseDay('2023-01-01')]
        expect(timeTickFormat(ticks)(ticks[1])).toBe('2023')
    })

    it('adds the month when ticks fall mid-year', () => {
        const ticks = [parseDay('2024-01-01'), parseDay('2024-04-01')]
        expect(timeTickFormat(ticks)(ticks[1])).toBe('Apr 2024')
    })
})

describe('nearestIndex', () => {
    it('finds the closest value', () => {
        expect(nearestIndex([0, 5, 10, 15], 11.9)).toBe(2)
        expect(nearestIndex([0, 5, 10, 15], 13)).toBe(3)
        expect(nearestIndex([0, 5, 10, 15], -4)).toBe(0)
    })
})

describe('sampleIndices', () => {
    it('keeps every row of a short series', () => {
        expect(sampleIndices(4, 40)).toEqual([0, 1, 2, 3])
    })

    it('thins a long series evenly, keeping both ends', () => {
        const picked = sampleIndices(261, 40)
        expect(picked.length).toBeLessThanOrEqual(40)
        expect(picked[0]).toBe(0)
        expect(picked.at(-1)).toBe(260)
        expect(new Set(picked).size).toBe(picked.length)
    })
})

describe('spreadLabels', () => {
    it('pushes crowded labels apart in order and leaves spaced ones alone', () => {
        expect(spreadLabels([10, 14, 60], 14)).toEqual([10, 24, 60])
        expect(spreadLabels([10, 12, 13], 14)).toEqual([10, 24, 38])
    })
})

describe('plotBox', () => {
    it('makes room for end labels on wide charts only', () => {
        const wide = plotBox(640, 300)
        expect(wide.withEnds).toBe(true)
        expect(wide.innerW).toBe(640 - 56 - 64)
        expect(wide.innerH).toBe(300 - 12 - 28)
        expect(plotBox(360, 300).withEnds).toBe(false)
        expect(plotBox(360, 300).innerW).toBe(360 - 56 - 16)
    })

    it('never goes negative on a tiny container', () => {
        expect(plotBox(10, 10)).toMatchObject({ innerW: 0, innerH: 0 })
    })
})

describe('anchorOf', () => {
    it('anchors labels near an edge to it, and centres the rest', () => {
        expect(anchorOf(4, 300)).toBe('start')
        expect(anchorOf(150, 300)).toBe('middle')
        expect(anchorOf(296, 300)).toBe('end')
    })
})

describe('spacedLabels', () => {
    const tick = (at: number, label = 'Oct 2025') => ({ key: at, at, label })

    it('drops a label that would run into the one before, keeping the first', () => {
        // "Jul 2025" starts at the left edge and runs right, into a centred "Oct 2025" 61px along.
        const kept = spacedLabels([tick(1, 'Jul 2025'), tick(61), tick(122), tick(183), tick(244)], 300)
        expect(kept.map((t) => t.at)).toEqual([1, 122, 183, 244])
    })

    it('keeps every label when there is room for all of them', () => {
        const ticks = [tick(40), tick(140), tick(240)]
        expect(spacedLabels(ticks, 300)).toEqual(ticks)
    })

    it('drops an end-anchored last label that would collide', () => {
        expect(spacedLabels([tick(200), tick(280)], 300).map((t) => t.at)).toEqual([200])
    })
})
