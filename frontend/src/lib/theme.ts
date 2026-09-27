/**
 * The light or dark theme
 * =======================
 * The page follows the device's colour-scheme setting unless the reader has
 * chosen one, and that choice is kept in this browser. index.html applies it
 * before first paint with the same key and the same rules, so this module
 * takes over from there: it switches when the choice or the device changes.
 */
import { useEffect, useSyncExternalStore } from 'react'
import { THEME_COLOURS } from './palette'

export type Theme = 'light' | 'dark'
export type ThemeChoice = 'system' | Theme

/** Where the choice is kept. The script in index.html reads the same key. */
export const THEME_KEY = 'ukra.theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

const isTheme = (value: unknown): value is Theme => value === 'light' || value === 'dark'

export const resolveTheme = (choice: ThemeChoice, device: Theme): Theme => (choice === 'system' ? device : choice)

/** Held here only when the browser refuses storage, so the switch still works for this visit. */
let unsaved: ThemeChoice = 'system'
const listeners = new Set<() => void>()

function savedChoice(): ThemeChoice {
    try {
        const value = localStorage.getItem(THEME_KEY)
        return isTheme(value) ? value : 'system'
    } catch {
        return unsaved
    }
}

function setChoice(choice: ThemeChoice) {
    try {
        if (choice === 'system') localStorage.removeItem(THEME_KEY)
        else localStorage.setItem(THEME_KEY, choice)
    } catch {
        unsaved = choice
    }
    listeners.forEach((notify) => notify())
}

const deviceQuery = () => (typeof window.matchMedia === 'function' ? window.matchMedia(DARK_QUERY) : null)
const deviceTheme = (): Theme => (deviceQuery()?.matches ? 'dark' : 'light')

/** Hears a new choice made here, in another tab (through storage), or on the device. */
function subscribe(onChange: () => void) {
    const query = deviceQuery()
    const onStorage = (e: StorageEvent) => {
        if (e.key === THEME_KEY || e.key === null) onChange()
    }
    listeners.add(onChange)
    query?.addEventListener('change', onChange)
    window.addEventListener('storage', onStorage)
    return () => {
        listeners.delete(onChange)
        query?.removeEventListener('change', onChange)
        window.removeEventListener('storage', onStorage)
    }
}

const snapshot = () => `${savedChoice()} ${deviceTheme()}`

/** Sets the theme on the page, and tells the browser so its own controls and toolbar match. */
function applyTheme(theme: Theme) {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOURS[theme].paper)
    document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', theme)
}

/** The reader's choice, the theme showing, and a way to change it. */
export function useTheme() {
    const [choice, device] = useSyncExternalStore(subscribe, snapshot).split(' ') as [ThemeChoice, Theme]
    const theme = resolveTheme(choice, device)
    useEffect(() => applyTheme(theme), [theme])
    return { choice, theme, setChoice }
}

function watchPage(onChange: () => void) {
    const observer = new MutationObserver(onChange)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
}

const pageTheme = (): Theme => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

/** The theme on the page right now, as set on <html>: for code that reads the tokens' values. */
export const usePageTheme = () => useSyncExternalStore(watchPage, pageTheme)
