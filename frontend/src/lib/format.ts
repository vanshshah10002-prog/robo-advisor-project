/**
 * en-GB number and date formatting
 * ================================
 * One place for every figure the UI prints, so "£1.2m", "+4.5%" and
 * "25 Sept 2026" read the same on every screen.
 *
 * - Missing or non-finite values render as an em dash, never "NaN" or "£0".
 * - Negatives use the true minus sign (U+2212), which matches the width of
 *   "+" in tabular figures so signed columns line up.
 * - Values that round to zero never show a sign ("£0", not "-£0").
 */

export const EMPTY = '—'
const MINUS = '−'
const LOCALE = 'en-GB'

type Maybe = number | null | undefined

const cache = new Map<string, Intl.NumberFormat>()

function numberFormat(key: string, options: Intl.NumberFormatOptions): Intl.NumberFormat {
    let nf = cache.get(key)
    if (!nf) {
        nf = new Intl.NumberFormat(LOCALE, options)
        cache.set(key, nf)
    }
    return nf
}

function isFiniteNumber(v: Maybe): v is number {
    return typeof v === 'number' && Number.isFinite(v)
}

function withMinus(s: string): string {
    return s.replace(/-/g, MINUS)
}

/** Formats `v`, first collapsing anything that rounds to zero at `digits` so no "-0" appears. */
function fmt(v: number, digits: number, nf: Intl.NumberFormat, scale = 1): string {
    const factor = 10 ** digits
    const rounded = Math.round(v * scale * factor) / factor
    return withMinus(nf.format(rounded === 0 ? 0 : v))
}

/** £100,000 — whole pounds by default; `pence` shows two decimals (£1,234.56). */
export function money(v: Maybe, { pence = false }: { pence?: boolean } = {}): string {
    if (!isFiniteNumber(v)) return EMPTY
    const digits = pence ? 2 : 0
    const nf = numberFormat(`money-${digits}`, {
        style: 'currency',
        currency: 'GBP',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    })
    return fmt(v, digits, nf)
}

/** +£1,240 / −£310 — for gains, losses and flows. */
export function signedMoney(v: Maybe, { pence = false }: { pence?: boolean } = {}): string {
    if (!isFiniteNumber(v)) return EMPTY
    const digits = pence ? 2 : 0
    const nf = numberFormat(`signed-money-${digits}`, {
        style: 'currency',
        currency: 'GBP',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        signDisplay: 'exceptZero',
    })
    return fmt(v, digits, nf)
}

/** £1.2m, £120k, £2.5bn — for axes and tight labels, never for exact balances. */
export function moneyCompact(v: Maybe): string {
    if (!isFiniteNumber(v)) return EMPTY
    const nf = numberFormat('money-compact', {
        style: 'currency',
        currency: 'GBP',
        notation: 'compact',
        maximumFractionDigits: 1,
    })
    return withMinus(nf.format(v))
}

/** 0.045 → "4.5%". Input is a fraction, as the API sends it. */
export function percent(fraction: Maybe, digits = 1): string {
    if (!isFiniteNumber(fraction)) return EMPTY
    const nf = numberFormat(`pct-${digits}`, {
        style: 'percent',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    })
    return fmt(fraction, digits, nf, 100)
}

/** 0.045 → "+4.5%", −0.021 → "−2.1%". */
export function signedPercent(fraction: Maybe, digits = 1): string {
    if (!isFiniteNumber(fraction)) return EMPTY
    const nf = numberFormat(`signed-pct-${digits}`, {
        style: 'percent',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        signDisplay: 'exceptZero',
    })
    return fmt(fraction, digits, nf, 100)
}

/** Difference between two percentages: 0.012 → "+1.2 pp". */
export function percentagePoints(fraction: Maybe, digits = 1): string {
    if (!isFiniteNumber(fraction)) return EMPTY
    const nf = numberFormat(`pp-${digits}`, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        signDisplay: 'exceptZero',
    })
    return `${fmt(fraction * 100, digits, nf)} pp`
}

/** Plain number with thousands separators: fund units, counts. */
export function decimal(v: Maybe, digits = 0): string {
    if (!isFiniteNumber(v)) return EMPTY
    const nf = numberFormat(`dec-${digits}`, { minimumFractionDigits: digits, maximumFractionDigits: digits })
    return fmt(v, digits, nf)
}

const dateFormat = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', year: 'numeric' })
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
})

function toDate(value: string | Date | null | undefined): Date | null {
    if (value === null || value === undefined || value === '') return null
    const d = value instanceof Date ? value : new Date(value)
    return Number.isNaN(d.getTime()) ? null : d
}

/** "25 Sept 2026". Accepts ISO strings from the API. */
export function date(value: string | Date | null | undefined): string {
    const d = toDate(value)
    return d ? dateFormat.format(d) : EMPTY
}

/** "25 Sept 2026, 16:30" in the viewer's time zone. */
export function dateTime(value: string | Date | null | undefined): string {
    const d = toDate(value)
    return d ? dateTimeFormat.format(d) : EMPTY
}
