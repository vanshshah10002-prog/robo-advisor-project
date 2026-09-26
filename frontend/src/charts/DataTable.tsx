import { clsx } from 'clsx'
import type { Key, ReactNode } from 'react'
import styles from './DataTable.module.css'

export interface Column<Row> {
    key: string
    label: ReactNode
    /** Right-aligned, serif tabular figures. */
    numeric?: boolean
    render: (row: Row) => ReactNode
}

export interface DataTableProps<Row> {
    /** Names the table for assistive technology; hidden because the frame shows a title. */
    caption: string
    columns: readonly Column<Row>[]
    rows: readonly Row[]
    rowKey: (row: Row) => Key
    /** A totals row, one cell per column, set under a double rule. */
    footer?: readonly ReactNode[]
    className?: string
}

/**
 * A statement-style table: hairline rows, a ruled head, figures right-aligned
 * in tabular serif, totals under a double rule. The first column heads each row.
 */
export function DataTable<Row>({ caption, columns, rows, rowKey, footer, className }: DataTableProps<Row>) {
    return (
        <div className={clsx(styles.scroll, className)}>
            <table className={styles.table}>
                <caption className="visually-hidden">{caption}</caption>
                <thead>
                    <tr>
                        {columns.map((c) => (
                            <th key={c.key} scope="col" className={clsx(c.numeric && styles.num)}>
                                {c.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={rowKey(row)}>
                            {columns.map((c, i) =>
                                i === 0 ? (
                                    <th key={c.key} scope="row" className={clsx(c.numeric && styles.num)}>
                                        {c.render(row)}
                                    </th>
                                ) : (
                                    <td key={c.key} className={clsx(c.numeric && styles.num)}>
                                        {c.render(row)}
                                    </td>
                                ),
                            )}
                        </tr>
                    ))}
                </tbody>
                {footer && (
                    <tfoot>
                        <tr>
                            {columns.map((c, i) =>
                                i === 0 ? (
                                    <th key={c.key} scope="row">
                                        {footer[i]}
                                    </th>
                                ) : (
                                    <td key={c.key} className={clsx(c.numeric && styles.num)}>
                                        {footer[i]}
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
