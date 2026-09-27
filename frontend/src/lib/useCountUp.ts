import { useEffect, useState } from 'react'

const COUNT_MS = 700
/** Where the count starts, as a share of the figure: a settle into place, not a spin up from zero. */
const START = 0.9

const easeOut = (t: number) => 1 - (1 - t) ** 3

/** Motion only where the browser can say the reader has not asked for less. */
const allowsMotion = () => typeof window.matchMedia === 'function' && !window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * A figure that settles into place once, when it first appears: the value
 * to show while it counts, then `null` for "show the figure itself". It
 * never moves for readers who asked for less motion. If the figure changes
 * while counting, the count heads for the new one.
 */
export function useCountUp(target: number, duration = COUNT_MS): number | null {
    const [counting, setCounting] = useState(allowsMotion)
    const [progress, setProgress] = useState(0)

    useEffect(() => {
        if (!counting) return
        let frame = 0
        let start: number | null = null
        const tick = (now: number) => {
            start ??= now
            const t = Math.min(1, (now - start) / duration)
            setProgress(t)
            if (t < 1) frame = requestAnimationFrame(tick)
            else setCounting(false)
        }
        frame = requestAnimationFrame(tick)
        return () => cancelAnimationFrame(frame)
    }, [counting, duration])

    return counting ? target * (START + (1 - START) * easeOut(progress)) : null
}
