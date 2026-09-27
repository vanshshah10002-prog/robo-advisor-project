import { act, render, renderHook, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CountUp } from '@/ui/CountUp'
import { useCountUp } from './useCountUp'

/** Motion allowed or not, and animation frames that run only when the test says. */
function stubMotion(reduced: boolean) {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('reduce') ? reduced : false, addEventListener() {}, removeEventListener() {} }))
    let queued: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => queued.push(fn))
    vi.stubGlobal('cancelAnimationFrame', () => {
        queued = []
    })
    return {
        frame(at: number) {
            const run = queued
            queued = []
            act(() => run.forEach((fn) => fn(at)))
        },
        pending: () => queued.length,
    }
}

describe('useCountUp', () => {
    it('settles from nine-tenths of the figure to the figure, then hands back the figure itself', () => {
        const frames = stubMotion(false)
        const { result } = renderHook(() => useCountUp(1_000))
        expect(result.current).toBe(900)
        frames.frame(0)
        expect(result.current).toBe(900)
        frames.frame(350)
        expect(result.current).toBeGreaterThan(900)
        expect(result.current).toBeLessThan(1_000)
        frames.frame(700)
        expect(result.current).toBeNull()
        expect(frames.pending()).toBe(0)
    })

    it('does not move for readers who asked for less motion', () => {
        const frames = stubMotion(true)
        const { result } = renderHook(() => useCountUp(1_000))
        expect(result.current).toBeNull()
        expect(frames.pending()).toBe(0)
    })

    it('does not move where the browser cannot say', () => {
        vi.stubGlobal('matchMedia', undefined)
        const { result } = renderHook(() => useCountUp(1_000))
        expect(result.current).toBeNull()
    })

    it('stops when the figure leaves the page', () => {
        const frames = stubMotion(false)
        const { unmount } = renderHook(() => useCountUp(1_000))
        frames.frame(0)
        unmount()
        expect(frames.pending()).toBe(0)
    })
})

describe('CountUp', () => {
    const pounds = (n: number) => `£${Math.round(n).toLocaleString('en-GB')}`

    it('gives assistive technology the figure itself while it counts', () => {
        const frames = stubMotion(false)
        const { container } = render(<CountUp value={124_518} format={pounds} />)
        expect(container.querySelector('[aria-hidden="true"]')).toHaveTextContent('£112,066')
        expect(screen.getByText('£124,518')).toHaveClass('visually-hidden')
        frames.frame(0)
        frames.frame(700)
        expect(container).toHaveTextContent(/^£124,518$/)
        expect(container.querySelector('[aria-hidden]')).toBeNull()
    })

    it('is just the figure without motion', () => {
        stubMotion(true)
        const { container } = render(<CountUp value={124_518} format={pounds} />)
        expect(container.innerHTML).toBe('£124,518')
    })
})
