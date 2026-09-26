import { describe, expect, it } from 'vitest'
import { clampLevel, level, levelStops } from './risk'

describe('level', () => {
    it('shows whole levels without a decimal', () => {
        expect(level(6)).toBe('6')
        expect(level(6.3)).toBe('6.3')
    })
})

describe('levelStops', () => {
    it('offers every whole level up to the assessed one, then the assessed one', () => {
        expect(levelStops(6.3)).toEqual([1, 2, 3, 4, 5, 6, 6.3])
        expect(levelStops(4)).toEqual([1, 2, 3, 4])
    })

    it('stays within 1 to 10', () => {
        expect(levelStops(0.4)).toEqual([1])
        expect(levelStops(12)).toHaveLength(10)
    })
})

describe('clampLevel', () => {
    it('keeps a lower choice and caps a higher one', () => {
        expect(clampLevel(3, 6.3)).toBe(3)
        expect(clampLevel(9, 6.3)).toBe(6.3)
        expect(clampLevel(0, 6.3)).toBe(1)
    })

    it('starts at the assessed level when nothing was chosen', () => {
        expect(clampLevel(null, 6.3)).toBe(6.3)
        expect(clampLevel(undefined, 5)).toBe(5)
    })
})
