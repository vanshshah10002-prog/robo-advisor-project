import { expect, test, type Page } from '@playwright/test'

function collectErrors(page: Page): string[] {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => {
        if (m.type() === 'error' && !m.text().includes('/api/')) errors.push(m.text())
    })
    return errors
}

test('the landing page renders on paper, in the new type', async ({ page }) => {
    const errors = collectErrors(page)
    await page.goto('/')

    await expect(page.locator('h1').first()).toBeVisible()
    const body = await page.evaluate(() => {
        const s = getComputedStyle(document.body)
        return { background: s.backgroundColor, font: s.fontFamily }
    })
    expect(body.background).toBe('rgb(247, 244, 237)')
    expect(body.font).toContain('Schibsted Grotesk')
    expect(errors).toEqual([])
})

test('the style guide shows every section and its fonts load', async ({ page }) => {
    const errors = collectErrors(page)
    await page.goto('/styleguide')

    await expect(page.getByRole('heading', { level: 1, name: 'The Statement' })).toBeVisible()
    for (const name of ['Paper and ink', 'Holdings colour', 'Charts', 'Type', 'Figures', 'Headline figures', 'Controls', 'Status']) {
        await expect(page.getByRole('heading', { level: 2, name, exact: true })).toBeVisible()
    }
    await page.evaluate(() => document.fonts.ready)
    const loaded = await page.evaluate(() =>
        [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/"/g, '')),
    )
    expect(loaded).toEqual(expect.arrayContaining(['Newsreader Variable', 'Schibsted Grotesk Variable']))
    expect(errors).toEqual([])
})

test('the page never scrolls sideways', async ({ page }) => {
    await page.goto('/styleguide')
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
})

for (const path of ['/', '/dashboard', '/styleguide']) {
    test(`keyboard users can skip to content on ${path}`, async ({ page, isMobile }) => {
        test.skip(isMobile, 'keyboard navigation is a desktop concern')
        await page.goto(path)
        await page.keyboard.press('Tab')
        const skip = page.getByRole('link', { name: 'Skip to content' })
        await expect(skip).toBeFocused()
        expect(await skip.evaluate((el) => getComputedStyle(el).outlineStyle)).toBe('solid')

        await page.keyboard.press('Enter')
        await expect(page.locator('main#main')).toBeFocused()
        await expect(page.locator('main')).toHaveCount(1)
    })
}

test('the shell marks the page and offers the one new action', async ({ page }) => {
    await page.goto('/styleguide')
    const nav = page.getByRole('navigation', { name: 'Main' })
    await expect(nav.getByRole('link')).toHaveText(['Portfolios', 'Dashboard'])
    await expect(page.getByRole('link', { name: 'Build a portfolio' })).toHaveAttribute('href', '/onboarding')
    await expect(page.getByRole('contentinfo')).toContainText('not financial')
})

test('charts read out from the keyboard and switch to a table', async ({ page, isMobile }) => {
    test.skip(isMobile, 'keyboard navigation is a desktop concern')
    await page.goto('/styleguide')
    const fan = page.getByRole('figure', { name: 'Your money, fifteen years on' })
    const plot = fan.getByRole('img')
    await plot.focus()
    await expect(fan.locator('[aria-live="polite"]')).toHaveText(/^2041, year 15\. Best 1 in 10 above £/)
    await page.keyboard.press('Home')
    await expect(fan.locator('[aria-live="polite"]')).toHaveText(/^2026, now\./)

    await fan.getByRole('button', { name: 'Table' }).click()
    await expect(fan.getByRole('table')).toBeVisible()
    await expect(fan.getByRole('row')).toHaveCount(17)
})

test('the amount field reports an invalid value accessibly', async ({ page }) => {
    await page.goto('/styleguide')
    const amount = page.getByLabel('Amount to invest (£)')
    await amount.fill('0')
    await expect(amount).toHaveAttribute('aria-invalid', 'true')
    await expect(amount).toHaveAccessibleDescription(/Enter an amount above £0\./)
})
