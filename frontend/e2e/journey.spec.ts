/**
 * The whole journey in a real browser, against a stubbed API: from the front
 * page, through the three questions and the result, to a proposal that is
 * opened and then followed. The API is stubbed so this runs without the
 * backend and the same way every time.
 */
import { expect, test, type Page, type Route } from '@playwright/test'
import * as fx from '../src/test/fixtures'

const OPENED_ID = 21

function collectErrors(page: Page): string[] {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => {
        if (m.type() === 'error') errors.push(m.text())
    })
    return errors
}

/** Routes every API call to a fixture, and records what was sent to open a portfolio. */
async function stubApi(page: Page) {
    const opened: unknown[] = []
    const replies: Record<string, (route: Route) => unknown> = {
        'GET /api/quiz-questions': () => fx.quiz,
        'POST /api/risk-profile': () => fx.riskProfile,
        'GET /api/risk-profile/4': () => fx.riskProfile,
        'POST /api/portfolio/preview': (route) => {
            const { risk_score: risk } = route.request().postDataJSON() as { risk_score: number }
            return { ...fx.preview, requested_risk_score: risk, risk_score: risk, capped: false }
        },
        'POST /api/monte-carlo': () => fx.monteCarloReal,
        'GET /api/strategy/track-record': () => fx.trackRecord,
        'POST /api/portfolio': (route) => {
            opened.push(route.request().postDataJSON())
            return { ...fx.createdPortfolio, portfolio_id: OPENED_ID }
        },
        [`GET /api/performance/${OPENED_ID}`]: () => ({ ...fx.performance, portfolio_id: OPENED_ID }),
        [`GET /api/portfolio/${OPENED_ID}`]: () => ({ ...fx.portfolioDetail, portfolio_id: OPENED_ID }),
        'GET /api/portfolios/user/4': () => [{ ...fx.portfolioSummary, portfolio_id: OPENED_ID }],
        'GET /api/asset-classes': () => [fx.assetClass],
        'GET /api/etfs': () => [fx.etf],
    }
    // By path, not a glob: in development the app's own modules are served from /src/api/.
    await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
        const request = route.request()
        const reply = replies[`${request.method()} ${new URL(request.url()).pathname}`]
        return reply ? route.fulfill({ json: reply(route) }) : route.fulfill({ status: 404, json: { detail: 'Not stubbed.' } })
    })
    return opened
}

async function noSidewaysScroll(page: Page) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
}

/** Answers a numbered question with its number key, as a keyboard user would. */
async function answerByKey(page: Page, legend: RegExp, option: number) {
    const group = page.getByRole('group', { name: legend })
    await group.getByRole('radio').first().focus()
    await page.keyboard.press(String(option))
    await expect(group.getByRole('radio').nth(option - 1)).toBeChecked()
}

async function answer(page: Page, legend: RegExp, option: number) {
    await page.getByRole('group', { name: legend }).getByRole('radio').nth(option - 1).check()
}

test('from the front page to an opened portfolio', async ({ page }) => {
    const errors = collectErrors(page)
    const opened = await stubApi(page)

    await page.goto('/')
    await expect(page.getByText(/^At level 5, £100,000 run through these rules/)).toBeVisible()
    await noSidewaysScroll(page)
    await page.getByRole('main').getByRole('link', { name: 'Build a portfolio' }).click()

    // Step 1: a blank Continue lists the problems and takes focus there.
    await expect(page.getByRole('heading', { level: 1, name: 'Your goal' })).toBeVisible()
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByRole('alert')).toBeFocused()
    await page.getByLabel('What should we call you?').fill('Ada')
    await page.getByLabel(/When will you need most/).fill('15')
    await answerByKey(page, /primary investment goal/, 4)
    await answerByKey(page, /annual return do you expect/, 3)
    await noSidewaysScroll(page)
    await page.getByRole('button', { name: 'Continue' }).click()

    await expect(page.getByRole('heading', { level: 1, name: 'Ups and downs' })).toBeVisible()
    await answer(page, /dropped 20%/, 3)
    await answer(page, /short-term volatility/, 4)
    await answer(page, /investment knowledge/, 3)
    await answer(page, /invested in equities/, 3)
    await page.getByRole('button', { name: 'Continue' }).click()

    await expect(page.getByRole('heading', { level: 1, name: 'Your finances' })).toBeVisible()
    await page.getByLabel('How much do you want to invest now?').fill('50,000')
    await page.getByLabel('Your savings and investments in total').fill('80,000')
    await page.getByLabel('Monthly income after tax').fill('3,200')
    await page.getByLabel('Monthly spending').fill('2,100')
    await page.getByRole('radio', { name: 'Employed', exact: true }).check()
    await answer(page, /stable is your income/, 4)
    await answer(page, /emergency savings/, 4)
    await answer(page, /net worth/, 2)
    await page.getByRole('radio', { name: 'Yes, an ISA' }).check()
    await noSidewaysScroll(page)
    await page.getByRole('button', { name: 'See my risk level' }).click()

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Your risk level is 5 out of 10')
    await expect(page.getByRole('region', { name: /How far level 5 has fallen before/ })).toBeVisible()
    await noSidewaysScroll(page)
    await page.getByRole('link', { name: 'See your proposal' }).click()

    // Onboarding never asks for a monthly amount; it is set here, and the proposal rebuilds.
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^£50,000 now, at risk level 5:/)
    await page.getByLabel('Each month').fill('250')
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^£50,000 now and £250 a month, at risk level 5:/)
    await expect(page.getByRole('figure', { name: /What £50,000 could become/ })).toBeVisible()
    await noSidewaysScroll(page)
    const open = page.getByRole('button', { name: 'Open portfolio' })
    await expect(open).toBeEnabled()
    await open.click()

    await expect(page).toHaveURL(`/portfolio/${OPENED_ID}`)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Worth £124,518/)
    await noSidewaysScroll(page)
    expect(opened).toEqual([{ user_id: 4, risk_score: 5, investment_amount: 50_000, monthly_contribution: 250, uses_isa: true }])

    await page.goto('/portfolios')
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('1 portfolio, worth £124,518 together.')
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Go to your portfolio' })).toHaveAttribute('href', `/portfolio/${OPENED_ID}`)
    expect(errors).toEqual([])
})

test('the old dashboard address leads to the portfolio last opened', async ({ page }) => {
    await stubApi(page)
    await page.goto('/')
    await page.evaluate((id) => {
        localStorage.setItem('ukra.identity', JSON.stringify({ state: { userId: 4, lastPortfolioId: id }, version: 1 }))
    }, OPENED_ID)
    await page.goto('/dashboard')
    await expect(page).toHaveURL(`/portfolio/${OPENED_ID}`)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Worth £124,518/)
})
