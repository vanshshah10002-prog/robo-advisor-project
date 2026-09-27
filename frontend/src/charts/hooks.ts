import { useCallback, useLayoutEffect, useState, type FocusEvent, type KeyboardEvent } from 'react'

/** Width used before the first measurement, and in test environments that cannot measure. */
export const FALLBACK_WIDTH = 640

/** Tracks an element's rendered width. Attach the returned callback as its `ref`. */
export function useElementWidth<T extends HTMLElement>(fallback = FALLBACK_WIDTH) {
    const [node, setNode] = useState<T | null>(null)
    const [width, setWidth] = useState(fallback)

    useLayoutEffect(() => {
        if (!node) return undefined
        const measure = () => {
            const w = node.getBoundingClientRect().width
            if (w > 0) setWidth(Math.round(w))
        }
        measure()
        if (typeof ResizeObserver === 'undefined') return undefined
        const observer = new ResizeObserver(measure)
        observer.observe(node)
        return () => observer.disconnect()
    }, [node])

    return [setNode, width] as const
}

export interface Cursor {
    /** The data point under the pointer or keyboard cursor, if any. */
    index: number | null
    /** True when the keyboard moved the cursor, so its value should be announced. */
    fromKeyboard: boolean
    point: (index: number | null) => void
    /** Spread onto the focusable element that owns the chart. */
    keyboard: {
        tabIndex: 0
        onKeyDown: (e: KeyboardEvent) => void
        onFocus: (e: FocusEvent) => void
        onBlur: () => void
    }
}

const PAGE_FRACTION = 10

/**
 * A crosshair cursor over `count` points, driven by pointer or keyboard.
 * Arrow keys step one point, Page Up/Down a tenth of the series, Home/End
 * jump to the ends, Escape hides it. Focus starts on the latest point.
 */
export function useCursor(count: number): Cursor {
    const [stored, setIndex] = useState<number | null>(null)
    const [fromKeyboard, setFromKeyboard] = useState(false)
    // A refetch can swap in a shorter series under a live cursor, so clamp on every read.
    const index = stored === null || count === 0 ? null : Math.min(stored, count - 1)

    const point = useCallback((i: number | null) => {
        setIndex(i)
        setFromKeyboard(false)
    }, [])

    const onKeyDown = (e: KeyboardEvent) => {
        if (count === 0) return
        const page = Math.max(1, Math.ceil(count / PAGE_FRACTION))
        const current = index ?? count - 1
        const moves: Record<string, number | null> = {
            ArrowRight: current + 1,
            ArrowUp: current + 1,
            ArrowLeft: current - 1,
            ArrowDown: current - 1,
            PageUp: current + page,
            PageDown: current - page,
            Home: 0,
            End: count - 1,
            Escape: null,
        }
        if (!(e.key in moves)) return
        e.preventDefault()
        const next = moves[e.key]
        setIndex(next === null ? null : Math.min(count - 1, Math.max(0, next)))
        setFromKeyboard(true)
    }

    const onFocus = (e: FocusEvent) => {
        if (e.target !== e.currentTarget || count === 0) return
        setIndex((i) => i ?? count - 1)
        setFromKeyboard(true)
    }

    const onBlur = () => {
        setIndex(null)
        setFromKeyboard(false)
    }

    return { index, fromKeyboard, point, keyboard: { tabIndex: 0, onKeyDown, onFocus, onBlur } }
}
