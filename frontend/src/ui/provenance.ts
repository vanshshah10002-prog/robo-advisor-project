/** Where a figure comes from. Every number that is not a plain account fact carries one. */
export type ProvenanceKind = 'measured' | 'simulated' | 'estimated'

export const PROVENANCE_MEANING: Record<ProvenanceKind, string> = {
    measured: 'From real prices and your own transactions.',
    simulated: 'From thousands of simulated market paths; a range, not a promise.',
    estimated: 'A model’s forward-looking estimate, which can be wrong.',
}
