import { describe, expect, it } from 'vitest'
import { moneyInput, parseMoney, parseWhole } from './parse'

describe('parseMoney', () => {
    it.each([
        ['50000', 50_000],
        ['£50,000', 50_000],
        [' 2,500.50 ', 2_500.5],
        ['0', 0],
        ['-10', -10],
    ])('reads %j as %d', (text, value) => {
        expect(parseMoney(text)).toBe(value)
    })

    it.each(['', '   ', 'abc', '12k', '1.2.3', '£', '50,000 pounds'])('refuses %j', (text) => {
        expect(parseMoney(text)).toBeNull()
    })
})

describe('parseWhole', () => {
    it('reads whole numbers only', () => {
        expect(parseWhole(' 15 ')).toBe(15)
        expect(parseWhole('1.5')).toBeNull()
        expect(parseWhole('-3')).toBeNull()
        expect(parseWhole('')).toBeNull()
    })
})

describe('moneyInput', () => {
    it('writes a stored figure back with separators', () => {
        expect(moneyInput(50_000)).toBe('50,000')
        expect(moneyInput(2_500.5)).toBe('2,500.5')
    })

    it('leaves the box empty when there is nothing stored', () => {
        expect(moneyInput(null)).toBe('')
        expect(moneyInput(undefined)).toBe('')
        expect(moneyInput(Number.NaN)).toBe('')
    })
})
