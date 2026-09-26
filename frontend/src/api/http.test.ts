import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { ApiError, buildUrl, readDetail, request } from './http'

const schema = z.object({ id: z.number(), name: z.string() })

function mockFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
    const fn = vi.fn(impl)
    vi.stubGlobal('fetch', fn)
    return fn
}

const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

describe('buildUrl', () => {
    it('prefixes the API base', () => {
        expect(buildUrl('/portfolio/3')).toBe('/api/portfolio/3')
    })

    it('encodes query parameters and drops undefined ones', () => {
        expect(buildUrl('/efficient-frontier', { asset_classes: 'a,b', risk_score: 5, skip: undefined })).toBe(
            '/api/efficient-frontier?asset_classes=a%2Cb&risk_score=5',
        )
    })
})

describe('readDetail', () => {
    it('reads a string detail', () => {
        expect(readDetail({ detail: 'Portfolio not found' }, 404)).toBe('Portfolio not found')
    })

    it('joins FastAPI validation messages', () => {
        const payload = { detail: [{ msg: 'must be > 0' }, { msg: 'field required' }] }
        expect(readDetail(payload, 422)).toBe('must be > 0; field required')
    })

    it.each([null, 'text', {}, { detail: '' }, { detail: [{}] }])('falls back for %j', (payload) => {
        expect(readDetail(payload, 500)).toBe('The server returned an error (HTTP 500).')
    })
})

describe('request', () => {
    it('returns the parsed body on success', async () => {
        mockFetch(async () => json({ id: 1, name: 'Balanced', extra: true }))
        await expect(request('/x', schema)).resolves.toEqual({ id: 1, name: 'Balanced' })
    })

    it('sends JSON bodies with a content type', async () => {
        const fetchMock = mockFetch(async () => json({ id: 1, name: 'n' }))
        await request('/x', schema, { method: 'POST', body: { a: 1 } })
        const [url, init] = fetchMock.mock.calls[0]
        expect(url).toBe('/api/x')
        expect(init?.method).toBe('POST')
        expect(init?.body).toBe('{"a":1}')
        expect(init?.headers).toEqual({ 'Content-Type': 'application/json' })
    })

    it('omits the content type when there is no body', async () => {
        const fetchMock = mockFetch(async () => json({ id: 1, name: 'n' }))
        await request('/x', schema)
        expect(fetchMock.mock.calls[0][1]?.headers).toBeUndefined()
    })

    it('raises an http ApiError carrying the server detail', async () => {
        mockFetch(async () => json({ detail: 'Portfolio not found' }, 404))
        const error = await request('/x', schema).catch((e: unknown) => e)
        expect(error).toBeInstanceOf(ApiError)
        expect(error).toMatchObject({ kind: 'http', status: 404, message: 'Portfolio not found' })
        expect((error as ApiError).isNotFound).toBe(true)
    })

    it('raises an http ApiError when the error body is not JSON', async () => {
        mockFetch(async () => new Response('<html>Bad gateway</html>', { status: 502 }))
        await expect(request('/x', schema)).rejects.toMatchObject({ kind: 'http', status: 502 })
    })

    it('raises a network ApiError when fetch rejects', async () => {
        mockFetch(async () => {
            throw new TypeError('Failed to fetch')
        })
        await expect(request('/x', schema)).rejects.toMatchObject({ kind: 'network', status: 0 })
    })

    it('rethrows aborts untouched so react-query can cancel quietly', async () => {
        mockFetch(async () => {
            throw new DOMException('aborted', 'AbortError')
        })
        await expect(request('/x', schema)).rejects.toMatchObject({ name: 'AbortError' })
    })

    it('raises a contract ApiError when the shape is wrong', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        mockFetch(async () => json({ id: 'one' }))
        const error = await request('/x', schema).catch((e: unknown) => e)
        expect(error).toMatchObject({ kind: 'contract', message: 'The server sent data in an unexpected format.' })
        expect((error as ApiError).isNotFound).toBe(false)
        expect(console.error).toHaveBeenCalledOnce()
    })
})
