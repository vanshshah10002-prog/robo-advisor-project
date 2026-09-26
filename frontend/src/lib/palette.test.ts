import { describe, expect, it } from 'vitest'
import { contrast } from './contrast'
import { CATEGORICAL, CHART_INK, DEFENSIVE_RAMP, GROWTH_RAMP, allocationColours, sleeveOf } from './palette'
import tokensCss from '../styles/tokens.css?raw'


function token(name: string): string {
    const match = tokensCss.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))
    if (!match) throw new Error(`--${name} is not a hex literal in tokens.css`)
    return match[1].toLowerCase()
}

describe('palette.ts mirrors tokens.css', () => {
    it.each(GROWTH_RAMP.map((hex, i) => [`chart-growth-${i + 1}`, hex]))('%s = %s', (name, hex) => {
        expect(token(name)).toBe(hex)
    })

    it.each(DEFENSIVE_RAMP.map((hex, i) => [`chart-defensive-${i + 1}`, hex]))('%s = %s', (name, hex) => {
        expect(token(name)).toBe(hex)
    })

    it.each(CATEGORICAL.map((hex, i) => [`chart-cat-${i + 1}`, hex]))('%s = %s', (name, hex) => {
        expect(token(name)).toBe(hex)
    })

    it('uses the same ink for chart furniture', () => {
        expect(CHART_INK.grid).toBe(token('color-rule'))
        expect(CHART_INK.axis).toBe(token('color-ink-3'))
        expect(CHART_INK.median).toBe(token('color-ink'))
        expect(CHART_INK.surface).toBe(token('color-sheet'))
    })
})

describe('contrast claims in tokens.css', () => {
    const surfaces = ['color-paper', 'color-sheet', 'color-sunk']
    const text = ['color-ink', 'color-ink-2', 'color-ink-3', 'color-accent', 'color-loss', 'color-ok', 'color-warn']

    it.each(text.flatMap((t) => surfaces.map((s) => [t, s])))('%s on %s meets 4.5:1', (t, s) => {
        expect(contrast(token(t), token(s))).toBeGreaterThanOrEqual(4.5)
    })

    it.each([
        ['color-accent', 'color-accent-wash'],
        ['color-loss', 'color-loss-wash'],
        ['color-ok', 'color-ok-wash'],
        ['color-warn', 'color-warn-wash'],
    ])('%s on %s meets 4.5:1', (t, s) => {
        expect(contrast(token(t), token(s))).toBeGreaterThanOrEqual(4.5)
    })

    it('inverse ink on the primary button meets 4.5:1', () => {
        expect(contrast(token('color-ink-inverse'), token('color-ink'))).toBeGreaterThanOrEqual(4.5)
        expect(contrast(token('color-ink-inverse'), token('color-accent-hover'))).toBeGreaterThanOrEqual(4.5)
    })

    it.each(surfaces)('control boundaries meet 3:1 on %s', (s) => {
        expect(contrast(token('color-rule-strong'), token(s))).toBeGreaterThanOrEqual(3)
    })

    it.each([...GROWTH_RAMP.slice(-1), ...DEFENSIVE_RAMP.slice(-1)])('lightest ramp step %s clears 2:1 on paper', (hex) => {
        expect(contrast(hex, token('color-paper'))).toBeGreaterThanOrEqual(2)
    })
})

describe('sleeveOf', () => {
    it.each(['uk_gilts', 'global_bonds', 'cash_equivalent', 'uk_inflation_linked', 'corporate_bonds'])(
        '%s is defensive',
        (ac) => expect(sleeveOf(ac)).toBe('defensive'),
    )

    it.each(['global_equity', 'uk_equity', 'commodities_gold', 'global_property', 'unknown_class'])(
        '%s is growth',
        (ac) => expect(sleeveOf(ac)).toBe('growth'),
    )
})

describe('allocationColours', () => {
    it('walks each ramp independently from its darkest step', () => {
        expect(allocationColours(['global_equity', 'global_bonds', 'uk_equity', 'cash_equivalent'])).toEqual([
            GROWTH_RAMP[0],
            DEFENSIVE_RAMP[0],
            GROWTH_RAMP[1],
            DEFENSIVE_RAMP[1],
        ])
    })

    it('wraps a sleeve with more than five holdings', () => {
        const colours = allocationColours(Array.from({ length: 7 }, (_, i) => `equity_${i}`))
        expect(colours[5]).toBe(GROWTH_RAMP[0])
        expect(colours[6]).toBe(GROWTH_RAMP[1])
    })
})

describe('contrast', () => {
    it('matches the WCAG reference points', () => {
        expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 5)
        expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 2)
        expect(contrast('#ffffff', '#ffffff')).toBe(1)
    })
})
