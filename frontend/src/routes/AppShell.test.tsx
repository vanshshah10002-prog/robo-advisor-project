import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect, useRef } from 'react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import AppShell from './AppShell'

function Boom(): never {
    throw new Error('page exploded')
}

/** A page that puts focus on its own field when it opens, as an error summary does. */
function FocusesItself() {
    const ref = useRef<HTMLInputElement>(null)
    useEffect(() => ref.current?.focus(), [])
    return <input ref={ref} aria-label="First answer" />
}

function renderAt(path: string) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route element={<AppShell />}>
                    <Route
                        index
                        element={
                            <>
                                <h1>Front page</h1>
                                <Link to="/focuses">Answer a question</Link>
                            </>
                        }
                    />
                    <Route path="/focuses" element={<FocusesItself />} />
                    <Route path="/portfolios" element={<h1>Your portfolios</h1>} />
                    <Route path="/start" element={<h1>Your goal</h1>} />
                    <Route path="/proposal" element={<h1>Your proposal</h1>} />
                    <Route path="/styleguide" element={<h1>The Statement</h1>} />
                    <Route path="/broken" element={<Boom />} />
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
        expect(screen.getByRole('contentinfo')).toHaveTextContent('no real money moves')
    })

    it('links home, to the places you return to, and to the one new action', () => {
        renderAt('/styleguide')
        expect(screen.getByRole('link', { name: 'UK Robo Advisor' })).toHaveAttribute('href', '/')
        const nav = screen.getByRole('navigation', { name: 'Main' })
        expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['How it works', 'Portfolios'])
        expect(screen.getByRole('link', { name: 'Build a portfolio' })).toHaveAttribute('href', '/start')
    })

    it('marks the current page, matching home exactly', () => {
        renderAt('/portfolios')
        const nav = screen.getByRole('navigation', { name: 'Main' })
        expect(within(nav).getByRole('link', { name: 'Portfolios' })).toHaveAttribute('aria-current', 'page')
        expect(within(nav).getByRole('link', { name: 'How it works' })).not.toHaveAttribute('aria-current')
    })

    it.each(['/start', '/proposal'])('drops the build action while building (%s)', (path) => {
        renderAt(path)
        expect(screen.queryByRole('link', { name: 'Build a portfolio' })).not.toBeInTheDocument()
    })

    it('leaves focus alone on the first page, so Tab reaches the skip link first', () => {
        renderAt('/')
        expect(document.body).toHaveFocus()
    })

    it('starts the next page at the top, with focus on its content', async () => {
        const user = userEvent.setup()
        const scrollTo = vi.spyOn(window, 'scrollTo')
        renderAt('/')
        await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Portfolios' }))
        expect(await screen.findByRole('heading', { name: 'Your portfolios' })).toBeInTheDocument()
        expect(screen.getByRole('main')).toHaveFocus()
        expect(scrollTo).toHaveBeenCalledWith(0, 0)
        vi.restoreAllMocks()
    })

    it('lets a page that places focus itself keep it', async () => {
        const user = userEvent.setup()
        renderAt('/')
        await user.click(screen.getByRole('link', { name: 'Answer a question' }))
        expect(await screen.findByLabelText('First answer')).toHaveFocus()
    })

    it('keeps the masthead when a page fails to render', () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        renderAt('/broken')
        expect(screen.getByRole('alert')).toHaveTextContent('This page could not be displayed.')
        expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
        expect(screen.getAllByRole('main')).toHaveLength(1)
        vi.restoreAllMocks()
    })
})
