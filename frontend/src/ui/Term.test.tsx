import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GLOSSARY } from '@/lib/glossary'
import { Term } from './Term'
import { placeTip } from './useTip'

describe('Term', () => {
    it('is described by its explanation, which shows on hover and hides when the pointer leaves', async () => {
        const user = userEvent.setup()
        render(<p>The <Term explain="median">median</Term> outcome.</p>)
        const term = screen.getByText('median')
        expect(term).toHaveAccessibleDescription(GLOSSARY.median)
        expect(screen.getByText(GLOSSARY.median)).not.toBeVisible()

        await user.hover(term)
        expect(screen.getByText(GLOSSARY.median)).toBeVisible()
        await user.unhover(term)
        expect(screen.getByText(GLOSSARY.median)).not.toBeVisible()
    })

    it('shows for the keyboard too, and Escape puts it away', async () => {
        const user = userEvent.setup()
        render(<Term explain="volatility">Volatility</Term>)
        await user.tab()
        expect(screen.getByText('Volatility')).toHaveFocus()
        expect(screen.getByText(GLOSSARY.volatility)).toBeVisible()
        await user.keyboard('{Escape}')
        expect(screen.getByText(GLOSSARY.volatility)).not.toBeVisible()
    })

    it('keeps its explanation out of the text around it', () => {
        render(<p>The <Term explain="median">median</Term> outcome.</p>)
        expect(screen.getByText(GLOSSARY.median)).toHaveAttribute('aria-hidden', 'true')
    })

    it('opens below the term, or above it near the bottom of the screen', () => {
        render(<Term explain="median">median</Term>)
        const term = screen.getByText('median')
        term.getBoundingClientRect = () => ({ left: 100, right: 160, top: 900, bottom: 920, width: 60, height: 20, x: 100, y: 900, toJSON() {} })
        fireEvent.mouseEnter(term)
        expect(screen.getByText(GLOSSARY.median).style.bottom).not.toBe('')
    })

    it('follows its term when the page scrolls or resizes while it is open', () => {
        render(<Term explain="median">median</Term>)
        const term = screen.getByText('median')
        const at = (top: number) => () => ({ left: 100, right: 160, top, bottom: top + 20, width: 60, height: 20, x: 100, y: top, toJSON() {} })
        term.getBoundingClientRect = at(100)
        fireEvent.focus(term)
        const tip = screen.getByText(GLOSSARY.median)
        expect(tip.style.top).toBe('120px')

        term.getBoundingClientRect = at(40)
        fireEvent.scroll(window)
        expect(tip.style.top).toBe('60px')
        term.getBoundingClientRect = at(900)
        fireEvent(window, new Event('resize'))
        expect(tip.style.top).toBe('')
        expect(tip.style.bottom).not.toBe('')
        expect(tip).toBeVisible()
    })
})

describe('placeTip', () => {
    const viewport = { width: 1280, height: 800 }
    const anchor = (left: number, top: number) => ({ left, top, bottom: top + 20 })

    it('lines up with the term and opens below it', () => {
        expect(placeTip(anchor(100, 200), viewport)).toEqual({ left: 100, width: 288, top: 220 })
    })

    it('stays inside the screen at the right edge', () => {
        expect(placeTip(anchor(1200, 200), viewport).left).toBe(1280 - 16 - 288)
    })

    it('stays inside a phone screen and narrows to fit it', () => {
        expect(placeTip(anchor(4, 200), { width: 300, height: 700 })).toEqual({ left: 16, width: 268, top: 220 })
    })

    it('opens above the term in the lower part of the screen', () => {
        expect(placeTip(anchor(100, 600), viewport)).toEqual({ left: 100, width: 288, bottom: 200 })
    })
})
