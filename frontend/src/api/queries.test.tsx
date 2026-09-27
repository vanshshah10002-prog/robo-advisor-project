import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './http'
import { createQueryClient, keys, shouldRetry, useContribute, usePerformance } from './queries'

const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function wrapperWith(client = createQueryClient()) {
    const Wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    return { client, Wrapper }
}

afterEach(() => {
    vi.unstubAllGlobals()
})

describe('shouldRetry', () => {
    it('retries network failures and 5xx up to the limit', () => {
        expect(shouldRetry(0, new ApiError('network', 0, 'down'))).toBe(true)
        expect(shouldRetry(1, new ApiError('http', 503, 'busy'))).toBe(true)
        expect(shouldRetry(2, new ApiError('http', 503, 'busy'))).toBe(false)
    })

    it('never retries client errors or contract breaks', () => {
        expect(shouldRetry(0, new ApiError('http', 404, 'missing'))).toBe(false)
        expect(shouldRetry(0, new ApiError('http', 422, 'invalid'))).toBe(false)
        expect(shouldRetry(0, new ApiError('contract', 200, 'shape'))).toBe(false)
    })

    it('retries unknown errors once more', () => {
        expect(shouldRetry(0, new Error('boom'))).toBe(true)
    })
})

describe('keys', () => {
    it('nests every per-portfolio key under the portfolio root', () => {
        const root = keys.portfolio(7)
        for (const key of [keys.performance(7), keys.rebalancePlan(7), keys.transactions(7), keys.portfolioDetail(7)]) {
            expect(key.slice(0, root.length)).toEqual([...root])
        }
    })

    it('makes frontier keys independent of asset-class order', () => {
        expect(keys.frontier(['b', 'a'], 5)).toEqual(keys.frontier(['a', 'b'], 5))
    })
})

describe('hooks', () => {
    it('stays idle until a portfolio id is known', () => {
        const fetchMock = vi.fn()
        vi.stubGlobal('fetch', fetchMock)
        const { Wrapper } = wrapperWith()
        const { result } = renderHook(() => usePerformance(null), { wrapper: Wrapper })
        expect(result.current.fetchStatus).toBe('idle')
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it('invalidates every view of the portfolio after a contribution', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () =>
                json({
                    portfolio_id: 3,
                    deposited_gbp: 500,
                    buys: [{ ticker: 'VWRL.L', value_gbp: 500, units: 4.2 }],
                    total_value: 10_500,
                    portfolio_drift: 0.01,
                    needs_rebalance: false,
                }),
            ),
        )
        const { client, Wrapper } = wrapperWith()
        const invalidate = vi.spyOn(client, 'invalidateQueries')
        const { result } = renderHook(() => useContribute(3), { wrapper: Wrapper })

        result.current.mutate({ amount_gbp: 500 })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))
        expect(invalidate).toHaveBeenCalledWith({ queryKey: keys.portfolio(3) })
    })
})
