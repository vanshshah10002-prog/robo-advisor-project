import type { ReactNode } from 'react'
import styles from './Chart.module.css'

/** How a series is drawn, so its key looks like its mark. */
export type Mark = 'line' | 'dash' | 'band' | 'swatch'

export interface LegendItem {
    key: string
    label: ReactNode
    colour: string
    mark?: Mark
}

/** A key drawn like the mark it stands for. Text stays ink; only the key is coloured. */
export function Key({ colour, mark = 'swatch' }: { colour: string; mark?: Mark }) {
    return (
        <svg className={styles.key} width="18" height="12" viewBox="0 0 18 12" aria-hidden="true" focusable="false">
            {mark === 'line' && <line x1="1" x2="17" y1="6" y2="6" stroke={colour} strokeWidth="2" strokeLinecap="round" />}
            {mark === 'dash' && (
                <line x1="1" x2="17" y1="6" y2="6" stroke={colour} strokeWidth="2" strokeDasharray="4 3" />
            )}
            {mark === 'band' && <rect x="1" y="1" width="16" height="10" rx="1" fill={colour} />}
            {mark === 'swatch' && <rect x="3" y="1" width="10" height="10" rx="1" fill={colour} />}
        </svg>
    )
}

/** Shown whenever a chart has two or more series. */
export function Legend({ items }: { items: readonly LegendItem[] }) {
    return (
        <ul className={styles.legend}>
            {items.map((item) => (
                <li key={item.key}>
                    <Key colour={item.colour} mark={item.mark} />
                    <span>{item.label}</span>
                </li>
            ))}
        </ul>
    )
}
