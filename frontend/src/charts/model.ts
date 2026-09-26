/**
 * Pure data shaping for the charts: ordering, totals, drift. Kept apart from
 * the components so it can be tested without rendering.
 */
import type { Sleeve } from '@/api/schemas'

export interface AllocationItem {
    key: string
    /** What it is: "Global equity", or the fund name. */
    label: string
    /** A second line: the ticker or the fund name. */
    detail?: string
    sleeve: Sleeve
    weight: number
    value?: number | null
}

/** Growth first, then defensive; largest first within each, so colours step dark to light. */
export function orderAllocation(items: readonly AllocationItem[]): AllocationItem[] {
    const rank = (s: Sleeve) => (s === 'growth' ? 0 : 1)
    return [...items].sort((a, b) => rank(a.sleeve) - rank(b.sleeve) || b.weight - a.weight)
}

export function sleeveTotals(items: readonly { sleeve: Sleeve; weight: number }[]): Record<Sleeve, number> {
    return items.reduce(
        (acc, i) => ({ ...acc, [i.sleeve]: acc[i.sleeve] + i.weight }),
        { growth: 0, defensive: 0 } as Record<Sleeve, number>,
    )
}

/** Where each item starts along a 0–1 strip. */
export function cumulativeStarts(items: readonly { weight: number }[]): number[] {
    return items.reduce<number[]>((acc, _, i) => [...acc, i === 0 ? 0 : acc[i - 1] + items[i - 1].weight], [])
}

export interface DriftItem {
    key: string
    label: string
    detail?: string
    target: number
    /** Null when the holding has no price, so no weight can be worked out. */
    current: number | null
    /** Tolerance either side of target before a rebalance is due. */
    band: number
}

const HEADROOM = 1.25
const MIN_SCALE = 0.01

export const driftOf = (item: DriftItem): number | null => (item.current === null ? null : item.current - item.target)

export const isOutside = (item: DriftItem): boolean => {
    const d = driftOf(item)
    return d !== null && Math.abs(d) > item.band
}

/** Half-width of the drift axis: room for the widest drift or band, with headroom. */
export function driftScale(items: readonly DriftItem[]): number {
    const widest = Math.max(MIN_SCALE, ...items.flatMap((i) => [Math.abs(driftOf(i) ?? 0), i.band]))
    return widest * HEADROOM
}

/** "Title. Label value. Label value." for a live region. */
export function describeRows(title: string, rows: readonly { label: string; value: string }[]): string {
    return [title, ...rows.map((r) => `${r.label} ${r.value}`)].join('. ')
}
