import { clsx } from 'clsx'
import type { ReactNode } from 'react'
import { PROVENANCE_MEANING, type ProvenanceKind } from './provenance'
import styles from './Tag.module.css'

export type TagTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'loss'

export interface TagProps {
    tone?: TagTone
    icon?: ReactNode
    children: ReactNode
    className?: string
}

/** A short status or attribute: "ISA", "Within band", "Rebalance due". Never colour alone — always words. */
export function Tag({ tone = 'neutral', icon, children, className }: TagProps) {
    return (
        <span className={clsx(styles.tag, styles[tone], className)}>
            {icon && <span className={styles.icon} aria-hidden="true">{icon}</span>}
            {children}
        </span>
    )
}

/**
 * Says where a number comes from. Every figure that is not a plain fact
 * about the account carries one of these.
 */
export function Provenance({ kind, className }: { kind: ProvenanceKind; className?: string }) {
    return (
        <span className={clsx(styles.provenance, className)} data-kind={kind} title={PROVENANCE_MEANING[kind]}>
            <span className={styles.mark} aria-hidden="true" />
            {kind}
        </span>
    )
}
