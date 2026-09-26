/**
 * Small helpers shared by the SVG charts: domains, tick density and labels.
 * Scales themselves come from d3-scale; nothing here touches the DOM.
 */

const MONTH_YEAR = new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' })

export interface Margin {
    top: number
    right: number
    bottom: number
    left: number
}

/** About one tick per `spacing` pixels, never fewer than two. */
export function tickCount(length: number, spacing: number): number {
    return Math.max(2, Math.floor(length / spacing))
}

/** [min, max] over every finite value; [0, 1] when there are none. */
export function extent(series: readonly (readonly (number | null | undefined)[])[]): [number, number] {
    let lo = Infinity
    let hi = -Infinity
    for (const values of series) {
        for (const v of values) {
            if (typeof v !== 'number' || !Number.isFinite(v)) continue
            if (v < lo) lo = v
            if (v > hi) hi = v
        }
    }
    return lo === Infinity ? [0, 1] : [lo, hi]
}

/**
 * Pads a value range so lines never sit on the frame. With `zero`, the
 * range always includes zero instead: filled areas are drawn from the zero
 * line, so it must be on the chart or their size misleads.
 */
export function paddedDomain([lo, hi]: [number, number], { zero = false } = {}): [number, number] {
    if (zero) {
        const [a, b] = [Math.min(0, lo), Math.max(0, hi)]
        return a === b ? [0, 1] : [a, b]
    }
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.06
    return [lo - pad, hi + pad]
}

/** API dates are "YYYY-MM-DD" (a UTC calendar day) or full ISO timestamps. */
export function parseDay(value: string): Date {
    return new Date(value.length === 10 ? `${value}T00:00:00Z` : value)
}

/** "2024" when every tick falls on 1 January, else "Mar 2024". */
export function timeTickFormat(ticks: readonly Date[]): (d: Date) => string {
    const yearly = ticks.every((t) => t.getUTCMonth() === 0 && t.getUTCDate() === 1)
    return yearly ? (d) => String(d.getUTCFullYear()) : (d) => MONTH_YEAR.format(d)
}

/** Index of the value in a sorted array closest to `target`. */
export function nearestIndex(sorted: readonly number[], target: number): number {
    let best = 0
    for (let i = 1; i < sorted.length; i += 1) {
        if (Math.abs(sorted[i] - target) < Math.abs(sorted[best] - target)) best = i
    }
    return best
}

/**
 * Indices to show in a table twin: at most `max` rows, evenly spaced, and
 * always the first and the last so the table opens and closes like the chart.
 */
export function sampleIndices(length: number, max: number): number[] {
    if (length <= max) return Array.from({ length }, (_, i) => i)
    const step = Math.ceil((length - 1) / (max - 1))
    const picked: number[] = []
    for (let i = 0; i < length - 1; i += step) picked.push(i)
    picked.push(length - 1)
    return picked
}

/**
 * Nudges end-of-line labels apart so none overlap, keeping their order.
 * `ys` must be sorted top to bottom; returns new positions.
 */
export function spreadLabels(ys: readonly number[], minGap: number): number[] {
    const out = [...ys]
    for (let i = 1; i < out.length; i += 1) {
        if (out[i] - out[i - 1] < minGap) out[i] = out[i - 1] + minGap
    }
    return out
}

export interface PlotBox {
    margin: Margin
    innerW: number
    innerH: number
    /** Wide enough to write values at the ends of the lines. */
    withEnds: boolean
}

const PLOT_MARGIN: Margin = { top: 12, right: 16, bottom: 28, left: 56 }
const END_LABEL_MIN_WIDTH = 520
const END_LABEL_SPACE = 64

/** The drawable area inside a chart of the given size, leaving room for axes and end labels. */
export function plotBox(width: number, height: number): PlotBox {
    const withEnds = width >= END_LABEL_MIN_WIDTH
    const margin = { ...PLOT_MARGIN, right: withEnds ? END_LABEL_SPACE : PLOT_MARGIN.right }
    return {
        margin,
        innerW: Math.max(0, width - margin.left - margin.right),
        innerH: Math.max(0, height - margin.top - margin.bottom),
        withEnds,
    }
}
