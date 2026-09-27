import type { ReactNode } from 'react'
import { useConstruction, useHistory } from '@/api/queries'
import type { Performance } from '@/api/schemas'
import { date, decimal, EMPTY, money, percent, signedPercent } from '@/lib/format'
import type { GlossaryTerm } from '@/lib/glossary'
import { Provenance } from '@/ui/Tag'
import { Term } from '@/ui/Term'
import { estimatedStatistics, measuredStatistics, type EstimatedStatistics, type MeasuredStatistics } from './model'
import styles from './Statistics.module.css'

interface Row {
    key: string
    explain: GlossaryTerm
    label: string
    value: string
    detail?: ReactNode
    /** The figure is not available yet, and `value` says when it will be. */
    pending?: boolean
}

/**
 * The technical figures beside the holdings: what the estimates the portfolio
 * was built with say about it at today's weights, then what its own values
 * have shown so far. Every label explains itself on hover or focus.
 */
export function Statistics({ id, performance }: { id: number; performance: Performance }) {
    return (
        <aside className={styles.panel} aria-labelledby="statistics-title">
            <h2 id="statistics-title" className={styles.title}>
                Portfolio statistics
            </h2>
            <Estimated id={id} performance={performance} />
            <Measured id={id} />
        </aside>
    )
}

function Group({ title, kind, children }: { title: string; kind: 'estimated' | 'measured'; children: ReactNode }) {
    return (
        <section className={styles.group} aria-label={title}>
            <h3 className={styles.groupTitle}>
                {title} <Provenance kind={kind} />
            </h3>
            {children}
        </section>
    )
}

/** Why there are no estimated figures, or null when there are. */
function estimatesMissing(construction: ReturnType<typeof useConstruction>, stats: EstimatedStatistics | null): string | null {
    if (construction.isPending) return 'Loading the estimates…'
    if (construction.isError) return `The estimates did not load: ${construction.error.message}`
    if (!construction.data.snapshot) return 'This portfolio was opened before its construction was recorded, so there are no estimates to combine.'
    if (!stats) return 'A fund is missing an estimate, so these figures cannot be combined.'
    return null
}

/** Why there are no measured figures, or null when there are. */
function valuesMissing(history: ReturnType<typeof useHistory>): string | null {
    if (history.isPending) return 'Loading its values…'
    if (history.isError) return `The history did not load: ${history.error.message}`
    if (history.data.points.length === 0) return history.data.reason ?? 'No values have been recorded yet.'
    return null
}

function Estimated({ id, performance: p }: { id: number; performance: Performance }) {
    const construction = useConstruction(id)
    const snapshot = construction.data?.snapshot ?? null
    const stats = snapshot ? estimatedStatistics(snapshot, p.holdings) : null
    const message = estimatesMissing(construction, stats)
    return (
        <Group title="Looking ahead" kind="estimated">
            {stats && snapshot ? (
                <>
                    <p className={styles.note}>
                        {stats.weightsFrom === 'today' ? 'At the weights held today' : 'At the target weights, as a fund has no price today'}; from the
                        estimates of {date(snapshot.as_of)}.
                    </p>
                    <Figures rows={estimatedRows(stats, p.total_value, snapshot.holdings.length)} />
                </>
            ) : (
                <p className={styles.note}>{message}</p>
            )}
        </Group>
    )
}

function Measured({ id }: { id: number }) {
    const history = useHistory(id)
    const message = valuesMissing(history)
    return (
        <Group title="So far" kind="measured">
            {message === null ? <Figures rows={measuredRows(measuredStatistics(history.data?.points ?? []))} /> : <p className={styles.note}>{message}</p>}
        </Group>
    )
}

function Figures({ rows }: { rows: readonly Row[] }) {
    return (
        <dl className={styles.figures}>
            {rows.map((r) => (
                <div key={r.key} className={styles.row}>
                    <dt className={styles.label}>
                        <Term explain={r.explain}>{r.label}</Term>
                    </dt>
                    <dd className={r.pending ? styles.pending : styles.value}>
                        <span>{r.value}</span>
                        {r.detail && <span className={styles.detail}>{r.detail}</span>}
                    </dd>
                </div>
            ))}
        </dl>
    )
}

function estimatedRows(s: EstimatedStatistics, value: number, funds: number): Row[] {
    const charges = s.ongoingCharges
    return [
        { key: 'return', explain: 'expectedReturn', label: 'Expected return', value: `${percent(s.expectedReturn)} a year` },
        { key: 'volatility', explain: 'volatility', label: 'Volatility', value: `${percent(s.volatility)} a year` },
        {
            key: 'sharpe',
            explain: 'sharpe',
            label: 'Sharpe ratio',
            value: s.sharpe === null ? EMPTY : decimal(s.sharpe, 2),
            detail: s.riskFree === null ? undefined : (
                <>
                    Against {percent(s.riskFree)} <Term explain="riskFree">risk-free</Term>
                </>
            ),
        },
        { key: 'var', explain: 'valueAtRisk', label: 'Value at risk (95%, 1 year)', value: percent(s.valueAtRisk), detail: `About ${money(s.valueAtRisk * value)} today` },
        { key: 'diversification', explain: 'diversificationRatio', label: 'Diversification ratio', value: decimal(s.diversificationRatio, 2) },
        { key: 'effective', explain: 'effectiveHoldings', label: 'Effective number of holdings', value: decimal(s.effectiveHoldings, 1), detail: `Of ${funds} funds` },
        {
            key: 'charges',
            explain: 'ongoingCharges',
            label: 'Ongoing charges',
            value: charges === null ? EMPTY : `${percent(charges, 2)} a year`,
            detail: charges === null ? undefined : `About ${money(charges * value)} a year`,
        },
    ]
}

function measuredRows(m: MeasuredStatistics): Row[] {
    return [
        { key: 'twr', explain: 'timeWeightedReturn', label: 'Time-weighted return', value: signedPercent(m.timeWeightedReturn), detail: 'Since opening' },
        m.annualisedReturn === null
            ? { key: 'annualised', explain: 'annualisedReturn', label: 'Annualised return', value: 'After a year of history', pending: true }
            : { key: 'annualised', explain: 'annualisedReturn', label: 'Annualised return', value: `${signedPercent(m.annualisedReturn)} a year` },
        m.realisedVolatility === null
            ? { key: 'realised', explain: 'realisedVolatility', label: 'Realised volatility', value: 'After 21 days of values', pending: true }
            : { key: 'realised', explain: 'realisedVolatility', label: 'Realised volatility', value: `${percent(m.realisedVolatility)} a year` },
        { key: 'drawdown', explain: 'maxDrawdown', label: 'Maximum drawdown', value: m.maxDrawdown ? percent(-m.maxDrawdown) : 'None yet', pending: !m.maxDrawdown },
    ]
}
