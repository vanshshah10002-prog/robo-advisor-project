/**
 * The theme in a real browser: chosen in the small print, applied at once,
 * and set again on the next visit before the app itself has loaded.
 */
import { expect, test } from '@playwright/test'
import * as fx from '../src/test/fixtures'
import { routeApi } from './support'

test.use({ colorScheme: 'light' })

test('a chosen theme applies at once and holds from the first paint of the next visit', async ({ page }) => {
    await routeApi(page, { 'GET /api/strategy/track-record': () => fx.trackRecord })
    await page.goto('/')
    const html = page.locator('html')
    await expect(html).toHaveAttribute('data-theme', 'light')

    await page.getByRole('group', { name: 'Appearance' }).getByRole('radio', { name: 'Dark' }).check()
    await expect(html).toHaveAttribute('data-theme', 'dark')
    await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(22, 19, 15)')
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#16130f')

    // With the app's own code blocked, only the script in index.html can set the theme.
    await page.route('**/src/main.tsx', (route) => route.abort())
    await page.reload()
    await expect(html).toHaveAttribute('data-theme', 'dark')
})

test('matching the device follows it', async ({ page }) => {
    await routeApi(page, { 'GET /api/strategy/track-record': () => fx.trackRecord })
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.goto('/')
    const html = page.locator('html')
    await expect(html).toHaveAttribute('data-theme', 'dark')
    await expect(page.getByRole('radio', { name: 'Match device' })).toBeChecked()

    await page.emulateMedia({ colorScheme: 'light' })
    await expect(html).toHaveAttribute('data-theme', 'light')
})
