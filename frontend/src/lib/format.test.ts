import { describe, expect, it } from 'vitest'
import {
    EMPTY,
    date,
    dateTime,
    decimal,
    money,
    moneyCompact,
    percent,
    percentagePoints,
    signedMoney,
    signedPercent,
} from './format'

const MINUS = '−'

describe('money', () => {
    it('formats whole pounds with thousands separators', () => {
        expect(money(100_000)).toBe('£100,000')
    })

    it('shows pence when asked', () => {
        expect(money(1234.5, { pence: true })).toBe('£1,234.50')
    })

    it('uses a true minus sign for negatives', () => {
        expect(money(-1234.5)).toBe(`${MINUS}£1,235`)
    })

    it('never prints a negative zero', () => {
        expect(money(-0.2)).toBe('£0')
        expect(money(-0.004, { pence: true })).toBe('£0.00')
    })

    it.each([null, undefined, Number.NaN, Number.POSITIVE_INFINITY])('renders %s as an em dash', (v) => {
        expect(money(v)).toBe(EMPTY)
    })
})

describe('signedMoney', () => {
    it('signs gains and losses', () => {
        expect(signedMoney(1240)).toBe('+£1,240')
        expect(signedMoney(-310)).toBe(`${MINUS}£310`)
    })

    it('leaves zero unsigned', () => {
        expect(signedMoney(0)).toBe('£0')
        expect(signedMoney(-0.3)).toBe('£0')
    })
})

describe('moneyCompact', () => {
    it('uses UK k / m / bn suffixes', () => {
        expect(moneyCompact(120_000)).toBe('£120k')
        expect(moneyCompact(1_250_000)).toBe('£1.3m')
        expect(moneyCompact(2.5e9)).toBe('£2.5bn')
    })

    it('keeps small values exact', () => {
        expect(moneyCompact(999)).toBe('£999')
    })

    it('signs negatives with a true minus', () => {
        expect(moneyCompact(-45_000)).toBe(`${MINUS}£45k`)
    })
})

describe('percent', () => {
    it('treats input as a fraction', () => {
        expect(percent(0.045)).toBe('4.5%')
        expect(percent(0.12345, 2)).toBe('12.35%')
    })

    it('never prints a negative zero', () => {
        expect(percent(-0.0001)).toBe('0.0%')
    })

    it('renders missing values as an em dash', () => {
        expect(percent(null)).toBe(EMPTY)
    })
})

describe('signedPercent', () => {
    it('signs both directions', () => {
        expect(signedPercent(0.045)).toBe('+4.5%')
        expect(signedPercent(-0.021)).toBe(`${MINUS}2.1%`)
    })

    it('leaves values that round to zero unsigned', () => {
        expect(signedPercent(0)).toBe('0.0%')
        expect(signedPercent(-0.0004)).toBe('0.0%')
    })
})

describe('percentagePoints', () => {
    it('expresses a difference of fractions in points', () => {
        expect(percentagePoints(0.012)).toBe('+1.2 pp')
        expect(percentagePoints(-0.078)).toBe(`${MINUS}7.8 pp`)
    })

    it('leaves zero unsigned', () => {
        expect(percentagePoints(0.0001)).toBe('0.0 pp')
    })
})

describe('decimal', () => {
    it('formats units with fixed decimals', () => {
        expect(decimal(1234.56789, 4)).toBe('1,234.5679')
        expect(decimal(12)).toBe('12')
    })
})

describe('date and dateTime', () => {
    it('formats ISO dates the British way', () => {
        expect(date('2026-09-25')).toMatch(/^25 Sept? 2026$/)
    })

    it('includes a 24-hour time', () => {
        expect(dateTime(new Date(2026, 8, 25, 16, 30))).toMatch(/^25 Sept? 2026, 16:30$/)
    })

    it.each([null, undefined, '', 'not a date'])('renders %s as an em dash', (v) => {
        expect(date(v)).toBe(EMPTY)
        expect(dateTime(v)).toBe(EMPTY)
    })
})
