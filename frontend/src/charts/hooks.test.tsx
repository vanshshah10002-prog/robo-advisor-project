import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FALLBACK_WIDTH, useElementWidth } from './hooks'

function Measured() {
    const [ref, width] = useElementWidth<HTMLDivElement>()
    return <div ref={ref}>{width}</div>
}

describe('useElementWidth', () => {
    afterEach(() => {
        vi.unstubAllGlobals()
        vi.restoreAllMocks()
    })

    it('uses the fallback where nothing can be measured', () => {
        render(<Measured />)
        expect(screen.getByText(String(FALLBACK_WIDTH))).toBeInTheDocument()
    })

    it('follows the element as it resizes, and stops when unmounted', () => {
        let width = 480
        let notify: () => void = () => {}
        const disconnect = vi.fn()
        vi.stubGlobal(
            'ResizeObserver',
            class {
                constructor(cb: () => void) {
                    notify = cb
                }
                observe() {}
                disconnect = disconnect
            },
        )
        vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ width }) as DOMRect)

        const { unmount } = render(<Measured />)
        expect(screen.getByText('480')).toBeInTheDocument()

        width = 333.6
        act(() => notify())
        expect(screen.getByText('334')).toBeInTheDocument()

        unmount()
        expect(disconnect).toHaveBeenCalledOnce()
    })
})
