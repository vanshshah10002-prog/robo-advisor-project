/**
 * Risk levels as people read them: "6" or "6.3", on a scale of 1 to 10.
 */
import { decimal } from './format'

export const MIN_LEVEL = 1
export const MAX_LEVEL = 10

/** 6 → "6", 6.3 → "6.3". */
export function level(score: number): string {
    return decimal(score, Number.isInteger(score) ? 0 : 1)
}

/**
 * The levels someone may choose: every whole level from 1 up to their
 * assessed level, then the assessed level itself if it is not whole.
 * A proposal can take less risk than assessed, never more.
 */
export function levelStops(assessed: number): number[] {
    const cap = Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, assessed))
    const whole = Array.from({ length: Math.floor(cap) }, (_, i) => i + 1)
    return Number.isInteger(cap) ? whole : [...whole, Math.round(cap * 10) / 10]
}

/** A chosen level held within what the assessment allows. */
export function clampLevel(chosen: number | null | undefined, assessed: number): number {
    const stops = levelStops(assessed)
    const top = stops[stops.length - 1]
    if (typeof chosen !== 'number' || !Number.isFinite(chosen)) return top
    return Math.min(top, Math.max(MIN_LEVEL, chosen))
}

/** The backtest covers whole levels only: the one a portfolio at `score` is compared with. */
export function nearestTested(score: number): number {
    return Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, Math.round(score)))
}
