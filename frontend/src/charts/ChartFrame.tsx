import { clsx } from 'clsx'
import { useId, useState, type ReactNode } from 'react'
import type { ProvenanceKind } from '@/ui/provenance'
import { Provenance } from '@/ui/Tag'
import styles from './Chart.module.css'

export type ChartView = 'chart' | 'table'

export interface ChartFrameProps {
    title: ReactNode
    /** One sentence with the takeaway, read before the chart. */
    summary?: ReactNode
    provenance?: ProvenanceKind
    /** Keys, shown above the plot so they are read before it. */
    legend?: ReactNode
    /** The same data as a table: every chart has one. */
    table: ReactNode
    /** Assumptions and sources, under the chart. */
    notes?: ReactNode
    /** A refetch is under way: the last render stays, dimmed, until it lands. */
    pending?: boolean
    /** Replaces the chart and the toggle when there is nothing to draw. */
    empty?: ReactNode
    defaultView?: ChartView
    className?: string
    children: ReactNode
}

/**
 * The frame every chart sits in: title, provenance, a Chart/Table switch,
 * legend, plot and notes. Only the chosen view is rendered, so screen readers
 * meet the data once.
 */
export function ChartFrame({
    title,
    summary,
    provenance,
    legend,
    table,
    notes,
    pending = false,
    empty,
    defaultView = 'chart',
    className,
    children,
}: ChartFrameProps) {
    const [view, setView] = useState<ChartView>(defaultView)
    const titleId = useId()
    const isEmpty = empty !== undefined && empty !== null && empty !== false

    return (
        <figure className={clsx(styles.frame, className)} aria-labelledby={titleId} aria-busy={pending || undefined}>
            <figcaption className={styles.head}>
                <span className={styles.titleRow}>
                    <span id={titleId} className={styles.title}>
                        {title}
                    </span>
                    {provenance && <Provenance kind={provenance} />}
                </span>
                {!isEmpty && <ViewSwitch view={view} onChange={setView} />}
                {summary && <span className={styles.summary}>{summary}</span>}
            </figcaption>

            <div className={clsx(styles.body, pending && styles.pending)}>
                {isEmpty ? (
                    <p className={styles.empty}>{empty}</p>
                ) : view === 'chart' ? (
                    <>
                        {legend}
                        {children}
                    </>
                ) : (
                    table
                )}
            </div>

            {notes && <div className={styles.notes}>{notes}</div>}
        </figure>
    )
}

function ViewSwitch({ view, onChange }: { view: ChartView; onChange: (v: ChartView) => void }) {
    return (
        <span className={styles.switch} role="group" aria-label="Show as">
            {(['chart', 'table'] as const).map((v) => (
                <button key={v} type="button" aria-pressed={view === v} onClick={() => onChange(v)}>
                    {v === 'chart' ? 'Chart' : 'Table'}
                </button>
            ))}
        </span>
    )
}
