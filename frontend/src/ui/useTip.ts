import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent, type SyntheticEvent } from 'react'

/** Kept clear of the screen's edges. */
const EDGE = 16
const TIP_MAX_WIDTH = 288
/** Below this share of the screen's height, a tip opens above its term rather than below. */
const LOWER_PART = 0.6

export interface TipPlace {
    left: number
    width: number
    /** Set when the tip opens below the term. */
    top?: number
    /** Set when it opens above, measured from the bottom of the screen. */
    bottom?: number
}

/**
 * Where a tip goes, in screen coordinates: lined up with its term, below it
 * or above it, and always wholly inside the screen.
 */
export function placeTip(anchor: { left: number; top: number; bottom: number }, viewport: { width: number; height: number }): TipPlace {
    const width = Math.min(TIP_MAX_WIDTH, viewport.width - 2 * EDGE)
    const left = Math.min(Math.max(anchor.left, EDGE), viewport.width - EDGE - width)
    return anchor.bottom < viewport.height * LOWER_PART ? { left, width, top: anchor.bottom } : { left, width, bottom: viewport.height - anchor.top }
}

/**
 * A tip that opens while its anchor is hovered or focused, and closes on
 * leaving, blurring or Escape. It is fixed to the screen, so a scrolling
 * table cannot clip it, and follows its anchor while the page scrolls or
 * resizes (closing instead would shut the tip of a term that Tab has just
 * scrolled into view). The tip is a child of the anchor in the React tree,
 * so moving the pointer onto it keeps it open.
 */
export function useTip() {
    const id = useId()
    const [place, setPlace] = useState<TipPlace | null>(null)
    const anchor = useRef<HTMLElement | null>(null)
    const measure = (el: HTMLElement) => setPlace(placeTip(el.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight }))
    const show = (e: SyntheticEvent<HTMLElement>) => {
        anchor.current = e.currentTarget
        measure(e.currentTarget)
    }
    const hide = () => setPlace(null)
    const open = place !== null

    useEffect(() => {
        if (!open) return
        const follow = () => {
            if (anchor.current) measure(anchor.current)
        }
        // Capture, because scrolling inside a table does not bubble to the window.
        window.addEventListener('scroll', follow, true)
        window.addEventListener('resize', follow)
        return () => {
            window.removeEventListener('scroll', follow, true)
            window.removeEventListener('resize', follow)
        }
    }, [open])

    const style: CSSProperties | undefined = place ? { position: 'fixed', left: place.left, width: place.width, top: place.top, bottom: place.bottom } : undefined
    return {
        id,
        open,
        below: place?.top !== undefined,
        style,
        anchor: {
            onMouseEnter: show,
            onMouseLeave: hide,
            onFocus: show,
            onBlur: hide,
            onKeyDown: (e: KeyboardEvent) => {
                if (e.key === 'Escape') hide()
            },
        },
    }
}
