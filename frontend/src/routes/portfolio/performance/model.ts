/**
 * Performance in numbers and words, from the daily history replayed from the
 * ledger. Returns are time-weighted: money paid in is not counted as growth.
 * Pure, so every figure on the page is tested against the series it comes from.
 */
import type { History, Performance, Sleeve } from '@/api/schemas'
import { date, money, percent, signedPercent } from '@/lib/format'

type Point = History['points'][number]

export type Period = '1m' | '3m' | 'ytd' | '1y' | 'all'

export const PERIODS: readonly { value: Period; label: string }[] = [
    { value: '1m', label: '1 month' },
    { value: '3m', label: '3 months' },
    { value: 'ytd', label: 'This year' },
    { value: '1y', label: '1 year' },
    { value: 'all', label: 'Since opening' },
]

const DAY_MS = 86_400_000
const YEAR_DAYS = 365.25

const parts = (iso: string) => iso.slice(0, 10).split('-').map(Number) as [number, number, number]
const iso = (y: number, m: number, d: number) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`

/** The same day `months` earlier, clamped to the end of a shorter month: 31 Mar less 1 month is 28 or 29 Feb. */
export function monthsBefore(day: string, months: number): string {
    const [y, m, d] = parts(day)
    const index = y * 12 + (m - 1) - months
    const [year, month] = [Math.floor(index / 12), (index % 12) + 1]
    const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
    return iso(year, month, Math.min(d, last))
}

/** The close a period is measured from: on or before this day. Null for "since opening". */
export function periodStart(period: Period, end: string): string | null {
    if (period === '1m') return monthsBefore(end, 1)
    if (period === '3m') return monthsBefore(end, 3)
    if (period === '1y') return monthsBefore(end, 12)
    if (period === 'ytd') return iso(parts(end)[0] - 1, 12, 31)
    return null
}

/** The points a period covers, starting from its base close; null if the history starts too late. */
export function pointsFor(points: readonly Point[], period: Period): readonly Point[] | null {
    if (points.length === 0) return null
    const start = periodStart(period, points[points.length - 1].date)
    if (start === null) return points
    // Points are in date order, so this is the last close on or before the start.
    const base = points.reduce((found, p, i) => (p.date <= start ? i : found), -1)
    return base === -1 ? null : points.slice(base)
}

/** Periods with enough history to show, always ending with "since opening". */
export const availablePeriods = (points: readonly Point[]): Period[] =>
    PERIODS.map((p) => p.value).filter((p) => p === 'all' || pointsFor(points, p) !== null)

/**
 * Time-weighted return over a period, or null when the history does not
 * cover it. "Since opening" is measured from the money first paid in, so it
 * includes the first day's trading costs.
 */
export function periodReturn(points: readonly Point[], period: Period): number | null {
    if (period === 'all') return points.length === 0 ? null : points[points.length - 1].cumulative_return
    const span = pointsFor(points, period)
    if (!span || span.length < 2) return null
    const [first, last] = [span[0], span[span.length - 1]]
    return (1 + last.cumulative_return) / (1 + first.cumulative_return) - 1
}

/** How far the time-weighted index sits below its highest close so far, at each point (0 at a high). */
export function drawdowns(points: readonly Point[]): number[] {
    let peak = -Infinity
    return points.map((p) => {
        const level = 1 + p.cumulative_return
        peak = Math.max(peak, level)
        return level / peak - 1
    })
}

/** The deepest fall from a high and the day it bottomed, or null when it has never fallen. */
export function worstFall(points: readonly Point[]): { value: number; date: string } | null {
    const falls = drawdowns(points)
    const at = falls.reduce((worst, v, i) => (v < falls[worst] ? i : worst), 0)
    return falls.length === 0 || falls[at] >= 0 ? null : { value: falls[at], date: points[at].date }
}

/** A yearly rate, only once there is at least a year to annualise. */
export function annualised(total: number, start: string, end: string): number | null {
    const days = (Date.parse(end) - Date.parse(start)) / DAY_MS
    return days < 365 ? null : (1 + total) ** (YEAR_DAYS / days) - 1
}

/** The sentence the Performance page opens with. */
export function performanceSentence(history: History): string {
    const { points } = history
    if (points.length === 0) return history.reason ?? 'No values have been recorded for this portfolio yet.'
    const first = points[0]
    const last = points[points.length - 1]
    const against = `${money(last.value)} against ${money(last.net_contributions)} paid in`
    if (points.length === 1) {
        return `Opened on ${date(first.date)}. Its value is recorded at each day's close, so there is one so far: ${against}.`
    }
    const fall = worstFall(points)
    const worst = fall ? ` Its worst fall from a high was ${percent(-fall.value)}.` : ' It has not yet fallen below a previous high.'
    return `Since it opened on ${date(first.date)}, it has returned ${signedPercent(last.cumulative_return)} and is worth ${against}.${worst}`
}

export interface HoldingGain {
    ticker: string
    assetClass: string
    sleeve: Sleeve
    value: number
    /** What its units cost, trading costs included. */
    cost: number
    gain: number
    /** Gain on its own cost; null when nothing was paid for it. */
    gainOnCost: number | null
    /** What it added to the whole portfolio's return, as a share of the money paid in. */
    addedToReturn: number | null
}

/** Gain or loss on each holding, largest holding first. */
export function holdingGains(p: Performance): HoldingGain[] {
    return p.holdings
        .map((h) => {
            const cost = h.units * h.average_cost
            return {
                ticker: h.ticker,
                assetClass: h.asset_class,
                sleeve: h.sleeve,
                value: h.current_value,
                cost,
                gain: h.unrealised_pnl,
                gainOnCost: cost > 0 ? h.unrealised_pnl / cost : null,
                addedToReturn: p.net_contributions > 0 ? h.unrealised_pnl / p.net_contributions : null,
            }
        })
        .sort((a, b) => b.value - a.value)
}

export const sumOf = <T,>(rows: readonly T[], pick: (row: T) => number) => rows.reduce((total, row) => total + pick(row), 0)

