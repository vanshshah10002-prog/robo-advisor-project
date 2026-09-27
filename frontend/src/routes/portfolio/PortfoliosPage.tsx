import { clsx } from 'clsx'
import { Link } from 'react-router-dom'
import { useArchivedPortfolios, useHistory, useUserPortfolios } from '@/api/queries'
import type { PortfolioSummary } from '@/api/schemas'
import { DataTable, Sparkline, type Column } from '@/charts'
import { date, money } from '@/lib/format'
import { level } from '@/lib/risk'
import { usePageTitle } from '@/lib/usePageTitle'
import { useIdentity } from '@/store/session'
import { Button, ButtonLink } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Delta } from '@/ui/Stat'
import { ArchivedList, OutcomeNotice } from './Archive'
import { listSentence, portfolioName } from './model'
import styles from './Portfolio.module.css'
import { archiveColumn, useArchiving } from './useArchiving'

const COLUMNS: Column<PortfolioSummary>[] = [
    {
        key: 'name',
        label: 'Portfolio',
        render: (r) => (
            <>
                <Link to={`/portfolio/${r.portfolio_id}`} className={styles.rowLink}>
                    {portfolioName(r)}
                </Link>
                <span className={styles.rowDetail}>{r.created_at ? `Opened ${date(r.created_at)}` : 'Opening date not recorded'}</span>
            </>
        ),
    },
    { key: 'risk', label: 'Risk level', numeric: true, render: (r) => level(r.risk_score) },
    { key: 'value', label: 'Value', numeric: true, render: (r) => (r.total_value === null ? 'Not valued' : money(r.total_value)) },
    { key: 'paid', label: 'Paid in', numeric: true, render: (r) => money(r.net_contributions) },
    { key: 'return', label: 'Return', numeric: true, render: (r) => (r.total_return_pct === null ? '—' : <Delta value={r.total_return_pct} />) },
    { key: 'trend', label: 'Since opening', render: (r) => <Trend id={r.portfolio_id} /> },
]

/** The daily value since opening, once there are two days to draw. */
function Trend({ id }: { id: number }) {
    const history = useHistory(id)
    const points = history.data?.points ?? []
    if (points.length < 2) return <span className={styles.rowDetail}>{history.isPending ? '' : 'Not enough days yet'}</span>
    const [first, last] = [points[0], points[points.length - 1]]
    return (
        <Sparkline
            values={points.map((p) => p.value)}
            label={`Value from ${money(first.value)} on ${date(first.date)} to ${money(last.value)} on ${date(last.date)}`}
        />
    )
}

/** Every portfolio this browser has opened, newest first, with its value today; the archived ones below. */
export default function PortfoliosPage() {
    usePageTitle('Your portfolios')
    const userId = useIdentity((s) => s.userId)
    const portfolios = useUserPortfolios(userId)
    const archived = useArchivedPortfolios(userId)
    const { outcome, pendingId, archive, restore } = useArchiving(portfolios.data)

    return (
        <article className={clsx(styles.page, 'stagger')} aria-labelledby="portfolios-title">
            <header className={styles.head}>
                <p className="label">Your portfolios</p>
                <h1 id="portfolios-title" className={styles.title}>
                    {portfolios.data?.length ? listSentence(portfolios.data) : 'Your portfolios'}
                </h1>
            </header>
            {outcome && <OutcomeNotice outcome={outcome} onUndo={restore} />}
            <List userId={userId} portfolios={portfolios} archived={archived} onArchive={archive} pendingId={pendingId} />
            {userId !== null && <ArchivedList archived={archived} onRestore={restore} pendingId={pendingId} />}
        </article>
    )
}

interface ListProps {
    userId: number | null
    portfolios: ReturnType<typeof useUserPortfolios>
    archived: ReturnType<typeof useArchivedPortfolios>
    onArchive: (row: PortfolioSummary) => void
    pendingId: number | null
}

function List({ userId, portfolios, archived, onArchive, pendingId }: ListProps) {
    const isEmpty = userId === null || (portfolios.isSuccess && portfolios.data.length === 0)
    if (isEmpty && archived.isPending && userId !== null) return <p className={styles.loading} aria-busy="true">Loading your portfolios…</p>
    if (isEmpty) {
        const allArchived = (archived.data?.length ?? 0) > 0
        return (
            <div className={styles.empty}>
                <p className={styles.lead}>
                    {allArchived
                        ? 'Every portfolio opened in this browser is archived. Restore one below to put it back on this list, or build a new one.'
                        : 'No portfolios have been opened in this browser yet. Building one takes about five minutes, and nothing is saved until you choose to open it.'}
                </p>
                <ButtonLink to="/start">Build a portfolio</ButtonLink>
            </div>
        )
    }
    if (portfolios.isPending) return <p className={styles.loading} aria-busy="true">Loading your portfolios…</p>
    if (portfolios.isError) {
        return (
            <Notice tone="error" title="Your portfolios did not load" action={<Button size="sm" variant="secondary" onClick={() => portfolios.refetch()}>Try again</Button>}>
                {portfolios.error.message}
            </Notice>
        )
    }
    return <DataTable caption="Your portfolios" stack columns={[...COLUMNS, archiveColumn(onArchive, pendingId)]} rows={portfolios.data} rowKey={(r) => r.portfolio_id} />
}
