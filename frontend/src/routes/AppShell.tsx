import { Suspense, useEffect, useRef, type RefObject } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { ButtonLink } from '@/ui/Button'
import { ErrorBoundary } from '@/ui/ErrorBoundary'
import { ThemeSwitch } from '@/ui/ThemeSwitch'
import styles from './AppShell.module.css'

const NAV = [
    { to: '/', label: 'How it works', end: true },
    { to: '/portfolios', label: 'Portfolios', end: false },
] as const

/** Paths where building is already under way, so the "Build" action would only repeat itself. */
const BUILDING = /^\/(start|proposal)(\/|$)/

/**
 * After moving to another page, starts it at the top and puts focus on the
 * page content, so a keyboard or screen-reader user begins there rather than
 * on a control that has gone. A page that has already placed focus inside
 * itself (an error summary, say) keeps it. The first page is left alone, so
 * Tab still reaches the skip link first.
 */
function useFocusOnNavigate(pathname: string, main: RefObject<HTMLElement | null>) {
    const previous = useRef(pathname)
    useEffect(() => {
        if (previous.current === pathname) return
        previous.current = pathname
        window.scrollTo(0, 0)
        const active = document.activeElement
        if (active && active !== document.body && main.current?.contains(active)) return
        main.current?.focus({ preventScroll: true })
    }, [pathname, main])
}

/**
 * The page shell: a masthead with the wordmark, the places you go back to,
 * and the one action that starts something new; then the page; then the
 * small print. Pages load on demand, inside an error boundary of their own,
 * so a failing page never takes the masthead with it.
 */
export default function AppShell() {
    const { pathname } = useLocation()
    const main = useRef<HTMLElement>(null)
    useFocusOnNavigate(pathname, main)

    return (
        <div className={styles.shell}>
            <a className="skip-link" href="#main">
                Skip to content
            </a>

            <header className={styles.masthead}>
                <div className={styles.bar}>
                    <Link to="/" className={styles.wordmark}>
                        UK Robo <em>Advisor</em>
                    </Link>
                    <nav aria-label="Main" className={styles.nav}>
                        <ul>
                            {NAV.map((item) => (
                                <li key={item.to}>
                                    <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? styles.active : undefined)}>
                                        {item.label}
                                    </NavLink>
                                </li>
                            ))}
                        </ul>
                    </nav>
                    {!BUILDING.test(pathname) && (
                        <ButtonLink to="/start" size="sm" className={styles.action}>
                            Build a portfolio
                        </ButtonLink>
                    )}
                </div>
            </header>

            <main id="main" ref={main} tabIndex={-1} className={styles.main}>
                <ErrorBoundary resetKey={pathname}>
                    <Suspense fallback={<p className={styles.loading} aria-busy="true">Loading…</p>}>
                        <Outlet />
                    </Suspense>
                </ErrorBoundary>
            </main>

            <footer className={styles.footer}>
                <div className={styles.footerInner}>
                    <p>
                        For education and personal use only. Not authorised or regulated by the FCA, and not
                        financial advice. The value of investments can fall as well as rise, and you may get back
                        less than you put in.
                    </p>
                    <p className={styles.small}>
                        Model portfolios: no real money moves. Prices are end-of-day closes in pounds sterling. Past
                        performance, real or simulated, is not a guide to future returns.
                    </p>
                    <ThemeSwitch />
                </div>
            </footer>
        </div>
    )
}
