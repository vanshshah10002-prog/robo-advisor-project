/**
 * Typed HTTP layer
 * ================
 * Every response is parsed against a zod schema, so a backend change that
 * breaks the contract fails loudly at the boundary instead of as a
 * `cannot read properties of undefined` deep inside a chart.
 */

import type { z } from 'zod'

export const API_BASE = '/api'

export type ApiErrorKind = 'http' | 'network' | 'contract'

export class ApiError extends Error {
    readonly kind: ApiErrorKind
    readonly status: number
    readonly detail: string

    constructor(kind: ApiErrorKind, status: number, detail: string, options?: { cause?: unknown }) {
        super(detail, options)
        this.name = 'ApiError'
        this.kind = kind
        this.status = status
        this.detail = detail
    }

    get isNotFound(): boolean {
        return this.kind === 'http' && this.status === 404
    }
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface RequestOptions {
    method?: Method
    body?: unknown
    query?: Record<string, string | number | boolean | undefined>
    signal?: AbortSignal
}

/** FastAPI sends `detail` as a string, or as a list of validation issues. */
export function readDetail(payload: unknown, status: number): string {
    const fallback = `The server returned an error (HTTP ${status}).`
    if (typeof payload !== 'object' || payload === null || !('detail' in payload)) return fallback
    const { detail } = payload as { detail: unknown }
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
        const messages = detail
            .map((d) => (typeof d === 'object' && d !== null && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
            .filter(Boolean)
        if (messages.length) return messages.join('; ')
    }
    return fallback
}

export function buildUrl(path: string, query?: RequestOptions['query']): string {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query ?? {})) {
        if (value !== undefined) params.set(key, String(value))
    }
    const qs = params.toString()
    return `${API_BASE}${path}${qs ? `?${qs}` : ''}`
}

export async function request<S extends z.ZodTypeAny>(
    path: string,
    schema: S,
    { method = 'GET', body, query, signal }: RequestOptions = {},
): Promise<z.output<S>> {
    let response: Response
    try {
        response = await fetch(buildUrl(path, query), {
            method,
            signal,
            headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
        })
    } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
        throw new ApiError('network', 0, 'Could not reach the server. Check that the API is running.', { cause })
    }

    const payload: unknown = await response.json().catch(() => null)

    if (!response.ok) {
        throw new ApiError('http', response.status, readDetail(payload, response.status))
    }

    const parsed = schema.safeParse(payload)
    if (!parsed.success) {
        console.error(`Response from ${method} ${path} did not match its schema`, parsed.error.issues)
        throw new ApiError('contract', response.status, 'The server sent data in an unexpected format.', {
            cause: parsed.error,
        })
    }
    return parsed.data
}
