import { describe, expect, it } from 'vitest'
import { humanise } from './names'

describe('humanise', () => {
    it.each([
        ['global_equity', 'Global equity'],
        ['uk_inflation_linked', 'UK inflation linked'],
        ['us_equity', 'US equity'],
        ['global_reits', 'Global REITs'],
        ['em_debt', 'EM debt'],
        ['cash', 'Cash'],
        ['', ''],
    ])('%s reads as "%s"', (id, name) => {
        expect(humanise(id)).toBe(name)
    })
})
