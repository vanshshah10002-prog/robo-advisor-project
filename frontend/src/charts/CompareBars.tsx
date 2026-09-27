import type { ReactNode } from 'react'
import { percent } from '@/lib/format'
import type { ProvenanceKind } from '@/ui/provenance'
import { ChartFrame } from './ChartFrame'
import { DataTable, FundCell, type Column } from './DataTable'
import { Legend } from './Legend'
import { compareScale, type CompareItem } from './model'
import styles from './CompareBars.module.css'

export interface CompareSeries {
    label: string
    colour: string
}

export interface CompareBarsProps {
    items: readonly CompareItem[]
    /** The two measures, in the order of each item's `values`. */
    series: readonly [CompareSeries, CompareSeries]
    title: string
    summary?: string
    provenance?: ProvenanceKind
    notes?: ReactNode
    format?: (v: number) => string
}

/**
 * Two measures side by side for each item, on one shared scale: say, each
 * fund's share of the money against its share of the risk. Each bar carries
 * its figure, so the comparison reads without the colours.
 */
export function CompareBars({ items, series, title, summary, provenance, notes, format = (v) => percent(v) }: CompareBarsProps) {
    const scale = compareScale(items)
    const columns: Column<CompareItem>[] = [
        { key: 'item', label: 'Holding', render: (i) => <FundCell name={i.label} ticker={i.detail} /> },
        { key: 'a', label: series[0].label, numeric: true, render: (i) => format(i.values[0]) },
        { key: 'b', label: series[1].label, numeric: true, render: (i) => format(i.values[1]) },
    ]

    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance={provenance}
            notes={notes}
            empty={items.length === 0 ? 'Nothing to compare yet.' : undefined}
            legend={<Legend items={series.map((s, k) => ({ key: String(k), label: s.label, colour: s.colour }))} />}
            table={<DataTable caption={title} columns={columns} rows={items} rowKey={(i) => i.key} />}
        >
            <ul className={styles.rows} aria-label={title}>
                {items.map((item) => (
                    <li key={item.key} className={styles.row}>
                        <span className={styles.name}>
                            {item.label}
                            {item.detail && <span className={styles.detail}>{item.detail}</span>}
                        </span>
                        <span className={styles.bars}>
                            {series.map((s, k) => (
                                <span key={s.label} className={styles.bar}>
                                    <span className={styles.fill} style={{ width: `${(Math.max(0, item.values[k]) / scale) * 100}%`, background: s.colour }} />
                                    <span className={styles.value}>
                                        <span className="visually-hidden">{s.label}: </span>
                                        {format(item.values[k])}
                                    </span>
                                </span>
                            ))}
                        </span>
                    </li>
                ))}
            </ul>
        </ChartFrame>
    )
}
