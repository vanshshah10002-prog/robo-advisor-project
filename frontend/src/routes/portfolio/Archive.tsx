/**
 * Archiving: taking a portfolio off the list without deleting anything. The
 * list offers it on each row, keeps the archived ones below with a way back,
 * and an archived portfolio's workspace says so.
 */
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useSetArchived, type useArchivedPortfolios } from '@/api/queries'
import type { PortfolioSummary } from '@/api/schemas'
import { DataTable, type Column } from '@/charts'
import { date, money } from '@/lib/format'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { portfolioName } from './model'
import styles from './Portfolio.module.css'
import { actionsLabel, rowAction, type Outcome } from './useArchiving'

/**
 * What archiving or restoring did. It takes focus, because the button that
 * was pressed has gone from the page with its row.
 */
export function OutcomeNotice({ outcome, onUndo }: { outcome: Outcome; onUndo: (row: PortfolioSummary) => void }) {
    const ref = useRef<HTMLDivElement>(null)
    useEffect(() => ref.current?.focus(), [outcome])
    const name = portfolioName(outcome.row)
    const failed = outcome.error !== undefined

    return (
        <div ref={ref} tabIndex={-1} role={failed ? undefined : 'status'} className={styles.outcome}>
            {failed ? (
                <Notice tone="error" title={`${name} could not be ${outcome.archived ? 'archived' : 'restored'}`}>
                    {outcome.error}
                </Notice>
            ) : outcome.archived ? (
                <Notice
                    title={`${name} is archived`}
                    action={
                        <Button size="sm" variant="secondary" onClick={() => onUndo(outcome.row)}>
                            Undo
                        </Button>
                    }
                >
                    It is off your list; nothing was deleted, and it still opens.
                </Notice>
            ) : (
                <Notice title={`${name} is back on your list`} />
            )}
        </div>
    )
}

function archivedColumns(onRestore: (row: PortfolioSummary) => void, pendingId: number | null): Column<PortfolioSummary>[] {
    return [
        {
            key: 'name',
            label: 'Portfolio',
            render: (r) => (
                <>
                    <Link to={`/portfolio/${r.portfolio_id}`} className={styles.rowLink}>
                        {portfolioName(r)}
                    </Link>
                    <span className={styles.rowDetail}>{r.archived_at ? `Archived ${date(r.archived_at)}` : 'Archive date not recorded'}</span>
                </>
            ),
        },
        { key: 'value', label: 'Value', numeric: true, render: (r) => (r.total_value === null ? 'Not valued' : money(r.total_value)) },
        {
            key: 'restore',
            label: actionsLabel,
            render: (r) => (
                <Button size="sm" variant="secondary" aria-label={`Restore ${portfolioName(r)}`} {...rowAction(r.portfolio_id, pendingId)} onClick={() => onRestore(r)}>
                    Restore
                </Button>
            ),
        },
    ]
}

/** The archived portfolios, under the list; nothing at all while there are none. */
interface ArchivedListProps {
    archived: ReturnType<typeof useArchivedPortfolios>
    onRestore: (row: PortfolioSummary) => void
    pendingId: number | null
}

export function ArchivedList({ archived, onRestore, pendingId }: ArchivedListProps) {
    if (archived.isError) {
        return (
            <Notice tone="error" title="Archived portfolios did not load" action={<Button size="sm" variant="secondary" onClick={() => archived.refetch()}>Try again</Button>}>
                {archived.error.message}
            </Notice>
        )
    }
    if (!archived.data?.length) return null
    return (
        <section className={styles.subsection} aria-labelledby="archived-title">
            <h2 id="archived-title" className={styles.sectionTitle}>
                Archived
            </h2>
            <p className={styles.note}>Off your list but kept: each one still opens, and can be put back.</p>
            <DataTable caption="Archived portfolios" stack columns={archivedColumns(onRestore, pendingId)} rows={archived.data} rowKey={(r) => r.portfolio_id} />
        </section>
    )
}

/** Shown at the top of an archived portfolio's workspace, with the way back. */
export function ArchivedNotice({ id, archivedAt }: { id: number; archivedAt: string | null }) {
    const restore = useSetArchived()
    return (
        <Notice
            title="This portfolio is archived"
            action={
                <Button size="sm" variant="secondary" disabled={restore.isPending} onClick={() => restore.mutate({ portfolioId: id, archived: false })}>
                    Restore
                </Button>
            }
        >
            {archivedAt ? `Archived on ${date(archivedAt)}. ` : ''}It is off your list of portfolios; nothing was deleted, and everything here still works.
            {restore.isError && ` It could not be restored: ${restore.error.message}`}
        </Notice>
    )
}
