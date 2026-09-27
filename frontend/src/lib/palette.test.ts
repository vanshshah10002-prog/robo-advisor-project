import { describe, expect, it } from 'vitest'
import { contrast } from './contrast'
import { CATEGORICAL, CHART_INK, DEFENSIVE_RAMP, GROWTH_RAMP, THEME_COLOURS, heatColour, heatShade, sleeveColours } from './palette'
import type { Theme } from './theme'
import tokensCss from '../styles/tokens.css?raw'

const THEMES: readonly Theme[] = ['light', 'dark']

function block(selector: string): string {
    const start = tokensCss.indexOf(`${selector} {`)
    if (start < 0) throw new Error(`${selector} is not in tokens.css`)
    return tokensCss.slice(start, tokensCss.indexOf('}', start))
}

const LIGHT = block(':root')
const DARK = block(":root[data-theme='dark']")

/** The dark block first, then the light one, as the cascade reads them. */
const BLOCKS: Record<Theme, readonly string[]> = { light: [LIGHT], dark: [DARK, LIGHT] }

function token(name: string, theme: Theme = 'light'): string {
    for (const css of BLOCKS[theme]) {
        const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))
        if (match) return match[1].toLowerCase()
    }
    throw new Error(`--${name} is not a hex literal in the ${theme} tokens`)
}

const declared = (css: string) => [...css.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)].map(([, name, value]) => ({ name, value: value.trim() }))

describe('charts draw with the tokens, so the theme reaches every mark', () => {
    it('hands out token references rather than colours', () => {
        expect(GROWTH_RAMP).toEqual([1, 2, 3, 4, 5].map((i) => `var(--chart-growth-${i})`))
        expect(DEFENSIVE_RAMP).toEqual([1, 2, 3, 4, 5].map((i) => `var(--chart-defensive-${i})`))
        expect(CATEGORICAL).toEqual([1, 2, 3, 4, 5, 6].map((i) => `var(--chart-cat-${i})`))
    })

    it.each(Object.entries(CHART_INK))('%s names a token that tokens.css declares', (_, ref) => {
        const name = ref.match(/^var\(--([a-z0-9-]+)\)$/)?.[1]
        expect(declared(LIGHT).map((d) => d.name)).toContain(name)
    })

    it('the dark theme redefines only the semantic, chart and shadow tokens', () => {
        const names = declared(DARK).map((d) => d.name)
        expect(names.filter((n) => !/^(color|chart|shadow)-/.test(n))).toEqual([])
    })

    it('the dark theme redefines every light colour that is not itself a reference', () => {
        const literal = declared(LIGHT).filter((d) => /^(color|chart)-/.test(d.name) && !d.value.startsWith('var('))
        const dark = new Set(declared(DARK).map((d) => d.name))
        expect(literal.map((d) => d.name).filter((n) => !dark.has(n))).toEqual([])
    })
})

describe.each(THEMES)('the %s colours in palette.ts mirror tokens.css', (theme) => {
    const colours = THEME_COLOURS[theme]

    it('paper, sheet and ink', () => {
        expect([colours.paper, colours.sheet, colours.ink]).toEqual([token('color-paper', theme), token('color-sheet', theme), token('color-ink', theme)])
    })

    it('both ramps and the comparison set', () => {
        expect(colours.growth).toEqual(colours.growth.map((_, i) => token(`chart-growth-${i + 1}`, theme)))
        expect(colours.defensive).toEqual(colours.defensive.map((_, i) => token(`chart-defensive-${i + 1}`, theme)))
        expect(colours.categorical).toEqual(colours.categorical.map((_, i) => token(`chart-cat-${i + 1}`, theme)))
    })

    it('the heatmap ends', () => {
        expect(colours.heat).toEqual({ low: token('chart-heat-low', theme), high: token('chart-heat-high', theme) })
    })
})

