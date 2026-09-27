/**
 * Rendering the real app at a path, against a stubbed API.
 *
 * `stubApi` routes each request by "METHOD /path" (or just "/path" for any
 * method) to a fixture, a status, or a function of the request body, and
 * records every call so tests can assert what was sent.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeAll, vi } from 'vitest'
import App from '@/App'

export interface Call {
    method: string
    path: string
    query: URLSearchParams
    body: unknown
}

/** A reply: the JSON body with status 200, or an explicit status and body. */
export type Reply = unknown | { status: number; body: unknown }
export type Handler = Reply | ((call: Call) => Reply)

const isStatusReply = (r: unknown): r is { status: number; body: unknown } =>
    typeof r === 'object' && r !== null && 'status' in r && 'body' in r && Object.keys(r).length === 2

export function stubApi(routes: Record<string, Handler>) {
    const calls: Call[] = []
    vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init?: RequestInit) => {
            const [path, qs] = url.split('?')
            const call: Call = {
                method: init?.method ?? 'GET',
                path,
                query: new URLSearchParams(qs),
                body: init?.body ? JSON.parse(String(init.body)) : undefined,
            }
            calls.push(call)
            const handler = routes[`${call.method} ${path}`] ?? routes[path]
            if (handler === undefined) return json({ detail: `no stub for ${call.method} ${path}` }, 404)
            const reply = typeof handler === 'function' ? (handler as (c: Call) => Reply)(call) : handler
            return isStatusReply(reply) ? json(reply.body, reply.status) : json(reply, 200)
        }),
    )
    return calls
}

function json(body: unknown, status: number): Response {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Shows the current path, so tests can assert where a redirect or a button led. */
function WhereAmI() {
    const { pathname } = useLocation()
    return <output data-testid="location">{pathname}</output>
}

export function renderApp(path: string) {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false }, mutations: { retry: false } },
    })
    const view = render(
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={[path]}>
                <App />
                <Routes>
                    <Route path="*" element={<WhereAmI />} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    )
    return { ...view, client }
}

/**
 * Loads lazy pages before a file's first test. The first import compiles
 * the page, which can take seconds; without this the first test's waits
 * would measure the compiler rather than the app.
 */
export function warmPages(...loaders: (() => Promise<unknown>)[]) {
    beforeAll(() => Promise.all(loaders.map((load) => load())), 60_000)
}
