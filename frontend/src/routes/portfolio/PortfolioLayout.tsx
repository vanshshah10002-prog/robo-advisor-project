import { Suspense, useEffect } from 'react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { isNotFound } from '@/api/http'
import { usePerformance, usePortfolioDetail } from '@/api/queries'
import type { Performance, PortfolioDetail } from '@/api/schemas'
import { money } from '@/lib/format'
import { level } from '@/lib/risk'
import { usePageTitle } from '@/lib/usePageTitle'
import { useIdentity } from '@/store/session'
import { Button, ButtonLink } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import NotFound from '../NotFound'
import { ArchivedNotice } from './Archive'
import { SECTIONS, type PortfolioContext } from './context'
import { isUnrecorded } from './model'
import styles from './Portfolio.module.css'

const parseId = (raw: string | undefined) => (raw && /^\d+$/.test(raw) ? Number(raw) : null)

/**
 * The portfolio workspace: one line saying which portfolio this is, the
 * sections, and the section. The valuation is loaded once here and shared,
 * so moving between sections never waits for it again.
 */
export default function PortfolioLayout() {
    const id = parseId(useParams().id)
    const setLastPortfolio = useIdentity((s) => s.setLastPortfolio)
    const performance = usePerformance(id)

    useEffect(() => {
        if (id !== null && performance.isSuccess) setLastPortfolio(id)
    }, [id, performance.isSuccess, setLastPortfolio])

    if (id === null) return <NotFound />
    if (performance.isPending) return <Loading />
    if (performance.isError) {
        if (isNotFound(performance.error)) return <Missing id={id} />
        return (
            <Notice tone="error" title="The portfolio could not be valued" action={<Button size="sm" variant="secondary" onClick={() => performance.refetch()}>Try again</Button>}>
                {performance.error.message}
            </Notice>
        )
    }
    // Keyed by portfolio, so what was typed in one portfolio's sections never carries over to another's.
    return <Workspace key={id} id={id} performance={performance.data} />
}

function Loading() {
    usePageTitle('Loading a portfolio')
    return <p className={styles.loading} aria-busy="true">Valuing the portfolio at the latest prices…</p>
}

function Missing({ id }: { id: number }) {
    usePageTitle('No such portfolio')
    return (
        <div className={styles.page}>
            <h1 className={styles.title}>There is no portfolio {id}</h1>
            <p className={styles.lead}>It may have been opened in another browser, or the link is wrong.</p>
            <ButtonLink to="/portfolios">See your portfolios</ButtonLink>
        </div>
    )
}

/** "Portfolio 20 · risk level 4 · ISA · £250 a month". */
function identityLine(id: number, detail: PortfolioDetail | undefined): string {
    if (!detail) return `Portfolio ${id}`
    const monthly = detail.monthly_contribution > 0 ? ` · ${money(detail.monthly_contribution)} a month` : ''
    return `Portfolio ${id} · risk level ${level(detail.risk_score)} · ${detail.uses_isa ? 'ISA' : 'General account'}${monthly}`
}

function Workspace({ id, performance }: { id: number; performance: Performance }) {
    const detail = usePortfolioDetail(id)
    const context: PortfolioContext = { id, performance, detail: detail.data }

    if (isUnrecorded(performance)) return <Unrecorded id={id} line={identityLine(id, detail.data)} />
    return (
        <div className={styles.workspace}>
            <div className={styles.identity}>
                <p className="label">{identityLine(id, detail.data)}</p>
                <nav aria-label="Portfolio sections" className={styles.sections}>
                    <ul>
                        {SECTIONS.map((s) => (
                            <li key={s.label}>
                                <NavLink to={`/portfolio/${id}${s.path ? `/${s.path}` : ''}`} end className={({ isActive }) => (isActive ? styles.current : undefined)}>
                                    {s.label}
                                </NavLink>
                            </li>
                        ))}
                    </ul>
                </nav>
            </div>
            {detail.data?.archived && <ArchivedNotice id={id} archivedAt={detail.data.archived_at} />}
            {detail.isError && (
                <Notice tone="error" title="Part of this portfolio did not load" action={<Button size="sm" variant="secondary" onClick={() => detail.refetch()}>Try again</Button>}>
                    {detail.error.message} Its risk level, account and monthly amount are left out until it does.
                </Notice>
            )}
            <Suspense fallback={<p className={styles.loading} aria-busy="true">Loading…</p>}>
                <Outlet context={context} />
            </Suspense>
        </div>
    )
}

/** Opened before purchases were recorded: there is nothing to value, chart or project, and it says so. */
function Unrecorded({ id, line }: { id: number; line: string }) {
    usePageTitle(`Portfolio ${id}`)
    return (
        <article className={styles.page} aria-labelledby="portfolio-title">
            <header className={styles.head}>
                <p className="label">{line}</p>
                <h1 id="portfolio-title" className={styles.title}>
                    Portfolio {id}
                </h1>
            </header>
            <Notice tone="info" title="This portfolio has no recorded purchases">
                It was opened before purchases were recorded, so there is nothing to value, chart or project. Build a new portfolio to follow
                one from the day it opens. <Link to="/start">Build a portfolio</Link>
            </Notice>
            <p className={styles.back}>
                <Link to="/portfolios">All your portfolios</Link>
            </p>
        </article>
    )
}

