import { clsx } from 'clsx'
import type { CSSProperties, ReactNode } from 'react'
import { heatColour } from '@/lib/palette'
import type { ProvenanceKind } from '@/ui/provenance'
import { ChartFrame } from './ChartFrame'
import { DataTable, FundCell, type Column } from './DataTable'
import { extremePairs, type MatrixLabel } from './model'
import styles from './Heatmap.module.css'

export interface HeatmapProps {
    /** Row and column names, in the order of the matrix. `short` heads the columns. */
    labels: readonly MatrixLabel[]
    /** Square and symmetric, values from −1 to 1. */
    matrix: readonly (readonly number[])[]
    title: string
    summary?: string
    provenance?: ProvenanceKind
    notes?: ReactNode
}

const show = (v: number) => v.toFixed(2).replace('-', '−')

/** How the pairs relate, for a screen reader meeting the grid as one image. */
function describe(labels: readonly MatrixLabel[], matrix: HeatmapProps['matrix']): string {
    const pairs = extremePairs(matrix)
    if (!pairs) return `Correlations between ${labels.length} funds`
    const name = ([i, j]: readonly [number, number]) => `${labels[i].label} and ${labels[j].label}`
    return (
        `Correlations between ${labels.length} funds. Closest: ${name(pairs.closest)}, ${show(pairs.closestValue)}. ` +
        `Most independent: ${name(pairs.apart)}, ${show(pairs.apartValue)}.`
    )
}

/**
 * A correlation matrix as a shaded grid: the darker a cell, the more the two
 * funds tend to move together. Zero or below is left unshaded, and every
 * cell carries its figure, so colour is never the only cue.
 */
export function Heatmap({ labels, matrix, title, summary, provenance, notes }: HeatmapProps) {
    const columns: Column<number>[] = [
        { key: 'fund', label: 'Fund', render: (i) => <FundCell name={labels[i].label} ticker={labels[i].short} /> },
        ...labels.map((l, j) => ({ key: l.key, label: l.short, numeric: true, render: (i: number) => (i === j ? '—' : show(matrix[i][j])) })),
    ]
    const grid = { '--n': labels.length } as CSSProperties

    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance={provenance}
            notes={notes}
            empty={labels.length < 2 ? 'Correlations need at least two funds.' : undefined}
            table={<DataTable caption={title} columns={columns} rows={labels.map((_, i) => i)} rowKey={(i) => labels[i].key} />}
        >
            <div className={styles.scroll}>
                <div className={styles.grid} style={grid} role="img" aria-label={describe(labels, matrix)}>
                    <span className={styles.corner} />
                    {labels.map((l) => (
                        <span key={l.key} className={styles.colHead}>
                            {l.short}
                        </span>
                    ))}
                    {labels.map((row, i) => (
                        <Row key={row.key} label={row} values={matrix[i]} diagonal={i} />
                    ))}
                </div>
            </div>
        </ChartFrame>
    )
}

function Row({ label, values, diagonal }: { label: MatrixLabel; values: readonly number[]; diagonal: number }) {
    return (
        <>
            <span className={styles.rowHead}>
                <span className={styles.rowName}>{label.label}</span>
                <span className={styles.rowShort}>{label.short}</span>
            </span>
            {values.map((v, j) =>
                j === diagonal ? (
                    <span key={j} className={clsx(styles.cell, styles.self)} />
                ) : (
                    <span key={j} className={styles.cell} style={{ background: heatColour(v) }}>
                        {show(v)}
                    </span>
                ),
            )}
        </>
    )
}
