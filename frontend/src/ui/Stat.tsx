import { clsx } from 'clsx'
import type { ReactNode } from 'react'
import { percentagePoints, signedMoney, signedPercent } from '@/lib/format'
import type { ProvenanceKind } from './provenance'
import { Provenance } from './Tag'
import styles from './Stat.module.css'

export type StatSize = 'md' | 'lg' | 'xl'

export interface StatProps {
    label: ReactNode
    /** Already formatted, e.g. `money(124518)`. */
    value: ReactNode
    provenance?: ProvenanceKind
    /** A secondary line under the value: a delta, a range, a comparison. */
    detail?: ReactNode
    size?: StatSize
    className?: string
}

/** A labelled figure. Must sit inside a `StatGroup`, which supplies the `<dl>`. */
export function Stat({ label, value, provenance, detail, size = 'md', className }: StatProps) {
    return (
        <div className={clsx(styles.stat, styles[size], className)}>
            <dt className={styles.label}>
                <span>{label}</span>
                {provenance && <Provenance kind={provenance} />}
            </dt>
            <dd className={styles.value}>{value}</dd>
            {detail && <dd className={styles.detail}>{detail}</dd>}
        </div>
    )
}

export function StatGroup({ children, className }: { children: ReactNode; className?: string }) {
    return <dl className={clsx(styles.group, className)}>{children}</dl>
}

export type DeltaFormat = 'percent' | 'money' | 'pp'

/**
 * A signed change. Losses are claret with a minus; gains stay ink with a
 * plus (accounting convention), so colour never carries the meaning alone.
 */
export function Delta({ value, format = 'percent' }: { value: number | null | undefined; format?: DeltaFormat }) {
    const text =
        format === 'money' ? signedMoney(value) : format === 'pp' ? percentagePoints(value) : signedPercent(value)
    const isLoss = typeof value === 'number' && text.startsWith('−')
    return <span className={clsx(styles.delta, isLoss && styles.loss)}>{text}</span>
}

