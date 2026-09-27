/**
 * Chart colours
 * =============
 * Marks are drawn with the chart tokens in src/styles/tokens.css, as CSS
 * variables, so switching to the dark theme recolours every chart
 * without a re-render. Each theme's literal hexes are kept here as well:
 * palette.test.ts checks them against tokens.css and checks their contrast,
 * and the style guide prints them.
 *
 * Holdings are coloured by what they do, not by index: growth holdings take
 * the verdigris ramp, defensive holdings the ochre ramp. The ramps are
 * ordinal, not categorical, so neighbouring steps are close by design —
 * any chart that places them side by side must separate segments with a
 * 1px paper gap and label them (legend or direct labels, plus a table view).
 */
import type { Theme } from './theme'

const tokens = (name: string, count: number) => Array.from({ length: count }, (_, i) => `var(--chart-${name}-${i + 1})`)

/** Strongest step first: the darkest in the light theme, the brightest in the dark one. */
export const GROWTH_RAMP: readonly string[] = tokens('growth', 5)
export const DEFENSIVE_RAMP: readonly string[] = tokens('defensive', 5)

/** Fixed order. Take slots from the front; never reorder or skip. */
export const CATEGORICAL: readonly string[] = tokens('cat', 6)

export const CHART_INK = {
    grid: 'var(--chart-grid)',
    axis: 'var(--chart-axis)',
    median: 'var(--chart-median)',
    surface: 'var(--color-sheet)',
    bandInner: 'var(--chart-band-inner)',
    bandOuter: 'var(--chart-band-outer)',
} as const

export interface ThemeColours {
    paper: string
    sheet: string
    ink: string
    growth: readonly string[]
    defensive: readonly string[]
    categorical: readonly string[]
    /** Correlation shading: the sheet at 0, a tint at 1 that keeps ink at 4.5:1. */
    heat: { low: string; high: string }
}

/** The literal colours behind the tokens, per theme. tokens.css is the source; a test keeps these equal. */
export const THEME_COLOURS: Record<Theme, ThemeColours> = {
    light: {
        paper: '#f7f4ed',
        sheet: '#fdfbf7',
        ink: '#1f1b16',
        growth: ['#00574c', '#007063', '#1d897c', '#40a495', '#5cbdae'],
        defensive: ['#763000', '#934a00', '#b0651f', '#ce803f', '#e99959'],
        categorical: ['#2f59ab', '#008b77', '#cb8027', '#c0434c', '#733d89', '#6a923a'],
        heat: { low: '#fdfbf7', high: '#7d93bf' },
    },
    dark: {
        paper: '#16130f',
        sheet: '#1e1a16',
        ink: '#f0eadf',
        growth: ['#6fd6c4', '#4ebcab', '#35a090', '#258476', '#1b695e'],
        defensive: ['#f5b074', '#dc9152', '#bf7536', '#9f5c22', '#814515'],
        categorical: ['#86a6ee', '#3fc3aa', '#e0a04e', '#ec8088', '#bf92da', '#a3c86e'],
        heat: { low: '#1e1a16', high: '#3b4d74' },
    },
}

const unit = (value: number) => Math.min(1, Math.max(0, value))
const channels = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))

/** The shade drawn for a correlation, mixed from the heat tokens: values at or below zero stay unshaded. */
export function heatShade(value: number): string {
    return `color-mix(in srgb, var(--chart-heat-high) ${Math.round(unit(value) * 100)}%, var(--chart-heat-low))`
}

/** The same shade as a hex, for checking contrast: an sRGB mix, as color-mix makes it. */
export function heatColour(value: number, theme: Theme = 'light'): string {
    const t = Math.round(unit(value) * 100) / 100
    const { low, high } = THEME_COLOURS[theme].heat
    const [lo, hi] = [channels(low), channels(high)]
    return `#${lo.map((c, i) => Math.round(c + (hi[i] - c) * t).toString(16).padStart(2, '0')).join('')}`
}

export type Sleeve = 'growth' | 'defensive'

/**
 * One colour per holding, in the order given (pass them largest first).
 * Within a sleeve, the first holding gets the strongest step. A sleeve with
 * more than five holdings wraps, so equal colours are always five apart.
 */
export function sleeveColours(sleeves: readonly Sleeve[]): string[] {
    const seen: Record<Sleeve, number> = { growth: 0, defensive: 0 }
    return sleeves.map((sleeve) => {
        const ramp = sleeve === 'growth' ? GROWTH_RAMP : DEFENSIVE_RAMP
        const colour = ramp[seen[sleeve] % ramp.length]
        seen[sleeve] += 1
        return colour
    })
}