describe.each(THEMES)('contrast claims in the %s tokens', (theme) => {
    const t = (name: string) => token(name, theme)
    const surfaces = ['color-paper', 'color-sheet', 'color-sunk']
    const text = ['color-ink', 'color-ink-2', 'color-ink-3', 'color-accent', 'color-loss', 'color-ok', 'color-warn']

    it.each(text.flatMap((ink) => surfaces.map((s) => [ink, s])))('%s on %s meets 4.5:1', (ink, s) => {
        expect(contrast(t(ink), t(s))).toBeGreaterThanOrEqual(4.5)
    })

    it.each([
        ['color-accent', 'color-accent-wash'],
        ['color-loss', 'color-loss-wash'],
        ['color-ok', 'color-ok-wash'],
        ['color-warn', 'color-warn-wash'],
    ])('%s on %s meets 4.5:1', (ink, s) => {
        expect(contrast(t(ink), t(s))).toBeGreaterThanOrEqual(4.5)
    })

    it('inverse ink on the primary button meets 4.5:1', () => {
        expect(contrast(t('color-ink-inverse'), t('color-ink'))).toBeGreaterThanOrEqual(4.5)
        expect(contrast(t('color-ink-inverse'), t('color-accent-hover'))).toBeGreaterThanOrEqual(4.5)
    })

    it.each(surfaces)('control boundaries meet 3:1 on %s', (s) => {
        expect(contrast(t('color-rule-strong'), t(s))).toBeGreaterThanOrEqual(3)
    })

    it('the weakest step of each ramp clears 2:1 on paper', () => {
        const { growth, defensive, paper } = THEME_COLOURS[theme]
        expect(contrast(growth[4], paper)).toBeGreaterThanOrEqual(2)
        expect(contrast(defensive[4], paper)).toBeGreaterThanOrEqual(2)
    })

    it('the two lead comparison colours clear 3:1 on paper', () => {
        const { categorical, paper } = THEME_COLOURS[theme]
        expect(contrast(categorical[0], paper)).toBeGreaterThanOrEqual(3)
        expect(contrast(categorical[1], paper)).toBeGreaterThanOrEqual(3)
    })

    it.each([0, 0.25, 0.5, 0.75, 1])('ink stays at 4.5:1 or more on the heat shade for %s', (v) => {
        expect(contrast(t('color-ink'), heatColour(v, theme))).toBeGreaterThanOrEqual(4.5)
    })
})

describe('sleeveColours', () => {
    it('walks each ramp independently from its strongest step', () => {
        expect(sleeveColours(['growth', 'defensive', 'growth', 'defensive'])).toEqual([GROWTH_RAMP[0], DEFENSIVE_RAMP[0], GROWTH_RAMP[1], DEFENSIVE_RAMP[1]])
    })

    it('wraps a sleeve with more than five holdings', () => {
        const colours = sleeveColours(Array.from({ length: 7 }, () => 'growth' as const))
        expect(colours[5]).toBe(GROWTH_RAMP[0])
        expect(colours[6]).toBe(GROWTH_RAMP[1])
    })
})

describe('heat shading', () => {
    it('mixes the heat tokens, leaving negatives unshaded and capping at 1', () => {
        expect(heatShade(0.42)).toBe('color-mix(in srgb, var(--chart-heat-high) 42%, var(--chart-heat-low))')
        expect(heatShade(-0.4)).toBe('color-mix(in srgb, var(--chart-heat-high) 0%, var(--chart-heat-low))')
        expect(heatShade(3)).toBe('color-mix(in srgb, var(--chart-heat-high) 100%, var(--chart-heat-low))')
    })

    it.each(THEMES)('runs from the sheet at 0 to the tint at 1 in the %s theme', (theme) => {
        const { heat, sheet } = THEME_COLOURS[theme]
        expect(heat.low).toBe(sheet)
        expect(heatColour(0, theme)).toBe(heat.low)
        expect(heatColour(-0.4, theme)).toBe(heat.low)
        expect(heatColour(1, theme)).toBe(heat.high)
        expect(heatColour(2, theme)).toBe(heat.high)
    })

    it('defaults to the light theme', () => {
        expect(heatColour(1)).toBe(THEME_COLOURS.light.heat.high)
    })

    it('is the 60% accent tint over the sheet at 1 in the light theme', () => {
        const mix = [1, 3, 5].map((i) => {
            const [a, s] = [token('color-accent'), token('color-sheet')].map((h) => parseInt(h.slice(i, i + 2), 16))
            return Math.round(0.6 * a + 0.4 * s)
        })
        expect(THEME_COLOURS.light.heat.high).toBe(`#${mix.map((c) => c.toString(16).padStart(2, '0')).join('')}`)
    })
})

describe('contrast', () => {
    it('matches the WCAG reference points', () => {
        expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 5)
        expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 2)
        expect(contrast('#ffffff', '#ffffff')).toBe(1)
    })
})
