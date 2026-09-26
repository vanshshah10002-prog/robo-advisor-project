/**
 * Chart colours
 * =============
 * SVG marks and legacy Recharts need literal colours, so the chart hexes live here and are
 * mirrored as custom properties in src/styles/tokens.css. palette.test.ts
 * fails if the two drift apart.
 *
 * Holdings are coloured by what they do, not by index: growth holdings take
 * the verdigris ramp, defensive holdings the ochre ramp. The ramps are
 * ordinal, not categorical, so neighbouring steps are close by design —
 * any chart that places them side by side must separate segments with a
 * 1px paper gap and label them (legend or direct labels, plus a table view).
 */

export const GROWTH_RAMP = ['#00574c', '#007063', '#1d897c', '#40a495', '#5cbdae'] as const
export const DEFENSIVE_RAMP = ['#763000', '#934a00', '#b0651f', '#ce803f', '#e99959'] as const

/** Fixed order. Take slots from the front; never reorder or skip. */
export const CATEGORICAL = ['#2f59ab', '#008b77', '#cb8027', '#c0434c', '#733d89', '#6a923a'] as const

export const CHART_INK = {
    grid: '#dad3c9',
    axis: '#69625a',
    median: '#1f1b16',
    surface: '#fdfbf7',
    bandInner: 'rgb(40 78 153 / 0.22)',
    bandOuter: 'rgb(40 78 153 / 0.10)',
} as const

export type Sleeve = 'growth' | 'defensive'

/** Mirrors backend/engine/policy.py `sleeve_of` until the API returns the sleeve itself (Phase 2, B2). */
const DEFENSIVE_CLASSES: ReadonlySet<string> = new Set([
    'uk_gilts',
    'uk_inflation_linked',
    'global_bonds',
    'corporate_bonds',
    'cash_equivalent',
    'uk_bonds',
    'high_yield_bonds',
    'us_treasury',
    'indian_bonds',
])

export function sleeveOf(assetClass: string): Sleeve {
    return DEFENSIVE_CLASSES.has(assetClass) ? 'defensive' : 'growth'
}

/**
 * One colour per holding, in the order given (pass them largest first).
 * Within a sleeve, the first holding gets the darkest step. A sleeve with
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

/** As `sleeveColours`, for callers that only know the asset class. */
export function allocationColours(assetClasses: readonly string[]): string[] {
    return sleeveColours(assetClasses.map(sleeveOf))
}
