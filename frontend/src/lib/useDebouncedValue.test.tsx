import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDebouncedValue } from './useDebouncedValue'

describe('useDebouncedValue', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('settles on the latest value once it stops changing', () => {
        const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 300), { initialProps: { v: 1 } })
        rerender({ v: 2 })
        act(() => vi.advanceTimersByTime(200))
        rerender({ v: 3 })
        act(() => vi.advanceTimersByTime(200))
        expect(result.current).toBe(1)
        act(() => vi.advanceTimersByTime(100))
        expect(result.current).toBe(3)
    })

    it('does not restart the wait for an equal object with a new identity', () => {
        const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 300), { initialProps: { v: { a: 1 } } })
        rerender({ v: { a: 2 } })
        act(() => vi.advanceTimersByTime(200))
        rerender({ v: { a: 2 } })
        act(() => vi.advanceTimersByTime(100))
        expect(result.current).toEqual({ a: 2 })
    })
})
