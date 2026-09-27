/**
 * Accessibility in a real browser: axe checks every page against the WCAG
 * 2.2 A and AA rules, in the light theme and in the dark one (reached the
 * way a reader would, from the device setting), on desktop and on a phone.
 * Motion is reduced so no page is checked halfway through its reveal.
 */
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import * as fx from '../src/test/fixtures'
import { collectErrors, fifteenMonths, returningBrowser, routeApi } from './support'

const ID = 21

async function stubEverything(page: Page) {
    await routeApi(page, {
        'GET /api/quiz-questions': () => fx.quiz,
        'GET /api/risk-profile/4': () => fx.riskProfile,
        'POST /api/portfolio/preview': () => fx.preview,
        'POST /api/monte-carlo': () => fx.monteCarloReal,
        'GET /api/strategy/track-record': () => fx.trackRecord,
        'GET /api/portfolios/user/4': () => [{ ...fx.portfolioSummary, portfolio_id: ID }],
        'GET /api/portfolios/user/4/archived': () => [fx.archivedSummary],
        [`GET /api/performance/${ID}`]: () => ({ ...fx.performance, portfolio_id: ID }),
        [`GET /api/portfolio/${ID}`]: () => ({ ...fx.portfolioDetail, portfolio_id: ID }),
        [`GET /api/portfolio/${ID}/history`]: () => fifteenMonths(ID),
        [`GET /api/portfolio/${ID}/construction`]: () => ({ ...fx.construction, portfolio_id: ID }),
        'GET /api/universe': () => ({ ...fx.heldUniverse, portfolio_id: ID }),
        [`GET /api/transactions/${ID}`]: () => [fx.transaction],
        [`GET /api/rebalance/${ID}`]: () => fx.rebalancePlan,
        'GET /api/asset-classes': () => [fx.assetClass],
        'GET /api/etfs': () => [fx.etf],
    })
}

/** Each page, and the heading that says it has finished loading. */
const PAGES: readonly [string, string, RegExp][] = [
    ['the front page', '/', /you can read/],
    ['the first question', '/start', /^Your goal$/],
    ['the result', '/start/result', /./],
    ['the proposal', '/proposal', /./],
    ['the portfolios list', '/portfolios', /^1 portfolio/],
    ['the overview', `/portfolio/${ID}`, /^Worth/],
    ['performance', `/portfolio/${ID}/performance`, /^Since it opened/],
    ['the asset universe', `/portfolio/${ID}/universe`, /building blocks are held/],
    ['the outlook', `/portfolio/${ID}/outlook`, /^In \d+ years/],
    ['activity', `/portfolio/${ID}/activity`, /transactions? since/],
    ['the style guide', '/styleguide', /Statement/],
    ['a missing page', '/nowhere', /./],
]

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

for (const theme of ['light', 'dark'] as const) {
    test.describe(`the ${theme} theme`, () => {
        test.use({ colorScheme: theme, reducedMotion: 'reduce' })

        for (const [name, path, heading] of PAGES) {
            test(`${name} meets WCAG 2.2 AA`, async ({ page }) => {
                // The heading alone may wait 30s for a cold compile, so the scan needs time beyond it.
                test.setTimeout(60_000)
                const errors = collectErrors(page)
                await stubEverything(page)
                await returningBrowser(page, ID)

                await page.goto(path)
                // Generous: under a full parallel run the dev server may still be compiling the page.
                await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading, { timeout: 30_000 })
                await expect(page.getByRole('main').locator('[aria-busy="true"]')).toHaveCount(0)
                await expect(page.locator('html')).toHaveAttribute('data-theme', theme)

                const { violations } = await new AxeBuilder({ page }).withTags(WCAG).analyze()
                const found = violations.map((v) => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
                expect(found).toEqual([])
                expect(errors).toEqual([])
            })
        }
    })
}
