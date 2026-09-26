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
