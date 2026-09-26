import { NavLink, Link, Outlet } from 'react-router-dom'
import { ButtonLink } from '@/ui/Button'
import styles from './AppShell.module.css'

const NAV = [
    { to: '/history', label: 'Portfolios' },
    { to: '/dashboard', label: 'Dashboard' },
] as const

/**
 * The page shell for rebuilt screens: a masthead with the wordmark, the two
 * places you go back to, and the one action that starts something new; then
 * the page; then the small print. Legacy screens keep their own chrome until
 * they are rebuilt (Phase 3–4).
 */
export default function AppShell() {
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
                                    <NavLink to={item.to} className={({ isActive }) => (isActive ? styles.active : undefined)}>
                                        {item.label}
                                    </NavLink>
                                </li>
                            ))}
                        </ul>
                    </nav>
                    <ButtonLink to="/onboarding" size="sm" className={styles.action}>
                        Build a portfolio
                    </ButtonLink>
                </div>
            </header>

            <main id="main" tabIndex={-1} className={styles.main}>
                <Outlet />
            </main>

            <footer className={styles.footer}>
                <div className={styles.footerInner}>
                    <p>
                        For education and personal use only. Not authorised or regulated by the FCA, and not
                        financial advice. The value of investments can fall as well as rise, and you may get back
                        less than you put in.
                    </p>
                    <p className={styles.small}>
                        Prices are end-of-day closes in pounds sterling. Past performance, real or simulated, is not a
                        guide to future returns.
                    </p>
                </div>
            </footer>
        </div>
    )
}
