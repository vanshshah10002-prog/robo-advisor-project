import { useFundNames } from '@/api/names'
import { useTransactions } from '@/api/queries'
import type { Transaction } from '@/api/schemas'
import { DataTable, FundCell, type Column } from '@/charts'
import { EMPTY, dateTime, decimal, money, signedMoney } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { sectionTitle, usePortfolio } from '../context'
import styles from '../Portfolio.module.css'
import { AddMoney } from './AddMoney'
import { actionLabel, activitySentence, ledgerSummary, newestFirst, pounds } from './model'
import { Rebalance } from './Rebalance'

/** Everything that has happened to the portfolio, and the two things that can happen next. */
export default function ActivityPage() {
    const { id, performance } = usePortfolio()
    usePageTitle(sectionTitle(id, 'Activity'))
    const transactions = useTransactions(id)

    return (
        <article className={styles.section} aria-labelledby="activity-title">
            <h1 id="activity-title" className={styles.title}>
                {transactions.data ? activitySentence(ledgerSummary(transactions.data), performance.needs_rebalance) : 'The ledger'}
            </h1>
            <div className={styles.panels}>
                <AddMoney id={id} />
                <Rebalance id={id} />
            </div>
            <section className={styles.subsection} aria-labelledby="ledger-title">
                <h2 id="ledger-title" className={styles.sectionTitle}>
                    Every transaction
                </h2>
                {transactions.isPending && <p className={styles.loading} aria-busy="true">Loading the ledger…</p>}
                {transactions.isError && (
                    <Notice tone="error" title="The ledger did not load" action={<Button size="sm" variant="secondary" onClick={() => transactions.refetch()}>Try again</Button>}>
                        {transactions.error.message}
                    </Notice>
                )}
                {transactions.data && <Ledger rows={transactions.data} />}
            </section>
        </article>
    )
}

function Ledger({ rows }: { rows: readonly Transaction[] }) {
    const fundName = useFundNames()
    const columns: Column<Transaction>[] = [
        { key: 'when', label: 'When', render: (t) => (t.timestamp ? dateTime(t.timestamp) : 'Not recorded') },
        { key: 'what', label: 'What', render: (t) => actionLabel(t.action) },
        { key: 'fund', label: 'Fund', render: (t) => (t.ticker === 'CASH' ? 'Cash' : <FundCell name={fundName(t.ticker)} ticker={t.ticker} />) },
        { key: 'units', label: 'Units', numeric: true, render: (t) => (t.ticker === 'CASH' ? EMPTY : decimal(t.quantity, 2)) },
        { key: 'price', label: 'Price', numeric: true, render: (t) => (t.ticker === 'CASH' ? EMPTY : money(t.price, { pence: true })) },
        { key: 'value', label: 'Value', numeric: true, render: (t) => money(t.value) },
        { key: 'cost', label: 'Cost', numeric: true, render: (t) => (t.cost === 0 ? EMPTY : pounds(t.cost)) },
        { key: 'realised', label: 'Realised', numeric: true, render: (t) => (t.realised_gain === 0 ? EMPTY : signedMoney(t.realised_gain)) },
    ]
    if (rows.length === 0) return <p className={styles.note}>Nothing has been recorded yet.</p>
    return <DataTable caption="Every transaction, newest first" stack columns={columns} rows={newestFirst(rows)} rowKey={(t) => t.id} />
}
