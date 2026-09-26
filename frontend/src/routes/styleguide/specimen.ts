/**
 * Illustrative figures for the style guide only. Tickers are real registry
 * lines; values and returns are made up and labelled as such on the page.
 * Values sum to TOTAL and weights to 1.
 */

export const SPECIMEN_TOTAL = 124_518

export interface SpecimenHolding {
    ticker: string
    name: string
    assetClass: string
    label: string
    weight: number
    value: number
    returnPct: number
}

export const SPECIMEN_HOLDINGS: readonly SpecimenHolding[] = [
    { ticker: 'VWRL.L', name: 'Vanguard FTSE All-World', assetClass: 'global_equity', label: 'Global equity', weight: 0.32, value: 39_846, returnPct: 0.412 },
    { ticker: 'VUAG.L', name: 'Vanguard S&P 500 Acc', assetClass: 'us_equity', label: 'US equity', weight: 0.1, value: 12_452, returnPct: 0.558 },
    { ticker: 'VUKE.L', name: 'Vanguard FTSE 100', assetClass: 'uk_equity', label: 'UK equity', weight: 0.08, value: 9_961, returnPct: 0.284 },
    { ticker: 'VAGP.L', name: 'Vanguard Global Aggregate Bond (GBP hedged)', assetClass: 'global_bonds', label: 'Global bonds', weight: 0.25, value: 31_130, returnPct: -0.041 },
    { ticker: 'IGLT.L', name: 'iShares Core UK Gilts', assetClass: 'uk_gilts', label: 'UK gilts', weight: 0.12, value: 14_942, returnPct: -0.146 },
    { ticker: 'INXG.L', name: 'iShares Index-Linked Gilts', assetClass: 'uk_inflation_linked', label: 'Index-linked gilts', weight: 0.05, value: 6_226, returnPct: -0.279 },
    { ticker: 'ERNS.L', name: 'iShares £ Ultrashort Bond', assetClass: 'cash_equivalent', label: 'Cash-like', weight: 0.08, value: 9_961, returnPct: 0.123 },
]

// ─── Chart specimens ─────────────────────────────────────────────────────────
// Deterministic, so the page and its screenshots never change between loads.

const Z = { p10: -1.2816, p25: -0.6745, p50: 0, p75: 0.6745, p90: 1.2816 } as const

/**
 * A lognormal fan for £50,000 plus £250 a month over 15 years: each band
 * compounds the lump sum and every year's contributions at that percentile.
 * An illustration of the shape, not a forecast.
 */
export function specimenFan(years = 15, initial = 50_000, yearly = 3_000, mu = 0.055, sigma = 0.11) {
    const grow = (z: number, t: number) => Math.exp((mu - sigma ** 2 / 2) * t + z * sigma * Math.sqrt(t))
    const ts = Array.from({ length: years + 1 }, (_, t) => t)
    const at = (z: number) =>
        ts.map((t) => {
            let v = initial * grow(z, t)
            for (let k = 1; k <= t; k += 1) v += yearly * grow(z, t - k + 0.5)
            return Math.round(v)
        })
    return {
        years: ts,
        p10: at(Z.p10),
        p25: at(Z.p25),
        p50: at(Z.p50),
        p75: at(Z.p75),
        p90: at(Z.p90),
        paidIn: ts.map((t) => initial + yearly * t),
    }
}

/** Small, fast, seeded PRNG (mulberry32). */
function seeded(seed: number): () => number {
    let a = seed >>> 0
    return () => {
        a = (a + 0x6d2b79f5) >>> 0
        let t = a
        t = Math.imul(t ^ (t >>> 15), t | 1)
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
}

const DAY_MS = 86_400_000

/**
 * Five years of weekly values for £10,000 in a strategy and a benchmark
 * that share most of their shocks. Made up, and labelled so on the page.
 */
export function specimenTrack(weeks = 261, start = '2021-09-27') {
    const rand = seeded(7)
    const normal = () => Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(2 * Math.PI * rand())
    const t0 = Date.parse(`${start}T00:00:00Z`)
    const dates: string[] = []
    const strategy: number[] = []
    const benchmark: number[] = []
    let s = 10_000
    let b = 10_000
    for (let w = 0; w < weeks; w += 1) {
        dates.push(new Date(t0 + w * 7 * DAY_MS).toISOString().slice(0, 10))
        strategy.push(Math.round(s))
        benchmark.push(Math.round(b))
        const common = normal()
        s *= 1 + 0.0013 + 0.019 * (0.9 * common + 0.44 * normal())
        b *= 1 + 0.0011 + 0.017 * (0.9 * common + 0.44 * normal())
    }
    return { dates, strategy, benchmark }
}

/** Drift from target for the specimen holdings: sums to zero, one holding outside its band. */
export const SPECIMEN_DRIFT: readonly number[] = [0.021, 0.006, -0.004, -0.032, 0.004, 0.003, 0.002]
export const SPECIMEN_BAND = 0.025
