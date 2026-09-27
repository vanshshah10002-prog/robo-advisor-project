/**
 * An opened portfolio in a real browser, against a stubbed API: every section
 * of the workspace, then money added and a rebalance run from Activity.
 */
import { expect, test, type Page } from '@playwright/test'
import * as fx from '../src/test/fixtures'
import { collectErrors, fifteenMonths, noSidewaysScroll, returningBrowser, routeApi } from './support'

const ID = 21

const deposit = { ...fx.transaction, id: 1, ticker: 'CASH', action: 'deposit', quantity: 100_000, price: 1, value: 100_000, cost: 0 }

/** Stubs the workspace, recording each POST so the actions can be checked. */
async function stubWorkspace(page: Page) {
    const posted: string[] = []
    const post = (path: string, reply: unknown) => () => {
        posted.push(path)
        return reply
    }
    await routeApi(page, {
        [`GET /api/performance/${ID}`]: () => ({ ...fx.performance, portfolio_id: ID }),
        [`GET /api/portfolio/${ID}`]: () => ({ ...fx.portfolioDetail, portfolio_id: ID }),
        [`GET /api/portfolio/${ID}/history`]: () => fifteenMonths(ID),
        [`GET /api/portfolio/${ID}/construction`]: () => ({ ...fx.construction, portfolio_id: ID }),
        'GET /api/universe': () => ({ ...fx.heldUniverse, portfolio_id: ID }),
        'GET /api/strategy/track-record': () => fx.trackRecord,
        'GET /api/risk-profile/4': () => fx.riskProfile,
        'POST /api/monte-carlo': () => fx.monteCarloReal,
        [`GET /api/transactions/${ID}`]: () => [deposit, { ...fx.transaction, id: 2 }],
        [`GET /api/rebalance/${ID}`]: () => fx.rebalancePlan,
        [`POST /api/rebalance/${ID}/execute`]: post('execute', { ...fx.rebalancePlan, executed: true }),
        [`POST /api/portfolio/${ID}/contribute`]: post('contribute', fx.contributionResult),
        'GET /api/asset-classes': () => [fx.assetClass],
        'GET /api/etfs': () => [fx.etf],
    })
    return posted
}

async function openSection(page: Page, name: string, heading: RegExp) {
    await page.getByRole('navigation', { name: 'Portfolio sections' }).getByRole('link', { name }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading)
    await noSidewaysScroll(page)
}

test('every section of an opened portfolio, then adding money and rebalancing', async ({ page }) => {
    const errors = collectErrors(page)
    const posted = await stubWorkspace(page)
    await returningBrowser(page, ID)

    await page.goto(`/portfolio/${ID}`)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Worth £124,518/)
    await noSidewaysScroll(page)

    await openSection(page, 'Performance', /^Since it opened on 30 Jun 2025, it has returned \+12\.0%/)
    await expect(page.getByRole('table', { name: 'Returns by period' })).toBeAttached()

    await openSection(page, 'Asset universe', /^8 of the 13 building blocks are held/)
    await expect(page.getByRole('img', { name: /^Correlations between 8 funds/ })).toBeVisible()

    await openSection(page, 'Outlook', /^In 15 years, in today's money/)
    await expect(page.getByRole('figure', { name: 'What £124,518 could become' })).toBeVisible()

    await openSection(page, 'Activity', /^2 transactions since 27 Sept 2021/)
    await page.getByLabel('Amount to add').fill('500')
    await page.getByRole('button', { name: 'Add £500' }).click()
    await expect(page.getByText('£500 added and invested in 1 fund. The portfolio is now worth £125,018.')).toBeVisible()
    await page.getByRole('button', { name: 'Rebalance now' }).click()
    await expect(page.getByText('Rebalanced: 1 trade, for about £15 in costs.')).toBeVisible()
    await noSidewaysScroll(page)

    expect(posted).toEqual(['contribute', 'execute'])
    expect(errors).toEqual([])
})
