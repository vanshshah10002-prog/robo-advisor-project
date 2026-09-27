import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { useIdentity, useOnboardingDraft } from '@/store/session'

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

// Pages wait on stubbed requests and on inputs settling; under a full,
// parallel run that can take longer than the default one-second wait.
configure({ asyncUtilTimeout: 5_000 })

// jsdom does not lay out, so scrolling is a no-op.
Element.prototype.scrollIntoView = function scrollIntoView() {}
window.scrollTo = (() => {}) as typeof window.scrollTo

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    useIdentity.getState().forget()
    useOnboardingDraft.getState().reset()
    sessionStorage.clear()
    localStorage.clear()
    delete document.documentElement.dataset.theme
})
