import { defineConfig, devices } from '@playwright/test'

/**
 * Browser checks against the Vite dev server. Uses the installed Chrome
 * (`channel: 'chrome'`) so no browser download is needed. No test needs the
 * backend: the journey stubs the API with the same fixtures as the unit tests.
 */
export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? 'github' : 'list',
    // A cold dev server compiles each page on first visit, which can pass five seconds.
    expect: { timeout: 10_000 },
    use: {
        baseURL: 'http://127.0.0.1:5173',
        trace: 'retain-on-failure',
    },
    projects: [
        { name: 'desktop', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
        { name: 'mobile', use: { ...devices['Pixel 7'], channel: 'chrome' } },
    ],
    webServer: {
        command: 'npm run dev -- --host 127.0.0.1 --strictPort',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
})
