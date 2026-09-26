/**
 * Shared by the browser checks: a stubbed API, collected console errors, and
 * the check that a page never scrolls sideways.
 */
import { expect, type Page, type Route } from '@playwright/test'

export type Replies = Record<string, (route: Route) => unknown>

export function collectErrors(page: Page): string[] {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => {
        if (m.type() === 'error') errors.push(m.text())
    })
    return errors
}

/** Answers each "METHOD /api/path" from `replies`; anything else is a 404, so a missed stub fails loudly. */
export async function routeApi(page: Page, replies: Replies) {
    // By path, not a glob: in development the app's own modules are served from /src/api/.
    await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
        const request = route.request()
        const reply = replies[`${request.method()} ${new URL(request.url()).pathname}`]
        return reply ? route.fulfill({ json: reply(route) }) : route.fulfill({ status: 404, json: { detail: 'Not stubbed.' } })
    })
}

export async function noSidewaysScroll(page: Page) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
}

/** Stores the identity a returning browser would have, then reloads so the app reads it. */
export async function returningBrowser(page: Page, lastPortfolioId: number) {
    await page.goto('/')
    await page.evaluate((id) => {
        localStorage.setItem('ukra.identity', JSON.stringify({ state: { userId: 4, lastPortfolioId: id }, version: 1 }))
    }, lastPortfolioId)
}
