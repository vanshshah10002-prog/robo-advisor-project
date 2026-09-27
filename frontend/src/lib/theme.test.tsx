import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { THEME_COLOURS } from './palette'
import { THEME_KEY, resolveTheme, usePageTheme, useTheme } from './theme'
import indexHtml from '../../index.html?raw'

/** A controllable stand-in for the device's colour-scheme setting. */
function stubDevice(dark: boolean) {
    const listeners = new Set<() => void>()
    const query = {
        matches: dark,
        addEventListener: (_: string, fn: () => void) => listeners.add(fn),
        removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
    }
    vi.stubGlobal('matchMedia', () => query)
    return {
        change(next: boolean) {
            query.matches = next
            act(() => listeners.forEach((fn) => fn()))
        },
        listening: () => listeners.size,
    }
}

beforeEach(() => {
    delete document.documentElement.dataset.theme
    document.head.innerHTML = '<meta name="theme-color" content="#f7f4ed"><meta name="color-scheme" content="light dark">'
})

afterEach(() => {
    delete document.documentElement.dataset.theme
})

describe('resolveTheme', () => {
    it('follows the device unless a theme was chosen', () => {
        expect(resolveTheme('system', 'dark')).toBe('dark')
        expect(resolveTheme('system', 'light')).toBe('light')
        expect(resolveTheme('light', 'dark')).toBe('light')
        expect(resolveTheme('dark', 'light')).toBe('dark')
    })
})

describe('useTheme', () => {
    it('matches the device when nothing has been chosen', () => {
        stubDevice(true)
        const { result } = renderHook(() => useTheme())
        expect(result.current.choice).toBe('system')
        expect(result.current.theme).toBe('dark')
        expect(document.documentElement.dataset.theme).toBe('dark')
    })

    it('follows the device as it changes, and stops listening when unmounted', () => {
        const device = stubDevice(false)
        const { result, unmount } = renderHook(() => useTheme())
        expect(result.current.theme).toBe('light')
        device.change(true)
        expect(result.current.theme).toBe('dark')
        expect(document.documentElement.dataset.theme).toBe('dark')
        unmount()
        expect(device.listening()).toBe(0)
    })

    it('keeps a chosen theme, saves it, and applies it', () => {
        const device = stubDevice(true)
        const { result } = renderHook(() => useTheme())
        act(() => result.current.setChoice('light'))
        expect(result.current).toMatchObject({ choice: 'light', theme: 'light' })
        expect(localStorage.getItem(THEME_KEY)).toBe('light')
        expect(document.documentElement.dataset.theme).toBe('light')
        device.change(true)
        expect(result.current.theme).toBe('light')
    })

    it('tells the browser which theme is showing, for its own controls and toolbar', () => {
        stubDevice(false)
        const { result } = renderHook(() => useTheme())
        act(() => result.current.setChoice('dark'))
        expect(document.querySelector('meta[name="theme-color"]')).toHaveAttribute('content', THEME_COLOURS.dark.paper)
        expect(document.querySelector('meta[name="color-scheme"]')).toHaveAttribute('content', 'dark')
    })

    it('follows a choice made in another tab', () => {
        stubDevice(false)
        const { result } = renderHook(() => useTheme())
        localStorage.setItem(THEME_KEY, 'dark')
        act(() => {
            window.dispatchEvent(new StorageEvent('storage', { key: THEME_KEY }))
        })
        expect(result.current.theme).toBe('dark')
    })

    it('forgets the saved theme when set back to the device', () => {
        stubDevice(false)
        localStorage.setItem(THEME_KEY, 'dark')
        const { result } = renderHook(() => useTheme())
        expect(result.current.choice).toBe('dark')
        act(() => result.current.setChoice('system'))
        expect(localStorage.getItem(THEME_KEY)).toBeNull()
        expect(result.current.theme).toBe('light')
    })

    it('ignores a saved value it does not know', () => {
        stubDevice(false)
        localStorage.setItem(THEME_KEY, 'sepia')
        const { result } = renderHook(() => useTheme())
        expect(result.current.choice).toBe('system')
    })

    it('still switches when storage is blocked', () => {
        stubDevice(false)
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked')
        })
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked')
        })
        const { result } = renderHook(() => useTheme())
        expect(result.current.choice).toBe('system')
        act(() => result.current.setChoice('dark'))
        expect(result.current.theme).toBe('dark')
        vi.restoreAllMocks()
    })

    it('treats a browser without matchMedia as light', () => {
        vi.stubGlobal('matchMedia', undefined)
        const { result } = renderHook(() => useTheme())
        expect(result.current.theme).toBe('light')
    })
})

describe('usePageTheme', () => {
    it('reports the theme set on the page as it changes, for code that reads token values', async () => {
        const { result } = renderHook(() => usePageTheme())
        expect(result.current).toBe('light')
        act(() => {
            document.documentElement.dataset.theme = 'dark'
        })
        await waitFor(() => expect(result.current).toBe('dark'))
    })
})

describe('the script in index.html, before first paint', () => {
    const script = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? ''
    // Runs the page's own inline script, as the browser would.
    const run = () => new Function(script)()
    const meta = (name: string) => document.querySelector(`meta[name="${name}"]`)?.getAttribute('content')

    it('is there, and reads the key the app saves under', () => {
        expect(script).toContain(`'${THEME_KEY}'`)
    })

    it('follows the device when nothing is saved', () => {
        stubDevice(true)
        run()
        expect(document.documentElement.dataset.theme).toBe('dark')
        expect(meta('theme-color')).toBe(THEME_COLOURS.dark.paper)
        expect(meta('color-scheme')).toBe('dark')
    })

    it('lets a saved choice win over the device', () => {
        stubDevice(true)
        localStorage.setItem(THEME_KEY, 'light')
        run()
        expect(document.documentElement.dataset.theme).toBe('light')
        expect(meta('theme-color')).toBe(THEME_COLOURS.light.paper)
    })

    it('falls back to the device when storage is blocked, and to light without matchMedia', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked')
        })
        stubDevice(true)
        run()
        expect(document.documentElement.dataset.theme).toBe('dark')
        vi.stubGlobal('matchMedia', undefined)
        run()
        expect(document.documentElement.dataset.theme).toBe('light')
        vi.restoreAllMocks()
    })
})
