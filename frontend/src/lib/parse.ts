/**
 * Reading figures people type
 * ===========================
 * Forgiving about how a number is written ("£50,000", "50000", " 2,500.50 "),
 * strict about what it is: anything that is not a plain finite number is
 * `null`, never a guess.
 */

const MONEY_NOISE = /[£,\s]/g
const PLAIN_NUMBER = /^-?\d+(\.\d+)?$/

/** "£50,000" → 50000. Null when empty or not a number. */
export function parseMoney(text: string): number | null {
    const cleaned = text.replace(MONEY_NOISE, '')
    if (!PLAIN_NUMBER.test(cleaned)) return null
    const value = Number(cleaned)
    return Number.isFinite(value) ? value : null
}

/** "15" → 15. Null for anything but a whole number. */
export function parseWhole(text: string): number | null {
    const cleaned = text.trim()
    return /^\d+$/.test(cleaned) ? Number(cleaned) : null
}

/** A stored figure back into an input: 50000 → "50,000", null → "". */
export function moneyInput(value: number | null | undefined): string {
    if (typeof value !== 'number' || !Number.isFinite(value)) return ''
    return value.toLocaleString('en-GB', { maximumFractionDigits: 2 })
}
