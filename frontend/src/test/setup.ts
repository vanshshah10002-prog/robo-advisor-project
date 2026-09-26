import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom has no PointerEvent, so fireEvent.pointerMove would build a plain
// Event and drop clientX. A MouseEvent subclass carries the coordinates.
if (typeof window.PointerEvent === 'undefined') {
    class PointerEventShim extends MouseEvent {
        readonly pointerId: number
        readonly pointerType: string
        constructor(type: string, init: PointerEventInit = {}) {
            super(type, init)
            this.pointerId = init.pointerId ?? 1
            this.pointerType = init.pointerType ?? 'mouse'
        }
    }
    window.PointerEvent = PointerEventShim as unknown as typeof PointerEvent
}

afterEach(() => {
    cleanup()
    sessionStorage.clear()
    localStorage.clear()
})
