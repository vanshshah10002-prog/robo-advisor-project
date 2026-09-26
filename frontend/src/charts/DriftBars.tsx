import { Warning } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import type { ReactNode } from 'react'
import { EMPTY, percent, percentagePoints } from '@/lib/format'
import { ChartFrame } from './ChartFrame'
import { DataTable, FundCell, type Column } from './DataTable'
import { driftOf, driftScale, isOutside, type DriftItem } from './model'
import styles from './DriftBars.module.css'

export interface DriftBarsProps {
    items: readonly DriftItem[]
    title: string
    summary?: string
    notes?: ReactNode
    pending?: boolean
}

const status = (i: DriftItem) => (i.current === null ? 'No price' : isOutside(i) ? 'Outside band' : 'Within band')

const COLUMNS: Column<DriftItem>[] = [
    { key: 'holding', label: 'Holding', render: (i) => <FundCell name={i.label} ticker={i.detail} /> },
    { key: 'target', label: 'Target', numeric: true, render: (i) => percent(i.target) },
    { key: 'current', label: 'Now', numeric: true, render: (i) => percent(i.current) },
    { key: 'drift', label: 'Drift', numeric: true, render: (i) => percentagePoints(driftOf(i)) },
    { key: 'band', label: 'Band', numeric: true, render: (i) => `±${percentagePoints(i.band).replace('+', '')}` },
    { key: 'status', label: 'Status', render: status },
]

function listLabel(title: string, outside: number): string {
    if (outside === 0) return `${title}: every holding is within its band`
    return `${title}: ${outside} outside ${outside === 1 ? 'its band' : 'their bands'}`
}

/**
 * How far each holding sits from its target. The centre line is the target,
 * the shaded span its rebalancing band; a bar that leaves the band is
 * drawn in the caution colour and says so in words.
 */
export function DriftBars({ items, title, summary, notes, pending }: DriftBarsProps) {
    const scale = driftScale(items)
    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance="measured"
            notes={notes}
            pending={pending}
            empty={items.length === 0 ? 'No holdings to compare yet.' : undefined}
            table={<DataTable caption={title} columns={COLUMNS} rows={items} rowKey={(i) => i.key} />}
        >
            <div className={styles.chart}>
                <p className={styles.axis} aria-hidden="true">
                    <span>{percentagePoints(-scale, 0)}</span>
                    <span>On target</span>
                    <span>{percentagePoints(scale, 0)}</span>
                </p>
                <ul className={styles.rows} aria-label={listLabel(title, items.filter(isOutside).length)}>
                    {items.map((item) => (
                        <DriftRow key={item.key} item={item} scale={scale} />
                    ))}
                </ul>
            </div>
        </ChartFrame>
    )
}

function DriftRow({ item, scale }: { item: DriftItem; scale: number }) {
    const pos = (v: number) => 50 + (v / scale) * 50
    const drift = driftOf(item)
    const out = isOutside(item)
    return (
        <li className={styles.row}>
            <span className={styles.name}>
                {item.label}
                {item.detail && <span className={styles.detail}>{item.detail}</span>}
            </span>
            <span className={styles.track} aria-hidden="true">
                <span className={styles.band} style={{ left: `${pos(-item.band)}%`, right: `${100 - pos(item.band)}%` }} />
                <span className={styles.centre} />
                {drift !== null && (
                    <span
                        className={clsx(styles.bar, out && styles.out)}
                        style={{ left: `${Math.min(50, pos(drift))}%`, width: `${(Math.abs(drift) / scale) * 50}%` }}
                    />
                )}
            </span>
            <span className={styles.figures}>
                <span className={styles.drift}>{drift === null ? EMPTY : percentagePoints(drift)}</span>
                <span className={styles.of}>{item.current === null ? 'no price' : `${percent(item.current)} of ${percent(item.target)}`}</span>
            </span>
            {out && (
                <span className={styles.flag}>
                    <Warning weight="bold" aria-hidden="true" /> Outside band
                </span>
            )}
        </li>
    )
}
