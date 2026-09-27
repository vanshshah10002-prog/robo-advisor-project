import { clsx } from 'clsx'
import type { ReactNode } from 'react'
import { Key, type Mark } from './Legend'
import styles from './Chart.module.css'

export interface TooltipRow {
    key: string
    label: string
    value: string
    colour?: string
    mark?: Mark
}

export interface ChartTooltipProps {
    title: ReactNode
    rows: readonly TooltipRow[]
    /** Anchor, in pixels from the plot's top-left corner. */
    x: number
    y?: number
    /** Width of the plot, so the tooltip can open away from the right edge. */
    width: number
}

const FLIP_AT = 0.58

/**
 * The crosshair readout. It lists every series at the cursor, in legend
 * order, and is decorative to assistive technology: keyboard moves are
 * announced through `Announce`, and the table view carries the same data.
 */
export function ChartTooltip({ title, rows, x, y = 0, width }: ChartTooltipProps) {
    return (
        <div
            className={clsx(styles.tooltip, x > width * FLIP_AT && styles.flip)}
            style={{ left: x, top: y }}
            aria-hidden="true"
        >
            <p className={styles.tooltipTitle}>{title}</p>
            <dl className={styles.tooltipRows}>
                {rows.map((row) => (
                    <div key={row.key}>
                        <dt>
                            {row.colour && <Key colour={row.colour} mark={row.mark} />}
                            {row.label}
                        </dt>
                        <dd>{row.value}</dd>
                    </div>
                ))}
            </dl>
        </div>
    )
}

/** A polite live region: says what the keyboard cursor landed on. */
export function Announce({ text }: { text: string }) {
    return (
        <p className="visually-hidden" aria-live="polite">
            {text}
        </p>
    )
}
