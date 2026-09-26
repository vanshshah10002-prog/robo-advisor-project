import { clsx } from 'clsx'
import type { Key, ReactNode } from 'react'
import styles from './DataTable.module.css'

export interface Column<Row> {
    key: string
    label: ReactNode
    /** Right-aligned, serif tabular figures. */
    numeric?: boolean
    render: (row: Row) => ReactNode
    /** Names the value when rows stack on a phone; defaults to `label` when that is text. */
    stackLabel?: string
}

export interface DataTableProps<Row> {
    /** Names the table for assistive technology; hidden because the frame shows a title. */
    caption: string
    columns: readonly Column<Row>[]
    rows: readonly Row[]
    rowKey: (row: Row) => Key
    /** A totals row, one cell per column, set under a double rule. */
    footer?: readonly ReactNode[]
    /** On a phone, each row becomes a block of labelled values instead of scrolling sideways. */
    stack?: boolean
    className?: string
}

const stackLabel = <Row,>(c: Column<Row>) => c.stackLabel ?? (typeof c.label === 'string' ? c.label : undefined)

const isBlank = (content: ReactNode) => content === '' || content === null || content === undefined || content === false

/**
 * A statement-style table: hairline rows, a ruled head, figures right-aligned
 * in tabular serif, totals under a double rule. The first column heads each row.
 */
export function DataTable<Row>({ caption, columns, rows, rowKey, footer, stack = false, className }: DataTableProps<Row>) {
    // Stacking changes how the cells display, which can drop their table roles, so they are restated.
    const role = (r: string) => (stack ? r : undefined)
    // A stacked value is one piece beside its label, however many parts it has (a fund's name and ticker, say).
    const value = (content: ReactNode) => (stack && !isBlank(content) ? <span className={styles.stackValue}>{content}</span> : content)
    return (
        <div className={clsx(styles.scroll, className)}>
            <table className={clsx(styles.table, stack && styles.stack)} role={role('table')}>
                <caption className="visually-hidden">{caption}</caption>
                <thead role={role('rowgroup')}>
                    <tr role={role('row')}>
                        {columns.map((c) => (
                            <th key={c.key} scope="col" role={role('columnheader')} className={clsx(c.numeric && styles.num)}>
                                {c.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody role={role('rowgroup')}>
                    {rows.map((row) => (
                        <tr key={rowKey(row)} role={role('row')}>
                            {columns.map((c, i) =>
                                i === 0 ? (
                                    <th key={c.key} scope="row" role={role('rowheader')} className={clsx(c.numeric && styles.num)}>
                                        {c.render(row)}
                                    </th>
                                ) : (
                                    <td key={c.key} role={role('cell')} data-label={stackLabel(c)} className={clsx(c.numeric && styles.num)}>
                                        {value(c.render(row))}
                                    </td>
                                ),
                            )}
                        </tr>
                    ))}
                </tbody>
                {footer && (
                    <tfoot role={role('rowgroup')}>
                        <tr role={role('row')}>
                            {columns.map((c, i) =>
                                i === 0 ? (
                                    <th key={c.key} scope="row" role={role('rowheader')}>
                                        {footer[i]}
                                    </th>
                                ) : (
                                    <td key={c.key} role={role('cell')} data-label={stackLabel(c)} className={clsx(c.numeric && styles.num)}>
                                        {value(footer[i])}
                                    </td>
                                ),
                            )}
                        </tr>
                    </tfoot>
                )}
            </table>
        </div>
    )
}

/** A fund name over its ticker, for the first column. */
export function FundCell({ name, ticker }: { name: ReactNode; ticker?: ReactNode }) {
    return (
        <>
            <span className={styles.fund}>{name}</span>
            {ticker && <span className={styles.ticker}>{ticker}</span>}
        </>
    )
}
