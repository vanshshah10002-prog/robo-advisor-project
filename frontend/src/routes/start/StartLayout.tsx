import { clsx } from 'clsx'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useOnboardingDraft } from '@/store/session'
import { RESULT_PATH, SECTIONS, validateSection } from './model'
import styles from './Start.module.css'

const STEPS = [...SECTIONS.map((s) => ({ path: s.path, title: s.title, key: s.key })), { path: RESULT_PATH, title: 'Your risk level', key: 'result' as const }]

/**
 * The frame around onboarding: a ruled row of the four steps, each done step
 * a link back, the current one marked for assistive technology.
 */
export default function StartLayout() {
    const { pathname } = useLocation()
    const draft = useOnboardingDraft()
    const current = Math.max(0, STEPS.findIndex((s) => s.path === pathname.replace(/\/$/, '')))

    return (
        <div className={styles.page}>
            <nav aria-label="Progress" className={styles.progress}>
                <ol>
                    {STEPS.map((step, i) => {
                        const done = i < current && (step.key === 'result' || validateSection(step.key, draft).length === 0)
                        const label = (
                            <>
                                <span className={styles.stepNumber}>{String(i + 1).padStart(2, '0')}</span>
                                <span>{step.title}</span>
                                {done && <span className="visually-hidden"> (done)</span>}
                            </>
                        )
                        return (
                            <li key={step.path} className={clsx(i === current && styles.current, done && styles.done)} aria-current={i === current ? 'step' : undefined}>
                                {done ? <Link to={step.path}>{label}</Link> : <span>{label}</span>}
                            </li>
                        )
                    })}
                </ol>
            </nav>
            <Outlet />
        </div>
    )
}
