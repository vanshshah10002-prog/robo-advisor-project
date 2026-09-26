import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import AppShell from './AppShell'

function renderAt(path: string) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route element={<AppShell />}>
                    <Route path="/history" element={<h1>Your portfolios</h1>} />
                    <Route path="/styleguide" element={<h1>The Statement</h1>} />
                </Route>
            </Routes>
        </MemoryRouter>,
    )
}

describe('AppShell', () => {
    it('frames the page: skip link, masthead, one main, small print', () => {
        renderAt('/styleguide')
        expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')
        expect(screen.getByRole('main')).toHaveAttribute('id', 'main')
        expect(within(screen.getByRole('main')).getByRole('heading', { name: 'The Statement' })).toBeInTheDocument()
        expect(screen.getByRole('contentinfo')).toHaveTextContent(/not financial\s+advice/)
    })

    it('links home, to the places you return to, and to the one new action', () => {
        renderAt('/styleguide')
        expect(screen.getByRole('link', { name: 'UK Robo Advisor' })).toHaveAttribute('href', '/')
        const nav = screen.getByRole('navigation', { name: 'Main' })
        expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Portfolios', 'Dashboard'])
        expect(screen.getByRole('link', { name: 'Build a portfolio' })).toHaveAttribute('href', '/onboarding')
    })

    it('marks the current page', () => {
        renderAt('/history')
        const nav = screen.getByRole('navigation', { name: 'Main' })
        expect(within(nav).getByRole('link', { name: 'Portfolios' })).toHaveAttribute('aria-current', 'page')
        expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
    })
})
