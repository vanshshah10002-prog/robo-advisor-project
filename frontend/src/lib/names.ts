/** Readable names for registry ids. */

const ACRONYMS: Record<string, string> = { uk: 'UK', us: 'US', esg: 'ESG', reit: 'REIT', reits: 'REITs', em: 'EM' }

/** "uk_inflation_linked" → "UK inflation linked", for when the registry name has not loaded. */
export function humanise(id: string): string {
    const words = id.split('_').map((w) => ACRONYMS[w] ?? w)
    const [first = '', ...rest] = words
    return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ')
}
